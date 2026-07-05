# The Four Signals — Why Each Is a Different Axis

**TL;DR:** cost and latency are visible in any request's logs. Quality
needs an eval signal. Drift needs a baseline to compare against over time.
Treating the four as one "dashboard" is how real incidents go unnoticed.

## Cost

Tokens in + tokens out, per request, priced per model.
Track it *per request*, not just monthly totals.

Why: a single runaway pattern — a huge retrieved context, a loop retrying
too many times — can spike spend invisibly inside an average. Per-request
cost makes the outlier attributable to a specific query pattern.

Tool calling (Phase 5) raises the stakes: an agent loop multiplies LLM
calls per question, so cost-per-*question* and cost-per-*call* diverge.
Both need tracking, or a runaway loop looks like ordinary traffic growth.

## Latency

Partially there via `latency_ms`. But an average hides the story.
Track **p50/p95/p99**, not the mean.

A mean can look fine while 1% of users wait 10x longer — often because
they hit the reranker (`rerank_enabled=True`) or a cold model load.

```
p50 ████ 800ms          ← the mean lives here and looks healthy
p95 ████████ 1.9s
p99 ████████████████ 8s ← the reranker + cold-start story, invisible in the mean
```

And break latency down by stage — retrieval vs generation — the same way
the FAISS benchmark breaks it down by index type. "The query took 2s"
tells you nothing about *where* the 2s went. In DocsMind's case the split
is stark: retrieval is sub-millisecond
([05-faiss/benchmark-results.md](../05-faiss/benchmark-results.md)); the
LLM call is ~seconds. Optimizing the wrong side is a week wasted.

## Quality

The hardest of the four. Latency and cost are visible in any request's
logs. Quality isn't — it needs an eval signal.

Phase 6 (RAGAS/DeepEval, faithfulness/groundedness scoring — not yet
built) is what turns quality from "spot-checking answers by hand" into a
metric tracked over time.

The structural problem: a quality judgment needs a *reference* — either a
human review (doesn't scale) or an LLM-as-judge (RAGAS-style). And a judge
is itself a model call — with its own cost, and its own ways of being
wrong. This asymmetry is why Phase 6 is scoped as a separate, harder phase
instead of being bundled into basic ops.

## Drift

Two kinds, worth naming separately.

**Data drift:** your *inputs* change — new question topics, different
phrasing, a corpus that grew.

**Model drift:** the *model's behavior* changes under you — a provider
silently updates the model behind the API, or an on-disk model file
changes. No code change on your side, different answers anyway.

Both are invisible unless you compare production traffic and eval scores
against a baseline over time. Not just at launch. Which leads to the
dependency most teams discover too late: **drift detection needs a stable
baseline to drift *from*.** The eval set isn't a one-time validation step
— it's the reference point ongoing monitoring compares against. Skip eval
now, and monitoring later has nothing to measure drift against.

## Side by side

| Signal | Observable from a single request? | Needs a reference? | Typical tooling |
|---|---|---|---|
| Cost | ✅ tokens × price | ❌ | Langfuse / provider dashboards |
| Latency | ✅ timers | ❌ (percentiles need volume) | Langfuse / APM |
| Quality | ❌ | ✅ golden set + judge | RAGAS / DeepEval on a schedule |
| Drift | ❌ | ✅ baseline over time | eval history + traffic stats |

→ Next: **[wiring-it-in.md](wiring-it-in.md)**
