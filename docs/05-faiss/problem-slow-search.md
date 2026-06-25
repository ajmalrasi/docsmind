# The Problem: Brute-Force Search Doesn't Scale

**TL;DR:** For a small corpus, comparing the query to every vector is fine.
For millions of vectors it becomes too slow. FAISS solves this.

## The naive approach

You have 50 chunks, each a 384-dimensional vector. A question comes in.

```
Step 1: Embed the question → 384 numbers
Step 2: Compare to chunk 1  → compute similarity score
Step 3: Compare to chunk 2  → compute similarity score
...
Step 51: Compare to chunk 50 → compute similarity score
Step 52: Sort all 50 scores
Step 53: Return top-4
```

Total comparisons: **50**. Time: **< 1ms**. No problem.

## Why this breaks at scale

| Corpus size | Comparisons per query | Approx time (CPU) |
|---|---|---|
| 50 chunks (Phase 1) | 50 | < 1ms |
| 100,000 chunks | 100,000 | ~10ms |
| 1,000,000 chunks | 1,000,000 | ~100ms |
| 1,000,000,000 chunks | 1 billion | ~100 seconds |

At millions of vectors, even with highly optimized C++ code, brute-force
becomes too slow for real-time queries. You need indexes that let you
**skip most vectors** and only look at the promising ones.

## What FAISS provides

FAISS is a library of index structures that organize vectors so you can:

1. **Exact search** (`IndexFlatIP`) — compare to everything, 100% recall.
   Right for small corpora.
2. **Approximate search** (`IndexIVF`, `IndexHNSW`) — skip most vectors,
   very fast, ~95–99% recall at scale. Right for large corpora.
3. **Compressed search** (`IndexPQ`, `IndexIVFPQ`) — compress vectors to
   save memory, trade some recall. Right for billion-scale.

Phase 1 uses **#1** because the corpus is small. Phase 2 benchmarks **#2 and #3**.

## The trade-off at the core of all this

```
Exact  → 100% recall, slower as scale grows
Approx → ~95-99% recall, fast even at millions of vectors
```

For most RAG applications, losing 1–5% of relevant results is acceptable
if it means 100× faster queries.

→ Next: **[indexflatip-explained.md](indexflatip-explained.md)**
