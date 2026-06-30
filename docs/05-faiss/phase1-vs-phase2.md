# Flat vs IVF vs HNSW vs PQ — The Full Comparison

**TL;DR:** Four index types, four different tradeoffs between speed, memory,
recall, and complexity. Phase 1 uses Flat. Phase 2 benchmarks the rest.

## The four index types

### 1. IndexFlatIP (Phase 1)

- **How:** Stores all vectors. Compares query to every single one.
- **Recall:** 100% — exact, no approximation
- **Speed:** O(N) — gets slower as N grows linearly
- **Memory:** N × 384 × 4 bytes (raw float32 vectors)
- **Training:** None
- **Good for:** Small corpora, ground-truth benchmarking

```
Query ──→ [compare to all N vectors] ──→ top-k
```

### 2. IndexIVF (Inverted File)

- **How:** Clusters vectors into `nlist` groups using k-means at build time.
  At query time, only searches the `nprobe` closest groups.
- **Recall:** ~90–99% (depending on `nprobe`)
- **Speed:** Much faster than Flat at large N — only searches a fraction of vectors
- **Memory:** Similar to Flat (stores raw vectors + cluster assignments)
- **Training:** Requires running k-means on a representative sample first
- **Good for:** 100k–10M vectors where exact search is too slow

```
Build: cluster all vectors into groups (k-means)
Query ──→ [find closest nprobe groups] ──→ [compare to those vectors only] ──→ top-k
```

### 3. IndexHNSW (Hierarchical Navigable Small World)

- **How:** Builds a multi-layer graph at ingest time. At query time, starts
  at the top layer and navigates greedily to the closest nodes.
- **Recall:** ~95–99% with good parameters
- **Speed:** Very fast — milliseconds even at millions of vectors
- **Memory:** Higher than Flat — stores graph edges in addition to vectors
  (~1.5–2× more memory)
- **Training:** None — graph is built incrementally as vectors are added
- **Good for:** Up to ~5–10M vectors in RAM where latency is critical

```
Build: link each vector to its M nearest neighbors at each layer
Query ──→ [start at top layer, greedy graph walk] ──→ top-k (approximate)
```

Key parameters:
- `M` — number of edges per node (higher = better recall, more memory)
- `efSearch` — search breadth (higher = better recall, slower)

### 4. IndexPQ / IndexIVFPQ (Product Quantization)

- **How:** Compresses each vector by splitting it into sub-vectors and
  replacing each with a code (quantization). Stores codes instead of raw floats.
- **Recall:** Lower than other methods — lossy compression
- **Speed:** Fast — smaller data fits in CPU cache better
- **Memory:** Dramatically lower — can be 8–32× smaller than raw vectors
- **Training:** Requires training the quantizer
- **Good for:** Billion-scale corpora where you can't fit raw vectors in RAM

```
Compress: [0.267, 0.535, 0.802, ..., (384 floats)] → [42, 17, 8] (3 codes)
Query ──→ [compare codes, not full floats] ──→ top-k (approximate, lossy)
```

---

## Side-by-side comparison

| Index | Recall | Speed at 1M | Memory | Training | Best for |
|-------|--------|-------------|--------|----------|----------|
| **Flat** | 100% | Slow (~100ms) | 1× | None | < 100k, baseline |
| **IVF** | ~95% | Fast (~5ms) | 1× | Yes | 100k–10M |
| **HNSW** | ~98% | Very fast (~1ms) | 1.5–2× | None | < 10M, low latency |
| **IVFPQ** | ~85% | Very fast (~1ms) | 0.03–0.1× | Yes | Billions, memory-limited |

---

## What Phase 2 will do

Run all four on the same corpus and measure:
- Recall@k (did we find the true top-k?)
- Query latency (ms per query)
- Index build time
- Memory usage

Then decide which index type to use based on those numbers — not theory.
That's the "benchmark notebook" deliverable of Phase 2.

**✅ Done.** The benchmark is built (`scripts/benchmark.py`) and the real
measured numbers — recall@k, latency, build time, and memory for all four index
types at 50k and 500k vectors — are in
**[benchmark-results.md](benchmark-results.md)**.

→ Next: **[benchmark-results.md](benchmark-results.md)**
