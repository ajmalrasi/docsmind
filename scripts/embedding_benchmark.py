"""Measure a Text Embeddings Inference endpoint without exposing corpus text.

Run this while the SSM tunnel is open. The benchmark uses synthetic automotive
sentences, validates the response contract, and emits machine-readable JSON so
CPU and future GPU runs can be compared with the same workload.
"""

from __future__ import annotations

import argparse
import json
import math
import platform
import statistics
import time
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import httpx


SAMPLE_TEXTS = (
    "The Volkswagen ID.4 uses the modular electric drive matrix platform.",
    "Audi quattro and Volkswagen 4motion are all-wheel-drive brand names.",
    "The MQB architecture supports multiple transverse-engine vehicle models.",
    "Porsche and Audi jointly developed the premium platform electric system.",
    "A dual-clutch transmission preselects the next gear for a faster shift.",
    "The EA888 is a turbocharged petrol engine family used across several brands.",
    "Skoda vehicles share components and platforms within Volkswagen Group.",
    "Battery capacity, motor output, and charging rate affect electric-car use.",
    "A retrieval system should preserve article titles and canonical citations.",
    "Hybrid search combines semantic similarity with exact keyword matching.",
    "Embedding vectors from different models must not share one vector index.",
    "The query encoder and document encoder must use compatible instructions.",
    "A production service applies bounded batches and request backpressure.",
    "CPU inference is inexpensive for development but slower than GPU inference.",
    "Latency percentiles expose slow requests that an average can hide.",
    "Throughput measures how many texts the service embeds each second.",
)


def _percentile(values: list[float], percentile: float) -> float:
    ordered = sorted(values)
    if len(ordered) == 1:
        return ordered[0]
    position = (len(ordered) - 1) * percentile
    lower = math.floor(position)
    upper = math.ceil(position)
    if lower == upper:
        return ordered[lower]
    weight = position - lower
    return ordered[lower] * (1 - weight) + ordered[upper] * weight


def _validate_vectors(payload: Any, expected_count: int) -> tuple[int, float]:
    if not isinstance(payload, list) or len(payload) != expected_count:
        raise RuntimeError(
            f"TEI returned {len(payload) if isinstance(payload, list) else 0} "
            f"vectors for {expected_count} inputs."
        )
    dimension = len(payload[0]) if payload else 0
    if dimension <= 0 or any(
        not isinstance(vector, list) or len(vector) != dimension for vector in payload
    ):
        raise RuntimeError("TEI returned vectors with inconsistent dimensions.")
    norms = [math.sqrt(sum(float(value) ** 2 for value in vector)) for vector in payload]
    return dimension, max(abs(norm - 1.0) for norm in norms)


def run_benchmark(
    *,
    base_url: str,
    batch_sizes: list[int],
    repeats: int,
    timeout: float,
) -> dict[str, Any]:
    with httpx.Client(base_url=base_url.rstrip("/"), timeout=timeout) as client:
        health = client.get("/health")
        health.raise_for_status()
        info_response = client.get("/info")
        info_response.raise_for_status()
        info = info_response.json()

        # Keep warm-up outside measured samples.
        warmup = client.post(
            "/embed",
            json={"inputs": [SAMPLE_TEXTS[0]], "normalize": True, "truncate": True},
        )
        warmup.raise_for_status()

        results: list[dict[str, Any]] = []
        expected_dimension: int | None = None
        for batch_size in batch_sizes:
            inputs = [SAMPLE_TEXTS[index % len(SAMPLE_TEXTS)] for index in range(batch_size)]
            latencies_ms: list[float] = []
            max_norm_error = 0.0
            for _ in range(repeats):
                started = time.perf_counter()
                response = client.post(
                    "/embed",
                    json={"inputs": inputs, "normalize": True, "truncate": True},
                )
                response.raise_for_status()
                elapsed_ms = (time.perf_counter() - started) * 1000
                dimension, norm_error = _validate_vectors(response.json(), batch_size)
                if expected_dimension is None:
                    expected_dimension = dimension
                elif dimension != expected_dimension:
                    raise RuntimeError(
                        f"TEI dimension changed from {expected_dimension} to {dimension}."
                    )
                max_norm_error = max(max_norm_error, norm_error)
                latencies_ms.append(elapsed_ms)

            total_seconds = sum(latencies_ms) / 1000
            results.append(
                {
                    "batch_size": batch_size,
                    "repeats": repeats,
                    "latency_ms": {
                        "mean": round(statistics.fmean(latencies_ms), 2),
                        "p50": round(statistics.median(latencies_ms), 2),
                        "p95": round(_percentile(latencies_ms, 0.95), 2),
                    },
                    "throughput_texts_per_second": round(
                        batch_size * repeats / total_seconds, 2
                    ),
                    "max_normalization_error": round(max_norm_error, 7),
                }
            )

    return {
        "measured_at": datetime.now(UTC).isoformat(),
        "client_platform": platform.platform(),
        "base_url": base_url,
        "health_status": health.status_code,
        "model": info.get("model_id") or info.get("modelId") or "unknown",
        "model_revision": info.get("model_sha") or info.get("revision"),
        "embedding_dimension": expected_dimension,
        "server_info": info,
        "results": results,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base-url", default="http://localhost:8080")
    parser.add_argument("--batch-sizes", type=int, nargs="+", default=[1, 4, 8])
    parser.add_argument("--repeats", type=int, default=10)
    parser.add_argument("--timeout", type=float, default=180.0)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    if args.repeats <= 0 or any(size <= 0 for size in args.batch_sizes):
        parser.error("repeats and batch sizes must be positive")

    result = run_benchmark(
        base_url=args.base_url,
        batch_sizes=args.batch_sizes,
        repeats=args.repeats,
        timeout=args.timeout,
    )
    rendered = json.dumps(result, indent=2, sort_keys=True)
    print(rendered)
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(rendered + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
