# Retrieval — Interview Questions

## Q: FAISS vs Pinecone / Weaviate / Qdrant?

| | FAISS | Pinecone | Qdrant |
|---|---|---|---|
| Type | Library (in-process) | Managed cloud service | Open-source DB (self-hosted or cloud) |
| Network overhead | None | HTTP per query | HTTP per query (self-hosted = LAN) |
| Cost | Free | Pay per vector/query | Free (self-hosted) |
| Data privacy | Stays in your process | Sent to Pinecone | Configurable |
| Filtering | Basic | Rich metadata filtering | Rich metadata filtering |
| Scalability | Up to ~10M vectors in RAM | Fully managed, any scale | Production-ready, horizontally scalable |
| Persistence | Manual (write_index) | Automatic | Automatic |

**Why FAISS in Phase 1:** Simple, zero infra, perfect for a self-hosted portfolio
project. **Why Qdrant in Phase 2:** adds proper persistence, filtering, and a
query API without sending data to a third party. Both are behind the same
`VectorStore` interface so the swap is a config change.

---

## Q: Why IndexFlatIP in Phase 1 and not HNSW?

Flat does an exact scan — 100% recall, O(N) time. For 50 chunks it returns in
< 1ms. HNSW is approximate — faster at scale but adds graph construction
complexity and parameter tuning, and trades a small amount of recall. At 50
vectors exact is the right choice: simplest, most correct, no premature
optimization.

---

## Q: Exact vs approximate search — when does the tradeoff matter?

At ~100k+ vectors, exact search starts to feel slow for interactive use
(>50ms). ANN (approximate nearest neighbor) indexes like HNSW return results
in 1–5ms at 1M vectors with ~95–99% recall. The 1–5% of missed results is
acceptable for most RAG use cases. The crossover point depends on your
latency budget and corpus size.

---

## Q: What is recall@k?

If there are 10 truly relevant chunks in the corpus and you retrieve k=10
results, how many of the 10 true positives appear in your results? Recall@10
= 8/10 = 80%. Measures coverage, not just top-1 quality. ANN indexes target
high recall@k (not 100%) while being much faster than exact search.

---

## Q: When would a similarity threshold filter make sense?

Phase 1 always returns top-k — even if the best matching chunks are barely
relevant (low scores). A threshold (e.g., drop results below 0.60) prevents
sending irrelevant context to the LLM. The downside: if your corpus doesn't
cover a topic at all, you'd return zero chunks and can't generate any answer.
The `INSUFFICIENT_CONTEXT` guardrail in the LLM prompt is a softer alternative.

---

## Q: Cosine similarity vs dot product vs Euclidean distance?

After L2 normalization (all vectors length 1.0), **cosine similarity equals
dot product**. So `IndexFlatIP` (inner product) gives you cosine similarity
for free — no special cosine index needed.

Euclidean distance is sensitive to vector magnitude (length). Before
normalization, a longer chunk might have a larger raw vector and appear
artificially "closer" to everything. Cosine only cares about direction
(angle), which represents meaning. For text retrieval, direction = meaning,
magnitude = irrelevant.
