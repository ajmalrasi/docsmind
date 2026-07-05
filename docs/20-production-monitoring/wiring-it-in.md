# Wiring It In — What Exists, the Seams, and Fire-Testing

**TL;DR:** DocsMind has real-but-stranded instrumentation: a `latency_ms`
that goes nowhere and an eval script run by hand. The seams for Phase 7 are
already visible — and the last step is testing the monitoring itself.

## What's already measured vs what isn't

Every `QueryResponse` from `RAGPipeline.query()` in
[`pipeline.py`](../../docsmind/pipeline.py) already carries a `latency_ms`
field. It's computed with `time.perf_counter()` around the whole
retrieve+generate call. That's real, shipped instrumentation — but the
number lives in one response object and goes nowhere.

The retrieval eval
([`scripts/retrieval_eval.py`](../../scripts/retrieval_eval.py)) measures
Hit@1/MRR. But it's an offline script you run by hand, not a live
dashboard.

| Piece | Status | Gap |
|---|---|---|
| Stage benchmark (FAISS) | ✅ `scripts/benchmark.py`, real numbers | offline, one stage |
| Per-request latency | ✅ `latency_ms` on every response | emitted nowhere |
| Retrieval quality | ✅ 15-query labeled eval | manual, not scheduled |
| Cost per request | ❌ | token counts not captured |
| Answer quality (faithfulness) | ❌ Phase 6 | needs RAGAS/DeepEval |
| Drift detection | ❌ | needs baseline + schedule |

## The seams

- **Cost + latency:** a lightweight event emitted from
  `RAGPipeline.query()` — the same call site that already computes
  `latency_ms`. Send it to an LLM-observability tool like Langfuse rather
  than generic app logs, because those tools understand tokens, cost, and
  prompt versions natively.
- **Quality:** Phase 6's RAGAS harness, run on a schedule against a fixed
  golden set ([`data/eval/retrieval_queries.json`](../../data/eval/retrieval_queries.json)
  is the precedent) *plus* sampled live traffic. Tracked over time, not
  once.
- **Drift:** comparing the distribution of live queries and scores against
  the eval baseline on a schedule. For DocsMind today this is genuinely
  unplanned/frontier — closer to an MLOps concern than a RAG one.

```
RAGPipeline.query()
   ├─ answer → user                       (unchanged)
   └─ event {latency_ms, tokens_in/out, model, retrieval_mode}
          → Langfuse                      (Phase 7 wiring)

nightly:  golden set → pipeline → RAGAS scores → history
                                         └─ compare vs baseline = drift signal
```

## Averages hide the incidents

A flat p50 chart while p99 climbs is the single most common way a real
incident goes unnoticed until users complain. The percentile discipline
from [four-signals.md](four-signals.md) is not optional polish — it's the
difference between the dashboard catching the reranker regression and a
user tweet catching it.

## Fire-test the monitoring itself

Inject a known regression — swap in a deliberately worse model, or a
corrupted index — and confirm the dashboards flag it.

Monitoring you haven't fire-tested is a false sense of safety. This is the
same logic as testing backups by restoring them: the artifact isn't the
dashboard, it's the *demonstrated detection*. DocsMind's version would be:
re-run the golden set with `chunk_size=64` mangled or a weaker model
configured, and verify the quality score visibly drops. If it doesn't,
the monitoring — not the pipeline — is what's broken.

→ Next: **[21-multimodal-document-rag/README.md](../21-multimodal-document-rag/README.md)**
