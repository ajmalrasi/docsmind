"""Document loading via LlamaIndex.

We use LlamaIndex's SimpleDirectoryReader for ingestion specifically — it handles
many file types and attaches file-path metadata we later turn into citations.
"""

from __future__ import annotations

from pathlib import Path

from llama_index.core import SimpleDirectoryReader
from llama_index.core.schema import Document

from docsmind.ingestion.briskoda import (
    BRISKODA_JSONL_SUFFIX,
    load_briskoda_documents,
)
from docsmind.ingestion.whatsapp import (
    WHATSAPP_JSONL_SUFFIX,
    load_whatsapp_documents,
)

# Technical/ML documentation file types we care about.
SUPPORTED_EXTS = [".md", ".txt", ".rst", ".py"]


def load_documents(
    data_dir: Path | str,
    *,
    whatsapp_window_minutes: int = 10,
    whatsapp_max_messages: int = 20,
) -> list[Document]:
    """Recursively load all supported documents under ``data_dir``."""
    data_dir = Path(data_dir)
    if not data_dir.exists():
        raise FileNotFoundError(f"Data directory does not exist: {data_dir}")

    regular_files = sorted(
        path
        for path in data_dir.rglob("*")
        if path.is_file() and path.suffix.lower() in SUPPORTED_EXTS
    )
    whatsapp_files = sorted(data_dir.rglob(f"*{WHATSAPP_JSONL_SUFFIX}"))
    briskoda_files = sorted(data_dir.rglob(f"*{BRISKODA_JSONL_SUFFIX}"))

    documents: list[Document] = []
    if regular_files:
        reader = SimpleDirectoryReader(input_files=[str(path) for path in regular_files])
        documents.extend(reader.load_data())

    for path in whatsapp_files:
        documents.extend(
            load_whatsapp_documents(
                path,
                window_minutes=whatsapp_window_minutes,
                max_messages=whatsapp_max_messages,
            )
        )

    for path in briskoda_files:
        documents.extend(load_briskoda_documents(path))

    if not documents:
        raise ValueError(f"No supported documents found under: {data_dir}")
    return documents
