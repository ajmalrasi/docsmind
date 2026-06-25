"""End-to-end demo: ingest if needed, then run a sample query with citations.

Usage: python -m scripts.demo ["your question"]
"""

from __future__ import annotations

import sys

from docsmind.config import get_settings
from docsmind.factory import build_pipeline

DEFAULT_QUESTION = "How do black holes form?"


def main() -> None:
    settings = get_settings()
    index_meta = settings.index_dir / "meta.json"
    if not index_meta.exists():
        print("No index found — building it first.\n")
        from scripts.ingest import main as ingest_main

        ingest_main()
        print()

    question = sys.argv[1] if len(sys.argv) > 1 else DEFAULT_QUESTION
    pipeline = build_pipeline(settings)

    print(f"Q: {question}\n")
    response = pipeline.query(question)

    print(f"A ({response.model}, {response.latency_ms:.0f} ms, "
          f"grounded={response.grounded}):\n")
    print(response.answer)
    print("\nCitations:")
    if not response.citations:
        print("  (none)")
    for c in response.citations:
        print(f"  [{c.marker}] {c.source} (score={c.score}) — {c.snippet[:100]}...")


if __name__ == "__main__":
    main()
