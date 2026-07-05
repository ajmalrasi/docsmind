# The Code Seam, the Cost, and How You'd Validate It

**TL;DR:** HyDE is a two-line change in `HybridRetriever.retrieve()` — but it
puts an LLM call on the critical path of *every* query. That's why it belongs
in Phase 5's agent, which can decide *when* to use it, rather than being
always-on.

## Where it will slot into the real code

One seam: `HybridRetriever.retrieve()` in
[`retriever.py`](../../docsmind/retrieval/retriever.py) currently embeds
`question` directly. HyDE inserts one LLM call before that embed:

```python
hypothetical = llm.generate(f"Write a short passage answering: {question}")
query_vec = embedder.embed(hypothetical)   # instead of embed(question)
```

Everything downstream is untouched: FAISS/Qdrant search, BM25, RRF fusion,
reranking. That's the benefit of the pipeline having clean stage boundaries —
a query-side technique only touches the query side.

One design question the code will have to answer: does BM25 also search with
the fake answer, or with the original question? Both are defensible. The fake
answer gives BM25 more domain keywords to match; the original question is
safer when the hypothetical goes off-topic. That's a dial to eval, not to
argue about.

## What it costs

- **Latency:** one LLM round-trip per query, on the critical path, *before*
  any search happens. Streaming can't hide it — nothing can stream until
  retrieval has run.
- **Tokens:** every query now includes a generation call even when plain
  search would have been enough.
- **Risk:** if the LLM's fake answer is off-topic (ambiguous question, or a
  topic the model knows nothing about), you've *steered retrieval wrong* —
  worse than the plain question. HyDE amplifies the LLM's prior, good or bad.

## When it shines, when to skip it

| Situation | HyDE? | Why |
|---|---|---|
| Short vague questions, strong domain vocabulary in corpus | ✅ | The question is missing exactly the vocabulary the fake answer supplies |
| Zero-shot setup, no labeled data to fine-tune retrievers | ✅ | HyDE needs no training — just an LLM call |
| Keyword-ish questions that share vocabulary with docs | ❌ | BM25 in hybrid already covers exact-term matching |
| Strict latency budget | ❌ | An LLM call before search starts is the one cost you can't hide |

## How you'd validate it

The same harness as Phase 3 — add a `hyde` config to
[`scripts/retrieval_eval.py`](../../scripts/retrieval_eval.py), run the same
15 labeled queries, compare Hit@1/MRR against dense and hybrid. No new
machinery needed; that's the payoff of having built the eval first.

In an interview, the real question is not "do you know HyDE?" — it's "how
would you know it helped?" The answer: the eval set existed before the
technique, so the technique gets measured the day it lands.

→ Next: **[query-transformations.md](query-transformations.md)**
