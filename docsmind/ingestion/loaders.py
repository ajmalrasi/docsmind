"""Document loading via LlamaIndex.

We use LlamaIndex's SimpleDirectoryReader for ingestion specifically — it handles
many file types and attaches file-path metadata we later turn into citations.
"""

from __future__ import annotations

from pathlib import Path

from llama_index.core import SimpleDirectoryReader
from llama_index.core.schema import Document

# Technical/ML documentation file types we care about.
SUPPORTED_EXTS = [".md", ".txt", ".rst", ".py"]


def load_documents(data_dir: Path | str) -> list[Document]:
    """Recursively load all supported documents under ``data_dir``."""
    data_dir = Path(data_dir)
    if not data_dir.exists():
        raise FileNotFoundError(f"Data directory does not exist: {data_dir}")

    reader = SimpleDirectoryReader(
        input_dir=str(data_dir),
        recursive=True,
        required_exts=SUPPORTED_EXTS,
    )
    return reader.load_data()
