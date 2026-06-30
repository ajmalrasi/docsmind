# Search Evaluation — the complete picture

**Scope:** this doc is about evaluating the **Search** box *only* — did the right
chunks come back, and were they ranked well? It stops before the LLM. Nothing
here is about the answer's wording, correctness, or hallucination (that's
answer/LLM evaluation, a different box — Phase 6).

```
Query → Embed → [ SEARCH ] → Rerank → Generate → Cite
                    ▲
        everything below grades ONLY this box
```

The real numbers these metrics produce on DocsMind live in
[eval-results.md](eval-results.md); this doc is the *concepts* behind them.

## Step 0 — you need labels (ground truth)

You can't grade search without knowing what "right" is. Every eval query needs a
**relevance label**: which chunks (or docs) *should* come back. Two choices:

- **Binary relevance** — a chunk is relevant (1) or not (0). Simple. What
  DocsMind uses.
- **Graded relevance** — degrees of relevance (perfect=3, related=1, off=0).
  Richer, more work to label. Only **NDCG** uses grades naturally.

And the granularity:

- **Document-level** — "the answer is in `black_holes.md`." Cheap, reliable.
  DocsMind uses this (source-level relevance).
- **Passage-level** — "the answer is in *this exact chunk*." Stricter, more effort.

> **Interview signal:** stating *which* labeling scheme you chose and *why*
> ("document-level binary, because it's cheap and reliable; passage-level would
> be stricter") shows you understand that label quality caps every metric below.
> A bad gold set makes every number meaningless.

## The core split: two families of metrics

Every search metric answers one of two questions. Learn these two buckets and you
have all of search evaluation:

```
Family 1 — DID WE FIND IT?       order-blind  (reorder the top-k, score unchanged)
Family 2 — DID WE RANK IT WELL?  order-aware  (reorder the top-k, score changes)
```

---

## Family 1 — Set metrics (order doesn't matter)

These treat the top-k results as a *bag* and ask what's in it.

### Precision@k
Of the k chunks I returned, how many were relevant?
```
Precision@k = (relevant in top k) / k
```
"How much of what I showed was good?" Punishes junk in the results.

### Recall@k
Of all the relevant chunks that exist, how many did I return?
```
Recall@k = (relevant in top k) / (total relevant)
```
"How much of the good stuff did I gather?"

> **The ceiling catch:** if a doc has 14 relevant chunks but k=5, the best
> possible Recall@5 is 5/14 ≈ 0.36. Low recall is often this cap, not failure —
> always read recall against its ceiling.

### F1@k
Precision and recall pull against each other: return more chunks → recall up,
precision down. **F1** is their balance (harmonic mean) — one number when you
care about both.

### Hit@k (Hit Rate)
Did *at least one* relevant chunk make the top k? Yes/no, averaged over queries.
The loosest, most forgiving set metric. DocsMind reports Hit@1 and Hit@3.

---

## Family 2 — Rank-aware metrics (order matters)

These reward putting relevant chunks **high** — what you actually want in RAG,
since you feed the LLM only the top few.

### MRR (Mean Reciprocal Rank)
`1/rank` of the *first* relevant chunk, averaged over queries.
```
first relevant at rank 1 → 1.0 ;  rank 2 → 0.5 ;  rank 3 → 0.33
```
Only cares about the **first** hit. Perfect for "I need one good chunk, fast."

### MAP (Mean Average Precision)
Builds on precision, and cares about **all** the hits:
1. Walk down the list. At each relevant chunk, compute Precision@(that position).
2. Average those → **Average Precision** for one query.
3. Average across queries → **MAP**.

MRR rewards the first hit; MAP rewards finding *many* relevant chunks *and* having
them high.

### NDCG@k (Normalized Discounted Cumulative Gain)
The richest rank metric. Three ideas stacked:
- **Gain** — each result scores its relevance (1/0, or a grade).
- **Discounted** — a relevant chunk is worth less the lower it sits: `1/log2(rank+1)`.
  Sum across the top k → **DCG**.
- **Normalized** — divide by the *ideal* ordering's DCG (**IDCG**) → a 0–1 score
  where 1.0 = perfect ranking. Normalizing makes queries comparable.

The only metric that handles **graded** relevance naturally.

---

## The cheat-sheet — pick by what you care about

| You care about… | Metric | Family |
|---|---|---|
| Did I show mostly good chunks? | Precision@k | set |
| Did I gather all the good chunks? | Recall@k | set |
| Balance of the two? | F1@k | set |
| Did *anything* relevant show up? | Hit@k | set |
| Is the first good chunk near the top? | MRR | rank |
| Are good chunks high *and* did I find many? | MAP | rank |
| Best overall ranking (supports grades)? | NDCG@k | rank |

## The big lesson: metrics encode goals, and they disagree

On DocsMind at `chunk_size=64`, rank metrics and set metrics **disagreed**:
hybrid + rerank won on Hit@1 / MRR (floated the single best chunk to #1) but
*lost* on Recall@5 / NDCG@5 (mixed in other-doc chunks, gathering fewer same-doc
ones). See [eval-results.md](eval-results.md) for the numbers.

There's no single "best" — it depends what the LLM needs downstream:

- **Pointed Q&A** (LLM reads the top 1–3 chunks) → optimize **MRR / NDCG@k**.
- **Summarization / multi-hop** (needs broad coverage) → weight **Recall@k**.

> **Interview signal — "Which retrieval metric do you optimize?"** Weak answer:
> "recall." Strong answer: *"Depends on the task. Pointed Q&A → MRR/NDCG, because
> order is everything when the LLM only reads the top few. Summarization →
> Recall@k for coverage. I report both so I see the tradeoff instead of hiding
> it."*

## What DocsMind's eval computes today

`scripts/retrieval_eval.py` currently prints **Hit@1, Hit@3, MRR, Recall@k,
NDCG@k**. **Precision@k** and **MAP** are explained here but not yet coded — a
natural next addition to complete the set-vs-rank picture.

→ Results & analysis: [eval-results.md](eval-results.md)
· Code: [`scripts/retrieval_eval.py`](../../scripts/retrieval_eval.py)
