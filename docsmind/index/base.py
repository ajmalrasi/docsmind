"""The pluggable VectorStore interface.

Every backend (FAISS in Phase 1; Qdrant in Phase 2b) implements this contract so
retrieval code is backend-agnostic. The hybrid retriever (Phase 3) also reads the
stored ``chunks`` to build its in-memory BM25 index, so that is part of the
contract too.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from pathlib import Path

import numpy as np

from docsmind.schemas import Chunk, SearchResult


class VectorStore(ABC):
    @abstractmethod
    def add(self, chunks: list[Chunk], embeddings: np.ndarray) -> None:
        """Index ``chunks`` with their corresponding (N, dim) embedding matrix."""

    @abstractmethod
    def search(self, query_embedding: np.ndarray, top_k: int) -> list[SearchResult]:
        """Return the ``top_k`` most similar chunks to a single query vector."""

    @abstractmethod
    def save(self, path: Path | str) -> None:
        """Persist the index and chunk metadata to ``path``."""

    @property
    @abstractmethod
    def size(self) -> int:
        """Number of indexed vectors."""

    @property
    @abstractmethod
    def index_type(self) -> str:
        """Identifier for the underlying index (e.g. 'flat')."""

    @property
    @abstractmethod
    def chunks(self) -> list[Chunk]:
        """All indexed chunks, in insertion order. Used by the BM25 retriever."""
