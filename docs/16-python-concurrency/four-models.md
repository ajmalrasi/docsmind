# Four Ideas, One Job — Handling More Than One Thing at Once

**TL;DR:** sync does one thing at a time. Async interleaves I/O waits on one
thread. Threads interleave too (the GIL forbids true parallel bytecode).
Processes are the only way Python runs CPU work truly in parallel.

## The four models

| Concept | What actually happens | Good for |
|---|---|---|
| **Synchronous** | One thing at a time, in order; each step blocks until done | Simple, predictable code; DocsMind's `RAGPipeline.query()` today |
| **Asynchronous (`async`/`await`)** | One thread, but it can pause a task that's *waiting on I/O* and work on another in the meantime | Many concurrent I/O waits (network, disk) on a single core |
| **Multithreading** | Multiple OS threads in one process — but Python's GIL means only one runs Python bytecode at a time | I/O-bound work with simpler code than async; C-extension code that releases the GIL |
| **Multiprocessing** | Separate processes, each with its own interpreter and memory — no shared GIL | CPU-bound work: real parallelism, not just overlapped waiting |

One more term to place: "parallel processing" isn't a fifth thing.
It's the *outcome* multiprocessing gives you — work happening at the same
instant on different cores.

The distinction that decides almost every question in this space:

- **Concurrency** = making progress on several things by interleaving them.
- **Parallelism** = several things literally running at the same instant.

Async and threading in Python give you concurrency.
Only multiprocessing gives you parallelism.

```
concurrency (1 core):   A──A    A──A          interleaved — progress on both,
                            B──B    B──B      never simultaneous

parallelism (2 cores):  A──A──A──A──A         literally at the same instant
                        B──B──B──B──B
```

## The GIL, in plain words

CPython has a Global Interpreter Lock — the **GIL**.
It means only one thread executes Python bytecode at any instant, even on a
16-core machine.

So multithreading does NOT speed up CPU-bound Python (crunching numbers in a
loop). The threads just take turns on one core.

But it DOES still help I/O-bound work.
A thread waiting on a network response releases the GIL while it waits.
Another thread runs in the meantime.

Multiprocessing sidesteps the GIL entirely: separate processes, separate
interpreters, separate memory. That's the real way to get CPU-bound
parallelism in Python.

## Picking the right lever

The decision procedure is one question: **what is the work waiting on?**

| The bottleneck is... | Right lever | Why |
|---|---|---|
| The network / disk (I/O-bound) | async, or threads | The wait releases the GIL; interleaving wins |
| The CPU (crunching, parsing, embedding on CPU) | multiprocessing | Only separate processes escape the GIL |
| The GPU (model inference) | batching, not threads | The GPU is its own queue; feed it bigger batches |

Where this bites in DocsMind: ingestion (`load_documents` + embedding a
corpus) is CPU/GPU-bound batch work → multiprocessing or batched GPU calls
are the right lever. Serving `/query` is I/O-bound (waiting on the LLM API)
→ async or thread-pool concurrency is the right lever. Grab the wrong lever
— say, threads to speed up embedding — and the GIL blocks you anyway.

→ Next: **[docsmind-server.md](docsmind-server.md)**
