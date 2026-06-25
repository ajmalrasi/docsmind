# IndexFlatIP — Phase 1's Index

**TL;DR:** `IndexFlatIP` stores all vectors in a flat array and computes the
inner product (dot product) between the query and every stored vector. With
L2-normalized vectors, this equals cosine similarity. Exact, simple, fast
enough for small corpora.

## What "Flat" means

No structure, no organization. Every vector is stored sequentially:

```
Index (flat):
  Position 0:  [0.267, 0.535, 0.802, ...]   ← Chunk 0 vector
  Position 1:  [0.278, 0.511, 0.813, ...]   ← Chunk 1 vector
  Position 2:  [-0.031, 0.089, 0.047, ...]  ← Chunk 2 vector
  ...
  Position 49: [0.123, -0.456, 0.789, ...]  ← Chunk 49 vector
```

A search goes: compare query to position 0, position 1, ..., position 49.
Sort. Return top-k. That's it.

## What "IP" means

IP = **Inner Product** = dot product.

```
inner_product(query, chunk_0) = q₁×c₁ + q₂×c₂ + ... + q₃₈₄×c₃₈₄
```

Because all vectors are L2-normalized (length = 1.0), this equals cosine
similarity. See [03-normalization](../03-normalization/) for the math.

## Creating and using it

```python
import faiss

dim = 384  # bge-small output dimension

# Create the index
index = faiss.IndexFlatIP(dim)

# Add chunk vectors (shape: N × 384, float32)
index.add(chunk_vectors)  # stored in memory

# Search
scores, indices = index.search(query_vector, k=4)
# scores:  [[0.891, 0.874, 0.856, 0.841]]  (inner products = cosine similarities)
# indices: [[12, 3, 8, 15]]                 (positions in the flat array)
```

## Properties

| Property | Value |
|----------|-------|
| Recall | 100% — exact, never misses a true top-k result |
| Search time | O(N) — linear in number of vectors |
| Index build time | Instant — just copy vectors into the array |
| Memory | N × dim × 4 bytes (float32). 50 chunks × 384 × 4 = ~75 KB |
| Training required | No |

## Why it's right for Phase 1

50 chunks × < 1ms search time = the exact index is the simplest, most
correct choice. There's no reason to add the complexity of IVF or HNSW
for a corpus this small. Phase 1 is about getting the pipeline right;
Phase 2 is about making it scale.

→ Next: **[how-search-works.md](how-search-works.md)**
