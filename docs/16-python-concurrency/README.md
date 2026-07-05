# 16 — Python Concurrency: Sync, Async, Threads, Processes (real code)

**The big idea:** sync, async, multithreading, and multiprocessing sound like
synonyms. They aren't — and treating them as synonyms is the interview trap.
DocsMind's `/query` endpoint is a plain `def`, not `async def`, and that's a
deliberate, correct choice. Being able to explain *why* beats assuming async
is always better.

**Where in the pipeline:** the **Serving** stage. Specifically: what happens
between a request hitting `/query` in
[`serving/app.py`](../../docsmind/serving/app.py) and the response going
out. This is infrastructure *underneath* the pipeline, not a stage in it.
But it's exactly where "how do you make this handle real traffic" questions
land.

```
request → FastAPI → def query() → pipeline.query() → blocking Anthropic call
                    ▲ runs in a thread pool — one slow request occupies
                      one thread, everything else keeps moving
```

## Files in this folder

| File | What it covers |
|------|----------------|
| [four-models.md](four-models.md) | Sync vs async vs threads vs processes, the GIL, and concurrency vs parallelism |
| [docsmind-server.md](docsmind-server.md) | Why `/query` is plain `def`, the async-with-blocking-call footgun, and when async earns its keep |

## 🎯 Interview Q&A

**Q: Why is `/query` a plain `def`, not `async def`, in DocsMind?**
The Anthropic SDK call inside it blocks. FastAPI's thread pool handles that
correctly for sync handlers. An `async def` wrapping a blocking call would
freeze the whole event loop for every other request.

**Q: Does multithreading speed up CPU-bound Python?**
No. The GIL lets only one thread run bytecode at a time. Multiprocessing is
what gives you real CPU parallelism.

**Q: When do you pick async over threads for I/O-bound work?**
When you need to hold open a very large number of concurrent waits cheaply —
thousands of connections. Async's per-task overhead is far below a thread's,
provided the whole call chain is async-native.

**Q: What's the difference between concurrency and parallelism?**
Concurrency = making progress on several things by interleaving them.
Parallelism = several things literally running at the same instant.
Async and threading in Python give you concurrency. Only multiprocessing
gives you parallelism.

## Code

[docsmind/serving/app.py](../../docsmind/serving/app.py) — both endpoints,
plain `def` by design.

→ Next: **[17-fastapi-http-semantics/README.md](../17-fastapi-http-semantics/README.md)**
