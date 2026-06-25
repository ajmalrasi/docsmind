# 04 — Vector Similarity

**The big idea:** Once chunks and the query are both vectors, we need a formula
to say how "close" they are. That formula is cosine similarity. The closer two
vectors are in direction, the higher the score, the more relevant the chunk.

## Files in this folder

| File | What it covers |
|------|----------------|
| [cosine-similarity.md](cosine-similarity.md) | What cosine similarity is and how to compute it |
| [similarity-scores.md](similarity-scores.md) | How to read a score: 0.0 = different, 1.0 = identical |
| [search-example.md](search-example.md) | A real question → scores → top-k walkthrough |

## 🎯 Interview Q&A

**Q: Why cosine similarity and not Euclidean distance?**
Cosine measures the *angle* between vectors — which represents the *direction*
of meaning — and ignores magnitude (vector length). Euclidean distance measures
straight-line distance and is affected by magnitude. For text, two sentences
about the same topic should be considered similar regardless of their length.
After L2 normalization (all vectors length 1.0), cosine similarity and inner
product are equivalent, so FAISS's IndexFlatIP gives you cosine similarity
for free.

**Q: What is a "good" similarity score?**
It depends on the corpus and model. With bge-small on English technical docs,
scores above ~0.75 are typically relevant hits. What matters more than the
absolute score is the *relative ranking* — you return top-k by score, not by
threshold. You tune k (and add a threshold as a filter if needed) based on
observed quality.

**Q: Exact vs approximate search — when does it matter?**
Exact search (what Phase 1 does — `IndexFlatIP`) compares the query to every
vector and is guaranteed to find the true top-k. For 50 chunks it's instant.
For 10 million chunks it's too slow. Approximate nearest neighbor (ANN) indexes
like HNSW or IVF skip most vectors and return *near*-top-k results in
milliseconds. You trade a small recall loss for massive speed gains. That's
Phase 2 territory.

## Code
[docsmind/retrieval/retriever.py](../../docsmind/retrieval/retriever.py)
[docsmind/index/faiss_store.py](../../docsmind/index/faiss_store.py)

→ Next: **[05-faiss/README.md](../05-faiss/README.md)**
