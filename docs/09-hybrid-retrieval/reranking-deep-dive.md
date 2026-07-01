# Reranking — the deep dive

**Where in the pipeline:** the very last step of the **Search** stage, after
RRF fusion and right before the top chunks go to the LLM. Everything upstream
(dense, BM25, fusion) exists to hand the reranker a good shortlist.

```
question → dense ─┐
                  ├→ RRF → ~20 candidates → [ RERANK ] → top_k → LLM
question → BM25 ──┘                              ▲
                                          this page
```

**Where in the code:** `CrossEncoderReranker` in
[`reranker.py`](../../docsmind/retrieval/reranker.py), called from
`HybridRetriever.retrieve()` in
[`retriever.py`](../../docsmind/retrieval/retriever.py) when
`rerank_enabled=True`. Model: `ms-marco-MiniLM-L-6-v2`, lazy-loaded on first
use so the pipeline starts fast when reranking is off.

## The problem it solves

At search time we currently rank chunks by comparing **precomputed vectors** —
the question and each chunk were embedded *separately* and never saw each
other. That's a **bi-encoder**, and the separation is exactly what makes it
fast: chunk vectors are computed once at ingest, and a query is just one embed
plus a lookup.

But separation costs accuracy. The embedder compressed each chunk into 384
numbers *before knowing what would be asked*. Nuance the question cares about
may simply not have survived the compression.

## The fix: let them read each other

A **cross-encoder** takes the (question, chunk) pair as **one input** and runs
it through the model together. Every word of the question can attend to every
word of the chunk. The output isn't a vector — it's a single relevance score
for *this pair*.

Plain version: the bi-encoder judges two people by comparing their dating
profiles. The cross-encoder puts them in a room and watches the conversation.

The catch is cost. Nothing can be precomputed — every (question, chunk) pair
is a fresh model forward pass at query time. That's why it can never replace
retrieval: scoring a million chunks per query is a million forward passes.
Scoring 20 shortlisted candidates is nothing.

So the shape is a funnel, and each stage earns its place by cost:

| Stage | Cost per query | Job |
|---|---|---|
| dense + BM25 | ~1 embed + lookups | scan *everything*, cheaply |
| RRF | arithmetic | merge two lists fairly |
| cross-encoder | ~20 forward passes | be *accurate* on the survivors |

## Did it work? (the measured answer)

From [eval-results.md](eval-results.md), on the 15-query labeled set:

- Default chunking: dense and hybrid tied at **0.93 Hit@1**; adding the
  reranker → **1.00 Hit@1, 1.00 MRR**. It fixed the one query everything else
  ranked #2.
- Fine chunking (72 chunks): kept the perfect Hit@1/MRR.
- The trade it made: Recall@5/NDCG@5 dipped, because pair-relevance sometimes
  promotes a keyword-matching chunk from another doc over a same-doc neighbor.

The honest summary: **the reranker was the most reliable win in Phase 3** —
hybrid's gain came and went with chunk size, the reranker helped in every
configuration tested.

## What breaks, and how you debug it

- **Latency spike when enabled.** Expected: it's per-pair model inference.
  First lever is `candidate_k` (how many survivors get reranked) — 20 → 10
  halves the work. Then batch the pairs, then a smaller cross-encoder.
- **First query after startup is slow.** Lazy model load. Warm it at boot if
  that matters.
- **A good chunk got demoted.** Check the cross-encoder's raw score for that
  (question, chunk) pair in isolation. MiniLM was trained on MS MARCO (web
  Q&A); domain mismatch shows up here — the fix at real scale is fine-tuning
  the reranker on your own domain pairs, not swapping retrievers.
- **It can only reorder what it's given.** If the right chunk isn't in the
  ~20 candidates, no reranker can save you — that's a retrieval (or chunking)
  bug upstream. Debug the funnel in order.

## The interview signals

- **Why a separate rerank stage instead of a better embedder?** Different cost
  classes. The bi-encoder's speed *comes from* never seeing the question;
  accuracy beyond that ceiling requires reading the pair together, which is
  only affordable on a shortlist.
- **Why is it off by default in your project?** It downloads a model and wants
  GPU; BM25 fusion is free. Defaults should be the cheapest thing that works,
  with one config flag to turn on the expensive thing.
- **How did you know it helped?** Same eval, same queries, one variable
  changed: Hit@1 0.93 → 1.00. That A/B discipline is the answer, not the
  number itself.
