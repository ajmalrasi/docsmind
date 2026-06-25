"""Central configuration. All settings are overridable via env vars or a .env file.

Every component (vector store, LLM, embedder) reads from this single Settings
object so the system is reconfigurable without touching code.
"""

from __future__ import annotations

from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="DOCSMIND_",
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # Generation. Provider selects the LLM backend: "cloud" (Anthropic) or
    # "local" (self-hosted via Ollama). This is the Phase 4 router seam.
    llm_provider: str = "cloud"

    # Cloud LLM. The Anthropic SDK reads ANTHROPIC_API_KEY itself, so the key is
    # never stored on this object.
    cloud_llm_model: str = "claude-opus-4-8"

    # Local LLM (Ollama). Used when llm_provider == "local".
    local_llm_model: str = "deepseek-coder-v2:16b-lite-instruct-q4_K_M"
    ollama_base_url: str = "http://localhost:11434"

    max_tokens: int = 1024

    # Self-hosted embedding model.
    embed_model: str = "BAAI/bge-small-en-v1.5"

    # Vector store. Phase 1 supports "flat"; later phases add ivf/hnsw/pq + Qdrant.
    index_type: str = "flat"

    # Paths
    data_dir: Path = Path("data/sample_docs")
    index_dir: Path = Path("data/index")

    # Retrieval / chunking
    top_k: int = 4
    chunk_size: int = 512
    chunk_overlap: int = 64


def get_settings() -> Settings:
    """Return a fresh Settings instance (reads env / .env at call time)."""
    return Settings()
