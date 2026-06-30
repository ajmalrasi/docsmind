"""Composition root.

One place that builds and wires components from Settings, reused by the ingest
script, the demo, and the FastAPI app.
"""

from __future__ import annotations

from docsmind.config import Settings
from docsmind.index.base import VectorStore
from docsmind.index.embeddings import Embedder
from docsmind.index.faiss_store import FaissVectorStore
from docsmind.llm.base import LLMClient
from docsmind.llm.cloud_client import CloudLLMClient
from docsmind.llm.local_client import LocalLLMClient
from docsmind.pipeline import RAGPipeline
from docsmind.retrieval.reranker import CrossEncoderReranker
from docsmind.retrieval.retriever import HybridRetriever, Retriever


def build_embedder(settings: Settings) -> Embedder:
    return Embedder(settings.embed_model)


def _qdrant_path(settings: Settings):
    """Local persistence dir for Qdrant when no server URL is configured."""
    return settings.index_dir / "qdrant"


def new_store(settings: Settings, dim: int) -> VectorStore:
    """A fresh, empty store for ingestion, configured per backend + index type."""
    if settings.vector_backend == "qdrant":
        from docsmind.index.qdrant_store import QdrantVectorStore

        return QdrantVectorStore(
            dim=dim,
            collection=settings.qdrant_collection,
            url=settings.qdrant_url,
            path=None if settings.qdrant_url else _qdrant_path(settings),
            hnsw_m=settings.qdrant_hnsw_m,
            recreate=True,
        )
    return FaissVectorStore(
        dim=dim,
        index_type=settings.index_type,
        nlist=settings.ivf_nlist,
        nprobe=settings.ivf_nprobe,
        hnsw_m=settings.hnsw_m,
        hnsw_ef_construction=settings.hnsw_ef_construction,
        hnsw_ef_search=settings.hnsw_ef_search,
        pq_m=settings.pq_m,
        pq_nbits=settings.pq_nbits,
    )


def load_store(settings: Settings) -> VectorStore:
    """Load a persisted store from disk (or reconnect to the Qdrant collection)."""
    if settings.vector_backend == "qdrant":
        from docsmind.index.qdrant_store import QdrantVectorStore

        return QdrantVectorStore.load(settings.index_dir)
    return FaissVectorStore.load(settings.index_dir)


def build_retriever(settings: Settings, embedder: Embedder, store: VectorStore):
    """Select dense vs. hybrid retrieval per settings.retrieval_mode."""
    if settings.retrieval_mode == "hybrid":
        reranker = (
            CrossEncoderReranker(settings.reranker_model)
            if settings.rerank_enabled
            else None
        )
        return HybridRetriever(
            embedder,
            store,
            candidate_k=settings.candidate_k,
            fusion_k=settings.fusion_k,
            reranker=reranker,
        )
    return Retriever(embedder, store)


def build_llm(settings: Settings) -> LLMClient:
    """Select the generation backend based on settings.llm_provider."""
    if settings.llm_provider == "local":
        return LocalLLMClient(settings.local_llm_model, settings.ollama_base_url)
    return CloudLLMClient(settings.cloud_llm_model)


def build_pipeline(settings: Settings) -> RAGPipeline:
    """Load the index and assemble the full query pipeline."""
    embedder = build_embedder(settings)
    store = load_store(settings)
    retriever = build_retriever(settings, embedder, store)
    llm = build_llm(settings)
    return RAGPipeline(retriever, llm, settings)
