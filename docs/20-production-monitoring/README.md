# Monitoring an LLM app in production — cost, latency, quality, drift (concept, Phase 7)

**Where in the pipeline:** it wraps the **entire** pipeline, as a cross-cutting concern.
Think of how logging wraps every function in a normal backend — monitoring is instrumentation *on* every stage, not a stage itself.
DocsMind has exactly one piece already wired up.
Everything else is `docsmind/ops/`, today a one-line docstring: *"Ops layer (Phase 7): Dockerfile, k8s manifests, Langfuse/MLflow wiring."*

```
ingest → chunk → embed → index → [ query → embed → search → rerank →
                                    filter → generate → cite → EVAL ]
           ▲                                    ▲                ▲
      already measured:                   already measured:   not built:
   05-faiss benchmark.py             pipeline.py: latency_ms   RAGAS/drift/
   (recall/latency/memory)           on every QueryResponse    cost dashboards
```

## What's already measured vs what isn't

Every `QueryResponse` from `RAGPipeline.query()` in [`pipeline.py`](../../docsmind/pipeline.py) already carries a `latency_ms` field.
It's computed with `time.perf_counter()` around the whole retrieve+generate call.
That's real, shipped instrumentation — but the number lives in one response object and goes nowhere.

The retrieval eval (`scripts/retrieval_eval.py`) measures Hit@1/MRR.
But it's an offline script you run by hand, not a live dashboard.

Turning "a number exists in one response" and "a script you run manually" into "a monitored system" — that's what Phase 7 (`docsmind/ops/`) is the placeholder for.

## The four things to track, and why each is a different axis

**Cost.**
Tokens in + tokens out, per request, priced per model.
Track it *per request*, not just monthly totals.
Why: a single runaway pattern — a huge retrieved context, a loop retrying too many times — can spike spend invisibly inside an average.
Per-request cost makes the outlier attributable to a specific query pattern.

**Latency.**
Partially there via `latency_ms`. But an average hides the story.
Track **p50/p95/p99**, not the mean.
A mean can look fine while 1% of users wait 10x longer — often because they hit the reranker (`rerank_enabled=True`) or a cold model load.
And break latency down by stage — retrieval vs generation — the same way the FAISS benchmark breaks it down by index type.
"The query took 2s" tells you nothing about *where* the 2s went.

**Quality.**
The hardest of the four.
Latency and cost are visible in any request's logs. Quality isn't — it needs an eval signal.
Phase 6 (RAGAS/DeepEval, faithfulness/groundedness scoring — not yet built) is what turns quality from "spot-checking answers by hand" into a metric tracked over time.

**Drift.**
Two kinds, worth naming separately.
**Data drift:** your *inputs* change — new question topics, different phrasing, a corpus that grew.
**Model drift:** the *model's behavior* changes under you — a provider silently updates the model behind the API, or an on-disk model file changes. No code change on your side, different answers anyway.
Both are invisible unless you compare production traffic and eval scores against a baseline over time. Not just at launch.

## Where this would slot into the real code

- **Cost + latency:** a lightweight event emitted from `RAGPipeline.query()` — the same call site that already computes `latency_ms`.
  Send it to an LLM-observability tool like Langfuse rather than generic app logs, because those tools understand tokens, cost, and prompt versions natively.
- **Quality:** Phase 6's RAGAS harness, run on a schedule against a fixed golden set (`data/eval/retrieval_queries.json` is the precedent) *plus* sampled live traffic. Tracked over time, not once.
- **Drift:** comparing the distribution of live queries and scores against the eval baseline on a schedule.
  For DocsMind today this is genuinely unplanned/frontier — closer to an MLOps concern than a RAG one.

## Trade-offs (the interview meat)

- **You cannot monitor quality the way you monitor latency.**
  Latency and cost are directly observable from any request.
  Quality needs a judgment: human review (doesn't scale) or an LLM-as-judge eval (RAGAS-style).
  And a judge is itself a model call — with its own cost, and its own ways of being wrong.
  This asymmetry is why Phase 6 is scoped as a separate, harder phase instead of being bundled into basic ops.
- **Averages actively hide the problems worth knowing about.**
  A flat p50 chart while p99 climbs is the single most common way a real incident goes unnoticed until users complain.
- **Drift detection needs a stable baseline to drift *from*.**
  That means the eval set isn't a one-time validation step.
  It's the reference point ongoing monitoring compares against.
  Skip eval now, and monitoring later has nothing to measure drift against.
- **How you'd validate the monitoring itself works.**
  Inject a known regression — swap in a deliberately worse model, or a corrupted index — and confirm the dashboards flag it.
  Monitoring you haven't fire-tested is a false sense of safety.

## The interview signals

- **What would you track for an LLM app in production, beyond "is it up"?**
  Cost per request. Latency at p95/p99, not just the mean. A recurring quality eval against a golden set. And drift — in both incoming traffic and model/provider behavior.
  Four different signals, not one dashboard number.
- **Why isn't quality monitored the same way as latency?**
  Latency is directly measurable from any request.
  Quality needs a judgment against a reference — human or LLM-as-judge — which is itself imperfect and costs money to run continuously.
- **What's the difference between data drift and model drift?**
  Data drift: your *inputs* changed (new question patterns, corpus changes).
  Model drift: the *model's behavior* changed under you — often silently, via a provider-side update — with no code change on your end to explain it.
