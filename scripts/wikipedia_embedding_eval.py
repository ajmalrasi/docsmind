"""Compare embedding models on persisted Volkswagen Wikipedia indexes.

Unlike ``retrieval_eval.py``, this script does not rebuild or re-embed the
corpus. It connects to two isolated OpenSearch indexes produced from the same
snapshot and changes only the query embedding provider.
"""

from __future__ import annotations

import argparse
import json
import statistics
import time
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from docsmind.config import get_settings
from docsmind.index.embeddings import Embedder, EmbeddingProvider, TEIEmbedder
from docsmind.index.opensearch_store import OpenSearchVectorStore
from docsmind.retrieval.retriever import HybridRetriever, Retriever


DEFAULT_EVAL_FILE = Path("data/eval/volkswagen_wikipedia_queries.v1.json")


def _percentile(values: list[float], percentile: float) -> float:
    ordered = sorted(values)
    if len(ordered) == 1:
        return ordered[0]
    position = (len(ordered) - 1) * percentile
    lower = int(position)
    upper = min(lower + 1, len(ordered) - 1)
    weight = position - lower
    return ordered[lower] * (1 - weight) + ordered[upper] * weight


def _title(result: Any) -> str:
    return str(result.chunk.metadata.get("title", ""))


def _score(retriever: Any, queries: list[dict[str, Any]], k: int) -> dict[str, Any]:
    hit1 = hit3 = reciprocal_rank = 0.0
    latencies_ms: list[float] = []
    details: list[dict[str, Any]] = []
    for item in queries:
        started = time.perf_counter()
        results = retriever.retrieve(item["question"], k)
        latencies_ms.append((time.perf_counter() - started) * 1000)
        relevant = set(item["relevant_titles"])
        titles = [_title(result) for result in results]
        first = next(
            (rank for rank, title in enumerate(titles, start=1) if title in relevant),
            None,
        )
        if first is not None:
            hit1 += first == 1
            hit3 += first <= 3
            reciprocal_rank += 1 / first
        details.append(
            {
                "id": item["id"],
                "kind": item.get("kind", "unknown"),
                "first_relevant_rank": first,
                "relevant_titles": sorted(relevant),
                "top_titles": titles,
            }
        )

    count = len(queries)
    return {
        "query_count": count,
        "hit@1": round(hit1 / count, 4),
        "hit@3": round(hit3 / count, 4),
        "mrr": round(reciprocal_rank / count, 4),
        "latency_ms": {
            "mean": round(statistics.fmean(latencies_ms), 2),
            "p50": round(statistics.median(latencies_ms), 2),
            "p95": round(_percentile(latencies_ms, 0.95), 2),
        },
        "details": details,
    }


def _load_store(
    path: Path, *, endpoint: str, region: str, profile_name: str
) -> OpenSearchVectorStore:
    return OpenSearchVectorStore.load(
        path,
        endpoint=endpoint,
        region=region,
        profile_name=profile_name,
    )


def _evaluate_model(
    *,
    label: str,
    embedder: EmbeddingProvider,
    store: OpenSearchVectorStore,
    queries: list[dict[str, Any]],
    k: int,
    candidate_k: int,
    fusion_k: int,
) -> dict[str, Any]:
    dense = Retriever(embedder, store)
    hybrid = HybridRetriever(
        embedder,
        store,
        candidate_k=candidate_k,
        fusion_k=fusion_k,
    )
    return {
        "label": label,
        "provider": embedder.provider_name,
        "model": embedder.model_name,
        "dimension": embedder.dim,
        "index_size": store.size,
        "dense": _score(dense, queries, k),
        "hybrid": _score(hybrid, queries, k),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--eval-file", type=Path, default=DEFAULT_EVAL_FILE)
    parser.add_argument("--bge-small-index-dir", type=Path, default=Path("data/index-wikipedia"))
    parser.add_argument(
        "--bge-m3-index-dir", type=Path, default=Path("data/index-wikipedia-bge-m3-v1")
    )
    parser.add_argument("--tei-base-url", default="http://localhost:8080")
    parser.add_argument("--k", type=int, default=5)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()

    payload = json.loads(args.eval_file.read_text(encoding="utf-8"))
    queries = payload["queries"]
    settings = get_settings()
    small_store = _load_store(
        args.bge_small_index_dir,
        endpoint=settings.opensearch_endpoint,
        region=settings.aws_region,
        profile_name=settings.aws_profile,
    )
    m3_store = _load_store(
        args.bge_m3_index_dir,
        endpoint=settings.opensearch_endpoint,
        region=settings.aws_region,
        profile_name=settings.aws_profile,
    )
    results = {
        "measured_at": datetime.now(UTC).isoformat(),
        "corpus_version": payload.get("corpus_version"),
        "label_status": payload.get("label_status"),
        "rank_depth": args.k,
        "models": [
            _evaluate_model(
                label="bge-small baseline",
                embedder=Embedder("BAAI/bge-small-en-v1.5", device="cpu"),
                store=small_store,
                queries=queries,
                k=args.k,
                candidate_k=settings.candidate_k,
                fusion_k=settings.fusion_k,
            ),
            _evaluate_model(
                label="BGE-M3 CPU TEI",
                embedder=TEIEmbedder(
                    "BAAI/bge-m3",
                    dimension=1024,
                    base_url=args.tei_base_url,
                    batch_size=8,
                    timeout=settings.tei_timeout_seconds,
                ),
                store=m3_store,
                queries=queries,
                k=args.k,
                candidate_k=settings.candidate_k,
                fusion_k=settings.fusion_k,
            ),
        ],
    }

    for model in results["models"]:
        for mode in ("dense", "hybrid"):
            metrics = model[mode]
            print(
                f"{model['label']:<22} {mode:<7} "
                f"Hit@1={metrics['hit@1']:.2f} Hit@3={metrics['hit@3']:.2f} "
                f"MRR={metrics['mrr']:.3f} p50={metrics['latency_ms']['p50']:.1f}ms"
            )

    rendered = json.dumps(results, indent=2, ensure_ascii=False) + "\n"
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(rendered, encoding="utf-8")
    else:
        print(rendered)


if __name__ == "__main__":
    main()
