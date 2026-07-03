# Tool calling — the LLM asks, your code answers (concept, Phase 5)

**Where in the pipeline:** at the **Generate** stage.
Today, Generate is one LLM call. `RAGPipeline.query()` retrieves once, generates once, done.
Tool calling turns that one call into a **loop**.
The model can ask for more information mid-answer, instead of only using what retrieval handed it upfront.
Not built in DocsMind yet. It's the core mechanic Phase 5's agent needs.

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

At the retrieve step today, your code decides *once* what context the model gets.
That decision happens before the LLM ever runs: `self._retriever.retrieve(question, top_k)`.

What if that one retrieval wasn't enough?
Maybe the search was too narrow. Maybe `top_k` was wrong.
Maybe the question needs *two* lookups — "compare X and Y" needs a search for X and a search for Y.
The model can't ask for more. It answers with what it got, or says `INSUFFICIENT_CONTEXT`.

Tool calling fixes this by giving the model a **menu of functions it's allowed to request**.
Each function is described as a schema: a name, a description, and JSON parameters.
The model never executes anything.
It outputs a structured request, like:

```json
{"name": "retrieve", "arguments": {"query": "supernova types"}}
```

Your code runs the actual `retrieve()`.
Your code feeds the result back as a new message.
The model reads it and continues — maybe calling another tool, maybe answering.

Plain version: the model is a customer at a counter, not the cook.
It places an order in a fixed format. You bring back what it asked for.
It never touches the stove.

## Where it would slot into the real code

Two places. The seam is worth naming precisely.

**1. The LLM client contract.**
`CloudLLMClient.generate()` in [`cloud_client.py`](../../docsmind/llm/cloud_client.py) makes one `messages.create()` call and returns plain text.
Tool calling needs two changes there.
First, pass the Anthropic `tools=[...]` parameter.
Second, widen the return type: not just `str`, but "either a text answer, or a tool request with a name and arguments."
That means the `LLMClient` interface itself changes shape.

**2. The control loop.**
Nothing in `docsmind/` currently *loops* on a model's response.
`RAGPipeline.query()` calls the LLM exactly once.
The loop — call model, check if it asked for a tool, run the tool, call model again — is new machinery.
That loop, plus a registry of callable tools (`retrieve`, maybe `web_search`, `code_exec`), is what `docsmind/agent/__init__.py` (today just a docstring) is a placeholder for.

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

- **Cost.** Every tool call is a full extra round-trip to the LLM.
  More tokens. More latency.
  And there's no natural upper bound on how many round-trips one question takes.
  You need a max-iterations guard, or the loop can run forever on an ambiguous question.
- **Reliability is the hard part, not wiring.**
  The API plumbing is easy.
  The hard part is the model emitting well-formed arguments that match your JSON schema, every single time, even for oddly-phrased questions.
  Closed models are strong here. Open models often regress: schema drift, malformed JSON, calling the wrong tool.
  How you close that gap — better prompting, few-shot examples of correct calls, or constrained decoding — is the single highest-signal topic for an inference/serving role.
- **Security surface.**
  The model now chooses what code runs, and with what arguments.
  Any tool that touches the filesystem, a shell, or an external API needs its own validation.
  Never trust `response.tool_input` just because it matched a schema.
  See [`18-llm-security`](../18-llm-security/README.md).
- **How you'd validate it.**
  Track tool-call success rate as its own metric, separate from answer quality.
  Did the model call the *right* tool? With *valid* arguments? In *one* try, not three?
  That metric is the one that breaks first when you swap models.

## The interview signals

- **What is tool calling, in one line?**
  The model requests a function by name and arguments; your code runs it and hands the result back. The model never executes anything itself.
- **Why can't the model just call the function directly?**
  It has no execution environment. It only emits text (structured as JSON here).
  Every "action" an LLM takes in the world is actually your code, triggered by a message it wrote.
- **What's the failure mode that actually shows up in production?**
  Not "the model refuses to use a tool."
  It's **malformed or wrong-tool calls** — especially after swapping to a smaller or open-weight model.
  This is a known, measurable regression (see `15-llm-serving-internals` for the serving side, and the roadmap's Auric-target note on this exact gap).
  The fix path, in cost order: prompting first, then structured-output constraints (Outlines/XGrammar), then fine-tuning as a last resort.
