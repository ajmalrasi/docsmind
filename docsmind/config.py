"""Central configuration. All settings are overridable via env vars or a .env file.

Every component (vector store, LLM, embedder) reads from this single Settings
object so the system is reconfigurable without touching code.
"""

from __future__ import annotations

from pathlib import Path
from typing import Literal

from pydantic import SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="DOCSMIND_",
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # Generation. "router" tries llm_primary_provider and falls back only when
    # that provider has a transient availability failure.
    llm_provider: Literal["cloud", "local", "vllm", "router"] = "cloud"
    llm_primary_provider: Literal["cloud", "local", "vllm"] = "vllm"
    llm_fallback_provider: Literal["cloud", "local", "vllm"] = "cloud"

    # Cloud LLM. The Anthropic SDK reads ANTHROPIC_API_KEY itself, so the key is
    # never stored on this object.
    cloud_llm_model: str = "claude-opus-4-8"

    # Local LLM (Ollama). Used when llm_provider == "local".
    local_llm_model: str = "deepseek-coder-v2:16b-lite-instruct-q4_K_M"
    ollama_base_url: str = "http://localhost:11434"

    # vLLM. The concrete checkpoint and host can change independently while the
    # application keeps the stable model alias "openclaw".
    vllm_model: str = "openclaw"
    vllm_base_url: str = "http://localhost:11434/v1"
    # Kept as SecretStr so settings/log representations cannot reveal it.
    vllm_api_key: SecretStr | None = None
    vllm_timeout_seconds: float = 300.0

    max_tokens: int = 1024

    # Self-hosted embedding model.
    embed_model: str = "BAAI/bge-small-en-v1.5"
    # Empty means sentence-transformers auto-selects a device. On an 8 GB GPU
    # dedicated to vLLM, set this to "cpu" so retrieval and generation coexist.
    embed_device: str = ""

    # Vector store backend. "faiss" (in-process, file-persisted) is the default;
    # "qdrant" (Phase 2b) runs the same VectorStore contract against a Qdrant
    # collection — local-path persisted by default, or a server when qdrant_url
    # is set. The retrieval code never sees the difference.
    vector_backend: str = "faiss"

    # Qdrant (Phase 2b). When qdrant_url is empty, Qdrant persists to a local
    # path under index_dir (no server needed); set it to e.g.
    # "http://localhost:6333" to use a Dockerized server on beast.
    qdrant_url: str = ""
    qdrant_collection: str = "docsmind"
    qdrant_hnsw_m: int = 16  # Qdrant's built-in HNSW graph: edges per node

    # Vector index type (FAISS only). "flat" (exact) is the default and the right
    # choice for a small corpus. Phase 2 adds the approximate types: "ivf",
    # "hnsw", "ivfpq".
    index_type: str = "flat"

    # Approximate-index tuning (only used when index_type != "flat"). These are
    # the speed/recall/memory dials the Phase 2 benchmark sweeps.
    ivf_nlist: int = 100  # IVF/IVFPQ: number of k-means cells
    ivf_nprobe: int = 8  # IVF/IVFPQ: cells probed per query (recall vs speed)
    hnsw_m: int = 32  # HNSW: edges per node (recall vs memory)
    hnsw_ef_construction: int = 200  # HNSW: build-time search breadth
    hnsw_ef_search: int = 64  # HNSW: query-time search breadth (recall vs speed)
    pq_m: int = 48  # IVFPQ: sub-quantizers (must divide embed dim, 384)
    pq_nbits: int = 8  # IVFPQ: bits per code (8 => 256 centroids per sub-vector)

    # Paths
    data_dir: Path = Path("data/sample_docs")
    index_dir: Path = Path("data/index")

    # Retrieval / chunking
    top_k: int = 4
    chunk_size: int = 512
    chunk_overlap: int = 64

    # WhatsApp conversation-window controls. These are used only when data_dir
    # contains an anonymized *.whatsapp.jsonl corpus.
    whatsapp_window_minutes: int = 10
    whatsapp_max_messages: int = 20

    # Retrieval mode (Phase 3). "dense" = pure embedding search (Phase 1).
    # "hybrid" = dense + BM25 fused with Reciprocal Rank Fusion, optionally
    # reranked by a cross-encoder. Hybrid is the default because BM25 fusion
    # needs no model and recovers exact-keyword matches dense retrieval misses.
    retrieval_mode: str = "hybrid"

    # How many candidates each retriever (dense, BM25) contributes before fusion
    # and reranking. Larger = better recall into the reranker, slower.
    candidate_k: int = 20
    # RRF constant: dampens the influence of top ranks. 60 is the canonical value
    # from the original RRF paper; rarely needs tuning.
    fusion_k: int = 60

    # Cross-encoder reranker (Phase 3). Off by default: it downloads a model and
    # is best run on the beast GPU. Turn on with DOCSMIND_RERANK_ENABLED=true.
    rerank_enabled: bool = False
    reranker_model: str = "cross-encoder/ms-marco-MiniLM-L-6-v2"


def get_settings() -> Settings:
    """Return a fresh Settings instance (reads env / .env at call time)."""
    return Settings()
