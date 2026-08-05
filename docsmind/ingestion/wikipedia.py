"""Load reproducible Wikipedia article snapshots as LlamaIndex documents."""

from __future__ import annotations

import json
from pathlib import Path

from llama_index.core.schema import Document


WIKIPEDIA_JSONL_SUFFIX = ".wikipedia.jsonl"


def load_wikipedia_documents(path: Path | str) -> list[Document]:
    """Return one document per article section with revision-aware provenance."""
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

            title = str(record.get("title", "")).strip()
            source_url = str(record.get("source_url", "")).strip()
            sections = record.get("sections")
            if not title or not source_url or not isinstance(sections, list):
                raise ValueError(
                    f"Missing title, source_url, or sections on {path}:{line_number}"
                )

            page_id = record.get("page_id")
            revision_id = record.get("revision_id")
            for section_index, section in enumerate(sections):
                if not isinstance(section, dict):
                    raise ValueError(
                        f"Invalid section on {path}:{line_number}:{section_index}"
                    )
                section_title = str(section.get("title", "Lead")).strip() or "Lead"
                text = str(section.get("text", "")).strip()
                if not text:
                    continue

                metadata = {
                    "source_type": "wikipedia",
                    "title": title,
                    "requested_title": str(record.get("requested_title", title)),
                    "section": section_title,
                    "source_url": source_url,
                    "page_id": page_id,
                    "revision_id": revision_id,
                    "revision_timestamp": str(
                        record.get("revision_timestamp", "")
                    ),
                    "fetched_at": str(record.get("fetched_at", "")),
                    "language": str(record.get("language", "en")),
                    "license": str(record.get("license", "CC BY-SA 4.0")),
                }
                stable_id = f"wikipedia:{page_id}:{revision_id}:{section_index}"
                documents.append(
                    Document(
                        id_=stable_id,
                        text=f"Article: {title}\nSection: {section_title}\n\n{text}",
                        metadata=metadata,
                    )
                )

    return documents
