# Retrieval Eval — does hybrid + rerank actually beat dense?

**Where in the pipeline:** this measures the **Search** stage directly. It runs
dense, hybrid, and hybrid+rerank over the *same* corpus and the *same* labeled
queries, and reports the same metrics for each. This is the evidence for the
hardest Phase 3 interview question: *"how did you know your retrieval improved?"*

Script: [`scripts/retrieval_eval.py`](../../scripts/retrieval_eval.py) ·
Query set: [`data/eval/retrieval_queries.json`](../../data/eval/retrieval_queries.json)

## The setup

15 labeled queries over the 5-doc space corpus. Each query is tagged with the
doc that should answer it (**source-level relevance** — did we retrieve a chunk
from the right doc?). The queries are a deliberate mix:

- **exact-term** queries ("What is the Schwarzschild radius?") — should favor BM25
- **paraphrase** queries ("Why do astronauts appear weightless?") — should favor dense

### The metrics (plain words)

> For the full framework behind these — the set-vs-rank split, Precision@k, MAP,
> and how ground-truth labels work — see [search-evaluation.md](search-evaluation.md).
> This section is just enough to read the tables below.

The first three care about the **single best** chunk. The last two care about
**all** chunks from the correct doc (the "relevant set").

| Metric | What it asks | Cares about |
|--------|--------------|-------------|
| **Hit@1** | Is the #1 result from the correct doc? | the top spot |
| **Hit@3** | Is the correct doc anywhere in the top 3? | being present |
| **MRR** | `1/rank` of the *first* correct chunk, averaged. Rewards putting the right answer *higher*. | the first hit's rank |
| **Recall@k** | Of *all* the correct doc's chunks, what share landed in the top k? | gathering everything |
| **NDCG@k** | Like MRR but for many relevant items: rewards relevant chunks, discounted the lower they sit. | ranking the whole set well |

**One catch on Recall@k:** if a doc produced 14 chunks but you only retrieve 5,
the best possible Recall@5 is 5/14 ≈ 0.36 — you *can't* fit them all in 5 slots.
So low recall numbers below aren't failure; read them against that ceiling.

## Results

### Default chunking (chunk_size=512 → 5 chunks, one per doc)

```
config             Hit@1   Hit@3     MRR     R@5   NDCG@5
---------------------------------------------------------
dense               0.93    1.00   0.967    1.00    0.975
hybrid              0.93    1.00   0.967    1.00    0.975
hybrid+rerank       1.00    1.00   1.000    1.00    1.000
```

With one chunk per doc, each relevant set is a single chunk, so Recall@5 is
trivially 1.00. Dense already nearly maxes out and BM25 has nothing to *recover* —
so **hybrid == dense**. The cross-encoder reranker still earns its place: it fixed
the one query the others ranked #2, lifting Hit@1 to a perfect 1.00.

### Finer chunking (chunk_size=64 → 72 chunks, ~14 per doc)

```
config             Hit@1   Hit@3     MRR     R@5   NDCG@5
---------------------------------------------------------
dense               0.93    1.00   0.967    0.31    0.857
hybrid              1.00    1.00   1.000    0.28    0.785
hybrid+rerank       1.00    1.00   1.000    0.27    0.764
```

Now the metrics **disagree** — and that is the most valuable result here.

- **Top-spot metrics say hybrid/rerank win.** Hit@1 climbs 0.93 → 1.00, MRR
  0.967 → 1.000. The concrete reason: the query **"What is left behind after a
  supernova?"** — dense ranked the correct `stellar_lifecycle.md` chunk at **#2**;
  BM25 caught the rare exact term *"supernova"* and RRF lifted it to **#1**.

- **Coverage metrics say dense wins.** Recall@5 drops 0.31 → 0.27 and NDCG@5 drops
  0.857 → 0.764. Why? Dense pulls chunks from the *same* doc together (they're
  semantically similar), so the top 5 is dominated by the correct doc. BM25 and the
  reranker deliberately inject chunks from *other* docs that match on keywords or
  pair-relevance — better single answer, but fewer same-doc chunks gathered.

(Recall@5 looks low because each doc has ~14 chunks but only 5 fit in the top 5 —
the ceiling is ~0.36, so dense's 0.31 is near-optimal coverage.)

## The honest takeaways (this is the senior answer)

1. **The metrics measure different goals, and they can disagree.** Hit@1/MRR ask
   *"is the single best chunk on top?"* Recall/NDCG ask *"did we gather all the
   relevant context?"* Hybrid + rerank optimize the first and slightly hurt the
   second. Which you want depends on the task: a pointed Q&A wants Hit@1; a
   summarization or multi-hop task wants recall.

2. **On a tiny, clean corpus, hybrid ≈ dense.** There's nothing for BM25 to
   recover when dense already nails it. The gain shows up once there are enough
   competing chunks (and, at real scale, on jargon dense struggles with).

3. **Granularity matters.** The *same* methods looked different at 5 vs 72 chunks.
   Retrieval quality is a property of the *whole* pipeline (chunking included),
   not one component.

> The interview answer this unlocks: not *"hybrid is better,"* but *"hybrid and
> the reranker improved Hit@1 and MRR by floating the single best chunk to the top
> — BM25 recovered an exact-term query dense ranked second — but they slightly
> lowered Recall@5 and NDCG@5 because they mix in other-doc chunks. Which tradeoff
> I want depends on whether the task needs the one best chunk or broad coverage."*

## Run it yourself

```bash
make eval                              # dense vs hybrid (fast, embedder only)
make eval ARGS=--rerank                # add the cross-encoder
make beast-eval                        # full run with rerank on the GPU
python -m scripts.retrieval_eval --rerank --chunk-size 64   # the finer-grained run
```

## What's still missing

This measures *retrieval* (did we fetch the right chunks?). It does **not** yet
measure *answer* quality (faithfulness, hallucination) — that's Phase 6 (RAGAS /
DeepEval), which grades the LLM's output, not the retriever's.
