# GET vs POST, and building an async endpoint (real code: serving/app.py)

**Where in the pipeline:** the **Serving** stage — the HTTP contract wrapping the pipeline, in [`serving/app.py`](../../docsmind/serving/app.py).
This doc covers the HTTP-and-FastAPI layer.
The sync/async execution model *underneath* it is [`16-python-concurrency`](../16-python-concurrency/README.md).

## Why `/health` is GET and `/query` is POST — semantics, not convention

HTTP methods aren't interchangeable labels.
Each one is a promise that other software — browsers, caches, proxies, load balancers — relies on.

**GET promises: "reading this changes nothing."**
So GETs are safe to cache, safe to prefetch, safe to retry blindly.
A monitoring tool can poll a GET every 5 seconds and nothing bad happens.
`/health` fits exactly: no request body, no state change, just "tell me your status."

**POST promises nothing of the sort.**
POST means "here is data, do something with it."
Not safe to retry blindly — retrying a payment POST could double-charge.
Not cacheable by default.
`/query` takes a `QueryRequest` body (the question, `top_k`) and triggers real work: retrieval plus an LLM call.
That's an action with an input, not a lookup.

The tell to use in an interview: if a request needs a body to say what it wants, or does something non-idempotent, it's not a GET.
There's a practical reason too.
GET parameters live in the URL — visible in server logs, proxies, and browser history.
If a question ever contains anything sensitive, you don't want it in a URL.

## The real request/response contract

```python
@app.get("/health", response_model=HealthResponse)
def health() -> HealthResponse: ...

@app.post("/query", response_model=QueryResponse)
def query(request: QueryRequest) -> QueryResponse: ...
```

`QueryRequest` and `QueryResponse` are pydantic models ([`schemas.py`](../../docsmind/schemas.py)).
FastAPI reads the *type annotations themselves* and does three jobs from them:

1. Parse the incoming JSON body.
2. Validate it — malformed requests get a 422 automatically, before your function body ever runs.
3. Serialize the return value back to JSON.

This is why DocsMind never hand-writes `request.json()` parsing or manual validation.
The type hints *are* the contract, enforced at the framework boundary.

## Turning `/query` into a genuinely async endpoint

Today's `def query(...)` runs in FastAPI's thread pool — see `16-python-concurrency` for why that's correct as-is.

To make it a *true* `async def`, every I/O call inside it must be awaitable, all the way down:

```python
@app.post("/query", response_model=QueryResponse)
async def query(request: QueryRequest) -> QueryResponse:
    pipeline = _state.get("pipeline")
    if pipeline is None:
        raise HTTPException(status_code=503, detail="No index loaded.")
    return await pipeline.aquery(request.question, request.top_k)  # new async path
```

That `aquery` doesn't exist yet.
Building it means `CloudLLMClient` switches to Anthropic's `AsyncAnthropic` client and does `await self._client.messages.create(...)` instead of the current blocking call.

The trap: changing `def` to `async def` alone does *nothing* useful if the code inside still blocks.
It's actively worse.
A blocking call inside `async def` stalls the single event-loop thread — every concurrent request freezes, not just one thread-pool slot.

## Trade-offs (the interview meat)

- **GET with a body: technically possible in some clients, universally discouraged.**
  Caches, proxies, and spec-compliant servers may silently drop it.
  Don't fight the convention to save one endpoint.
- **`response_model` isn't just documentation.**
  It validates and *filters* the return value.
  If your handler accidentally returns extra internal fields, `response_model` strips anything not declared on the schema before it goes over the wire.
  That's a real security boundary against leaking internal state — easy to overlook (see `18-llm-security`).
- **Async only pays off if the whole chain is async.**
  One blocking call three functions deep negates the benefit — and regresses concurrent throughput below the sync version.
- **How you'd validate the async migration actually helped.**
  Load-test both versions — current sync-thread-pool vs `async def` + `AsyncAnthropic` — at increasing concurrency.
  Compare p50/p99 latency and max sustained requests/sec.
  "Async is faster" is only true under concurrent I/O-bound load, and only if you proved it.

## The interview signals

- **Why does `/query` use POST instead of GET?**
  It has a body, and it triggers non-idempotent, non-cacheable work (retrieval + an LLM call).
  GET's contract — safe, cacheable, no body — doesn't fit.
- **What does `response_model` actually do beyond docs?**
  Validates and filters the outgoing payload against the schema.
  It's enforcement, not an OpenAPI hint.
- **Would switching `def` to `async def` alone speed anything up here?**
  No — and it could make things worse.
  A blocking call inside `async def` stalls the entire event loop, instead of occupying one thread-pool slot.
