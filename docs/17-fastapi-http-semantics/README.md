# 17 — FastAPI & HTTP Semantics: GET vs POST (real code)

**The big idea:** HTTP methods aren't interchangeable labels — each one is a
promise that browsers, caches, proxies, and load balancers rely on. `/health`
is GET because reading it changes nothing; `/query` is POST because it
carries a body and triggers real work. And in FastAPI, the type hints *are*
the contract, enforced at the framework boundary.

**Where in the pipeline:** the **Serving** stage — the HTTP contract
wrapping the pipeline, in
[`serving/app.py`](../../docsmind/serving/app.py). This section covers the
HTTP-and-FastAPI layer; the sync/async execution model *underneath* it is
[16-python-concurrency](../16-python-concurrency/README.md).

```
client ── GET  /health ──→ no body, no state change, safe to poll ──→ status
client ── POST /query  ──→ JSON body (question, top_k)
                            → pydantic validates → retrieval + LLM call → answer
```

## Files in this folder

| File | What it covers |
|------|----------------|
| [get-vs-post.md](get-vs-post.md) | The promises each method makes, and why `/query` can't be a GET |
| [request-contract.md](request-contract.md) | Pydantic models as the enforced contract — parsing, 422s, and `response_model` as a security boundary |
| [async-endpoint.md](async-endpoint.md) | Turning `/query` into a genuinely async endpoint — and the trap of a fake one |

## 🎯 Interview Q&A

**Q: Why does `/query` use POST instead of GET?**
It has a body, and it triggers non-idempotent, non-cacheable work
(retrieval + an LLM call). GET's contract — safe, cacheable, no body —
doesn't fit.

**Q: What does `response_model` actually do beyond docs?**
Validates and *filters* the outgoing payload against the schema. It's
enforcement, not an OpenAPI hint — extra internal fields get stripped
before they go over the wire.

**Q: Would switching `def` to `async def` alone speed anything up here?**
No — and it could make things worse. A blocking call inside `async def`
stalls the entire event loop, instead of occupying one thread-pool slot.

**Q: How would you prove an async migration helped?**
Load-test both versions at increasing concurrency, compare p50/p99 latency
and max sustained requests/sec. "Async is faster" is a claim about
concurrent I/O-bound load, verified — not a default truth.

## Code

[docsmind/serving/app.py](../../docsmind/serving/app.py) — both endpoints.
[docsmind/schemas.py](../../docsmind/schemas.py) — `QueryRequest`,
`QueryResponse`, the pydantic contract.

→ Next: **[18-llm-security/README.md](../18-llm-security/README.md)**
