# The Guardrail — INSUFFICIENT_CONTEXT

**TL;DR:** When the retrieved chunks don't contain enough to answer the
question, Claude should reply with the exact string `INSUFFICIENT_CONTEXT`.
The pipeline detects this, sets `grounded=false`, and returns no citations.
This is a soft guardrail — it works if Claude follows instructions.

## The check

```python
# docsmind/pipeline.py

INSUFFICIENT = "INSUFFICIENT_CONTEXT"

grounded = INSUFFICIENT not in answer
citations = self._extract_citations(answer, results) if grounded else []

return QueryResponse(
    answer=answer,
    citations=citations,
    grounded=grounded,
    ...
)
```

Two outcomes:

**Grounded (normal case):**
```json
{
  "answer": "Black holes form when matter collapses past its event horizon [1][2]...",
  "citations": [...],
  "grounded": true
}
```

**Not grounded (context insufficient):**
```json
{
  "answer": "INSUFFICIENT_CONTEXT",
  "citations": [],
  "grounded": false
}
```

## When does this trigger?

**Scenario 1 — Question outside the corpus:**
```
Question: "How do I bake sourdough bread?"
```
The retrieved top-4 chunks are all about black holes, stars, and rockets. None
mention bread. The model sees the context, finds nothing relevant, and returns
`INSUFFICIENT_CONTEXT`.

**Scenario 2 — Low-quality retrieval hit:**
FAISS always returns top-k even if scores are low. If all scores are 0.2–0.3
(barely related), the context won't be useful. Claude should detect this
and return `INSUFFICIENT_CONTEXT`.

**Scenario 3 — Empty index:**
If `make ingest` was never run, FAISS returns zero results. The pipeline
short-circuits before even calling Claude:

```python
if not results:
    return QueryResponse(
        answer=INSUFFICIENT,
        citations=[],
        grounded=False,
        ...
    )
```

## The limits of this guardrail

**It's a soft guardrail.** It relies on Claude following the system prompt.

What can go wrong:
- Claude paraphrases — *"I don't have enough information..."* — instead of
  the exact string `INSUFFICIENT_CONTEXT`. The `not in` check misses it,
  `grounded=true` is set incorrectly.
- Claude answers partly from memory (ignoring "ONLY from context") without
  flagging insufficient context. The pipeline can't detect this.
- Claude uses a citation marker `[1]` but the claim isn't actually supported
  by passage `[1]`. The pipeline extracts the citation as valid — no one checks
  faithfulness.

## How Phase 5 and 6 fix this

**Phase 5 (LangGraph agent):** Adds a structural verification step — a second
model call that explicitly checks whether each claim in the answer is supported
by its cited passage. If not, the agent loops back and re-generates.

**Phase 6 (RAGAS evaluation):** Runs systematic evaluation on a golden question
set, measuring:
- **Faithfulness** — are claims actually supported by the retrieved passages?
- **Answer relevance** — does the answer address the question?
- **Context recall** — did retrieval find the right passages?

This moves from "we hope Claude behaved" to "we measured that Claude behaved
on 200 test questions with a 94% faithfulness score."

## Why the exact string matters

```python
INSUFFICIENT = "INSUFFICIENT_CONTEXT"
grounded = INSUFFICIENT not in answer
```

The check is a substring search. If the constant changes in one place but
not the other, the guardrail silently breaks. That's why the same constant
`INSUFFICIENT` is used in both the system prompt and the check — defined once,
referenced twice. If you change the fallback phrase, you only change it in
one place.

→ Back to: **[README.md](README.md)**
→ Next topic: **[07-full-pipeline/README.md](../07-full-pipeline/README.md)**
