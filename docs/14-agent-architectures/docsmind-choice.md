# DocsMind's Choice — One LangGraph Loop, and What Would Change That

**TL;DR:** `docsmind/agent/` is planned as a single-agent LangGraph loop
with explicit tools. For "answer questions from one corpus, with citations,"
there's one job — not several specialist roles needing a supervisor.

## Where it slots into the real code

[`docsmind/agent/__init__.py`](../../docsmind/agent/__init__.py) is today
just a docstring:

> *"Placeholder for the LangGraph agent: planning loop with retrieve /
> web_search / code_exec / cite tools and anti-hallucination guardrails."*

That's a **single-agent** design. One LangGraph loop, several tools, no
sub-agents:

```
            ┌──────────── LangGraph state ────────────┐
question →  plan → tool? ──yes──→ run tool → observe ─┘
              │                     (retrieve / web_search / code_exec)
              no
              ↓
            cite → guardrail check → answer
```

Each box is a graph node; the state (messages so far, retrieved chunks,
iteration count) flows along the edges. The loop's max-iterations guard from
[12-tool-calling/the-loop.md](../12-tool-calling/the-loop.md) becomes a
simple edge condition.

## Why single-agent is the right call here

For DocsMind's actual problem — answer questions from one document corpus,
with citations — there's one job. Not several specialist roles that need a
supervisor splitting work. The tools differ (`retrieve` vs `web_search`),
but the *role* using them is the same researcher.

The choice also compounds with the learning goal: a single explicit graph is
a thing you can trace node by node and explain in an interview. A crew of
role-playing agents is a demo that resists explanation.

## When would that change?

If DocsMind later added a separate "web search agent" and a
"code-execution agent," with genuinely different tool access and prompting
needs — *then* a supervisor would earn its complexity. The tell from
[patterns.md](patterns.md): the single agent's system prompt turning into a
disguised router.

## How you'd validate the choice

An end-to-end eval, run against both shapes on the same task set — the same
discipline as Phase 3's retrieval eval and Phase 6's answer eval:

| Metric | Single agent | Multi-agent |
|---|---|---|
| Task success rate | baseline | must beat it, not tie it |
| Tokens per task | fewer (no coordination hops) | more — every hop is an LLM call |
| Latency per task | lower | higher, and more variable |
| Debuggability | one trace | traces × agents |

If multi-agent doesn't measurably beat a single well-scoped agent, the
extra complexity isn't earning its cost. In an interview, having *run* that
comparison — even on a toy task set — beats any amount of architecture
vocabulary.

→ Next: **[15-llm-serving-internals/README.md](../15-llm-serving-internals/README.md)**
