# State, Nodes, Edges — The Whole Mental Model

LangGraph has exactly three moving parts. Learn these and everything else is
detail.

## 1. State — the shared notebook

The state is one dictionary that travels through the graph. Every node reads it
and writes back into it. You declare its shape with a `TypedDict` so you (and the
editor) know what keys exist.

```python
from typing import TypedDict, List

class RAGState(TypedDict):
    question: str        # set once, at the start
    chunks: List[str]    # filled by the retrieve node
    answer: str          # filled by the generate node
```

Think of it as a form that starts mostly blank. Each node fills in its section
and passes the form along. There is no other global memory — if a node needs a
value, it must be in the state.

## 2. Node — a function that fills in part of the form

A node is **just a function**. It takes the whole state and returns a **dict of
only the keys it wants to change**. LangGraph merges that dict back into the
state for you.

```python
def retrieve(state: RAGState) -> dict:
    results = retriever.retrieve(state["question"], top_k=5)  # HybridRetriever
    return {"chunks": [r.text for r in results]}              # merged into state
```

Two things to notice, because both are interview tells:

- The node **reads** `state["question"]` and **writes** `chunks`. It doesn't
  mutate the state object — it *returns* the change. LangGraph does the merge.
- It returns **only** `chunks`, not the whole state. You patch the form; you
  don't recopy it.

A second node, same rule:

```python
def generate(state: RAGState) -> dict:
    context = "\n\n".join(state["chunks"])
    answer = llm.generate(                      # CloudLLMClient.generate
        system="Answer only from the context. Cite sources.",
        prompt=f"Context:\n{context}\n\nQuestion: {state['question']}",
        max_tokens=512,
    )
    return {"answer": answer}
```

## 3. Edge — the arrow that says "go here next"

Edges define the order nodes run in. Two special markers, `START` and `END`, are
the entry and exit.

```python
from langgraph.graph import START, END

# START → retrieve → generate → END
add_edge(START, "retrieve")
add_edge("retrieve", "generate")
add_edge("generate", END)
```

That's a straight line — three edges, no decisions. It's a valid graph. When
someone says "our graph is still sequential," this is what they mean: real
nodes, real state, but every edge is unconditional. Nothing wrong with that —
it's the honest starting point, and the branch is [one step away](conditional-edges.md).

## The one-paragraph version to say out loud

> "State is a `TypedDict` — the shared memory. A node is a function that takes
> state and returns a dict that gets merged into it. Edges wire the nodes in
> order, from `START` to `END`. That's the entire model; conditional edges are
> the only thing that makes it more than a function chain."

## Interview depth signal

- **Why return a partial dict instead of mutating state?** So LangGraph controls
  the merge — which is what lets it snapshot state for checkpointing (memory) and
  run nodes in parallel safely. Mutation would break both.
- **What breaks if two nodes write the same key?** Last write wins by default. If
  you actually want to *accumulate* (e.g. append messages, not overwrite), you
  attach a **reducer** to that key with `Annotated[list, add_messages]`. Knowing
  that reducers exist is the senior signal.

→ Next: **[build-a-graph.md](build-a-graph.md)**
