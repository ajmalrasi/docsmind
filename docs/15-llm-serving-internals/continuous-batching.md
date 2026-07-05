# Continuous Batching — Don't Let One Slow Request Block the Queue

**TL;DR:** naive batching waits for the whole batch to finish before starting
the next one, so one long answer stalls everyone. Continuous batching swaps
requests in and out *mid-batch*, at the token level. It's the core trick
behind vLLM and TGI.

## The problem with static batches

Naive batching groups N requests and waits for **all of them** to finish
before starting the next batch. One long request stalls everyone behind it.
The GPU sits idle waiting for the straggler.

```
static batch:      req A ████████████████████████  (long)
                   req B ████░░░░░░░░░░░░░░░░░░░░  done early, slot wasted
                   req C ██████░░░░░░░░░░░░░░░░░░  done early, slot wasted
                   req D (queued)  ← waits for A to finish

continuous:        req A ████████████████████████
                   req B ████ → D slots in ██████████
                   req C ██████ → E slots in ████████
                            ▲ freed slots refill immediately, mid-batch
```

## How continuous batching works

**Continuous batching** — the core trick behind vLLM, TGI, and friends —
tracks each request independently, at the token level. The moment one
request finishes (hits its stop token), a new request from the queue slots
into the freed spot. Mid-batch, immediately.

The GPU stays busy. Throughput goes up. Short requests stop paying for long
ones.

Plain version: not a bus that waits for every passenger to reach their stop
before picking up new riders. A bus that drops people off and picks new ones
up at every stop, never idling.

This is also why it pairs with PagedAttention
(see [kv-cache.md](kv-cache.md)): requests joining and leaving mid-batch
need cache memory that can be allocated and freed in small blocks, not one
big contiguous slab per request.

## The trade-off: it only helps under load

Continuous batching only helps under **concurrent** load. A dev box serving
one request at a time — today's Ollama setup — gets nothing from it. It's a
production-multi-user optimization.

Which is exactly why it matters for the "deploy at scale" interview question
and not for `make demo`:

| Load pattern | Static batching | Continuous batching |
|---|---|---|
| 1 request at a time (dev box) | fine | identical — nothing to interleave |
| Bursty, mixed-length requests | GPU idles behind stragglers | GPU stays saturated |
| Steady high concurrency | throughput = slowest request's pace | throughput ≈ hardware limit |

## How you'd validate it

Benchmark throughput (requests/sec and tok/s) vs concurrency level, same
model, Ollama vs vLLM, on the beast. The expected shape: nearly identical at
concurrency 1, vLLM pulling ahead as concurrency rises. Producing that curve
— not quoting it — is the roadmap's whole point: "I measured continuous
batching's effect on my own hardware" is an entry-gate bullet.

→ Next: **[speculative-decoding.md](speculative-decoding.md)**
