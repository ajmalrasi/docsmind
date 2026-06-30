# 05 — FAISS

**The big idea:** FAISS is a library that stores vectors and lets you find the
most similar ones to a query vector — fast. Think of it as a database
optimized for "find me the nearest neighbors" rather than "find me the row
where id=42."

## Files in this folder

| File | What it covers |
|------|----------------|
| [problem-slow-search.md](problem-slow-search.md) | Why brute-force similarity search doesn't scale |
| [indexflatip-explained.md](indexflatip-explained.md) | Phase 1's index — what it does, why it's the right choice for now |
| [how-search-works.md](how-search-works.md) | Step-by-step: from query vector to top-k results |
| [phase1-vs-phase2.md](phase1-vs-phase2.md) | Flat vs IVF vs HNSW vs PQ — the full tradeoff table |
| [benchmark-results.md](benchmark-results.md) | Phase 2: real measured recall@k, latency & memory for all four |
| [code-walkthrough.md](code-walkthrough.md) | The actual Phase 1 code explained line by line |

## 🎯 Interview Q&A

**Q: FAISS vs Pinecone / Weaviate / Qdrant — why use FAISS?**
FAISS is a library (C++ with Python bindings), not a service. It runs in your
process, in memory, no network hop. Pinecone/Weaviate are managed cloud
vector DBs — you send data to them over HTTP. For Phase 1 (self-hosted, small
corpus, portfolio project): FAISS is simpler, faster, free, and private.
For production at scale you'd add Qdrant (open-source, self-hosted DB with a
proper query API, filtering, and persistence). That's Phase 2. The
`VectorStore` interface in Phase 1 means swapping is a config change.

**Q: Why IndexFlatIP in Phase 1 and not HNSW?**
Flat does an exact search — compares query to every vector. For 50 chunks it
returns in < 1ms and recall is 100%. HNSW is an approximate algorithm — it
traverses a graph and skips most vectors. Faster at scale, but adds complexity
(graph construction time, parameter tuning, approximate results). Phase 1
prioritizes correctness and simplicity. At 50–10,000 vectors, Flat is the
right choice.

**Q: What is recall@k?**
If there are 10 truly relevant chunks in the corpus and your retriever returns
k=10 results that contain 8 of them, your recall@10 is 8/10 = 80%. It
measures how many relevant results you found, not just whether the top result
was good. Approximate indexes like HNSW sacrifice a bit of recall for speed —
HNSW on a well-tuned corpus typically achieves 95%+ recall@10.

**Q: What does FAISS NOT do?**
FAISS doesn't store your chunk text, metadata, or sources. It only stores and
searches vectors (numbers). That's why `FaissVectorStore` keeps a separate
`self._chunks` list that maps each vector index position to its chunk object.
You search FAISS for indices, then look up the actual text yourself.

## Code
[docsmind/index/faiss_store.py](../../docsmind/index/faiss_store.py)
[docsmind/index/base.py](../../docsmind/index/base.py)

→ Next: **[06-generation/README.md](../06-generation/README.md)**
