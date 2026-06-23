# Serving Open LLMs with vLLM

vLLM is a high-throughput inference engine for serving open-weight language models
such as Mistral and Llama.

## PagedAttention

vLLM's core innovation is PagedAttention, which manages the KV cache in
non-contiguous memory pages (like virtual memory in an OS). This nearly
eliminates KV-cache fragmentation and lets the server batch many concurrent
requests, raising throughput substantially over naive serving.

## Continuous batching

Rather than waiting for a fixed batch to fill, vLLM admits new requests into the
running batch as soon as slots free up. This keeps the GPU busy and lowers
average latency under load.

## OpenAI-compatible server

`vllm serve <model>` exposes an OpenAI-compatible HTTP API, so existing clients
can target a self-hosted model by changing only the base URL. Quantized weights
(AWQ, GPTQ) let larger models fit on a single consumer GPU such as an RTX 3070 Ti
with 8 GB of VRAM, at some cost to quality.

## When to self-host

Self-hosting an SLM is attractive for cost control, data privacy, and latency on
high-volume workloads. A common pattern is to route most traffic to the
self-hosted model and fall back to a larger cloud model for hard queries or to
act as an LLM-as-judge during evaluation.
