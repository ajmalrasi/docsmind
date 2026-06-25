# Similarity Scores — How to Read Them

**TL;DR:** Cosine similarity returns a number between -1.0 and 1.0.
For normalized text embeddings you'll typically see 0.0 to 1.0 in practice.

## Score ranges

| Score | Meaning | Example |
|-------|---------|---------|
| 0.95 – 1.0 | Nearly identical | Same sentence paraphrased |
| 0.80 – 0.95 | Highly similar | Same topic, direct hit |
| 0.60 – 0.80 | Related | Same domain, connected aspect |
| 0.40 – 0.60 | Loosely related | Same broad area, different topic |
| 0.0 – 0.40 | Different | Unrelated topics |

These ranges are rough guides — they shift based on the model and corpus.
bge-small on this corpus puts direct hits above ~0.80 and clearly-related docs
in the 0.60s.

## What Phase 1 actually returns

```python
# docsmind/schemas.py
class SearchResult(BaseModel):
    chunk: Chunk
    score: float   # cosine similarity, 0.0 to 1.0
```

**Real output** from the query *"How do black holes form?"* against the space
corpus (these are the actual measured scores):

```
Results:
  score=0.8141  source=black_holes.md       ← direct hit (retrieved)
  score=0.6333  source=stellar_lifecycle.md ← genuinely related (retrieved)
  score=0.5691  source=solar_system.md      ← same domain, off-topic (retrieved)
  score=0.5240  source=rocket_propulsion.md ← same domain, off-topic (retrieved)
  score=0.5140  source=the_iss.md           ← 5th place, not in top-4
```

`black_holes.md` is the clear winner at 0.81. `stellar_lifecycle.md` at 0.63 is
*correctly* second — massive stars collapse into black holes, so it's truly
related. The rest are space-domain but off-topic, clustered lower.

## We rank, we don't threshold

Phase 1 returns the **top-k by score** (k=4 here), not everything above a
threshold. Notice that `solar_system.md` (0.57) and `rocket_propulsion.md`
(0.52) get retrieved even though they don't really answer the question — they're
just the next-highest scores. That's why the `INSUFFICIENT_CONTEXT` guardrail
(in the LLM prompt) matters: the model is told to ignore passages that don't
actually help, and to flag when none of them do.

→ Next: **[search-example.md](search-example.md)**
