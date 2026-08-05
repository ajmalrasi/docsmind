"""Authenticated, corpus-independent smoke test for the configured vLLM API."""

from __future__ import annotations

import argparse
import json
import time

from docsmind.config import get_settings
from docsmind.llm.vllm_client import VLLMClient


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "prompt",
        nargs="?",
        default="Reply with exactly: VLLM_OK",
    )
    parser.add_argument("--max-tokens", type=int, default=32)
    args = parser.parse_args()

    settings = get_settings()
    api_key = (
        settings.vllm_api_key.get_secret_value()
        if settings.vllm_api_key is not None
        else None
    )
    client = VLLMClient(
        model=settings.vllm_model,
        base_url=settings.vllm_base_url,
        api_key=api_key,
        timeout=settings.vllm_timeout_seconds,
    )

    started = time.perf_counter()
    answer = client.generate(
        "Follow the user's instruction exactly.",
        args.prompt,
        args.max_tokens,
    )
    elapsed_ms = (time.perf_counter() - started) * 1000
    print(
        json.dumps(
            {
                "status": "ok",
                "model": client.model,
                "latency_ms": round(elapsed_ms, 2),
                "answer": answer,
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
