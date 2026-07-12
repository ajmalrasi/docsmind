# 22 — LangGraph Hands-On: State, Nodes, Edges (concept, Phase 5)

**The big idea:** LangGraph is a way to write your agent as a **graph of small
functions** instead of one long function. Each function is a **node**. A shared
dictionary — the **state** — flows from node to node along **edges**. That's the
whole model. A plain retrieve → generate flow is a graph with two nodes and one
edge; the moment you want a branch ("if no context, refuse") or a loop ("call a
tool, look at the result, maybe call another"), the graph shape pays off.

**Where in the pipeline:** at the **Generate / agent** stage — the same seam as
[tool calling](../12-tool-calling/README.md). Section 14 answered *which shape*
(one loop vs many). This section answers *how you actually write it.*

```
today (RAGPipeline.query):   question → retrieve → generate → answer
                                         (one straight function call)

as a LangGraph:              START → [retrieve] → [generate] → END
                                        node        node
                                     └──── state flows along edges ────┘
```

## Why this section exists

"Are you on LangChain or LangGraph?" is easy to answer. **"Write me a node"** is
where people freeze — because they've talked about graphs but never built one.
This section fixes that: by the end you can write the state, a node, wire the
edges, add a branch, and explain *why a graph beats a plain function chain.*

## Files in this folder

| File | What it covers |
|------|----------------|
| [state-nodes-edges.md](state-nodes-edges.md) | The three primitives — the entire mental model, with the smallest possible code |
| [build-a-graph.md](build-a-graph.md) | Build DocsMind's retrieve → generate flow as a runnable graph, step by step |
| [conditional-edges.md](conditional-edges.md) | The branch and the loop — why it's a *graph*, not a sequence, and the guardrail as an edge |

## 🎯 Interview Q&A

**Q: What is a LangGraph node, in one line?**
A plain function: it takes the current state and returns a dict, and that dict
gets **merged back into the state** for the next node.

**Q: What is the "state"?**
One shared object — a `TypedDict` — that every node reads from and writes to. It
*is* the memory passed along the edges. Nothing else is global.

**Q: Your graph is just retrieve → generate. Why use LangGraph at all, if it's
sequential?**
Because the cost of *adding a branch or a loop later* is one line, not a
rewrite. A linear graph is just a graph with no branches **yet**. The payoff is
conditional edges: "if retrieval came back empty, route to a refuse node instead
of letting the model hallucinate" — that's my `INSUFFICIENT_CONTEXT` guardrail
expressed as an edge, not an `if` buried in a function.

**Q: LangChain vs LangGraph — what's the actual difference?**
LangChain chains steps in a fixed line (and hides control flow inside
abstractions). LangGraph makes the control flow **the graph** — you can see and
control every branch, loop, and retry. For anything with a decision in it,
LangGraph is the honest tool.

**Q: How does LangGraph give an agent memory across turns?**
A checkpointer. You `compile(checkpointer=...)` and pass a `thread_id`; the state
is saved after each node, so the next turn resumes with history. Same graph,
persistence bolted on at compile time.

## Code

[docsmind/agent/__init__.py](../../docsmind/agent/__init__.py) — today just a
docstring; this is the exact file where the graph below lands.
[docsmind/retrieval/retriever.py](../../docsmind/retrieval/retriever.py) — the
`HybridRetriever` the `retrieve` node calls.
[docsmind/llm/cloud_client.py](../../docsmind/llm/cloud_client.py) — the
`generate()` the `generate` node calls.

→ Next: **[state-nodes-edges.md](state-nodes-edges.md)**
