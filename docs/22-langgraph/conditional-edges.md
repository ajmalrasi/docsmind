# Conditional Edges — Why It's a Graph, Not a Sequence

This is the page that turns "our graph is still sequential" from an apology into
a *design choice you're about to upgrade.* A conditional edge is the one feature
that makes LangGraph worth more than a chain of function calls.

## The straight line, and the branch

A normal edge always goes to the same next node. A **conditional edge** runs a
small router function that *looks at the state* and returns the name of where to
go next.

```
unconditional:   retrieve ────────────→ generate

conditional:     retrieve ──┬─ chunks found? ──→ generate
                            └─ empty?         ──→ refuse
```

## The guardrail as an edge

DocsMind already has an `INSUFFICIENT_CONTEXT` guardrail — when retrieval is
weak, refuse instead of hallucinating. In a plain function that's an `if` buried
in the middle. In a graph it becomes a **visible branch**:

```python
def route_after_retrieve(state: RAGState) -> str:
    # return value is just a label — which edge to take
    return "generate" if state["chunks"] else "refuse"

def refuse(state: RAGState) -> dict:
    return {"answer": "INSUFFICIENT_CONTEXT"}

builder.add_node("refuse", refuse)

# replace the plain retrieve→generate edge with a conditional one
builder.add_conditional_edges(
    "retrieve",
    route_after_retrieve,
    {
        "generate": "generate",   # found context → answer it
        "refuse":   "refuse",     # no context   → guardrail
    },
)
builder.add_edge("refuse", END)
```

Now the graph *branches*. This is the concrete answer to "why LangGraph if it's
sequential?" — **because turning a sequence into a decision is one
`add_conditional_edges` call, and the decision is now a thing you can see, test,
and trace**, not logic hidden inside a function.

## The loop — an agent, in graph form

The same conditional-edge tool makes a loop. Point an edge *back* to an earlier
node, and gate it with a router. This is the tool-calling loop from
[section 12](../12-tool-calling/README.md), drawn as a graph:

```python
def should_continue(state: AgentState) -> str:
    if state["iterations"] >= 5:          # the max-iterations guard, as an edge
        return "stop"
    return "use_tool" if state["tool_calls"] else "stop"

builder.add_conditional_edges(
    "model",
    should_continue,
    {"use_tool": "run_tool", "stop": END},
)
builder.add_edge("run_tool", "model")     # ← the loop: tool result goes back in
```

`model → run_tool → model → run_tool → …` until the router says `stop`. That
back-edge is the entire difference between a one-shot call and an agent. The
iteration guard from tool calling isn't a `while` counter anymore — it's an edge
condition, so it's impossible to forget and easy to see.

## The mental upgrade

| | Plain function chain | LangGraph |
|---|---|---|
| Order of steps | Hardcoded in call order | Edges — visible, reorderable |
| A decision | `if/else` buried in a function | A conditional edge — its own testable function |
| A loop | `while` with a manual guard | A back-edge + a router |
| Memory across turns | You build it | `compile(checkpointer=...)` + `thread_id` |
| Seeing what happened | `print` debugging | A trace of nodes + state at each hop |

## Interview depth signal

- **"Why not just use `if` statements?"** You can — for two nodes. The graph
  pays off when branches, loops, and retries multiply: the control flow becomes a
  thing you can *look at and reason about* instead of tracing through nested
  functions. And it's the seam checkpointing and streaming hook into.
- **"How would you keep the loop from running forever?"** The router is the
  guard: an iteration count in the state, checked on every back-edge, routing to
  `END` past the cap. Show it as an edge, not a `break`.
- **"How did you validate the branch works?"** Feed a question with no matching
  context and assert the graph reaches `refuse` and returns
  `INSUFFICIENT_CONTEXT` — the same guardrail test, now asserting on the *path
  through the graph*, not just the output string.

→ Back to: **[the site overview](../README.md)**
