# 20 — Production Monitoring: Cost, Latency, Quality, Drift (concept, Phase 7)

**The big idea:** monitoring wraps the **entire** pipeline as a
cross-cutting concern — instrumentation *on* every stage, not a stage
itself. DocsMind already measures a little (a `latency_ms` on every
response, an offline retrieval eval). Turning "a number exists in one
response object" into "a monitored system" is what Phase 7
(`docsmind/ops/`) is the placeholder for.

**Where in the pipeline:** everywhere and nowhere — like logging in a
normal backend.

```
ingest → chunk → embed → index → [ query → embed → search → rerank →
                                    filter → generate → cite → EVAL ]
           ▲                                    ▲                ▲
      already measured:                   already measured:   not built:
   05-faiss benchmark.py             pipeline.py: latency_ms   RAGAS/drift/
   (recall/latency/memory)           on every QueryResponse   cost dashboards
```

## Files in this folder

| File | What it covers |
|------|----------------|
| [four-signals.md](four-signals.md) | Cost, latency, quality, drift — why each is a different axis with different tooling |
| [wiring-it-in.md](wiring-it-in.md) | What DocsMind measures today, the exact seams for Langfuse/RAGAS, and fire-testing the monitoring itself |

## 🎯 Interview Q&A

**Q: What would you track for an LLM app in production, beyond "is it up"?**
Cost per request. Latency at p95/p99, not just the mean. A recurring
quality eval against a golden set. And drift — in both incoming traffic
and model/provider behavior. Four different signals, not one dashboard
number.

**Q: Why isn't quality monitored the same way as latency?**
Latency is directly measurable from any request. Quality needs a judgment
against a reference — human or LLM-as-judge — which is itself imperfect
and costs money to run continuously.

**Q: What's the difference between data drift and model drift?**
Data drift: your *inputs* changed (new question patterns, corpus changes).
Model drift: the *model's behavior* changed under you — often silently,
via a provider-side update — with no code change on your end to explain it.

**Q: How do you know your monitoring works?**
Fire-test it: inject a known regression — a deliberately worse model, a
corrupted index — and confirm the dashboards flag it. Monitoring you
haven't fire-tested is a false sense of safety.

## Code

[docsmind/pipeline.py](../../docsmind/pipeline.py) — `latency_ms` via
`time.perf_counter()`, the one shipped piece of instrumentation.
[docsmind/ops/](../../docsmind/ops/) — today a one-line docstring:
*"Ops layer (Phase 7): Dockerfile, k8s manifests, Langfuse/MLflow wiring."*

→ Next: **[21-multimodal-document-rag/README.md](../21-multimodal-document-rag/README.md)**
