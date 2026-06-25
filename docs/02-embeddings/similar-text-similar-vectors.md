# Similar Text → Similar Vectors

**TL;DR:** The core magic of embeddings. A model trained on millions of text
pairs learns to produce vectors that are close together for similar meanings
and far apart for different meanings.

## The pattern

```
"A black hole traps light at its event horizon"  → [0.12, -0.45, 0.78, 0.32, ...]
"Nothing escapes once it crosses the horizon"    → [0.11, -0.44, 0.79, 0.31, ...]  ← very close
"The asteroid belt lies between Mars and Jupiter" → [-0.89, 0.34, -0.12, 0.67, ...]  ← far away
```

The first two sentences mean similar things → their numbers are nearly identical.
The asteroid-belt sentence is a different topic → its numbers are very different.

## Why this is powerful for search

When a user asks: *"How do black holes form?"*

1. Embed the question → get a vector, e.g. `[0.08, -0.41, 0.75, 0.35, ...]`
2. Compare it to all chunk vectors in FAISS
3. The chunks *about* black holes will have similar vectors → high similarity score
4. The chunk about the space station will have very different vectors → low score
5. Return the top-k by similarity → the most relevant chunks for the question

This works even if the chunks use different words than the question.
That's the difference from keyword search.

## How "close" and "far" are measured

We use **cosine similarity** — the angle between two vectors.
This is explained in detail in [04-vector-similarity](../04-vector-similarity/).

For now: similarity score 0.0 to 1.0:
- **0.85–1.0** → very similar (same topic, same idea)
- **0.5–0.85** → related (same domain, different aspect)
- **0.0–0.5** → different (different topics)

(These are the real ranges you'll see in this corpus — e.g. "How do black holes
form?" scores 0.81 against `black_holes.md` and 0.63 against
`stellar_lifecycle.md`, since massive stars collapse into black holes.)

## How the model learned this

`bge-small-en-v1.5` was trained on millions of (text, related text) pairs.
The training objective: make the vectors of related pairs closer, unrelated
pairs farther. After training on enough data, the model generalizes — it can
place *any* new text in the right neighborhood of meaning, even text it's
never seen.

→ Next: **[bge-small-model.md](bge-small-model.md)**
