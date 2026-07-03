# Inside the serving box — KV cache, batching, speculative decoding (concept, roadmap)

**Where in the pipeline:** entirely *inside* the box that [`LocalLLMClient.generate()`](../../docsmind/llm/local_client.py) treats as a black box.
DocsMind's code just does `POST /api/chat` to Ollama and gets text back.
This doc is about what happens between that request landing and tokens streaming out.
It's also why the roadmap wants to swap Ollama for **vLLM**: to get control over that box.
Nothing here changes the `LLMClient` interface. It changes what sits behind it at serving time.

```
today:   docsmind → LocalLLMClient.generate() → Ollama (opaque) → tokens back

roadmap: docsmind → LocalLLMClient.generate() → vLLM server ──┐
                                                                ├─ KV cache
                                                                ├─ continuous batching
                                                                └─ (optionally) speculative decoding
```

## The problem: generating text one token at a time is slow, by construction

An LLM generates **autoregressively**.
That means token N+1 depends on tokens 1..N.
So you can't compute a whole answer in one shot, the way you'd compute a batch of embeddings.
Every token needs a full forward pass through every layer of the model.
A 500-token answer is 500 forward passes, in sequence.

No shortcuts — *unless* you exploit what's repeated across those passes.
Each of the three techniques below exploits a different repetition.

## KV cache — stop recomputing what you already computed

Inside attention, each new token looks back at every previous token.
It does that through each previous token's **key** and **value** vectors.

Here's the waste: naively, generating token 501 would recompute the keys and values for tokens 1–500.
But those haven't changed. They're the same every step.

The **KV cache** just stores them.
Token 501 computes only its own K/V pair, then attends to the 500 cached ones.

Plain version: instead of re-reading the whole conversation before writing each new sentence, you keep notes on what's been said and only read the new part.

This cache is why LLM serving is called **memory-bound**, not compute-bound.
The cache must live in GPU memory for the whole generation.
It grows with context length × batch size.
On an 8GB card, *this* is what caps context length and concurrent requests — the exact number the roadmap's beast (RTX 3070 Ti, 8GB) benchmark needs to measure.

## Continuous batching — don't let one slow request block the queue

Naive batching groups N requests and waits for **all of them** to finish before starting the next batch.
One long request stalls everyone behind it. The GPU sits idle waiting for the straggler.

**Continuous batching** — the core trick behind vLLM, TGI, and friends — tracks each request independently, at the token level.
The moment one request finishes (hits its stop token), a new request from the queue slots into the freed spot. Mid-batch, immediately.
The GPU stays busy. Throughput goes up. Short requests stop paying for long ones.

Plain version: not a bus that waits for every passenger to reach their stop before picking up new riders.
A bus that drops people off and picks new ones up at every stop, never idling.

## Speculative decoding — guess ahead, verify in bulk

Generation is one token per forward pass because you don't know token N+1 until you've computed token N.
**Speculative decoding** breaks that constraint with a cheat: two models.

A small, fast **draft model** guesses several tokens ahead — say 4 to 8 — cheaply.
Then the big model runs **once** to verify all of them in parallel.
That works because verification doesn't have the one-at-a-time dependency generation has: checking "would I have written these tokens?" can happen for all of them in a single pass.
Correct guesses are accepted for free.
The first wrong guess is thrown away, and the big model's own token is used instead.

Plain version: instead of writing word by word, pausing to think after each word, you let a fast intern sketch the whole sentence.
The expert checks it all at once — keeps what's right, redoes only what's wrong.

## How they stack

| Technique | Solves | Cost of *not* having it |
|---|---|---|
| KV cache | Recomputing unchanged attention history every token | O(n²)-ish recompute per token instead of O(n) |
| Continuous batching | GPU idling behind slow requests in a static batch | Throughput capped by your slowest concurrent request |
| Speculative decoding | One token per full forward pass | Full model cost per token even when tokens are "easy" (predictable) |

All three are **invisible to the client**.
`LocalLLMClient` doesn't need to know any of this is happening — it sends a prompt, tokens come back faster.
That's exactly why the roadmap frames Ollama → vLLM as a serving-layer swap with zero change to `docsmind/llm/base.py`'s contract.

## Trade-offs (the interview meat)

- **KV cache trades memory for compute.**
  It's a direct spend of GPU VRAM to buy speed.
  On an 8GB card this is the real ceiling: bigger models or longer contexts eat the cache budget long before they eat compute.
- **Continuous batching only helps under concurrent load.**
  A dev box serving one request at a time — today's Ollama setup — gets nothing from it.
  It's a production-multi-user optimization.
  Which is exactly why it matters for the "deploy at scale" interview question and not for `make demo`.
- **Speculative decoding lives or dies on the draft model's hit rate.**
  A bad draft model wastes the verification pass on tokens that get rejected anyway — worse than no speculation at all.
  It shines on predictable output (code, structured formats).
  It helps less on creative, high-entropy text.
- **How you'd validate any of this.**
  Don't repeat vendor claims. Measure.
  tok/s, time-to-first-token (TTFT), throughput vs batch size — on the actual hardware (the beast's 3070 Ti).
  Same discipline as `05-faiss`'s benchmark: recall/latency/memory were measured, not asserted.
  This is the exact measurement the cloud-deployment roadmap calls out as still missing.

## The interview signals

- **Why is LLM inference described as memory-bound?**
  The KV cache sits in GPU memory for the entire generation, and it scales with context length × batch size.
  You run out of memory long before you run out of compute on most consumer GPUs.
- **What's the actual mechanism behind vLLM's speedup claims?**
  Continuous (also called "in-flight") batching, plus PagedAttention — a memory layout trick for the KV cache, similar in spirit to OS virtual-memory paging.
  Not magic. Two specific engineering decisions.
- **When does speculative decoding *not* help?**
  Low-predictability output, or a draft model too weak to guess usefully.
  You pay the draft cost and still fall back to the slow path most of the time.
