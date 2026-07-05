# The Loop — From One-Shot Retrieval to Model-Driven Requests

**TL;DR:** today your code decides *once* what context the model gets, before
the LLM ever runs. Tool calling hands the model a menu of functions it may
*request* — and turns generation into a loop of request → execute → read
result → continue.

## The problem it solves

At the retrieve step today, your code decides *once* what context the model gets.
That decision happens before the LLM ever runs:
`self._retriever.retrieve(question, top_k)`.

What if that one retrieval wasn't enough?
Maybe the search was too narrow. Maybe `top_k` was wrong.
Maybe the question needs *two* lookups — "compare X and Y" needs a search for
X and a search for Y.
The model can't ask for more. It answers with what it got, or says
`INSUFFICIENT_CONTEXT`.

## How the loop works

Tool calling gives the model a **menu of functions it's allowed to request**.
Each function is described as a schema: a name, a description, and JSON
parameters. The model never executes anything.
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

## What changes, stage by stage

| | Today (Phase 1–3) | With tool calling (Phase 5) |
|---|---|---|
| Who decides what context the model sees | Your code, once, up front | The model, incrementally, mid-answer |
| Number of LLM calls per question | Exactly 1 | 1 + one per tool round-trip (unbounded without a guard) |
| Number of retrievals per question | Exactly 1 | As many as the model requests |
| "Compare X and Y" questions | One blended search, often mediocre for both | Two targeted searches |
| Failure mode | `INSUFFICIENT_CONTEXT` when the single retrieval missed | Malformed/wrong tool calls (see [reliability-and-security.md](reliability-and-security.md)) |

## The one design rule to keep

The loop needs a **max-iterations guard**. There's no natural upper bound on
how many round-trips one question takes; an ambiguous question can send the
model in circles. Every production tool-calling loop caps iterations and has
a "give your best answer now" escape hatch. Forgetting the guard is the
classic first-week bug of agent code.

→ Next: **[code-seam.md](code-seam.md)**
