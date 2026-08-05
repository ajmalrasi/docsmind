from docsmind.config import Settings
from docsmind.factory import build_embedder
from docsmind.index.embeddings import (
    BedrockCohereEmbedder,
    BedrockTitanEmbedder,
    TEIEmbedder,
)


def test_defaults():
    s = Settings(_env_file=None)
    assert s.cloud_llm_model == "claude-opus-4-8"
    assert s.index_type == "flat"
    assert s.top_k == 4
    assert s.embedding_provider == "local"
    assert s.embed_device == ""
    assert s.bedrock_embed_model == "amazon.titan-embed-text-v2:0"
    assert s.bedrock_embed_dimensions == 1024
    assert s.vector_backend == "faiss"
    assert s.opensearch_index == "docsmind-chunks"
    assert s.aws_region == "us-east-1"
    assert s.aws_profile == "docsmind"
    assert s.llm_primary_provider == "vllm"
    assert s.llm_fallback_provider == "cloud"
    assert s.vllm_api_key is None


def test_env_override(monkeypatch):
    monkeypatch.setenv("DOCSMIND_TOP_K", "9")
    monkeypatch.setenv("DOCSMIND_INDEX_TYPE", "hnsw")
    s = Settings(_env_file=None)
    assert s.top_k == 9
    assert s.index_type == "hnsw"


def test_opensearch_env_overrides(monkeypatch):
    monkeypatch.setenv("DOCSMIND_VECTOR_BACKEND", "opensearch")
    monkeypatch.setenv(
        "DOCSMIND_OPENSEARCH_ENDPOINT",
        "https://example.aoss.us-east-1.on.aws",
    )
    monkeypatch.setenv("DOCSMIND_OPENSEARCH_INDEX", "test-chunks")
    monkeypatch.setenv("DOCSMIND_AWS_PROFILE", "test-profile")

    s = Settings(_env_file=None)

    assert s.vector_backend == "opensearch"
    assert s.opensearch_endpoint.endswith(".on.aws")
    assert s.opensearch_index == "test-chunks"
    assert s.aws_profile == "test-profile"


def test_bedrock_embedding_env_overrides(monkeypatch):
    monkeypatch.setenv("DOCSMIND_EMBEDDING_PROVIDER", "bedrock")
    monkeypatch.setenv("DOCSMIND_BEDROCK_EMBED_DIMENSIONS", "512")
    monkeypatch.setenv("DOCSMIND_BEDROCK_EMBED_BATCH_SIZE", "48")
    monkeypatch.setenv("DOCSMIND_BEDROCK_EMBED_CONCURRENCY", "4")
    monkeypatch.setenv("DOCSMIND_BEDROCK_EMBED_REGION", "us-east-2")

    s = Settings(_env_file=None)

    assert s.embedding_provider == "bedrock"
    assert s.bedrock_embed_dimensions == 512
    assert s.bedrock_embed_batch_size == 48
    assert s.bedrock_embed_concurrency == 4
    assert s.bedrock_embed_region == "us-east-2"

    embedder = build_embedder(s)
    assert isinstance(embedder, BedrockTitanEmbedder)
    assert embedder.dim == 512
    assert embedder.model_name == "amazon.titan-embed-text-v2:0"
    assert embedder._region == "us-east-2"
    assert embedder._concurrency == 4


def test_factory_selects_cohere_for_cohere_model_id():
    settings = Settings(
        _env_file=None,
        embedding_provider="bedrock",
        bedrock_embed_model="cohere.embed-v4:0",
    )

    assert isinstance(build_embedder(settings), BedrockCohereEmbedder)


def test_factory_selects_tei_provider():
    settings = Settings(
        _env_file=None,
        embedding_provider="tei",
        tei_base_url="http://embedding.internal:8080",
        tei_embed_batch_size=4,
    )

    embedder = build_embedder(settings)
    assert isinstance(embedder, TEIEmbedder)
    assert embedder.model_name == "BAAI/bge-m3"
    assert embedder.dim == 1024
    assert embedder._batch_size == 4


def test_vllm_secret_and_router_env_overrides(monkeypatch):
    monkeypatch.setenv("DOCSMIND_LLM_PROVIDER", "router")
    monkeypatch.setenv("DOCSMIND_VLLM_API_KEY", "do-not-print-this")

    s = Settings(_env_file=None)

    assert s.llm_provider == "router"
    assert s.vllm_api_key is not None
    assert s.vllm_api_key.get_secret_value() == "do-not-print-this"
    assert "do-not-print-this" not in repr(s)
