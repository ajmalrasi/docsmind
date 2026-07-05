# KV Cache — Stop Recomputing What You Already Computed

**TL;DR:** inside attention, each new token looks back at every previous
token through that token's key and value vectors. Those don't change between
steps — so cache them. The price: the cache lives in GPU memory for the whole
generation, which is why serving is *memory*-bound.

## The waste being eliminated

Inside attention, each new token looks back at every previous token.
It does that through each previous token's **key** and **value** vectors.

Here's the waste: naively, generating token 501 would recompute the keys and
values for tokens 1–500. But those haven't changed. They're the same every
step.

The **KV cache** just stores them. Token 501 computes only its own K/V pair,
then attends to the 500 cached ones.

```
without cache:  step 501 = recompute K,V for tokens 1..500  + compute token 501
with cache:     step 501 =        (read cache)              + compute token 501

per-step work:  O(n) recompute  →  O(1) new work + cache reads
```

Plain version: instead of re-reading the whole conversation before writing
each new sentence, you keep notes on what's been said and only read the new
part.

## The price: memory, and lots of it

The cache must live in GPU memory for the whole generation.
It grows with **context length × batch size** (× layers × heads × head_dim,
for every token, in both K and V).

This cache is why LLM serving is called **memory-bound**, not compute-bound.
On an 8GB card, *this* is what caps context length and concurrent requests —
the exact number the roadmap's beast (RTX 3070 Ti, 8GB) benchmark needs to
measure.

Back-of-envelope for a 7B-class model (fp16): each token's KV entry across
all layers is roughly 0.5 MB. A 4k context is ~2 GB of cache — a quarter of
the card — *before* counting the model weights. Quantize the weights and the
cache becomes the dominant tenant. This single number explains most serving
behavior on consumer GPUs.

## PagedAttention — the memory layout fix

Naive serving allocates each request's cache as one contiguous block sized
for the *maximum* possible context — mostly wasted on short requests.

vLLM's **PagedAttention** carves the cache into fixed-size blocks and maps
them like OS virtual-memory pages: allocate on demand, no contiguity
requirement, near-zero fragmentation. That's not a speed trick per se — it's
what lets continuous batching pack many more concurrent requests into the
same VRAM (see [continuous-batching.md](continuous-batching.md)).

## Trade-off and validation

KV cache trades **memory for compute** — a direct spend of GPU VRAM to buy
speed. There's no configuration where you skip it in production; the real
decisions are around what it enables and limits: max context, max batch,
whether prefix caching (sharing the cache for a common system prompt across
requests) is worth turning on.

How you'd validate on the beast: serve the same model with different max
context lengths, watch `nvidia-smi` memory, and record where requests start
queueing. That measured ceiling — not the spec sheet — is the number an
interviewer wants to hear.

→ Next: **[continuous-batching.md](continuous-batching.md)**
