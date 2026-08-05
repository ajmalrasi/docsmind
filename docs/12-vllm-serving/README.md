# Phase 4 — vLLM serving and model routing

## Pipeline position

```text
Ingest → Chunk → Embed → Index → Query → Search → Rerank
                                              ↓
                         vLLM → Generate → Cite → Eval
                           ↓ unavailable
                        Anthropic
```

This runs at the **Generate** stage, after retrieval has assembled numbered
context passages and before the pipeline extracts citations.

The insertion point is `build_llm()` in `docsmind/factory.py`. The rest of the
pipeline sees only the `LLMClient` contract. Changing astronomy documents to a
forum, chat, or another corpus changes ingestion and retrieval data, not model
routing.

## What was added

- `VLLMClient` sends an optional Bearer token to an OpenAI-compatible vLLM API.
- `LLMRouter` tries a configured primary model and uses a fallback model only
  when the primary is temporarily unavailable.
- `scripts/vllm_smoke.py` proves endpoint connectivity without involving RAG.
- `scripts/vllm_benchmark.py` measures TTFT, total latency, decode speed, and
  aggregate throughput independently of the corpus.

## Why availability-based fallback first

At Generate, the current need is simple: prefer the self-hosted model, but keep
the application alive when that server is overloaded or down. This is basically
an electrical backup generator. It activates because the primary stopped
serving, not because the question looked difficult.

The technical term is **failover routing**. It is narrower than semantic or
quality routing, where a classifier chooses a model based on query complexity.
Failover is easier to test and safer as the first production policy.

The router falls back for:

- connection failures and timeouts;
- HTTP 408 and 429;
- HTTP 5xx server failures.

It does not fall back for HTTP 4xx configuration failures. A wrong API key or
model alias needs correction. Silently sending that traffic to Anthropic would
hide the incident and create unexpected cost.

## How to run it

Put the real values in `.env`, which is excluded from Git:

```bash
DOCSMIND_LLM_PROVIDER=router
DOCSMIND_LLM_PRIMARY_PROVIDER=vllm
DOCSMIND_LLM_FALLBACK_PROVIDER=cloud
DOCSMIND_VLLM_MODEL=openclaw
DOCSMIND_VLLM_BASE_URL=https://your-vllm-host.example/v1
DOCSMIND_VLLM_API_KEY=your-secret
```

```bash
make vllm-smoke
make vllm-demo ARGS='"Ask a question supported by the current corpus"'
make vllm-benchmark ARGS='--concurrency 1 2 4 --requests-per-level 4'
```

## What the measurements mean

- **TTFT (time to first token)** is how long the user waits before output begins.
  Prompt processing, queueing, and network latency dominate it.
- **Decode tokens/second** is how quickly one response continues after the first
  token. Model size, quantization, memory bandwidth, and GPU kernels dominate it.
- **Aggregate output tokens/second** measures total server work across concurrent
  users. Continuous batching can increase this even while each user slows down.
- **Requests/second** is completed request throughput for this exact prompt and
  output limit. It is not meaningful without recording the workload.

## Trade-offs and debugging

Why vLLM over a plain Transformers loop? vLLM adds continuous batching, KV-cache
management, and an OpenAI-compatible serving API. A plain loop is easier to
understand, but it does not demonstrate the production serving behavior this
phase is meant to measure.

What breaks first? Wrong credentials produce 401/403. A wrong served-model alias
usually produces 404/400. Saturation appears as rising TTFT and sometimes 429 or
5xx. GPU memory pressure can crash workers or reduce the usable KV cache. Debug
these separately: smoke test authentication, inspect server logs, then sweep
concurrency while watching GPU utilization and memory.

## Interview depth signal

In an interview, the real question is not “did you run vLLM?” It is “why vLLM,
how did you measure it, what failed, and what did you change?”

The evidence to cite is:

1. exact model, quantization, GPU, vLLM version, and cost per hour;
2. p50/p95 TTFT and latency at several concurrency levels;
3. per-request and aggregate output tokens/second;
4. the failure policy and proof that it falls back only when intended;
5. answer-quality and structured-output success rates before replacing the cloud
   model for more traffic.

The benchmark covers items 2 and 3. Server metadata, hourly cost, GPU telemetry,
and answer-quality evaluation remain separate measurements because client-side
timing cannot infer them reliably. The first measured serving and GPU results are
recorded in [benchmark-results.md](benchmark-results.md).
