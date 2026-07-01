# Hybrid Retrieval & Reranking — Interview Questions

Phase 3 depth questions. The theme: every answer should end in a number you
measured, because "how did you know it worked?" is always the follow-up.

---

## Q: Why hybrid retrieval? Isn't dense search enough?

Dense and BM25 **fail differently**. Dense finds paraphrases but blurs rare
exact terms (error codes, names — a 384-number vector averages them away).
BM25 nails exact terms but is blind to paraphrase. Running both covers both
holes.

The measured proof from DocsMind: on the query *"What is left behind after a
supernova?"*, dense ranked the right chunk **#2**; BM25 caught the exact word
"supernova" and fusion lifted it to **#1**. Hit@1 went 0.93 → 1.00.

---

## Q: Two retrievers give two ranked lists with incompatible scores. How do you combine them?

You don't reconcile the scores — you throw them away. **Reciprocal Rank
Fusion**: each chunk earns `1/(k + rank)` per list, summed. Only rank position
matters, so BM25's unbounded scores can't bully cosine's 0–1 scores.

Why not min-max normalize and add? You'd be tuning weights per corpus forever.
RRF's whole appeal is that it needs no tuning — `k=60` from the original paper
works everywhere because it just softens the rank-1-vs-rank-2 gap.

Code: [`fusion.py`](../../docsmind/retrieval/fusion.py) — it's ~20 lines.

---

## Q: Bi-encoder vs cross-encoder — and why do you need both?

- **Bi-encoder** (bge-small): encodes question and chunk *separately*, compares
  vectors. Fast, because chunk vectors are precomputed once at ingest.
- **Cross-encoder** (ms-marco-MiniLM): reads the (question, chunk) *pair
  together* and scores the match. Far more accurate — the question and chunk
  actually attend to each other — but runs fresh per pair at query time.

So the architecture is a funnel: bi-encoder + BM25 shortlist ~20 candidates
cheaply, cross-encoder re-scores only those 20. You could never cross-encode
the whole corpus; you'd never want to ship the shortlist unchecked.

---

## Q: What did reranking actually buy you?

The most reliable win in the whole eval. At default chunking, dense and hybrid
tied at 0.93 Hit@1; the reranker fixed the one miss → **1.00 Hit@1, 1.00 MRR**.
And it kept that perfect score at fine chunking too.

The honest caveat that makes the answer senior: hybrid's gain depended on
chunk size and corpus (at 512-token chunks, hybrid == dense — BM25 had nothing
to recover). The reranker helped **regardless of configuration**. If I could
keep only one Phase 3 piece, it's the reranker.

---

## Q: Your metrics disagreed. Explain.

At fine chunking (72 chunks), hybrid+rerank *raised* Hit@1/MRR (0.93 → 1.00)
but *lowered* Recall@5 and NDCG@5 (0.857 → 0.764). Both are correct:

- Hit@1/MRR ask "is the single best chunk on top?" — hybrid optimizes this.
- Recall/NDCG ask "did we gather all relevant context?" — dense wins this,
  because same-doc chunks are semantically similar and cluster together in
  its top-k, while BM25/reranker inject keyword-matching chunks from other docs.

Which to optimize depends on the task: pointed Q&A wants Hit@1;
summarization or multi-hop wants recall. Knowing *which metric your product
needs* is the actual skill being tested.

---

## Q: How was the eval built?

15 labeled queries over the corpus, each tagged with the source doc that
answers it — a deliberate mix of exact-term queries (should favor BM25) and
paraphrase queries (should favor dense). Metrics: Hit@1, Hit@3, MRR, Recall@5,
NDCG@5, computed identically for dense / hybrid / hybrid+rerank so the
comparison is apples-to-apples. One command re-runs it (`make eval`).

Small, but it's a real harness: labeled ground truth, fixed query set,
comparable configs. Scaling it up is more labels, not a new design.

---

## Q: When would hybrid NOT help?

- Small clean corpus at coarse chunking — dense already nails it (measured:
  identical 0.93 at 512-token chunks).
- Pure paraphrase workloads with no rare exact terms — BM25 adds noise.
- And BM25 costs infrastructure at scale: DocsMind rebuilds it in memory from
  stored chunks at startup, fine for a small corpus; a big one needs a real
  inverted index (or a backend like Qdrant/OpenSearch that maintains one).

Saying when your own technique *doesn't* pay is the strongest credibility
signal available in this topic.

---

## Q: A user reports a bad answer. How do you debug retrieval?

Walk the funnel backwards, stage by stage:

1. **Was the right chunk retrieved at all?** Look at the top-k. If absent →
   chunking or embedding problem (chunk too big? term blurred? try the query
   in BM25 alone vs dense alone to see which side missed).
2. **Retrieved but ranked too low?** → fusion/rerank problem; check where each
   retriever ranked it before RRF.
3. **Retrieved and ranked #1 but the answer is still wrong?** → generation
   problem, not retrieval; that's the Phase 6 (faithfulness) territory.

The point of the funnel design is exactly this: each stage can be inspected
and blamed independently.
