"""Composition root.

One place that builds and wires components from Settings, reused by the ingest
script, the demo, and the FastAPI app.
"""

from __future__ import annotations

from docsmind.config import Settings
from docsmind.index.base import VectorStore
from docsmind.index.embeddings import Embedder
from docsmind.llm.base import LLMClient
from docsmind.llm.cloud_client import CloudLLMClient
from docsmind.llm.local_client import LocalLLMClient
from docsmind.llm.router import LLMRouter
from docsmind.llm.vllm_client import VLLMClient
from docsmind.pipeline import RAGPipeline
from docsmind.retrieval.reranker import CrossEncoderReranker
from docsmind.retrieval.retriever import HybridRetriever, Retriever


def build_embedder(settings: Settings) -> Embedder:
    return Embedder(settings.embed_model, device=settings.embed_device or None)


def _qdrant_path(settings: Settings):
    """Local persistence dir for Qdrant when no server URL is configured."""
    return settings.index_dir / "qdrant"


def new_store(settings: Settings, dim: int) -> VectorStore:
    """A fresh, empty store for ingestion, configured per backend + index type."""
    if settings.vector_backend == "opensearch":
        from docsmind.index.opensearch_store import OpenSearchVectorStore

        return OpenSearchVectorStore(
            dim=dim,
            endpoint=settings.opensearch_endpoint,
            index_name=settings.opensearch_index,
            region=settings.aws_region,
            profile_name=settings.aws_profile,
            bulk_size=settings.opensearch_bulk_size,
            page_size=settings.opensearch_page_size,
            request_timeout=settings.opensearch_request_timeout,
            max_retries=settings.opensearch_max_retries,
            recreate=True,
        )
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
    if settings.vector_backend == "faiss":
        # Import after embedding on ingestion paths. On macOS, importing FAISS's
        # native runtime before PyTorch can segfault sentence-transformer encode.
        from docsmind.index.faiss_store import FaissVectorStore

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
    raise ValueError(
        f"Unknown vector_backend={settings.vector_backend!r}; "
        "use faiss, qdrant, or opensearch."
    )


def load_store(settings: Settings) -> VectorStore:
    """Load a persisted store from disk (or reconnect to the Qdrant collection)."""
    if settings.vector_backend == "opensearch":
        from docsmind.index.opensearch_store import OpenSearchVectorStore

        return OpenSearchVectorStore.load(
            settings.index_dir,
            endpoint=settings.opensearch_endpoint or None,
            index_name=settings.opensearch_index,
            region=settings.aws_region,
            profile_name=settings.aws_profile,
        )
    if settings.vector_backend == "qdrant":
        from docsmind.index.qdrant_store import QdrantVectorStore

        return QdrantVectorStore.load(settings.index_dir)
    if settings.vector_backend == "faiss":
        from docsmind.index.faiss_store import FaissVectorStore

        return FaissVectorStore.load(settings.index_dir)
    raise ValueError(
        f"Unknown vector_backend={settings.vector_backend!r}; "
        "use faiss, qdrant, or opensearch."
    )


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


def _build_llm_provider(settings: Settings, provider: str) -> LLMClient:
    """Build one provider without applying routing policy."""
    if provider == "vllm":
        api_key = (
            settings.vllm_api_key.get_secret_value()
            if settings.vllm_api_key is not None
            else None
        )
        return VLLMClient(
            settings.vllm_model,
            settings.vllm_base_url,
            api_key=api_key,
            timeout=settings.vllm_timeout_seconds,
        )
    if provider == "local":
        return LocalLLMClient(settings.local_llm_model, settings.ollama_base_url)
    if provider == "cloud":
        return CloudLLMClient(settings.cloud_llm_model)
    raise ValueError(f"Unknown LLM provider: {provider!r}")


def build_llm(settings: Settings) -> LLMClient:
    """Build one provider or an availability-based primary/fallback router."""
    if settings.llm_provider == "router":
        if settings.llm_primary_provider == settings.llm_fallback_provider:
            raise ValueError("LLM router primary and fallback providers must differ")
        primary = _build_llm_provider(settings, settings.llm_primary_provider)
        fallback = _build_llm_provider(settings, settings.llm_fallback_provider)
        return LLMRouter(primary, fallback)
    return _build_llm_provider(settings, settings.llm_provider)


def build_pipeline(settings: Settings) -> RAGPipeline:
    """Load the index and assemble the full query pipeline."""
    embedder = build_embedder(settings)
    # Load the PyTorch-backed embedder before a native vector-store runtime.
    # FAISS-first import order can segfault sentence-transformer encode on macOS.
    _ = embedder.dim
    store = load_store(settings)
    retriever = build_retriever(settings, embedder, store)
    llm = build_llm(settings)
    return RAGPipeline(retriever, llm, settings)
