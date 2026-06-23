"""Dense retriever.

Phase 1 is pure dense (embedding) retrieval. Phase 3 adds BM25 + fusion + a
cross-encoder reranker behind this same ``retrieve`` method.
"""

from __future__ import annotations

from docsmind.index.base import VectorStore
from docsmind.index.embeddings import Embedder
from docsmind.schemas import SearchResult


class Retriever:
    def __init__(self, embedder: Embedder, store: VectorStore) -> None:
        self._embedder = embedder
        self._store = store

    def retrieve(self, question: str, top_k: int) -> list[SearchResult]:
        query_vec = self._embedder.encode([question])[0]
        return self._store.search(query_vec, top_k)
