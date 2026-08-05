"""Read-only smoke and latency check for the configured OpenSearch backend.

The command deliberately prints counts and timings only, never chunk text.

Usage:
    python -m scripts.opensearch_smoke
    python -m scripts.opensearch_smoke --question "another question" --runs 10
"""

from __future__ import annotations

import argparse
import statistics
import time

from docsmind.config import get_settings
from docsmind.factory import build_embedder, build_retriever, load_store


def _milliseconds(samples: list[float]) -> str:
    return (
        f"min={min(samples):.2f} "
        f"median={statistics.median(samples):.2f} "
        f"mean={statistics.fmean(samples):.2f}"
    )


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--question",
        default="What symptoms were mentioned when someone asked if it was clutch slip?",
    )
    parser.add_argument("--runs", type=int, default=5)
    args = parser.parse_args()
    if args.runs <= 0:
        parser.error("--runs must be positive")

    settings = get_settings()
    if settings.vector_backend != "opensearch":
        raise SystemExit(
            "Set DOCSMIND_VECTOR_BACKEND=opensearch before running this smoke test."
        )

    store = load_store(settings)
    print(f"backend={store.index_type}")
    print(f"vector_count={store.size}")

    started = time.perf_counter()
    chunks = store.chunks
    chunk_load_ms = (time.perf_counter() - started) * 1000
    print(f"chunk_count={len(chunks)}")
    print(f"bm25_payload_load_ms={chunk_load_ms:.2f}")

    embedder = build_embedder(settings)
    query_vector = embedder.embed_query(args.question)

    dense_ms = []
    for _ in range(args.runs):
        started = time.perf_counter()
        dense_results = store.search(query_vector, top_k=settings.top_k)
        dense_ms.append((time.perf_counter() - started) * 1000)
    print(f"dense_result_count={len(dense_results)}")
    print(f"dense_ms {_milliseconds(dense_ms)}")

    retriever = build_retriever(settings, embedder, store)
    hybrid_ms = []
    for _ in range(args.runs):
        started = time.perf_counter()
        hybrid_results = retriever.retrieve(args.question, top_k=settings.top_k)
        hybrid_ms.append((time.perf_counter() - started) * 1000)
    print(f"hybrid_result_count={len(hybrid_results)}")
    print(f"hybrid_ms {_milliseconds(hybrid_ms)}")

    close = getattr(store, "close", None)
    if close is not None:
        close()


if __name__ == "__main__":
    main()
