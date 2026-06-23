from docsmind.config import Settings


def test_defaults():
    s = Settings(_env_file=None)
    assert s.cloud_llm_model == "claude-opus-4-8"
    assert s.index_type == "flat"
    assert s.top_k == 4


def test_env_override(monkeypatch):
    monkeypatch.setenv("DOCSMIND_TOP_K", "9")
    monkeypatch.setenv("DOCSMIND_INDEX_TYPE", "hnsw")
    s = Settings(_env_file=None)
    assert s.top_k == 9
    assert s.index_type == "hnsw"
