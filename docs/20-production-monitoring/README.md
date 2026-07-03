# Monitoring an LLM app in production — cost, latency, quality, drift (concept, Phase 7)

**Where in the pipeline:** wraps the **entire** pipeline as a cross-cutting
concern, the same way logging wraps every function in a normal backend — it's
not one stage, it's instrumentation *on* every stage. DocsMind has exactly one
piece of this already wired up; everything else is `docsmind/ops/`, today a
one-line docstring: *"Ops layer (Phase 7): Dockerfile, k8s manifests,
Langfuse/MLflow wiring."*

```
ingest → chunk → embed → index → [ query → embed → search → rerank →
                                    filter → generate → cite → EVAL ]
           ▲                                    ▲                ▲
      already measured:                   already measured:   not built:
   05-faiss benchmark.py             pipeline.py: latency_ms   RAGAS/drift/
   (recall/latency/memory)           on every QueryResponse    cost dashboards
```

## What's already measured vs what isn't

Every `QueryResponse` returned by `RAGPipeline.query()` in
[`pipeline.py`](../../docsmind/pipeline.py) already carries a `latency_ms`
field, computed with `time.perf_counter()` around the whole retrieve+generate
call. That's real, already-shipped instrumentation — just not yet
*collected* anywhere beyond the single response object. The retrieval eval
(`scripts/retrieval_eval.py`) separately measures Hit@1/MRR, but as an
offline script you run by hand, not a live production dashboard. Turning
"a number exists in one response" and "a script you run manually" into
"a monitored system" is exactly what Phase 7 (`docsmind/ops/`) is a
placeholder for.

## The four things to track, and why each is a different axis

**Cost.** Tokens in + tokens out, per request, priced per model. Not
optional to track per-call — a single runaway prompt (huge retrieved
context, a loop that retries too many times) can spike spend invisibly if
you only look at monthly totals. Track cost *per request* so an outlier is
attributable to a specific query pattern, not buried in an average.

**Latency.** Already partially there via `latency_ms` — but a single average
hides the story. Track **p50/p95/p99**, not just mean: a mean can look fine
while 1% of users wait 10x longer, often because they hit the reranker
(`rerank_enabled=True`) or a cold model load. Break it down by pipeline stage
(retrieval vs generation) the way the FAISS benchmark already breaks down
latency by index type — an aggregate "query took 2s" tells you nothing about
*where* the 2s went.

**Quality.** The hardest of the four, because "quality" isn't observable from
logs alone the way latency and cost are — it needs an eval signal. Phase 6
(RAGAS/DeepEval, faithfulness/groundedness scoring — not yet built) is what
would turn quality from "spot-checking answers by hand" into a tracked
metric over time.

**Drift.** Two different kinds, worth naming separately: **data drift**
(the incoming questions or corpus start looking different from what the
system was built/eval'd on — new topics, different phrasing patterns) and
**model drift** (a provider silently updates a model version behind an API,
or an on-disk model file changes, and behavior shifts with no code change on
your side). Both are invisible unless you're comparing production traffic
patterns and eval scores against a baseline over time, not just at
launch.

## Where this would slot into the real code

- **Cost + latency:** a lightweight event emitted from `RAGPipeline.query()`
  — same call site that already computes `latency_ms` — sent to something
  like Langfuse (traces LLM calls specifically) rather than generic app logs,
  because LLM observability tools understand tokens/cost/prompt-versioning
  natively.
- **Quality:** Phase 6's RAGAS harness, run periodically against a fixed
  golden set (the retrieval eval's `data/eval/retrieval_queries.json` is the
  precedent) *and* sampled live traffic, tracked over time rather than
  once.
- **Drift:** comparing the distribution of live queries/scores against the
  eval baseline on a schedule — this is genuinely unplanned/frontier for
  DocsMind today, closer to an MLOps concern than a RAG one.

## Trade-offs (the interview meat)

- **You cannot monitor quality the way you monitor latency.** Latency and
  cost are directly observable from any request. Quality requires either
  human review (doesn't scale) or an LLM-as-judge eval (RAGAS-style) — which
  is itself a model call with its own cost and its own failure modes (a judge
  model can be wrong too). This asymmetry is *why* Phase 6 is scoped as a
  separate, harder phase rather than bundled into basic ops.
- **Averages actively hide the problems worth knowing about.** A flat p50
  latency chart while p99 climbs is the single most common way a real
  incident goes unnoticed until users complain.
- **Drift detection needs a stable baseline to drift *from*** — which means
  the eval set (Phase 3's retrieval eval, Phase 6's future answer eval) isn't
  just a one-time validation step, it's the reference point ongoing
  monitoring compares against. Skipping eval now means monitoring later has
  nothing to measure drift against.
- **How you'd validate the monitoring itself works:** inject a known
  regression (swap in a deliberately worse model, or a corrupted index) and
  confirm the dashboards actually flag it — monitoring you haven't fire-tested
  is a false sense of safety.

## The interview signals

- **What would you track for an LLM app in production, beyond "is it up"?**
  Cost per request, latency at p95/p99 (not just mean), a recurring quality
  eval against a golden set, and drift in both incoming traffic and
  model/provider behavior — four different signals, not one dashboard number.
- **Why isn't quality monitored the same way as latency?** Latency is
  directly measurable from any request; quality needs a judgment (human or
  LLM-as-judge) against a reference, which is itself imperfect and costs
  money to run continuously.
- **What's the difference between data drift and model drift?** Data drift
  is your *inputs* changing (new question patterns, corpus changes); model
  drift is the *model's behavior* changing under you — often silently, via a
  provider-side update — with no code change on your end to explain it.
