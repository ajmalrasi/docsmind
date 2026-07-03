# GET vs POST, and building an async endpoint (real code: serving/app.py)

**Where in the pipeline:** the **Serving** stage — the HTTP contract wrapping
the pipeline, in [`serving/app.py`](../../docsmind/serving/app.py). This doc
is about the HTTP-and-FastAPI layer specifically; see
[`16-python-concurrency`](../16-python-concurrency/README.md) for the
sync/async execution-model question that sits right underneath it.

## Why `/health` is GET and `/query` is POST — not convention, semantics

HTTP methods aren't interchangeable labels; each carries a contract other
software (browsers, caches, proxies, load balancers) relies on:

- **GET** means "give me a representation of this resource, and doing so has
  no side effects." GET requests are cacheable and safe to retry blindly —
  a browser prefetching, a proxy caching, a monitoring tool polling every 5
  seconds, none of that should ever be dangerous for a GET. `/health` in
  `app.py` fits exactly: no request body, no state change, just "tell me your
  current status."
- **POST** means "here is data, do something with it" — not safe to retry
  blindly (retrying a payment POST could double-charge) and not cacheable by
  default. `/query` takes a `QueryRequest` body (the question, `top_k`) and
  triggers real work (retrieval + an LLM call) — it's an action with an input,
  not a lookup, so GET (which can't cleanly carry a JSON body) is the wrong
  verb.

The tell in an interview: if a request needs a body to say what it wants, or
does something non-idempotent, it's not a GET. `/query`'s question text
couldn't fit cleanly or safely in a URL anyway — GET params are visible in
logs, proxies, and browser history, which also matters if the "question" ever
contains anything sensitive.

## The real request/response contract

```python
@app.get("/health", response_model=HealthResponse)
def health() -> HealthResponse: ...

@app.post("/query", response_model=QueryResponse)
def query(request: QueryRequest) -> QueryResponse: ...
```

`QueryRequest` and `QueryResponse` are pydantic models
([`schemas.py`](../../docsmind/schemas.py)) — FastAPI uses the *type
annotation itself* to know how to parse the incoming JSON body, validate it
(reject malformed requests with a 422 automatically, before your function
body even runs), and serialize the return value back to JSON. This is why
DocsMind never hand-writes `request.json()` parsing or manual validation —
the type hints *are* the contract, checked automatically at the framework
boundary.

## Turning `/query` into a genuinely async endpoint

Today's `def query(...)` runs in FastAPI's thread pool (see
`16-python-concurrency` for why that's actually correct as-is). To make it a
*true* `async def` that doesn't block the event loop, every I/O call inside
it needs to be awaitable, all the way down:

```python
@app.post("/query", response_model=QueryResponse)
async def query(request: QueryRequest) -> QueryResponse:
    pipeline = _state.get("pipeline")
    if pipeline is None:
        raise HTTPException(status_code=503, detail="No index loaded.")
    return await pipeline.aquery(request.question, request.top_k)  # new async path
```

That `aquery` doesn't exist yet — it would need `CloudLLMClient` to use
Anthropic's `AsyncAnthropic` client and `await self._client.messages.create(...)`
instead of the current blocking call. Changing the route's `def` to `async
def` alone does *nothing* useful if the code inside still blocks — that
mismatch (an `async def` wrapping a synchronous call) is worse than not using
async at all, because it stalls the single event-loop thread for every
concurrent request, not just the one thread pool slot a plain `def` would
have used.

## Trade-offs (the interview meat)

- **GET with a body is technically possible in some clients, universally
  discouraged.** Caches, proxies, and spec-compliant servers may silently
  drop it. Don't fight the convention to save one endpoint.
- **response_model isn't just documentation** — it validates and *filters*
  the return value. If your handler accidentally returns extra internal
  fields, `response_model` strips anything not declared on the schema before
  it goes out over the wire. That's a real, if easy to overlook, security
  boundary (see `18-llm-security`) against accidentally leaking internal
  state.
- **Async only pays off if the whole chain is async.** One blocking call
  buried three functions deep negates the benefit and actively regresses
  concurrent throughput versus staying sync.
- **How you'd validate the async migration actually helped:** load test both
  versions (current sync-thread-pool vs. a real `async def` + `AsyncAnthropic`
  version) at increasing concurrency and compare p50/p99 latency and max
  sustained requests/sec — the claim "async is faster" is only true under
  concurrent I/O-bound load, and only if you proved it, not assumed it.

## The interview signals

- **Why does `/query` use POST instead of GET?** It has a body, and it
  triggers non-idempotent, non-cacheable work (retrieval + an LLM call) —
  GET's contract (safe, cacheable, no body) doesn't fit.
- **What does `response_model` actually do beyond docs?** Validates and
  filters the outgoing payload against the schema — it's enforcement, not
  just an OpenAPI hint.
- **Would switching `def` to `async def` alone speed anything up here?** No —
  and it could make things worse, because a blocking call inside an `async
  def` stalls the entire single-threaded event loop instead of occupying one
  thread-pool slot.
