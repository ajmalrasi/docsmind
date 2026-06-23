"""Composition root.

One place that builds and wires components from Settings, reused by the ingest
script, the demo, and the FastAPI app.
"""

from __future__ import annotations

from docsmind.config import Settings
from docsmind.index.embeddings import Embedder
from docsmind.index.faiss_store import FaissVectorStore
from docsmind.llm.cloud_client import CloudLLMClient
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


def build_pipeline(settings: Settings) -> RAGPipeline:
    """Load the index and assemble the full query pipeline."""
    embedder = build_embedder(settings)
    store = load_store(settings)
    retriever = Retriever(embedder, store)
    llm = CloudLLMClient(settings.cloud_llm_model)
    return RAGPipeline(retriever, llm, settings)
