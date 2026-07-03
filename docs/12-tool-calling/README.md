# Tool calling — the LLM asks, your code answers (concept, Phase 5)

**Where in the pipeline:** between **Generate** and **Cite** — actually, it
replaces the assumption that Generate is a single LLM call at all. Right now
`RAGPipeline.query()` does one retrieve, one generate, done. Tool calling turns
that one step into a **loop**: the LLM can ask for more information mid-answer
instead of only working with what retrieval handed it upfront. Not built in
DocsMind yet; it's the core mechanic Phase 5's agent needs.

```
today:     question → retrieve(top_k) → ONE generate call → answer

tool calling:  question → generate call ──┬─→ model says "call retrieve('x')"
                                           │        ↓
                                           │   your code runs it, returns result
                                           │        ↓
                                           └─→ generate call again, sees result
                                                    ↓ (repeat until model is done)
                                                 final answer
```

## The problem it solves

Right now, `RAGPipeline.query()` decides *once*, before the LLM ever runs, what
context the model gets: `self._retriever.retrieve(question, top_k)`. If the
first retrieval was too narrow, wrong `top_k`, or the question actually needs
two lookups (e.g. "compare X and Y" needing two separate searches), the model
has no way to ask for more. It just answers with what it got, or says
`INSUFFICIENT_CONTEXT`.

Tool calling gives the model a **menu of functions it's allowed to invoke**,
described to it as a schema (name, description, JSON parameters) — not code,
just a spec. The model doesn't execute anything. It outputs a structured
request like `{"name": "retrieve", "arguments": {"query": "supernova types"}}`.
Your code is the one that actually runs `retrieve()`, and feeds the result back
in as another message. The model then continues, possibly calling another tool,
until it decides it has enough to answer in plain text.

Plain version: the model is a customer at a counter, not the cook. It doesn't
walk into the kitchen — it places an order in a fixed format, and *you* bring
back what it asked for. It never touches the stove.

## Where it would slot into the real code

Two places, and the seam is worth naming precisely:

**1. The LLM client contract.** `CloudLLMClient.generate()` in
[`cloud_client.py`](../../docsmind/llm/cloud_client.py) currently makes one
`messages.create()` call with `system` + `prompt` and returns plain text. Tool
calling needs the Anthropic `tools=[...]` parameter added to that call, and the
return type widened from `str` to "either a text answer, or a tool-use request
with a name and arguments" — the `LLMClient` interface itself changes shape.

**2. The control loop.** Nothing in `docsmind/` currently *loops* on a model's
response — `RAGPipeline.query()` calls the LLM exactly once. The loop
(call model → check if it asked for a tool → run the tool → call model again)
is new machinery. That loop, plus a registry of callable tools (`retrieve`,
maybe `web_search`, `code_exec`), is what `docsmind/agent/__init__.py` — today
just a docstring — is a placeholder for.

```python
# sketch of the shape, not real code yet
tools = [{"name": "retrieve", "description": "...", "input_schema": {...}}]
while True:
    response = llm.generate_with_tools(system, messages, tools)
    if response.stop_reason != "tool_use":
        return response.text  # model is done
    result = TOOL_REGISTRY[response.tool_name](**response.tool_input)
    messages.append(tool_result_message(response.tool_use_id, result))
```

## Trade-offs (the interview meat)

- **Cost:** every tool call is a full extra round-trip to the LLM — more
  tokens, more latency, and no clean upper bound on how many round-trips a
  question takes. You need a max-iterations guard or the loop can run forever
  on an ambiguous question.
- **Reliability, not just capability.** The hard part isn't wiring the API —
  it's the model reliably emitting well-formed arguments that match your JSON
  schema, every time, including for oddly-phrased questions. This is exactly
  where **closed models are strong and open models often regress** — schema
  drift, malformed JSON, calling the wrong tool. That gap, and how you close it
  (better prompting, few-shot examples of correct calls, or constrained
  decoding — see the interview-depth note below), is the single highest-signal
  thing to be able to talk through for an inference/serving role.
- **Security surface:** the model is now choosing what code runs and with what
  arguments. Any tool that touches the filesystem, a shell, or an external API
  needs its own validation — never trust `response.tool_input` as safe just
  because it came from a schema. See [`18-llm-security`](../18-llm-security/README.md).
- **How you'd validate it:** track tool-call success rate separately from
  answer quality — did the model call the *right* tool, with *valid*
  arguments, in *one* call rather than three retries? That's a distinct metric
  from "was the final answer correct," and it's the one that breaks first when
  you swap models.

## The interview signals

- **What is tool calling, in one line?** The model requests a function by name
  and arguments; your code executes it and hands the result back — the model
  never runs anything itself.
- **Why can't the model just call the function directly?** It has no execution
  environment. It only emits text (structured as JSON here). Every "action" an
  LLM takes in the world is actually your code, triggered by a message it
  wrote.
- **What's the failure mode that actually shows up in production?** Not "the
  model refuses to use a tool" — it's **malformed or wrong-tool calls**,
  especially after swapping to a smaller or open-weight model. This is a
  known, measurable regression (see `15-llm-serving-internals` for the serving
  side and the DocsMind roadmap's Auric-target note on this exact gap) — the
  fix path is prompting first, then structured-output constraints
  (Outlines/XGrammar), then fine-tuning as a last resort, in that order of
  cost.
