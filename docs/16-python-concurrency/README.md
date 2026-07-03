# Sync, async, threads, processes — what DocsMind's server actually does (concept + real code)

**Where in the pipeline:** the **Serving** stage.
Specifically: what happens between a request hitting `/query` in [`serving/app.py`](../../docsmind/serving/app.py) and the response going out.
This is infrastructure *underneath* the pipeline, not a stage in it.
But it's exactly where "how do you make this handle real traffic" questions land.

## Four ideas, one job: handle more than one thing at once

They sound like synonyms. They aren't.
Treating them as synonyms is the interview trap.

| Concept | What actually happens | Good for |
|---|---|---|
| **Synchronous** | One thing at a time, in order; each step blocks until done | Simple, predictable code; DocsMind's `RAGPipeline.query()` today |
| **Asynchronous (`async`/`await`)** | One thread, but it can pause a task that's *waiting on I/O* and work on another in the meantime | Many concurrent I/O waits (network, disk) on a single core |
| **Multithreading** | Multiple OS threads in one process — but Python's GIL means only one runs Python bytecode at a time | I/O-bound work with simpler code than async; C-extension code that releases the GIL |
| **Multiprocessing** | Separate processes, each with its own interpreter and memory — no shared GIL | CPU-bound work: real parallelism, not just overlapped waiting |

One more term to place: "parallel processing" isn't a fifth thing.
It's the *outcome* multiprocessing gives you — work happening at the same instant on different cores.

The distinction that decides almost every question in this space:

- **Concurrency** = making progress on several things by interleaving them.
- **Parallelism** = several things literally running at the same instant.

Async and threading in Python give you concurrency.
Only multiprocessing gives you parallelism.

## The GIL, in plain words

CPython has a Global Interpreter Lock — the **GIL**.
It means only one thread executes Python bytecode at any instant, even on a 16-core machine.

So multithreading does NOT speed up CPU-bound Python (crunching numbers in a loop).
The threads just take turns on one core.

But it DOES still help I/O-bound work.
A thread waiting on a network response releases the GIL while it waits.
Another thread runs in the meantime.

Multiprocessing sidesteps the GIL entirely: separate processes, separate interpreters, separate memory.
That's the real way to get CPU-bound parallelism in Python.

## What DocsMind actually does today

Look at [`serving/app.py`](../../docsmind/serving/app.py).
Both endpoints are plain `def`, not `async def`:

```python
@app.get("/health", response_model=HealthResponse)
def health() -> HealthResponse: ...

@app.post("/query", response_model=QueryResponse)
def query(request: QueryRequest) -> QueryResponse: ...
```

That's a deliberate, correct choice — not an oversight.
Being able to explain *why* beats assuming async is always better.

Here's the mechanism.
FastAPI runs plain `def` endpoints in a **thread pool**, automatically.
So a slow sync handler — like `pipeline.query()`, which makes a blocking network call to the Anthropic API inside `CloudLLMClient.generate()` — occupies one pool thread, and nothing else.

Now the footgun.
Suppose `query` were `async def`, but still called the *blocking* Anthropic SDK inside.
A blocking call inside `async def` freezes the **entire event loop** — the single thread every async request shares.
Every concurrent request stalls behind it.
That's strictly worse than what DocsMind has today.

## When `async def` would actually help here

`async def` earns its keep when the I/O call itself is **awaitable**.
That means an async client — `httpx.AsyncClient`, or the Anthropic SDK's `AsyncAnthropic` — that hands control back to the event loop while waiting on the network, instead of occupying a whole thread.

At DocsMind's current traffic (a demo server, `make serve`), the sync-plus-thread-pool setup is simpler and equally fine.

It starts to matter at real concurrent load.
Picture hundreds of simultaneous `/query` requests, each waiting seconds on Claude's API.
Threads cost real OS memory each; hundreds is a practical ceiling.
One async event loop can juggle thousands of waiting requests far more cheaply.

## Trade-offs (the interview meat)

- **Sync + thread pool vs true async: both handle concurrent I/O, at different costs.**
  Threads: real memory per thread, ceiling in the hundreds.
  Async: thousands of cheap waiting tasks on one thread — but only if *every* library in the call chain is async-aware.
  One blocking call buried in an `async def` chain is worse than staying fully sync.
- **Multiprocessing's cost is memory and communication, not CPU.**
  Each process duplicates memory (or needs explicit shared memory).
  Data crossing process boundaries must be serialized.
  You pay for genuine parallelism at the boundaries.
- **Where this actually bites in DocsMind.**
  Ingestion (`load_documents` + embedding a corpus) is CPU/GPU-bound batch work → multiprocessing or batched GPU calls are the right lever.
  Serving `/query` is I/O-bound (waiting on the LLM API) → async or thread-pool concurrency is the right lever.
  Grab the wrong lever — say, threads to speed up embedding — and the GIL blocks you anyway.
- **How you'd validate a concurrency choice.**
  Load-test `/query` with increasing concurrent requests.
  Watch p50/p99 latency and error rate.
  Same measure-don't-assume discipline as every other choice in this repo.

## The interview signals

- **Why is `/query` a plain `def`, not `async def`, in DocsMind?**
  The Anthropic SDK call inside it blocks.
  FastAPI's thread pool handles that correctly for sync handlers.
  An `async def` wrapping a blocking call would freeze the whole event loop for every other request.
- **Does multithreading speed up CPU-bound Python?**
  No. The GIL lets only one thread run bytecode at a time.
  Multiprocessing is what gives you real CPU parallelism.
- **When do you pick async over threads for I/O-bound work?**
  When you need to hold open a very large number of concurrent waits cheaply — thousands of connections.
  Async's per-task overhead is far below a thread's, provided the whole call chain is async-native.
