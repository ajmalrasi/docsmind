"""Retrievers.

Two implementations sit behind one ``retrieve(question, top_k)`` method, so the
pipeline is agnostic to which is wired in (selected by ``retrieval_mode``):

    Retriever         Phase 1 — pure dense (embedding) search.
    HybridRetriever   Phase 3 — dense + BM25, fused with RRF, then optionally
                      reranked by a cross-encoder.

The hybrid flow, stage by stage:

    question
       ├─ embed → dense search ──┐
       └─ BM25 search ───────────┤
                                 ▼
                       Reciprocal Rank Fusion        (merge the two rankings)
                                 ▼
                       cross-encoder rerank           (optional, top candidates)
                                 ▼
                       top_k SearchResults → pipeline
"""

from __future__ import annotations

from docsmind.index.base import VectorStore
from docsmind.index.embeddings import Embedder
from docsmind.retrieval.bm25 import BM25Index
from docsmind.retrieval.fusion import reciprocal_rank_fusion
from docsmind.retrieval.reranker import CrossEncoderReranker
from docsmind.schemas import SearchResult


class Retriever:
    """Phase 1 dense retriever: embed the query, search the vector store."""

    def __init__(self, embedder: Embedder, store: VectorStore) -> None:
        self._embedder = embedder
        self._store = store

    def retrieve(self, question: str, top_k: int) -> list[SearchResult]:
        query_vec = self._embedder.encode([question])[0]
        return self._store.search(query_vec, top_k)


class HybridRetriever:
    """Phase 3 hybrid retriever: dense + BM25 → RRF → optional rerank."""

    def __init__(
        self,
        embedder: Embedder,
        store: VectorStore,
        *,
        candidate_k: int = 20,
        fusion_k: int = 60,
        reranker: CrossEncoderReranker | None = None,
    ) -> None:
        self._embedder = embedder
        self._store = store
        self._bm25 = BM25Index(store.chunks)
        self._candidate_k = candidate_k
        self._fusion_k = fusion_k
        self._reranker = reranker

    def retrieve(self, question: str, top_k: int) -> list[SearchResult]:
        # 1. Two independent retrievals, each pulling a wide candidate set.
        query_vec = self._embedder.encode([question])[0]
        dense = self._store.search(query_vec, self._candidate_k)
        sparse = self._bm25.search(question, self._candidate_k)

        # 2. Fuse the two rankings into one ordered candidate list.
        fused = reciprocal_rank_fusion([dense, sparse], k=self._fusion_k)

        # 3. Rerank the candidates if a cross-encoder is wired in; otherwise the
        #    fused order already reflects both signals — just trim to top_k.
        if self._reranker is not None:
            return self._reranker.rerank(question, fused, top_k)
        return fused[:top_k]
