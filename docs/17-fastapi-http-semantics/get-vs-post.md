# GET vs POST — Semantics, Not Convention

**TL;DR:** GET promises "reading this changes nothing," which makes it safe
to cache, prefetch, and retry. POST promises nothing of the sort. `/health`
fits GET exactly; `/query` — a body plus real work — can only be POST.

## The promises each method makes

HTTP methods aren't interchangeable labels. Each one is a promise that
other software — browsers, caches, proxies, load balancers — relies on.

**GET promises: "reading this changes nothing."**
So GETs are safe to cache, safe to prefetch, safe to retry blindly.
A monitoring tool can poll a GET every 5 seconds and nothing bad happens.
`/health` fits exactly: no request body, no state change, just "tell me
your status."

**POST promises nothing of the sort.**
POST means "here is data, do something with it."
Not safe to retry blindly — retrying a payment POST could double-charge.
Not cacheable by default.
`/query` takes a `QueryRequest` body (the question, `top_k`) and triggers
real work: retrieval plus an LLM call. That's an action with an input, not
a lookup.

| | GET `/health` | POST `/query` |
|---|---|---|
| Request body | none | JSON (`question`, `top_k`) |
| Side effects | none | retrieval + a paid LLM call |
| Safe to retry blindly | ✅ | ❌ — each retry costs tokens and latency |
| Cacheable by intermediaries | ✅ | ❌ by default |
| Idempotent | ✅ | LLM output isn't even deterministic |

The tell to use in an interview: if a request needs a body to say what it
wants, or does something non-idempotent, it's not a GET.

## The practical reason on top of the semantic one

GET parameters live in the URL — visible in server logs, proxies, and
browser history. If a question ever contains anything sensitive, you don't
want it in a URL. POST bodies don't end up in access logs by default.

This connects to [18-llm-security](../18-llm-security/README.md): PII
hygiene starts at the transport layer, before any masking logic runs.

## The edge case interviewers poke at

GET with a body: technically possible in some clients, universally
discouraged. Caches, proxies, and spec-compliant servers may silently drop
the body. Don't fight the convention to save one endpoint — the ecosystem's
assumptions about GET are the *feature* you'd be breaking.

→ Next: **[request-contract.md](request-contract.md)**
