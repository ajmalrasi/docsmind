# Real Examples — Chunking Your Docs

**TL;DR:** Here's what the chunker actually does to
[faiss_index_types.md](../../data/sample_docs/faiss_index_types.md) with
`chunk_size=512, chunk_overlap=64`.

## The original document (full text)

```
# FAISS Index Types

FAISS provides several index structures that trade retrieval accuracy (recall)
against query latency and memory footprint.

## Flat (IndexFlatIP / IndexFlatL2)
A flat index stores every vector and compares the query against all of them. It
gives exact, 100% recall but query time grows linearly with the number of
vectors. Flat is the right choice for small corpora or as a ground-truth baseline
when benchmarking approximate indexes. With L2-normalized vectors, inner-product
search (IndexFlatIP) is equivalent to cosine similarity.

## IVF (Inverted File Index)
IVF partitions the vector space into `nlist` cells using k-means and, at query
time, only searches the `nprobe` cells nearest to the query. Increasing `nprobe`
raises recall at the cost of latency. IVF requires a training step on a
representative sample before vectors can be added.

## HNSW (Hierarchical Navigable Small World)
HNSW builds a multi-layer graph and navigates it greedily. It typically delivers
the best recall-vs-latency tradeoff for in-memory search...

## PQ (Product Quantization)
PQ compresses vectors into compact codes...

## Choosing an index
- Small corpus or baseline: Flat.
- Large corpus, accuracy-sensitive: HNSW.
- Very large corpus, memory-constrained: IVF-PQ.
```

This doc is short (~300 words), so the splitter produces **2 chunks**.

---

## Chunk 1

```
Chunk {
    id:     "node_001",
    source: "faiss_index_types.md",
    text:   "# FAISS Index Types

             FAISS provides several index structures that trade retrieval
             accuracy (recall) against query latency and memory footprint.

             ## Flat (IndexFlatIP / IndexFlatL2)
             A flat index stores every vector and compares the query against
             all of them. It gives exact, 100% recall but query time grows
             linearly with the number of vectors...

             ## IVF (Inverted File Index)
             IVF partitions the vector space into `nlist` cells using k-means
             and, at query time, only searches the `nprobe` cells nearest to
             the query. Increasing `nprobe` raises recall at the cost of
             latency. IVF requires a training step on a representative sample
             before vectors can be added."
}
```

*This chunk ends at the IVF section.*

---

## Chunk 2 (with overlap)

```
Chunk {
    id:     "node_002",
    source: "faiss_index_types.md",
    text:   "IVF requires a training step on a representative sample        ← overlap!
             before vectors can be added.

             ## HNSW (Hierarchical Navigable Small World)
             HNSW builds a multi-layer graph and navigates it greedily.
             It typically delivers the best recall-vs-latency tradeoff
             for in-memory search...

             ## PQ (Product Quantization)
             PQ compresses vectors into compact codes...

             ## Choosing an index
             - Small corpus or baseline: Flat.
             - Large corpus, accuracy-sensitive: HNSW.
             - Very large corpus, memory-constrained: IVF-PQ."
}
```

*The first sentence of Chunk 2 is the last sentence of Chunk 1 — that's the overlap.*

---

## What happens at query time

Question: *"Does IVF need training before adding vectors?"*

1. The question gets embedded → a vector
2. FAISS compares it to all chunk vectors
3. **Chunk 2** scores high because it starts with exactly that sentence
4. Claude reads Chunk 2 and answers: *"Yes, IVF requires a training step [1]"*
5. `[1]` maps back to `source: faiss_index_types.md` → citation shown to user

Without overlap, that sentence lived only at the very end of Chunk 1.
Chunk 1's embedding had to represent the *whole* IVF + Flat sections —
not sharp enough on that one sentence. The overlap puts it at the *top* of
Chunk 2, where it dominates the embedding. Retrieval improves.

→ Back to: **[README.md](README.md)**
→ Next topic: **[02-embeddings/README.md](../02-embeddings/README.md)**
