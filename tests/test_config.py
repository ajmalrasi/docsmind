from docsmind.config import Settings


def test_defaults():
    s = Settings(_env_file=None)
    assert s.cloud_llm_model == "claude-opus-4-8"
    assert s.index_type == "flat"
    assert s.top_k == 4
    assert s.embed_device == ""
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


def test_vllm_secret_and_router_env_overrides(monkeypatch):
    monkeypatch.setenv("DOCSMIND_LLM_PROVIDER", "router")
    monkeypatch.setenv("DOCSMIND_VLLM_API_KEY", "do-not-print-this")

    s = Settings(_env_file=None)

    assert s.llm_provider == "router"
    assert s.vllm_api_key is not None
    assert s.vllm_api_key.get_secret_value() == "do-not-print-this"
    assert "do-not-print-this" not in repr(s)
