# Chunking — Interview Questions

## Q: Why chunk at all? Why not embed the whole document?

Embedding a whole document averages all its topics into one blurry vector.
A chunk about HNSW gives a sharp, focused embedding. Retrieval precision
drops sharply when documents are too large because the embedding can't
represent multiple unrelated ideas simultaneously.

---

## Q: Big chunks vs small chunks — what's the tradeoff?

| | Small (e.g. 128 tokens) | Large (e.g. 1024 tokens) |
|---|---|---|
| Embedding focus | Sharp — one idea | Blurry — averaged meaning |
| Context per hit | May be too little | Rich surrounding context |
| Missed boundaries | More | Fewer |
| Number of vectors | More (more storage) | Fewer |

512 tokens is a common sweet spot for English technical prose. You tune it
against an eval set, not by intuition.

---

## Q: Why is chunk size tied to the embedding model?

bge-small-en-v1.5 has a max input of **512 tokens**. If a chunk is longer,
the model *silently truncates* — the tail is never embedded. Chunk size must
never exceed the embedding model's max sequence length or you lose data
without knowing it.

---

## Q: Why overlap? What does it cost?

Overlap prevents an idea at a chunk boundary from being cut in half —
the same sentence appears at the end of one chunk and the start of the next,
so at least one chunk contains it fully. Cost: ~10–20% duplicated storage
and occasional duplicate retrieval results.

---

## Q: Fixed-size vs sentence-aware vs semantic chunking?

- **Fixed-size:** fastest, cuts mid-sentence.
- **Sentence-aware (Phase 1):** respects sentence boundaries, good default.
- **Semantic:** splits where topic changes, best quality, slower.
- **Structural:** splits on headers/code blocks — excellent for markdown docs.

You'd mention semantic or structural chunking as "the next improvement"
if retrieval quality matters.

---

## Q: How would you know if your chunk size is wrong?

Run an eval set: a set of (question, expected source doc) pairs. Measure
recall@k — what fraction of questions retrieved the expected chunk in top-k.
If recall is low, the chunk boundaries may be wrong. You don't guess; you
measure.
