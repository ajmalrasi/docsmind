"""End-to-end demo: ingest if needed, then run a sample query with citations.

Usage: python -m scripts.demo ["your question"]
"""

from __future__ import annotations

import sys

from docsmind.config import get_settings
from docsmind.factory import build_pipeline

DEFAULT_DOCUMENT_QUESTION = "How do black holes form?"
DEFAULT_WHATSAPP_QUESTION = (
    "What symptoms were mentioned when someone asked if it was clutch slip?"
)


def main() -> None:
    settings = get_settings()
    index_meta = settings.index_dir / "meta.json"
    if not index_meta.exists():
        print("No index found — building it first.\n")
        from scripts.ingest import main as ingest_main

        ingest_main()
        print()

    has_whatsapp_corpus = any(settings.data_dir.rglob("*.whatsapp.jsonl"))
    default_question = (
        DEFAULT_WHATSAPP_QUESTION if has_whatsapp_corpus else DEFAULT_DOCUMENT_QUESTION
    )
    question = sys.argv[1] if len(sys.argv) > 1 else default_question
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
