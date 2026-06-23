"""Chunking via LlamaIndex node parsers.

Phase 1 uses sentence-aware splitting. Later phases can swap in structural /
code-aware splitters behind this same function signature.
"""

from __future__ import annotations

from llama_index.core.node_parser import SentenceSplitter
from llama_index.core.schema import Document

from docsmind.schemas import Chunk


def chunk_documents(
    documents: list[Document],
    chunk_size: int = 512,
    chunk_overlap: int = 64,
) -> list[Chunk]:
    """Split documents into overlapping chunks, preserving source provenance."""
    splitter = SentenceSplitter(chunk_size=chunk_size, chunk_overlap=chunk_overlap)
    nodes = splitter.get_nodes_from_documents(documents)

    chunks: list[Chunk] = []
    for node in nodes:
        source = (
            node.metadata.get("file_name")
            or node.metadata.get("file_path")
            or "unknown"
        )
        chunks.append(
            Chunk(
                id=node.node_id,
                text=node.get_content(),
                source=source,
                metadata=dict(node.metadata),
            )
        )
    return chunks
