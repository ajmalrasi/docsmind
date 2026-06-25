# 02 — Embeddings

**The big idea:** A computer can't compare English sentences directly. We
convert each chunk into a list of 384 numbers — called an *embedding* or
*vector* — that captures the chunk's meaning. Chunks with similar meaning get
similar numbers. That's what makes "search by meaning" possible.

## Files in this folder

| File | What it covers |
|------|----------------|
| [problem-text-is-not-numbers.md](problem-text-is-not-numbers.md) | Why computers can't search raw text |
| [what-is-an-embedding.md](what-is-an-embedding.md) | What 384 numbers actually represent |
| [similar-text-similar-vectors.md](similar-text-similar-vectors.md) | The core magic — why similar meaning = similar vector |
| [bge-small-model.md](bge-small-model.md) | Why we use bge-small, self-hosted vs cloud |
| [real-examples.md](real-examples.md) | Concrete numbers, before and after encoding |

## 🎯 Interview Q&A

**Q: Why self-hosted bge-small over OpenAI / Cohere embeddings?**
Embedding is a *bulk* operation — you embed your entire corpus at ingest time.
100,000 chunks = 100,000 model calls. On a paid per-token API that costs real
money and hits rate limits. Self-hosted runs locally, is free after download,
and your documents never leave your infrastructure. bge-small is good enough for
English technical docs. The `Embedder` class is a single swap point, so
switching to a bigger or cloud model later is a one-line config change.

**Q: Dense embeddings vs keyword search (BM25) — which is better?**
Neither alone. Dense embeddings capture semantic meaning ("car" ≈ "automobile")
but can miss exact terms, IDs, or rare tokens. BM25 nails exact matches but
is blind to meaning. Hybrid (dense + BM25, then rerank) usually beats either.
That's exactly Phase 3 of DocsMind — mention it as the natural next improvement.

**Q: Why do query and documents have to use the same model?**
Each model learns its own vector space. A vector from model A and a vector from
model B live in completely different spaces — comparing them for similarity is
meaningless. Same model at ingest and query time is non-negotiable.

**Q: Why 384 dimensions and not more?**
Smaller vectors = faster search + less memory. bge-small's 384-dim quality is
strong for English technical prose. Larger models (bge-large at 1024 dims,
OpenAI at 3072 dims) help on harder, more diverse, or multilingual content —
but every query now does math on 3072 numbers instead of 384. It's a
quality-vs-cost knob you tune with an eval set.

**Q: Bi-encoder vs cross-encoder?**
bge-small is a bi-encoder: encodes query and documents independently, so you
precompute document vectors once. Fast and scalable.
A cross-encoder reads query + document *together* — much more accurate but must
run for every query-document pair, so you can't use it on a full corpus. It's
used as a *reranker* on the top-k results (Phase 3).

## Code
[docsmind/index/embeddings.py](../../docsmind/index/embeddings.py)

→ Next: **[03-normalization/README.md](../03-normalization/README.md)**
