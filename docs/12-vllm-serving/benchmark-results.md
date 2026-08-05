# vLLM benchmark results — AWS EC2

Measured on 2026-08-05. These numbers describe the **Generate** stage only:
retrieval and corpus processing are excluded so the measurements remain useful
when DocsMind's data changes.

## Runtime under test

| Component | Observed configuration |
|---|---|
| Cloud instance | AWS EC2 `g6.xlarge`, `us-east-1` |
| GPU | NVIDIA L4, 23,034 MiB reported VRAM |
| Model | Gemma 4 12B QAT W4A16, served as `openclaw` |
| Weight runtime | vLLM `compressed-tensors` quantization |
| KV cache | FP8 |
| Context / scheduler | 16,384 tokens; maximum 4 sequences |
| vLLM | `0.25.1`; eager execution |
| API | Bearer-authenticated OpenAI-compatible HTTPS endpoint |

AWS documents `g6.xlarge` as one L4 GPU with 24 GB GPU memory, 4 vCPUs, and
16 GiB system memory. See the [AWS G6 instance page](https://aws.amazon.com/ec2/instance-types/g6/).

## Workload

- One warm-up request.
- Four measured requests per concurrency level.
- Identical prompt at every level.
- Temperature `0.2`.
- Maximum 96 output tokens; every measured request reached 96 tokens.
- Streaming enabled so TTFT is measured at the first emitted token.
- Measurements include public-network and TLS latency from the Mac client.

This is a small serving smoke benchmark, not a capacity limit. Four samples per
level are enough to prove the measurement path, but not enough for a production
SLO or a statistically stable p95.

## Results

| Concurrency | p50 TTFT | p95 TTFT | p50 total latency | Per-request decode | Aggregate output | Requests/s |
|---:|---:|---:|---:|---:|---:|---:|
| 1 | 371 ms | 371 ms | 5.75 s | 17.83 tok/s | 16.68 tok/s | 0.174 |
| 2 | 401 ms | 943 ms | 5.83 s | 17.68 tok/s | 31.54 tok/s | 0.329 |
| 4 | 651 ms | 959 ms | 6.13 s | 17.57 tok/s | 60.20 tok/s | 0.627 |

Aggregate output throughput increased 3.6× from concurrency 1 to 4, while each
request continued decoding near 17.6–17.8 tokens/s. The cost was higher queueing:
p50 TTFT increased from 371 ms to 651 ms. This is the continuous-batching
trade-off: the server completes more total work, but an individual user can wait
longer before the first token.

## GPU sample at concurrency 4

A second four-request run used 128 output tokens and sampled `nvidia-smi` once per
second. It measured:

| Metric | Result |
|---|---:|
| p50 / p95 TTFT | 928 / 941 ms |
| p50 / p95 total latency | 8.23 / 8.24 s |
| Per-request decode | 17.50 tok/s |
| Aggregate output | 62.13 tok/s |
| GPU utilization while active | approximately 60–63% |
| GPU memory | 21,746 / 23,034 MiB (94.4%) |
| Peak observed board power | 63.6 W |

The memory result matches vLLM's configured `gpu-memory-utilization=0.95` target.
It does not mean model weights alone consume 94% of VRAM: vLLM reserves remaining
space for the KV cache. The 60–63% compute utilization means this four-sequence
test did not fully saturate the L4.

## Cost interpretation

The Linux On-Demand rate observed for `g6.xlarge` in `us-east-1` on 2026-08-05
was **$0.8048/hour**, or about **$587.50 for 730 continuously running hours**.
The exact rate should be rechecked before quoting it because cloud pricing can
change. The current figure is also listed by
[DoiT's EC2 price tracker](https://www.doit.com/compute/spot/us-east-1/g6.xlarge);
AWS explains the billing model on its
[EC2 On-Demand pricing page](https://aws.amazon.com/ec2/pricing/on-demand/).

At the measured 62.13 aggregate output tokens/s, continuously saturated compute
works out to roughly **$3.60 per million output tokens**:

```text
62.13 tokens/s × 3,600 = 223,668 output tokens/hour
$0.8048 ÷ 223,668 × 1,000,000 ≈ $3.60/million output tokens
```

That is not a complete production token price. It excludes EBS, network transfer,
idle time, prompt-token work, failed requests, observability, and redundancy. A
mostly idle always-on GPU costs far more per useful token.

## End-to-end RAG proof

An isolated five-document astronomy corpus was indexed into a disposable FAISS
store. The full path then ran:

```text
question → BGE query embedding → dense + BM25 → RRF → vLLM → citations
```

For “What happens to a massive star when it runs out of fuel?”, `openclaw`
returned a grounded answer in **8.45 seconds** and cited `stellar_lifecycle.md`
and `black_holes.md`. The configured private corpus and OpenSearch index were not
read, modified, or re-ingested.

## Failure discovered during verification

On macOS, importing FAISS before the PyTorch-backed sentence transformer caused
a native segmentation fault during multi-text embedding. Loading PyTorch first
and FAISS only when the selected backend is constructed fixed it. The composition
root now enforces that order and has regression tests for lazy backend import.

In an interview, this is a stronger depth signal than saying “I used FAISS.” It
shows a native-runtime interaction, a minimal reproducer, the import-order cause,
and a fix verified through the full application path.

## Next quality gate

These results prove availability and serving performance. They do not prove that
the open model should replace Anthropic for every request. Before routing more
traffic, measure grounded answer quality, citation correctness, tool-call schema
success, and structured-output validity on a labeled evaluation set.
