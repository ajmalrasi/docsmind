# What DocsMind's Server Actually Does — and the Async Footgun

**TL;DR:** FastAPI runs plain `def` endpoints in a thread pool
automatically. That's why DocsMind's blocking Anthropic call is handled
correctly today — and why naively adding `async def` would make things
*worse*, not better.

## What the code does today

Look at [`serving/app.py`](../../docsmind/serving/app.py).
Both endpoints are plain `def`, not `async def`:

```python
@app.get("/health", response_model=HealthResponse)
def health() -> HealthResponse: ...

@app.post("/query", response_model=QueryResponse)
def query(request: QueryRequest) -> QueryResponse: ...
```

That's a deliberate, correct choice — not an oversight.

Here's the mechanism. FastAPI runs plain `def` endpoints in a **thread
pool**, automatically. So a slow sync handler — like `pipeline.query()`,
which makes a blocking network call to the Anthropic API inside
`CloudLLMClient.generate()` — occupies one pool thread, and nothing else.
Other requests keep flowing on other threads.

## The footgun

Suppose `query` were `async def`, but still called the *blocking* Anthropic
SDK inside. A blocking call inside `async def` freezes the **entire event
loop** — the single thread every async request shares. Every concurrent
request stalls behind it.

```
sync def + thread pool:      async def + blocking call inside:

req 1 ──[thread 1: waits]     req 1 ──[event loop: BLOCKED]
req 2 ──[thread 2: fine]      req 2 ──   ...stalled...
req 3 ──[thread 3: fine]      req 3 ──   ...stalled...
```

That's strictly worse than what DocsMind has today. `async def` is not a
speed keyword — it's a contract: "everything I await hands control back."
Break the contract and you serialize your whole server.

## When `async def` would actually help here

`async def` earns its keep when the I/O call itself is **awaitable**. That
means an async client — `httpx.AsyncClient`, or the Anthropic SDK's
`AsyncAnthropic` — that hands control back to the event loop while waiting
on the network, instead of occupying a whole thread.

At DocsMind's current traffic (a demo server, `make serve`), the
sync-plus-thread-pool setup is simpler and equally fine.

It starts to matter at real concurrent load. Picture hundreds of
simultaneous `/query` requests, each waiting seconds on Claude's API.
Threads cost real OS memory each; hundreds is a practical ceiling. One
async event loop can juggle thousands of waiting requests far more cheaply.

| | Threads (today) | Async (migration path) |
|---|---|---|
| Cost per concurrent wait | one OS thread (~MBs of stack) | one task object (~KBs) |
| Practical ceiling | hundreds | tens of thousands |
| Code requirement | none — works with any library | *every* library in the chain must be async-aware |
| Failure mode | pool exhaustion → queuing (graceful) | one blocking call → whole loop stalls (silent, severe) |

The migration itself — `aquery()`, `AsyncAnthropic` — is sketched in
[17-fastapi-http-semantics/async-endpoint.md](../17-fastapi-http-semantics/async-endpoint.md).

## How you'd validate a concurrency choice

Load-test `/query` with increasing concurrent requests. Watch p50/p99
latency and error rate. Same measure-don't-assume discipline as every other
choice in this repo: "async is faster" is only true under concurrent
I/O-bound load, and only if you proved it on your own endpoint.

→ Next: **[17-fastapi-http-semantics/README.md](../17-fastapi-http-semantics/README.md)**
