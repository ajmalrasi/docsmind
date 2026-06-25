# Embeddings — Interview Questions

## Q: Why self-hosted bge-small over OpenAI embeddings?

Embedding is a **bulk operation** — you encode your entire corpus at ingest.
100k chunks on a paid API costs real money and hits rate limits. Self-hosted
runs locally, is free after download, and your documents never leave your
infrastructure. bge-small is MIT-licensed (no lock-in) and achieves strong
quality on English technical text. If you needed multilingual support or
top-tier quality, you'd evaluate a larger or cloud model — it's a one-line
swap in the `Embedder` class.

---

## Q: Why do the query and documents have to use the same embedding model?

Each model learns its own vector space. A vector from model A and a vector
from model B live in completely different coordinate systems. Comparing them
with cosine similarity is like measuring the distance between a GPS
coordinate in WGS84 and one in a local grid — meaningless. Same model at
ingest and query is non-negotiable.

---

## Q: Dense embeddings vs BM25 — which is better?

Neither alone. Dense captures semantic meaning ("car" ≈ "automobile") but
misses exact tokens, IDs, rare terms. BM25 nails exact matches but is blind
to meaning. Hybrid (dense + BM25, scores fused, then reranked) beats either.
That's Phase 3 of this project — the right answer is always "hybrid."

---

## Q: Bi-encoder vs cross-encoder?

**Bi-encoder** (what bge-small is): encodes query and document independently.
You precompute document vectors once. Fast, scalable to millions of docs.

**Cross-encoder**: takes (query, document) together as input, much more
accurate. But you must run it for every query-doc pair — can't precompute.
Used as a **reranker** on the top-k results from bi-encoder retrieval. That's
Phase 3.

---

## Q: Why 384 dimensions and not 1024 or 3072?

Smaller vectors = faster inner product math + less memory. 384 is enough
for English technical prose with bge-small. Larger dimensions help on harder,
more diverse, or multilingual content. It's a quality-vs-cost knob you tune
with a retrieval eval set.

---

## Q: What is semantic drift?

If your corpus updates frequently and you want to update your embedding model
(e.g. retrain or upgrade), all existing vectors become stale — they were
produced by a different model and now live in a different space. You'd have to
re-embed and re-index the entire corpus. This is a real ops concern in
production, especially for large corpora.

---

## Q: Can you fine-tune an embedding model?

Yes. If your domain is very specialized (legal, medical, code), a
general-purpose embedding model may not capture domain-specific meaning well.
Fine-tuning on domain (query, positive_passage, negative_passage) triplets
can significantly improve retrieval quality. Mentioned as a future improvement,
not Phase 1 scope.
