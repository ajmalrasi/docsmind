"""Measure vLLM TTFT, latency, decode speed, and concurrency throughput.

This benchmark calls the model server directly. Retrieval and corpus content are
intentionally excluded so changing DocsMind's data cannot invalidate serving
measurements.
"""

from __future__ import annotations

import argparse
from concurrent.futures import ThreadPoolExecutor
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
import json
import math
from pathlib import Path
import statistics
import time

import httpx

from docsmind.config import get_settings

DEFAULT_PROMPT = (
    "Explain why measuring time to first token and output tokens per second "
    "reveals different LLM serving bottlenecks. Use four short bullet points."
)


@dataclass(frozen=True)
class RequestMetrics:
    ttft_ms: float
    latency_ms: float
    completion_tokens: int | None
    decode_tokens_per_second: float | None


def _percentile(values: list[float], percentile: float) -> float:
    ordered = sorted(values)
    index = max(0, math.ceil(percentile * len(ordered)) - 1)
    return ordered[index]


def _one_request(
    client: httpx.Client,
    *,
    url: str,
    headers: dict[str, str],
    model: str,
    prompt: str,
    max_tokens: int,
) -> RequestMetrics:
    started = time.perf_counter()
    first_token_at: float | None = None
    completion_tokens: int | None = None
    payload = {
        "model": model,
        "messages": [{"role": "user", "content": prompt}],
        "max_tokens": max_tokens,
        "temperature": 0.2,
        "stream": True,
        "stream_options": {"include_usage": True},
    }

    with client.stream("POST", url, headers=headers, json=payload) as response:
        response.raise_for_status()
        for line in response.iter_lines():
            if not line.startswith("data:"):
                continue
            data = line.removeprefix("data:").strip()
            if not data or data == "[DONE]":
                continue
            event = json.loads(data)
            usage = event.get("usage")
            if usage:
                completion_tokens = usage.get("completion_tokens")
            choices = event.get("choices") or []
            if not choices:
                continue
            delta = choices[0].get("delta") or {}
            emitted = delta.get("content") or delta.get("reasoning_content")
            if emitted and first_token_at is None:
                first_token_at = time.perf_counter()

    finished = time.perf_counter()
    if first_token_at is None:
        raise RuntimeError("Streaming response completed without emitting a token")
    decode_seconds = max(finished - first_token_at, 1e-9)
    decode_rate = (
        completion_tokens / decode_seconds if completion_tokens is not None else None
    )
    return RequestMetrics(
        ttft_ms=(first_token_at - started) * 1000,
        latency_ms=(finished - started) * 1000,
        completion_tokens=completion_tokens,
        decode_tokens_per_second=decode_rate,
    )


def _summarize(
    metrics: list[RequestMetrics], wall_seconds: float, concurrency: int
) -> dict:
    ttft = [item.ttft_ms for item in metrics]
    latency = [item.latency_ms for item in metrics]
    token_counts = [
        item.completion_tokens
        for item in metrics
        if item.completion_tokens is not None
    ]
    decode_rates = [
        item.decode_tokens_per_second
        for item in metrics
        if item.decode_tokens_per_second is not None
    ]
    return {
        "concurrency": concurrency,
        "requests": len(metrics),
        "ttft_ms": {
            "p50": round(statistics.median(ttft), 2),
            "p95": round(_percentile(ttft, 0.95), 2),
        },
        "latency_ms": {
            "p50": round(statistics.median(latency), 2),
            "p95": round(_percentile(latency, 0.95), 2),
        },
        "mean_decode_tokens_per_second_per_request": (
            round(statistics.mean(decode_rates), 2) if decode_rates else None
        ),
        "aggregate_output_tokens_per_second": (
            round(sum(token_counts) / wall_seconds, 2) if token_counts else None
        ),
        "requests_per_second": round(len(metrics) / wall_seconds, 3),
        "wall_seconds": round(wall_seconds, 3),
        "samples": [asdict(item) for item in metrics],
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--concurrency", nargs="+", type=int, default=[1, 2, 4])
    parser.add_argument("--requests-per-level", type=int, default=4)
    parser.add_argument("--warmup-requests", type=int, default=1)
    parser.add_argument("--max-tokens", type=int, default=128)
    parser.add_argument("--prompt", default=DEFAULT_PROMPT)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    if any(level < 1 for level in args.concurrency):
        parser.error("all concurrency levels must be at least 1")
    if args.requests_per_level < 1 or args.warmup_requests < 0:
        parser.error("request counts must be non-negative and at least one measured")

    settings = get_settings()
    url = f"{settings.vllm_base_url.rstrip('/')}/chat/completions"
    headers = {}
    if settings.vllm_api_key is not None:
        headers["Authorization"] = (
            f"Bearer {settings.vllm_api_key.get_secret_value()}"
        )

    limits = httpx.Limits(max_connections=max(args.concurrency) + 2)
    with httpx.Client(timeout=settings.vllm_timeout_seconds, limits=limits) as client:
        for _ in range(args.warmup_requests):
            _one_request(
                client,
                url=url,
                headers=headers,
                model=settings.vllm_model,
                prompt=args.prompt,
                max_tokens=args.max_tokens,
            )

        levels = []
        for concurrency in args.concurrency:
            started = time.perf_counter()
            with ThreadPoolExecutor(max_workers=concurrency) as executor:
                futures = [
                    executor.submit(
                        _one_request,
                        client,
                        url=url,
                        headers=headers,
                        model=settings.vllm_model,
                        prompt=args.prompt,
                        max_tokens=args.max_tokens,
                    )
                    for _ in range(args.requests_per_level)
                ]
                metrics = [future.result() for future in futures]
            levels.append(
                _summarize(metrics, time.perf_counter() - started, concurrency)
            )

    result = {
        "measured_at": datetime.now(timezone.utc).isoformat(),
        "model": settings.vllm_model,
        "base_url": settings.vllm_base_url,
        "max_tokens": args.max_tokens,
        "prompt": args.prompt,
        "levels": levels,
    }
    rendered = json.dumps(result, indent=2)
    print(rendered)
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(rendered + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
