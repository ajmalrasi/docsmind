"""Benchmark FAISS index types: recall@k vs latency vs memory.

This is the Phase 2 deliverable. It answers the question Phase 1 left open:
*when is the exact flat index too slow, and what do you trade to fix it?*

It uses synthetic *clustered* unit vectors (not the tiny sample corpus, which
is far too small to show any difference). Clustering matters: real embeddings
live on clusters/manifolds, so they have genuine neighborhoods. Uniform random
vectors in high dimensions are nearly equidistant — the worst case for any
approximate index — and would understate recall badly. Flat is the ground
truth; every approximate index is scored on how often it recovers flat's
true top-k.

Usage:
    python -m scripts.benchmark                 # defaults: 50k vectors, dim 384
    python -m scripts.benchmark --n 200000 --queries 1000
"""

from __future__ import annotations

import argparse
import statistics
import time

import faiss
import numpy as np

from docsmind.config import get_settings
from docsmind.index.faiss_store import FaissVectorStore
from docsmind.schemas import Chunk


def _clustered_unit_vectors(
    n: int, dim: int, centers: np.ndarray, seed: int, jitter: float = 0.15
) -> np.ndarray:
    """n unit vectors drawn near random cluster centers — mimics how real
    embeddings sit in neighborhoods rather than spread out uniformly."""
    rng = np.random.default_rng(seed)
    labels = rng.integers(0, len(centers), size=n)
    vecs = centers[labels] + jitter * rng.standard_normal((n, dim)).astype(np.float32)
    vecs = np.ascontiguousarray(vecs, dtype=np.float32)
    faiss.normalize_L2(vecs)
    return vecs


def _cluster_centers(n_clusters: int, dim: int, seed: int) -> np.ndarray:
    centers = np.random.default_rng(seed).standard_normal((n_clusters, dim))
    centers = np.ascontiguousarray(centers, dtype=np.float32)
    faiss.normalize_L2(centers)
    return centers


def _build(index_type: str, dim: int, data: np.ndarray, **params) -> tuple[FaissVectorStore, float]:
    store = FaissVectorStore(dim=dim, index_type=index_type, **params)
    chunks = [Chunk(id=str(i), text="", source="synthetic") for i in range(data.shape[0])]
    t0 = time.perf_counter()
    store.add(chunks, data)
    return store, (time.perf_counter() - t0) * 1000.0


def _recall_and_latency(
    store: FaissVectorStore, queries: np.ndarray, truth: np.ndarray, top_k: int
) -> tuple[float, list[float]]:
    """Mean recall@k vs ground-truth ids, plus per-query latencies (ms)."""
    hits = 0
    latencies: list[float] = []
    for q, true_ids in zip(queries, truth):
        t0 = time.perf_counter()
        results = store.search(q, top_k=top_k)
        latencies.append((time.perf_counter() - t0) * 1000.0)
        got = {int(r.chunk.id) for r in results}
        hits += len(got & set(true_ids.tolist()))
    recall = hits / (len(queries) * top_k)
    return recall, latencies


def _index_bytes(store: FaissVectorStore) -> int:
    return int(faiss.serialize_index(store._index).nbytes)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--n", type=int, default=50_000, help="number of vectors")
    parser.add_argument("--dim", type=int, default=384, help="embedding dimension")
    parser.add_argument("--queries", type=int, default=500, help="number of query vectors")
    parser.add_argument("--top-k", type=int, default=10, help="neighbors per query")
    parser.add_argument("--seed", type=int, default=0)
    args = parser.parse_args()

    s = get_settings()
    n_clusters = max(50, args.n // 500)
    print(
        f"Benchmark: n={args.n:,} dim={args.dim} queries={args.queries} top_k={args.top_k}\n"
        f"(synthetic clustered unit vectors, {n_clusters} clusters; flat is ground truth)\n"
    )

    centers = _cluster_centers(n_clusters, args.dim, args.seed)
    data = _clustered_unit_vectors(args.n, args.dim, centers, args.seed + 1)
    queries = _clustered_unit_vectors(args.queries, args.dim, centers, args.seed + 2)

    configs = [
        ("flat", {}),
        ("ivf", {"nlist": s.ivf_nlist, "nprobe": s.ivf_nprobe}),
        ("hnsw", {"hnsw_m": s.hnsw_m, "hnsw_ef_search": s.hnsw_ef_search,
                  "hnsw_ef_construction": s.hnsw_ef_construction}),
        ("ivfpq", {"nlist": s.ivf_nlist, "nprobe": s.ivf_nprobe,
                   "pq_m": s.pq_m, "pq_nbits": s.pq_nbits}),
    ]

    # Build flat first to establish ground-truth top-k ids for every query.
    flat, flat_build = _build("flat", args.dim, data)
    truth = np.array(
        [[int(r.chunk.id) for r in flat.search(q, top_k=args.top_k)] for q in queries]
    )

    rows = []
    for index_type, params in configs:
        if index_type == "flat":
            store, build_ms = flat, flat_build
        else:
            store, build_ms = _build(index_type, args.dim, data, **params)
        recall, latencies = _recall_and_latency(store, queries, truth, args.top_k)
        rows.append({
            "type": index_type,
            "build_ms": build_ms,
            "recall": recall,
            "p50": statistics.median(latencies),
            "p95": statistics.quantiles(latencies, n=20)[18],
            "mb": _index_bytes(store) / 1e6,
        })

    flat_mb = next(r["mb"] for r in rows if r["type"] == "flat")
    header = f"{'index':<8}{'recall@k':>10}{'p50 ms':>10}{'p95 ms':>10}{'build ms':>11}{'mem MB':>9}{'mem x':>8}"
    print(header)
    print("-" * len(header))
    for r in rows:
        print(
            f"{r['type']:<8}{r['recall']:>10.3f}{r['p50']:>10.3f}{r['p95']:>10.3f}"
            f"{r['build_ms']:>11.0f}{r['mb']:>9.1f}{r['mb'] / flat_mb:>8.2f}"
        )
    print("\nrecall@k = fraction of flat's true top-k that the index recovered.")


if __name__ == "__main__":
    main()
