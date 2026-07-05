# The Code Seam — Two Precise Places DocsMind Changes

**TL;DR:** tool calling touches exactly two places: the LLM client's contract
(`cloud_client.py` learns a `tools=` parameter and a wider return type), and a
brand-new control loop (`docsmind/agent/`, today just a docstring).

## 1. The LLM client contract

`CloudLLMClient.generate()` in
[`cloud_client.py`](../../docsmind/llm/cloud_client.py) makes one
`messages.create()` call and returns plain text.

Tool calling needs two changes there:

1. Pass the Anthropic `tools=[...]` parameter — the JSON schemas of the
   functions the model may request.
2. Widen the return type: not just `str`, but "either a text answer, **or** a
   tool request with a name and arguments."

That second change ripples: the `LLMClient` interface in
[`base.py`](../../docsmind/llm/base.py) itself changes shape, and
`LocalLLMClient` has to honor the same contract — which is precisely where
open-weight models start failing (see
[reliability-and-security.md](reliability-and-security.md)).

## 2. The control loop

Nothing in `docsmind/` currently *loops* on a model's response.
`RAGPipeline.query()` calls the LLM exactly once.

The loop — call model, check if it asked for a tool, run the tool, call model
again — is new machinery. That loop, plus a registry of callable tools
(`retrieve`, maybe `web_search`, `code_exec`), is what
[`docsmind/agent/__init__.py`](../../docsmind/agent/__init__.py) (today just
a docstring) is a placeholder for.

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

## Why the seam placement matters

The `VectorStore` and `LLMClient` abstractions were built so each layer can
be swapped without the others noticing. Tool calling respects the same
discipline:

```
RAGPipeline.query()          ← unchanged for the simple path
        │
docsmind/agent/  (new loop)  ← the ONLY place that knows about iteration
        │
LLMClient.generate_with_tools()  ← contract widened, both clients implement it
        │
retrieve() / web_search() / ...  ← plain functions, registered by schema
```

The agent loop knows about tools. The pipeline doesn't. The tools don't know
they're being called by a model. In an interview, this is the difference
between "I wired up the API" and "I designed the seam" — the second one is
what gets probed.

## What each tool costs

Every tool call is a full extra round-trip to the LLM. More tokens, more
latency, and the conversation history grows with every result you append —
so late round-trips are more expensive than early ones. This is why the
max-iterations guard from [the-loop.md](the-loop.md) is also a *cost*
control, not just a correctness control.

→ Next: **[reliability-and-security.md](reliability-and-security.md)**
