"""Load BRISKODA forum-post JSONL records as LlamaIndex documents."""

from __future__ import annotations

import json
from pathlib import Path

from llama_index.core.schema import Document

BRISKODA_JSONL_SUFFIX = ".briskoda.jsonl"


def load_briskoda_documents(path: Path | str) -> list[Document]:
    """Return one document per forum post, preserving citation metadata."""
    path = Path(path)
    documents: list[Document] = []

    with path.open(encoding="utf-8") as handle:
        for line_number, raw_line in enumerate(handle, start=1):
            if not raw_line.strip():
                continue
            try:
                record = json.loads(raw_line)
            except json.JSONDecodeError as exc:
                raise ValueError(f"Invalid JSON on {path}:{line_number}") from exc

            text = str(record.get("text", "")).strip()
            topic_title = str(record.get("topic_title", "")).strip()
            if not text or not topic_title:
                raise ValueError(
                    f"Missing topic_title or text on {path}:{line_number}"
                )

            metadata = {
                "source_type": "briskoda",
                "topic_id": str(record.get("topic_id", "")),
                "post_id": str(record.get("post_id", "")),
                "topic_title": topic_title,
                "topic_url": str(record.get("topic_url", "")),
                "source_url": str(record.get("post_url", "")),
                "author": str(record.get("author", "")),
                "posted_at": str(record.get("posted_at", "")),
                "post_number": record.get("post_number"),
            }
            documents.append(
                Document(
                    text=f"Topic: {topic_title}\n\n{text}",
                    metadata=metadata,
                )
            )

    return documents
