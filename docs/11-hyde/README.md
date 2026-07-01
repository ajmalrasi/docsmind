# HyDE — search with a fake answer (concept, Phase 5)

**Where in the pipeline:** the **query side** of Search — between receiving
the question and embedding it. Everything downstream (index, fusion, rerank)
is untouched. Not built in DocsMind yet; it's a Phase 5 (agent) technique.
This page exists so the concept is mapped before the code lands.

```
                 today:  question ────────────→ embed → search
                  HyDE:  question → LLM writes a
                         hypothetical answer ──→ embed → search
```

## The problem it solves

At query time we currently embed the **question** and hunt for nearby chunks.
But questions and answers are *different kinds of text*. "Why do astronauts
float?" is short, interrogative, and contains none of the vocabulary of the
passage that answers it (microgravity, free fall, orbital velocity). The
question's vector sits in a slightly wrong neighborhood — we're searching for
a thing shaped like a question in an index full of things shaped like answers.

## The fix

**HyDE — Hypothetical Document Embeddings.** Ask an LLM to *write a fake
answer first*, embed **that**, and search with it.

The fake answer may be factually wrong — doesn't matter. It's the right *kind*
of text: declarative, answer-shaped, full of the domain vocabulary that real
answer chunks also use. Its vector lands in the answer neighborhood, and
nearest-neighbor search does the rest. The retrieved chunks are real; the fake
answer is thrown away before generation.

Plain version: instead of describing a suspect to the sketch artist, you draw
the sketch yourself — badly — and match it against the photo database. A bad
sketch of the right face beats a perfect description in the wrong medium.

## Where it will slot into the real code

One seam: `HybridRetriever.retrieve()` in
[`retriever.py`](../../docsmind/retrieval/retriever.py) currently embeds
`question` directly. HyDE inserts one LLM call before that embed:

```python
hypothetical = llm.generate(f"Write a short passage answering: {question}")
query_vec = embedder.embed(hypothetical)   # instead of embed(question)
```

Note what this costs: **an extra LLM call before retrieval even starts** —
added latency and tokens on every query. That's why it belongs in Phase 5's
agent, which can *decide* when to use it, rather than being always-on.

## Trade-offs (the interview meat)

- **Cost:** one LLM round-trip per query, on the critical path, before any
  search happens. Streaming can't hide it.
- **Risk:** if the LLM's fake answer is off-topic (ambiguous question, or a
  topic the model knows nothing about), you've *steered retrieval wrong* —
  worse than the plain question. HyDE amplifies the LLM's prior, good or bad.
- **When it shines:** short vague questions over a corpus with strong domain
  vocabulary; zero-shot setups with no labeled data to fine-tune retrievers.
- **When to skip it:** queries that already share vocabulary with the docs
  (keyword-ish questions — BM25 covers those in hybrid), or strict latency
  budgets.
- **How you'd validate it:** the same harness as Phase 3 — add a `hyde`
  config to `scripts/retrieval_eval.py`, run the same 15 labeled queries,
  compare Hit@1/MRR against dense and hybrid. No new machinery needed; that's
  the payoff of having built the eval first.

## Same family, different tricks (Phase 5 preview)

HyDE is one of several **query transformations** — all living at the same
"rewrite the query before search" stage:

- **Multi-Query:** rephrase the question N ways, search all, fuse with RRF
  (the same fusion already built in Phase 3).
- **Decomposition:** split a multi-hop question into sub-questions, retrieve
  per sub-question.
- **HyDE:** transform the question into answer-shaped text (this page).

Same seam, same eval, different rewrite. When Phase 5 lands, each gets the
full treatment.

## The interview signals

- **What is HyDE, in one line?** Embed a hypothetical answer instead of the
  question, because answers live near answers in embedding space.
- **Why does a *wrong* fake answer still work?** Retrieval only needs the
  vector to land in the right neighborhood — vocabulary and shape put it
  there; factual precision doesn't matter because the fake text is discarded.
- **When does it backfire?** Off-topic hypothetical → confidently wrong
  retrieval, plus an LLM call of latency on every query. You A/B it on a
  labeled eval set before turning it on — never by vibes.
