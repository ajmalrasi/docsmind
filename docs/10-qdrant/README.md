# Qdrant — a vector store you talk to, not one you embed (Phase 2b)

**TL;DR:** FAISS lives *inside* your program (a notebook on your desk). Qdrant is
a *separate service* you talk to over the network (a librarian in another room).
Both store vectors and find nearest neighbors. The difference is operational, not
about raw speed.

## Where this lives in the pipeline

Phase 2b only swaps the **Index** box. Same `VectorStore` contract, so the
retriever and pipeline never learn which backend is underneath.

```
Ingest → Chunk → Embed → [ INDEX: faiss | qdrant ] → Search → Generate
                              ▲
                  the only thing that changes
```

## Embedded vs. service (the core idea)

**FAISS = embedded.** "Embedded" means it runs *inside your own Python process*.
The vectors sit in this program's memory and get written to a file. Fast to
search, but only this one process can read them at a time.

**Qdrant = a service.** It's a separate program. You send it "find the closest
vectors to this one" over HTTP, it does the work and sends results back. DocsMind
runs it in one of two modes:

| Mode | What it is | When |
|------|------------|------|
| **local-path** | Qdrant persists to a directory on disk, no server process | Default — keeps tests and `make demo` offline |
| **server (URL)** | A Dockerized Qdrant reachable over HTTP (e.g. on beast) | The "real" deployment shape |

Set `qdrant_url` to use the server; leave it empty for local-path.

## Why move to a service at all?

**Not for speed** — that's the common wrong answer. The reasons are operational:

- **Concurrency.** Many copies of your API can query the *same* Qdrant at once.
  With FAISS, each process needs its own copy of the index in memory.
- **Live updates.** Qdrant supports adding/deleting vectors on the fly. A FAISS
  flat index is rebuilt to change.
- **Metadata filtering.** Qdrant can filter while it searches ("only docs from
  2024"), using the payload stored next to each vector.

> You reach for Qdrant when the index **outgrows a single process** — not when
> search feels slow.

## One technical contrast to keep

Qdrant builds an **HNSW** graph for every collection by default — so its search is
**approximate** out of the box. FAISS `flat` (the Phase 1 default) is **exact**.
Just by switching backends, you traded exact answers for fast-approximate ones.
(HNSW is the same graph index covered in [05-faiss](../05-faiss/).)

## How it's wired

- `QdrantVectorStore` ([`qdrant_store.py`](../../docsmind/index/qdrant_store.py))
  implements the same `add / search / save / size / index_type / chunks` contract
  as `FaissVectorStore`.
- The `vector_backend` setting (`"faiss"` default / `"qdrant"`) selects it in the
  factory. Switch with `DOCSMIND_VECTOR_BACKEND=qdrant` and re-ingest.
- Vectors use **cosine** distance. Our embeddings are already L2-normalized, so
  cosine and dot product agree.
- Point payloads carry the full chunk (id, text, source, metadata), so search
  results and the BM25 corpus can be rebuilt straight from Qdrant.

## The interview signals

- **Why move from FAISS to Qdrant?** Operations, not performance: concurrent
  access across API replicas, live upserts, metadata filtering. FAISS is one
  process's memory; Qdrant is a shared service.
- **What did it cost?** A network hop per query, a service to run and monitor, and
  you gave up FAISS's exact `flat` for Qdrant's approximate HNSW.
- **How did you keep tests offline?** Local-path / in-memory Qdrant — no server
  needed, same code path.

→ Code: [`qdrant_store.py`](../../docsmind/index/qdrant_store.py)
· Interface: [`base.py`](../../docsmind/index/base.py)
