# Hybrid Retrieval — dense + BM25 + reranking (Phase 3)

**TL;DR:** Phase 1 searched one way (by meaning). Phase 3 searches two ways
(meaning + exact words), combines them fairly, then double-checks the top few
with a stronger model. Each piece patches a specific weakness of the others.

## Where this lives in the pipeline

Phase 3 only touches the **Search** stage. Nothing before or after changes.

```
Ingest → Chunk → Embed → Index → [ SEARCH ] → Generate → Cite
                                      ▲
        ┌─────────────────────────────┘
        │  question
        │     ├─ embed → dense search   (by meaning)
        │     └─ BM25 search            (by exact words)
        │              ↓ Reciprocal Rank Fusion   (combine the two)
        │              ↓ cross-encoder rerank      (optional, top few)
        │              ↓ top_k chunks → LLM
```

## The three pieces, in plain words

### 1. BM25 — search by exact words

Dense search (Phase 1) finds chunks that *mean* the same thing, even with no
shared words. Its weakness: **rare exact terms get blurred.** An embedding
squashes a whole passage into one 384-number vector, so sharp details — error
codes, version numbers, names like `Schwarzschild` — get averaged away.

**BM25** is classic keyword search. It matches the *actual words*, and weights
*rare* words more (matching "Voronoi" counts for more than matching "the"). The
technical name is **sparse retrieval** — "sparse" because it only cares about the
handful of words present, unlike the **dense** vector where all 384 numbers are
filled in.

> The whole reason hybrid exists: **dense and BM25 fail differently.** Dense
> misses exact rare words; BM25 misses paraphrases. Run both → cover both holes.

Code: [`bm25.py`](../../docsmind/retrieval/bm25.py)

### 2. Reciprocal Rank Fusion (RRF) — combine the two lists fairly

Now you have two ranked lists, but their scores live on **different scales**:
dense cosine is ~0–1, BM25 is an unbounded sum. You **cannot just add them** —
BM25's big numbers would bully dense's small ones.

RRF's trick: **throw away the scores, use only the rank position.** A chunk at
rank *r* in a list is worth `1 / (k + r)`. Add up each chunk's points across both
lists. A chunk both retrievers rank highly floats to the top.

```
score(chunk) = sum over each list of  1 / (k + rank_in_that_list)
```

`k = 60` (from the original RRF paper) softens the gap between rank 1 and 2 so one
list can't dominate. No per-corpus tuning needed — that's the appeal.

> Everyday version: two judges score on different scales (one out of 10, one out
> of 100). Don't fight over the scales — ask each for their 1st, 2nd, 3rd and
> combine the *ranks*.

Code: [`fusion.py`](../../docsmind/retrieval/fusion.py)

### 3. Cross-encoder reranker — double-check the top few

The embedder is a **bi-encoder**: it encodes the question and each chunk
*separately*, then compares vectors. Fast (chunks pre-computed once), but the
question and chunk never actually look at each other.

A **cross-encoder** reads the (question, chunk) pair **together** through the
model and scores the match directly. Far more accurate — but **slow**, because it
runs fresh per chunk at query time. So you never run it on the whole corpus, only
on the ~20 candidates RRF already shortlisted.

> Everyday version: dense + BM25 + RRF are a fast résumé screen that picks 20
> candidates. The cross-encoder is the careful interview you only give to those 20.

It's **off by default** (`rerank_enabled=False`) — it downloads a model and wants
the beast GPU. One env var turns it on.

Code: [`reranker.py`](../../docsmind/retrieval/reranker.py) ·
Full depth writeup: [reranking-deep-dive.md](reranking-deep-dive.md)

## How it's wired

`HybridRetriever` ([`retriever.py`](../../docsmind/retrieval/retriever.py)) runs
all three behind the same `retrieve(question, top_k)` method the dense
`Retriever` uses — so the pipeline never knows which is plugged in. The
`retrieval_mode` setting picks: `"dense"` (Phase 1) or `"hybrid"` (Phase 3,
default). BM25 is rebuilt in memory from the stored chunks at startup (fine for a
small corpus; at scale you'd persist a real inverted index).

## Did it actually help?

See [eval-results.md](eval-results.md) for real numbers — the honest answer is
"it depends on the corpus," with a concrete win where BM25 recovered an exact
term dense ranked second. For the *concepts* behind those metrics (set vs rank
families, Precision/Recall/MRR/MAP/NDCG, ground-truth labels), see
[search-evaluation.md](search-evaluation.md).

## The interview signals

- **Why hybrid, not just embeddings?** They fail differently — dense misses exact
  rare tokens (error codes, names); BM25 misses paraphrases.
- **How do you merge two different score scales?** You don't — RRF fuses on rank
  position, `1/(k+rank)`, no tuning.
- **Why is reranking a separate stage?** Cost. The cross-encoder reads query+doc
  together (accurate but slow), so you only afford it on the ~20 fused candidates.

→ Code walkthrough: [`retriever.py`](../../docsmind/retrieval/retriever.py)
· [`bm25.py`](../../docsmind/retrieval/bm25.py)
· [`fusion.py`](../../docsmind/retrieval/fusion.py)
· [`reranker.py`](../../docsmind/retrieval/reranker.py)
