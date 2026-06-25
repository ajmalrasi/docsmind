# Similar Text → Similar Vectors

**TL;DR:** The core magic of embeddings. A model trained on millions of text
pairs learns to produce vectors that are close together for similar meanings
and far apart for different meanings.

## The pattern

```
"HNSW is a graph-based index"           → [0.12, -0.45, 0.78, 0.32, ...]
"HNSW builds a navigable graph"         → [0.11, -0.44, 0.79, 0.31, ...]  ← very close
"Docker is a containerization platform" → [-0.89, 0.34, -0.12, 0.67, ...]  ← far away
```

The first two sentences mean similar things → their numbers are nearly identical.
The Docker sentence is a different topic → its numbers are very different.

## Why this is powerful for search

When a user asks: *"When should I use HNSW over IVF-PQ?"*

1. Embed the question → get a vector, e.g. `[0.08, -0.41, 0.75, 0.35, ...]`
2. Compare it to all chunk vectors in FAISS
3. The chunks that are *about* HNSW will have similar vectors → high similarity score
4. The chunks about Kubernetes will have very different vectors → low similarity score
5. Return the top-4 by similarity → all relevant to the question

This works even if the chunks use different words than the question.
That's the difference from keyword search.

## How "close" and "far" are measured

We use **cosine similarity** — the angle between two vectors.
This is explained in detail in [04-vector-similarity](../04-vector-similarity/).

For now: similarity score 0.0 to 1.0:
- **0.85–1.0** → very similar (same topic, same idea)
- **0.5–0.85** → related (same domain, different aspect)
- **0.0–0.5** → different (different topics)

## How the model learned this

`bge-small-en-v1.5` was trained on millions of (text, related text) pairs.
The training objective: make the vectors of related pairs closer, unrelated
pairs farther. After training on enough data, the model generalizes — it can
place *any* new text in the right neighborhood of meaning, even text it's
never seen.

→ Next: **[bge-small-model.md](bge-small-model.md)**
