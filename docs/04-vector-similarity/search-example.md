# Search Example — Question to Top-k

**TL;DR:** A full walkthrough of one query through the retrieval layer —
from raw question text to ranked chunks with scores.

## Setup

We have 4 documents chunked into ~50 vectors, all stored in FAISS.

**Question:** *"When should I use HNSW over IVF-PQ?"*

---

## Step 1: Embed the question

```python
# docsmind/retrieval/retriever.py

query_vec = self._embedder.encode(["When should I use HNSW over IVF-PQ?"])[0]
# query_vec shape: (384,)
# query_vec is normalized (length = 1.0)
```

The same `bge-small-en-v1.5` model that encoded the chunks encodes the question.
Same model → same vector space → comparable vectors.

---

## Step 2: FAISS searches all 50 vectors

```python
# docsmind/index/faiss_store.py

scores, indices = self._index.search(query_vec.reshape(1, -1), top_k=4)
```

FAISS computes the inner product (= cosine similarity) between the question
vector and all 50 chunk vectors. Returns the 4 highest scores with their
positions (indices) in the stored array.

```
Internal FAISS result:
  indices = [12, 3, 8, 15]        # positions in the stored array
  scores  = [0.89, 0.87, 0.85, 0.84]
```

---

## Step 3: Look up the chunks at those positions

```python
for score, idx in zip(scores[0], indices[0]):
    chunk = self._chunks[idx]
    results.append(SearchResult(chunk=chunk, score=float(score)))
```

```
SearchResult #1  score=0.891
  source: faiss_index_types.md
  text: "HNSW builds a multi-layer graph and navigates it greedily.
         It typically delivers the best recall-vs-latency tradeoff..."

SearchResult #2  score=0.874
  source: faiss_index_types.md
  text: "IVF partitions the vector space into `nlist` cells using k-means.
         Increasing `nprobe` raises recall at the cost of latency..."

SearchResult #3  score=0.856
  source: faiss_index_types.md
  text: "HNSW uses more memory than IVF because it stores graph edges
         in addition to the vectors..."

SearchResult #4  score=0.841
  source: faiss_index_types.md
  text: "Large corpus, accuracy-sensitive, fits in RAM: HNSW.
         Very large corpus, memory-constrained: IVF-PQ..."
```

---

## Step 4: Hand off to the pipeline

These 4 chunks (with their sources and scores) go to `RAGPipeline.query()`,
which:
1. Formats them as numbered context passages `[1]`, `[2]`, `[3]`, `[4]`
2. Sends them + the question to Claude
3. Claude answers using only those passages and cites by number
4. The pipeline extracts citations and maps `[n]` back to `source` filenames

---

## The speed

For 50 chunks: FAISS finishes in < 1 millisecond.
For 1 million chunks with a Flat index: ~100ms (linear scan).
For 1 million chunks with HNSW: ~1ms (approximate, graph traversal).

That's why Phase 2 adds approximate indexes — they matter at scale.

→ Back to: **[README.md](README.md)**
→ Next topic: **[05-faiss/README.md](../05-faiss/README.md)**
