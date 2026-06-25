# 01 — Chunks & Overlap

**The big idea:** Documents are too long and too broad to search as a whole.
We split them into small focused pieces called *chunks*. We overlap neighboring
chunks slightly so ideas at the boundary don't get lost.

## Files in this folder

| File | What it covers |
|------|----------------|
| [what-is-a-chunk.md](what-is-a-chunk.md) | What a chunk is, what it contains, why small |
| [why-overlap.md](why-overlap.md) | The boundary problem and how overlap solves it |
| [real-examples.md](real-examples.md) | Actual text from your docs shown being chunked |

## 🎯 Interview Q&A

**Q: Why chunk at all?**
Because embedding a whole document into one vector averages out all its topics
into a blurry signal. A chunk about event horizons gives a sharp, focused
vector. That's what makes retrieval precise.

**Q: Big chunks vs small chunks?**
Small → sharper retrieval, less context per hit.
Large → fuzzier retrieval (embedding averages more ideas), more context per hit.
512 tokens is a common sweet spot for technical prose. You tune it by measuring
retrieval quality on an eval set, not by guessing.

**Q: Why 512 specifically in Phase 1?**
Two reasons: (1) it balances precision vs context for technical docs, and (2) it
matches the hard limit of `bge-small-en-v1.5` — feed it more than 512 tokens and
it **silently truncates** the tail. Chunk size should never exceed the embedding
model's max input length.

**Q: Fixed-size vs sentence-aware vs semantic chunking?**
- **Fixed-size:** cuts every N tokens, fast, can cut mid-sentence.
- **Sentence-aware (Phase 1):** breaks on sentence boundaries, readable, good default.
- **Semantic:** splits where the topic changes, smartest but slower.
- **Structural:** splits on markdown headers / code blocks — great for technical docs.

**Q: What does overlap cost?**
Duplicated storage and sometimes the same content retrieved twice. Typical overlap
is 10–20% of chunk size. Phase 1 uses 64/512 ≈ 12.5%.

## Code
[docsmind/ingestion/chunker.py](../../docsmind/ingestion/chunker.py)

→ Next: **[02-embeddings/README.md](../02-embeddings/README.md)**
