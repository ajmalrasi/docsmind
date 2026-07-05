# Turning `/query` Into a Genuinely Async Endpoint

**TL;DR:** a *true* async endpoint needs every I/O call inside it to be
awaitable, all the way down. Changing `def` to `async def` without that is
not a no-op — it's a regression.

## What the migration actually looks like

Today's `def query(...)` runs in FastAPI's thread pool — see
[16-python-concurrency/docsmind-server.md](../16-python-concurrency/docsmind-server.md)
for why that's correct as-is.

To make it a *true* `async def`, every I/O call inside it must be
awaitable, all the way down:

```python
@app.post("/query", response_model=QueryResponse)
async def query(request: QueryRequest) -> QueryResponse:
    pipeline = _state.get("pipeline")
    if pipeline is None:
        raise HTTPException(status_code=503, detail="No index loaded.")
    return await pipeline.aquery(request.question, request.top_k)  # new async path
```

That `aquery` doesn't exist yet. Building it means `CloudLLMClient`
switches to Anthropic's `AsyncAnthropic` client and does
`await self._client.messages.create(...)` instead of the current blocking
call.

The chain that must go async, end to end:

```
async def query()                       serving/app.py
  → await pipeline.aquery()             pipeline.py (new)
    → await llm.agenerate()             llm/base.py contract widened
      → await AsyncAnthropic.messages.create()   the actual awaitable I/O
```

One blocking link anywhere in that chain and the event loop stalls — the
footgun in detail:
[16-python-concurrency/docsmind-server.md](../16-python-concurrency/docsmind-server.md).

What about retrieval? FAISS search and BM25 scoring are CPU work, not I/O —
there's nothing to await. They're fast enough (sub-millisecond at this
corpus size, per the [05-faiss benchmark](../05-faiss/benchmark-results.md))
to run inline; a heavy reranker would instead go through
`run_in_executor` to avoid hogging the loop.

## The trap, stated once more precisely

Changing `def` to `async def` alone does *nothing* useful if the code
inside still blocks. It's actively worse. A blocking call inside
`async def` stalls the single event-loop thread — every concurrent request
freezes, not just one thread-pool slot.

The rule: `async def` is a promise to the event loop, not a performance
flag. Only make the promise if every call inside keeps it.

## How you'd validate the migration actually helped

Load-test both versions — current sync-thread-pool vs `async def` +
`AsyncAnthropic` — at increasing concurrency. Compare p50/p99 latency and
max sustained requests/sec.

| Concurrency | Expected result |
|---|---|
| 1–10 requests | no measurable difference — don't claim one |
| ~100s | thread pool starts queuing; async holds latency flat |
| 1000s | threads exhaust memory; async keeps going (if the chain is clean) |

"Async is faster" is only true under concurrent I/O-bound load, and only if
you proved it. The measured crossover point — not the slogan — is the
interview answer.

→ Next: **[18-llm-security/README.md](../18-llm-security/README.md)**
