"""Composition root.

One place that builds and wires components from Settings, reused by the ingest
script, the demo, and the FastAPI app.
"""

from __future__ import annotations

from docsmind.config import Settings
from docsmind.index.embeddings import Embedder
from docsmind.index.faiss_store import FaissVectorStore
from docsmind.llm.base import LLMClient
from docsmind.llm.cloud_client import CloudLLMClient
from docsmind.llm.local_client import LocalLLMClient
from docsmind.pipeline import RAGPipeline
from docsmind.retrieval.retriever import Retriever


def build_embedder(settings: Settings) -> Embedder:
    return Embedder(settings.embed_model)


def new_store(settings: Settings, dim: int) -> FaissVectorStore:
    """A fresh, empty store for ingestion."""
    return FaissVectorStore(dim=dim, index_type=settings.index_type)


def load_store(settings: Settings) -> FaissVectorStore:
    """Load a persisted store from disk."""
    return FaissVectorStore.load(settings.index_dir)


def build_llm(settings: Settings) -> LLMClient:
    """Select the generation backend based on settings.llm_provider."""
    if settings.llm_provider == "local":
        return LocalLLMClient(settings.local_llm_model, settings.ollama_base_url)
    return CloudLLMClient(settings.cloud_llm_model)


def build_pipeline(settings: Settings) -> RAGPipeline:
    """Load the index and assemble the full query pipeline."""
    embedder = build_embedder(settings)
    store = load_store(settings)
    retriever = Retriever(embedder, store)
    llm = build_llm(settings)
    return RAGPipeline(retriever, llm, settings)
