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
the best recall-vs-latency tradeoff for in-memory search. The key parameters are
`M` (graph connectivity) and `efSearch` (search breadth — higher means better
recall and higher latency). HNSW uses more memory than IVF because it stores graph
edges in addition to the vectors.

## PQ (Product Quantization)

PQ compresses vectors into compact codes by splitting each vector into sub-vectors
and quantizing each independently. It dramatically reduces memory at the cost of
some recall, and is often combined with IVF (IVF-PQ) for billion-scale search.

## Choosing an index

- Small corpus or baseline: Flat.
- Large corpus, accuracy-sensitive, fits in RAM: HNSW.
- Very large corpus, memory-constrained: IVF-PQ.
