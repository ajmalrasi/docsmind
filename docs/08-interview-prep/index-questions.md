# Index Types & Vector DBs — Interview Questions

These are the Phase 2 / 2b depth questions. The pattern interviewers probe:
not "did you use FAISS?" but "why *this* index, and how did you know?"

---

## Q: Flat vs IVF vs HNSW vs PQ — when do you use each?

All four live at the same pipeline stage — the **Index** box — and answer the
same question ("nearest vectors to this one"), differently:

| Index | Idea in one line | Trade |
|---|---|---|
| **Flat** | Check every vector (exact scan) | 100% recall, O(N) time |
| **IVF** | Cluster vectors; search only the nearest clusters | Speed for recall (misses across cluster borders) |
| **HNSW** | Greedy walk through a graph of neighbors | Speed for memory (stores the graph) |
| **IVFPQ** | IVF + compress vectors to a few bytes | Memory for recall (lossy compression) |

Rule of thumb: flat until it hurts (~100k vectors), HNSW when latency matters
and RAM is fine, IVF when you want a tunable middle, PQ only when the vectors
don't fit in memory.

---

## Q: You benchmarked these. What were the actual numbers?

At 50k synthetic clustered vectors (384-dim, like bge-small):

| Index | Latency | Recall@10 | Memory |
|---|---|---|---|
| flat | 0.78 ms | 100% | 1.0x |
| ivf | 0.10 ms | 90% | ~1.0x |
| hnsw | 0.40 ms | 86% | 1.18x |
| ivfpq | 0.09 ms | 33% | **0.04x** |

And flat scales linearly: 0.78 ms at 50k → 7.2 ms at 500k. That O(N) line is
*why* ANN indexes exist — you can see exactly where flat stops being viable.

The IVFPQ row is the teaching moment: 25x less memory, but recall collapsed to
33% because 384 floats got squashed into a few bytes. Compression is not free.

Script: [`scripts/benchmark.py`](../../scripts/benchmark.py) · full writeup:
[benchmark-results.md](../05-faiss/benchmark-results.md)

---

## Q: Why synthetic *clustered* vectors and not random ones?

Real embeddings cluster — chunks about black holes sit near each other.
Uniform random vectors spread evenly, which makes IVF look artificially good
(clean cluster borders) and hides the recall loss you'd see in production.
Benchmarking on data shaped like your real data is the difference between a
number you can defend and a number that evaporates in production.

---

## Q: So which index does your real pipeline use — and why?

**Flat.** The corpus is a few dozen chunks; exact search returns in well under
a millisecond. Choosing HNSW there would be premature optimization — extra
build time, extra parameters to tune, a recall trade, for zero felt benefit.

The senior signal is the *decision procedure*, not the index: measure where
flat's O(N) line crosses your latency budget, and switch only past that point.

---

## Q: What do nprobe and ef actually do?

They are the **recall-vs-speed dial** on each ANN index, turned at query time:

- **IVF `nprobe`** — how many clusters to look inside. More clusters = fewer
  misses at borders, more work.
- **HNSW `ef_search`** — how wide the graph walk keeps its candidate list.
  Wider = better recall, slower.

Same shape both times: spend more compute per query, recover more recall.
In DocsMind these live in config (`ivf_nprobe`, `hnsw_ef_search`) so the dial
is turnable without re-ingesting.

---

## Q: Why does IVF/IVFPQ "train on add" — and what can go wrong?

IVF must first learn where the clusters *are* (k-means over your vectors)
before it can assign anything to them. So the store trains on the first
`add()`. Two failure modes worth naming: training on too few vectors gives
garbage centroids (FAISS will warn), and if your data distribution shifts
later, the old centroids quietly degrade recall — you re-train to fix it.

---

## Q: FAISS vs Qdrant — why did you add a second backend?

Not for speed — for **operations**. FAISS is a library inside one process:
each API replica needs its own copy of the index in memory, and a flat index
is rebuilt to change. Qdrant is a service: many replicas query the same store,
vectors upsert live, and it filters on metadata while searching.

The hidden cost of the switch: Qdrant builds HNSW by default, so you traded
FAISS-flat's *exact* search for *approximate* — just by changing backends.

---

## Q: How did you make the backends swappable?

One `VectorStore` interface (`add / search / save / size / chunks`), two
implementations, selected by a `vector_backend` config setting. The retriever
and pipeline never learn which is underneath. This is the same seam pattern
used everywhere in DocsMind (embedder, LLM client) — every external dependency
sits behind an interface so a swap is a config change, not a refactor.

---

## Q: Compare FAISS, Pinecone, Weaviate, Milvus, pgvector.

Group them by *operational shape*, not by feature list:

- **Library, in-process:** FAISS. Fastest, free, no filtering, no server. You
  own persistence and scaling.
- **Self-hostable service:** Qdrant, Weaviate, Milvus. HTTP API, metadata
  filtering, live updates, horizontal scale. You run them.
- **Managed cloud:** Pinecone. Zero ops, pay per use, data leaves your VPC.
- **Bolt-on to a DB you already run:** pgvector. Right when the vectors are
  small-scale and Postgres is already there — one fewer system to operate.

The interview answer: "I'd pick by who operates it and where the data may
live, then benchmark recall/latency on my own vectors — which I did."
