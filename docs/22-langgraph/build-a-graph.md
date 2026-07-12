# Build a Graph — DocsMind's Retrieve → Generate, Runnable

This is the whole thing in one file. It's the code to write on a whiteboard when
someone says **"show me a LangGraph node."** Everything you saw in
[state-nodes-edges.md](state-nodes-edges.md), assembled and run.

## The complete graph

```python
from typing import TypedDict, List
from langgraph.graph import StateGraph, START, END

# ── 1. State: the shared notebook every node reads and writes ──────────────
class RAGState(TypedDict):
    question: str
    chunks: List[str]
    answer: str

# ── 2. Nodes: functions that take state, return the keys they change ───────
def retrieve(state: RAGState) -> dict:
    results = retriever.retrieve(state["question"], top_k=5)   # HybridRetriever
    return {"chunks": [r.text for r in results]}

def generate(state: RAGState) -> dict:
    context = "\n\n".join(state["chunks"])
    answer = llm.generate(                                      # CloudLLMClient
        system="Answer only from the context. Cite sources.",
        prompt=f"Context:\n{context}\n\nQuestion: {state['question']}",
        max_tokens=512,
    )
    return {"answer": answer}

# ── 3. Build: register nodes, wire edges, compile ──────────────────────────
builder = StateGraph(RAGState)
builder.add_node("retrieve", retrieve)
builder.add_node("generate", generate)

builder.add_edge(START, "retrieve")
builder.add_edge("retrieve", "generate")
builder.add_edge("generate", END)

graph = builder.compile()

# ── 4. Run: invoke with the starting state, read the final state back ──────
result = graph.invoke({"question": "What is a supernova?"})
print(result["answer"])
```

That runs. `invoke` returns the final state dict — the same form, now with every
section filled in.

## Read it as four steps

| Step | What you're doing | The one line that matters |
|------|-------------------|---------------------------|
| 1 · State | Declare the shape of the shared memory | `class RAGState(TypedDict): ...` |
| 2 · Nodes | Write each function: state in, partial dict out | `return {"chunks": ...}` |
| 3 · Wire | `add_node` each, then `add_edge` in order | `add_edge("retrieve", "generate")` |
| 4 · Run | `compile()` once, then `invoke(initial_state)` | `graph.invoke({"question": ...})` |

## Where this lands in DocsMind

Right now [docsmind/agent/__init__.py](../../docsmind/agent/__init__.py) is a
docstring placeholder. This graph is what fills it. Notice the nodes don't
reimplement anything — `retrieve` calls the existing
[`HybridRetriever`](../../docsmind/retrieval/retriever.py) and `generate` calls
the existing [`CloudLLMClient`](../../docsmind/llm/cloud_client.py). **LangGraph
is the wiring, not the work.** The retrieval and generation you already built
become two nodes; the graph just decides the order and, next, the branches.

## invoke vs stream — know both

- `graph.invoke(state)` — run to the end, get the final state. Simplest.
- `graph.stream(state)` — yields the state update after **each node**, so you can
  show progress ("retrieving…", "generating…") or stream tokens. This is what a
  real UI uses.

## Interview depth signal

- **"Walk me through the execution."** START hands the initial state to
  `retrieve`; `retrieve` returns `{"chunks": [...]}` which merges in; the edge
  routes to `generate`; `generate` reads `chunks` + `question`, returns
  `{"answer": ...}`; the edge routes to END; `invoke` returns the final state.
  Being able to narrate the *state at each hop* is the signal.
- **"What did you gain over a plain function?"** Nothing yet — and saying that
  honestly is good. The gain is structural: the graph is now a place to hang a
  branch, a loop, a retry, or a checkpointer without touching the node code. That
  is [the next page](conditional-edges.md).

→ Next: **[conditional-edges.md](conditional-edges.md)**
