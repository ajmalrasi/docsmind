# The Request/Response Contract — Type Hints That Enforce Themselves

**TL;DR:** FastAPI reads the pydantic type annotations and does three jobs
from them: parse, validate (bad requests get a 422 before your code runs),
and serialize. `response_model` additionally *filters* the output — a real
security boundary, not documentation.

## The real contract

```python
@app.get("/health", response_model=HealthResponse)
def health() -> HealthResponse: ...

@app.post("/query", response_model=QueryResponse)
def query(request: QueryRequest) -> QueryResponse: ...
```

`QueryRequest` and `QueryResponse` are pydantic models
([`schemas.py`](../../docsmind/schemas.py)).
FastAPI reads the *type annotations themselves* and does three jobs from
them:

1. **Parse** the incoming JSON body.
2. **Validate** it — malformed requests get a 422 automatically, before
   your function body ever runs.
3. **Serialize** the return value back to JSON.

This is why DocsMind never hand-writes `request.json()` parsing or manual
validation. The type hints *are* the contract, enforced at the framework
boundary.

```
raw JSON body
     ↓ parse            ← FastAPI, from the annotation
     ↓ validate         ← pydantic; failure = 422, handler never runs
QueryRequest object → your handler → QueryResponse object
     ↓ filter + serialize   ← response_model
JSON over the wire
```

## `response_model` is a security boundary

`response_model` isn't just documentation. It validates and **filters** the
return value. If your handler accidentally returns extra internal fields,
`response_model` strips anything not declared on the schema before it goes
over the wire.

That's a real defense against leaking internal state. Concretely: if a
future `QueryResponse` gained an internal `debug_context` field carrying raw
retrieved chunks, forgetting to remove it before returning would leak
corpus content — *unless* the response schema never declared it, in which
case FastAPI silently drops it. Easy to overlook; catches a real class of
bug (see [18-llm-security](../18-llm-security/README.md)).

## Why this pattern generalizes

The pipeline uses the same idea at every boundary: pydantic-settings
validates config at startup (fail fast on a bad `.env`), `QueryRequest`
validates input at the HTTP edge, `response_model` filters output at the
same edge. One principle — **validate at the boundary, trust inside** —
applied three times.

In an interview, the depth question is "where do you validate?" The answer
that lands: at the boundaries, once, declaratively — not scattered
`isinstance` checks through the business logic.

→ Next: **[async-endpoint.md](async-endpoint.md)**
