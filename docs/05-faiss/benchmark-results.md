# Benchmark Results — Flat vs IVF vs HNSW vs IVFPQ (real numbers)

**Where in the pipeline:** this is the **Index** stage (build time) and the
**Search** stage (query latency + recall). Nothing else in the pipeline moves.
Phase 1 hard-wired `flat` here; Phase 2 makes the index type a config dial and
measures what each choice costs you.

```
Ingest → Chunk → Embed → [ INDEX ]      ← build time, memory
Query  → Embed → [ SEARCH ] → Generate  ← latency, recall@k
                     ▲
            flat | ivf | hnsw | ivfpq   ← the only thing that changes
```

The previous doc ([phase1-vs-phase2.md](phase1-vs-phase2.md)) gave the *theory*.
This one runs `scripts/benchmark.py` and reports what actually happened.

## Why synthetic data (and why clustered)

Our real corpus is ~15 chunks. Approximate indexes need *thousands* of vectors
before their tradeoff even appears — and IVF/IVFPQ can't train on 15 points.
So the benchmark generates synthetic unit vectors instead.

But not *random* vectors. In 384 dimensions, uniform-random points are nearly
all equidistant (the "curse of dimensionality") — there are no neighborhoods,
so every approximate index scores terribly and the numbers lie. Real embeddings
**cluster** (similar text → nearby vectors). So the benchmark builds clustered
vectors, which behave like the embeddings your pipeline actually produces.

`flat` is the ground truth: its exact top-k *is* the correct answer. Every other
index is graded on how much of flat's top-k it recovers.

## The headline run — 50,000 vectors, dim 384, top_k=10

```
index     recall@k    p50 ms    p95 ms   build ms   mem MB   mem x
------------------------------------------------------------------
flat         1.000     0.775     0.885          5     76.8    1.00
ivf          0.900     0.104     0.134         71     77.4    1.01
hnsw         0.862     0.404     0.496      10658     90.4    1.18
ivfpq        0.332     0.086     0.096       1750      3.3    0.04
```

Read it as **what you pay and what you get**:

- **flat** — perfect recall, but it scans all 50k vectors every query. Zero
  build cost, zero training. The baseline you grade everyone against.
- **ivf** — 90% recall for **7× faster** queries (0.10 vs 0.78 ms) and almost no
  extra memory. It clustered the vectors once (71 ms) and now probes only 8 of
  100 cells per query. Best all-round trade here.
- **hnsw** — 86% recall, ~2× faster than flat, but **18% more memory** (it stores
  a graph on top of the vectors) and a **brutal 10.7 s build**. The graph is
  what you pay up front to get fast walks later.
- **ivfpq** — **25× smaller** (3.3 MB vs 76.8 MB) by compressing each vector to a
  short code. The price is recall: 33%. It's a memory play, not an accuracy play
  — you'd use it at billion-scale and re-rank survivors with exact vectors.

## The whole point — flat scales O(N), approximate doesn't

Same benchmark at **500,000 vectors** (10× the data):

```
              p50 latency
index       50k  →  500k
-----------------------------
flat       0.78  →  7.22 ms     10× data = 10× slower   (linear scan)
ivf        0.10  →  0.95 ms     stays ~1 ms             (probes a fixed slice)
```

That single comparison is the reason approximate indexes exist. Flat's cost
grows with the corpus; IVF's barely moves. At 50k, flat's 0.78 ms is fine —
**you would not bother switching.** At millions, flat's tens of milliseconds per
query is the bottleneck, and IVF/HNSW earn their complexity.

## The gotcha — parameters must scale with N

At 500k, IVF's recall *dropped* to ~0.23 with the same settings. Why? `nlist`
auto-scaled to ~1000 cells, but `nprobe` stayed at 8 — so we searched only
**8 of 1000** cells instead of 8 of 100. The fix is to raise `nprobe`
(and HNSW's `efSearch`) as the corpus grows. The dials:

| Dial | Index | Turn up → | Turn down → |
|------|-------|-----------|-------------|
| `nprobe` | ivf, ivfpq | better recall, slower | faster, lower recall |
| `efSearch` | hnsw | better recall, slower | faster, lower recall |
| `nlist` | ivf, ivfpq | finer cells (needs higher nprobe) | coarser cells |
| `hnsw_m` | hnsw | better recall, more memory | less memory |

These live in [config.py](../../docsmind/config.py) (`ivf_nprobe`, `hnsw_ef_search`, …)
so you tune them without touching code.

## What this means for DocsMind

The real pipeline **stays on `flat`** — correct, simplest, and instant for a
small corpus. Phase 2's deliverable isn't a switch; it's the *evidence* that
tells you exactly when to switch and what each option costs. That's the
interview answer: not "HNSW is fast," but "at 50k flat was 0.78 ms so I kept it;
the benchmark shows IVF wins ~100k+ at 90% recall for 7× the speed."

## Run it yourself

```bash
make benchmark                          # 50k vectors
python -m scripts.benchmark --n 500000  # bigger, shows flat's O(N) climb
```

→ Back to: **[phase1-vs-phase2.md](phase1-vs-phase2.md)**
→ Code: **[scripts/benchmark.py](../../scripts/benchmark.py)** · **[faiss_store.py](../../docsmind/index/faiss_store.py)**
