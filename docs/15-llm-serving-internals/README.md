# Inside the serving box — KV cache, batching, speculative decoding (concept, roadmap)

**Where in the pipeline:** entirely *inside* the box that
[`LocalLLMClient.generate()`](../../docsmind/llm/local_client.py) treats as a
black box. DocsMind's code just does `POST /api/chat` to Ollama and gets text
back — this doc is about what happens between that request landing and the
response streaming out, and why the roadmap wants to swap Ollama for **vLLM**
to get control over it. Nothing here changes DocsMind's `LLMClient` interface;
it changes what sits behind `LocalLLMClient` at serving time.

```
today:   docsmind → LocalLLMClient.generate() → Ollama (opaque) → tokens back

roadmap: docsmind → LocalLLMClient.generate() → vLLM server ──┐
                                                                ├─ KV cache
                                                                ├─ continuous batching
                                                                └─ (optionally) speculative decoding
```

## The problem: generating text one token at a time is slow, by construction

An LLM produces output **autoregressively** — token N+1 depends on tokens
1..N, so you can't compute the whole answer in one shot the way you'd compute
a batch of embeddings. Every single token requires a full forward pass through
every layer of the model. A 500-token answer is 500 forward passes, done in
sequence, no shortcuts — *unless* you exploit structure in what's repeated
across those passes. That's what the three techniques below each do.

## KV cache — stop recomputing what you already computed

Inside attention, each token attends to every *previous* token via that
token's **key** and **value** vectors. Naively, generating token 501 would
recompute the keys/values for tokens 1-500 all over again — wasted work,
since they haven't changed.

The **KV cache** just stores those key/value vectors from every previous step
and reuses them. Token 501 only computes its own K/V pair and attends to the
500 cached ones. This is why LLM serving is described as memory-bound, not
compute-bound, at generation time — the cache has to live in GPU memory for
the whole sequence, and it grows linearly with context length × batch size.
It's *the* reason 8GB VRAM caps how long a context and how many concurrent
requests you can serve — this is the exact number the roadmap's beast (RTX
3070 Ti, 8GB) benchmark needs to measure.

Plain version: instead of re-reading the whole conversation before writing
each new sentence, you keep your notes on what's already been said and only
read the new part.

## Continuous batching — don't let one slow request block the queue

Naive batching groups N requests together and waits for **all of them** to
finish before starting the next batch — one long request stalls everyone
behind it, and GPU sits idle waiting for the last one.

**Continuous batching** (the core trick behind vLLM, TGI, etc.) instead
tracks each request's generation independently at the token level: as soon as
one request finishes (hits its stop token), a new request from the queue
slots into that freed spot immediately, mid-batch. The GPU stays busy;
throughput goes up without hurting the latency of short requests stuck
behind long ones.

Plain version: instead of a bus that waits for every passenger to reach their
stop before picking up the next rider, it's a bus that drops people off and
picks new ones up continuously, at every stop, never idling.

## Speculative decoding — guess ahead, verify in bulk

Generation is one token per forward pass because you don't know token N+1
until you've computed token N. **Speculative decoding** breaks that
constraint by using a small, fast **draft model** to guess several tokens
ahead (say, 4-8) cheaply, then running the big model **once** to verify all
of them in parallel — a single forward pass can check many tokens at once
because verification doesn't have the same one-at-a-time dependency
generation does. Correct guesses are accepted for free; the first wrong guess
is discarded and the big model's own token is used instead.

Plain version: instead of writing a sentence word by word and pausing to think
after each word, you sketch a whole draft sentence fast and cheap, then have
the real expert check it all at once — keeping what's right, redoing only
what's wrong.

## How they stack

| Technique | Solves | Cost of *not* having it |
|---|---|---|
| KV cache | Recomputing unchanged attention history every token | O(n²)-ish recompute per token instead of O(n) |
| Continuous batching | GPU idling behind slow requests in a static batch | Throughput capped by your slowest concurrent request |
| Speculative decoding | One token per full forward pass | Full model cost per token even when tokens are "easy" (predictable) |

All three are largely **transparent to the client** — `LocalLLMClient` doesn't
need to know any of this is happening; it just sends a prompt and gets tokens
back faster. That's exactly why the roadmap frames swapping Ollama → vLLM as
a serving-layer change with zero change to `docsmind/llm/base.py`'s contract.

## Trade-offs (the interview meat)

- **KV cache costs memory, not compute** — it's a direct trade of GPU VRAM for
  speed. On an 8GB card, this is the real ceiling: bigger models or longer
  contexts eat the cache budget before they eat compute.
- **Continuous batching only helps under concurrent load.** A dev box serving
  one request at a time (today's Ollama setup) gets none of this benefit —
  it's a production-multi-user optimization, which is exactly why it matters
  for the "deploy at scale" interview question and not for `make demo`.
- **Speculative decoding's win depends on the draft model's hit rate.** A bad
  draft model wastes the verification pass on tokens that get rejected anyway
  — worse than no speculation. It shines when output is predictable (code,
  structured formats); it helps less on creative, high-entropy text.
- **How you'd validate any of this:** don't take vendor claims — measure
  tok/s, time-to-first-token (TTFT), and throughput-vs-batch-size yourself, on
  the actual hardware (the beast's 3070 Ti), the same way `05-faiss`'s
  benchmark measured recall/latency/memory instead of asserting them. This is
  the exact measurement the cloud-deployment roadmap calls out as still
  missing.

## The interview signals

- **Why is LLM inference described as memory-bound?** The KV cache has to sit
  in GPU memory for the entire generation, and it scales with context length
  × batch size — you run out of memory long before you run out of compute on
  most consumer/prosumer GPUs.
- **What's the actual mechanism behind vLLM's speedup claims?** Continuous
  (sometimes called "in-flight") batching plus PagedAttention (a memory
  layout trick for the KV cache, similar in spirit to OS virtual memory
  paging) — not magic, a specific pair of engineering decisions.
- **When does speculative decoding *not* help?** Low-predictability output,
  or a draft model too weak to guess usefully — you pay the draft cost and
  still fall back to the slow path most of the time.
