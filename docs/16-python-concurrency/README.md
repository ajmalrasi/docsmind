# Sync, async, threads, processes — what DocsMind's server actually does (concept + real code)

**Where in the pipeline:** the **Serving** stage — specifically, what happens
between a request hitting `/query` in
[`serving/app.py`](../../docsmind/serving/app.py) and the response going out.
This is infrastructure underneath the whole pipeline, not a stage in it — but
it's exactly where "how do you make this handle real traffic" questions land.

## The four ideas, at the same job: "handle more than one thing at once"

They solve overlapping-sounding problems in genuinely different ways — the
interview trap is treating them as synonyms.

| Concept | What actually happens | Good for |
|---|---|---|
| **Synchronous** | One thing at a time, in order, each step blocks until done | Simple, predictable code; DocsMind's `RAGPipeline.query()` today |
| **Asynchronous (`async`/`await`)** | One thread, but it can pause a task that's *waiting on I/O* and work on another task in the meantime | Many concurrent I/O-bound waits (network calls, disk) on a single core |
| **Multithreading** | Multiple OS threads in one process — but Python's GIL means only one thread runs Python bytecode at a time | I/O-bound work where you want simpler code than async, or C-extension code that releases the GIL |
| **Multiprocessing** | Multiple separate processes, each with its own Python interpreter and memory — no GIL sharing | CPU-bound work (real parallelism, not just overlapped waiting) |

"Parallel processing" isn't a fifth thing — it's the *outcome* multiprocessing
(and multi-core hardware) gives you: work genuinely happening at the same
instant on different cores. Async and threading in Python give you
**concurrency** (interleaved progress) without necessarily giving you
**parallelism** (simultaneous execution) — that distinction is the crux of
almost every question in this space.

## The GIL, in one paragraph

CPython's Global Interpreter Lock means only one thread executes Python
bytecode at any instant, even on a multi-core machine. This is why
multithreading in Python doesn't speed up CPU-bound work (crunching numbers in
a loop) — the threads just take turns on one core. It *does* still help
I/O-bound work, because a thread waiting on a network response releases the
GIL while it waits, letting another thread run. Multiprocessing sidesteps the
GIL entirely by using separate processes (separate interpreters, separate
memory) — the real way to get CPU-bound parallelism in Python.

## What DocsMind actually does today

Look at [`serving/app.py`](../../docsmind/serving/app.py): both `/health` and
`/query` are defined with plain `def`, not `async def`.

```python
@app.get("/health", response_model=HealthResponse)
def health() -> HealthResponse: ...

@app.post("/query", response_model=QueryResponse)
def query(request: QueryRequest) -> QueryResponse: ...
```

That's a deliberate, correct choice, not an oversight — and it's worth being
able to explain *why* rather than assuming async is always better.

FastAPI runs plain `def` endpoints in a **thread pool**, automatically, so one
slow synchronous handler (like `pipeline.query()`, which makes a blocking
network call to the Anthropic API inside `CloudLLMClient.generate()`) doesn't
block FastAPI's whole event loop. If `query` were declared `async def` but
called a *blocking* library (the `anthropic` SDK's sync client, not an async
one) without `await`, that blocking call would freeze the entire single-threaded
event loop — every other concurrent request would stall behind it. That's a
strictly worse outcome than what DocsMind has today.

## When `async def` would actually help here

`async def` earns its keep when the I/O call itself is **awaitable** — an
async HTTP client (`httpx.AsyncClient`, or the Anthropic SDK's
`AsyncAnthropic`) that yields control back to the event loop while waiting on
the network, instead of occupying a whole thread. At DocsMind's current
traffic (a demo server, `make serve`), the thread-pool-backed sync handler is
simpler and equally fine. It would start to matter at real concurrent load —
many simultaneous `/query` requests each waiting seconds on Claude's API —
where async lets one event loop juggle hundreds of waiting requests far more
cheaply (in memory and OS overhead) than hundreds of threads would.

## Trade-offs (the interview meat)

- **Sync + thread pool vs. true async: both handle concurrent I/O, at
  different costs.** Threads cost real OS memory per thread and have a
  practical ceiling (hundreds); an async event loop can juggle thousands of
  waiting I/O operations on one thread, cheaply — but only if *every* library
  in the call chain is actually async-aware. Mixing a blocking call into an
  `async def` handler is a classic footgun, worse than staying fully sync.
- **Multiprocessing's cost is memory and IPC, not CPU.** Each process
  duplicates memory (or needs explicit shared memory) and inter-process
  communication has real overhead — you pay for genuine parallelism with
  serialization cost at the boundaries.
- **Where this actually bites in DocsMind:** ingestion (`load_documents` +
  embedding a whole corpus) is CPU/GPU-bound batch work — multiprocessing or
  batched GPU calls are the right lever there. Serving a `/query` request is
  I/O-bound (waiting on the LLM API) — async or thread-pool concurrency is the
  right lever there. Reaching for the wrong tool (e.g. threading to speed up
  embedding a large corpus) wouldn't help because the GIL blocks the CPU-bound
  part anyway.
- **How you'd validate a concurrency choice:** load-test `/query` with
  increasing concurrent requests and watch p50/p99 latency and error rate —
  the same measure-don't-assume discipline as every other choice in this repo.

## The interview signals

- **Why is `/query` a plain `def`, not `async def`, in DocsMind?** Because the
  Anthropic SDK call inside it is blocking; FastAPI's thread pool handles that
  correctly for sync handlers, while an `async def` around a blocking call
  would freeze the whole event loop for every other request.
- **Does multithreading speed up CPU-bound Python code?** No — the GIL means
  only one thread runs bytecode at a time; multiprocessing is what gives you
  real CPU parallelism.
- **When do you reach for async over threads for I/O-bound work?** When you
  need to hold open a very large number of concurrent waits cheaply (thousands
  of connections) — async's per-task overhead is far lower than a thread's,
  provided the whole call chain is async-native.
