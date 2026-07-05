# 11 — HyDE: Search With a Fake Answer (concept, Phase 5)

**The big idea:** questions and answers are different *shapes* of text, so a
question's vector lands in a slightly wrong neighborhood of the index. HyDE
fixes that by asking an LLM to write a fake answer first, embedding **that**,
and searching with it. The fake answer is thrown away; the retrieved chunks
are real. Not built in DocsMind yet — it's a Phase 5 (agent) technique. This
section maps the concept before the code lands.

**Where in the pipeline:** the **query side** of Search — between receiving
the question and embedding it. Everything downstream (index, fusion, rerank)
is untouched.

```
today:  question ────────────────────────────→ embed → search
 HyDE:  question → LLM writes a fake answer ──→ embed → search
```

## Files in this folder

| File | What it covers |
|------|----------------|
| [problem-and-fix.md](problem-and-fix.md) | Why question-shaped vectors miss answer-shaped chunks, and how a fake answer fixes it |
| [code-seam-and-tradeoffs.md](code-seam-and-tradeoffs.md) | The one-line insertion point in `retriever.py`, what it costs, how you'd validate it |
| [query-transformations.md](query-transformations.md) | HyDE's siblings — Multi-Query and Decomposition — same seam, different rewrites |

## 🎯 Interview Q&A

**Q: What is HyDE, in one line?**
Embed a hypothetical answer instead of the question, because answers live
near answers in embedding space.

**Q: Why does a *wrong* fake answer still work?**
Retrieval only needs the vector to land in the right neighborhood.
Vocabulary and shape put it there; factual precision doesn't matter, because
the fake text is discarded before generation. The chunks it retrieves are real.

**Q: When does it backfire?**
When the LLM's hypothetical is off-topic — an ambiguous question, or a domain
the model knows nothing about. Then you've *steered retrieval wrong*, which is
worse than the plain question. Plus you paid an LLM call of latency for it.

**Q: How would you decide whether to turn it on?**
A/B it on a labeled eval set — never by vibes. DocsMind already has the
harness: add a `hyde` config to `scripts/retrieval_eval.py`, run the same 15
labeled queries, compare Hit@1/MRR against dense and hybrid.

## Code

[docsmind/retrieval/retriever.py](../../docsmind/retrieval/retriever.py) —
`HybridRetriever.retrieve()`, the seam where the question is embedded today.

→ Next: **[12-tool-calling/README.md](../12-tool-calling/README.md)**
