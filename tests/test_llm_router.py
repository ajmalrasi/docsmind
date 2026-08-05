import pytest

from docsmind.config import Settings
from docsmind.factory import build_llm
from docsmind.llm.base import (
    LLMClient,
    LLMRequestError,
    LLMUnavailableError,
)
from docsmind.llm.router import LLMRouter


class StubLLM(LLMClient):
    def __init__(self, model: str, outcome: str | Exception):
        self.model = model
        self.outcome = outcome
        self.calls = 0

    def generate(self, system: str, prompt: str, max_tokens: int) -> str:
        self.calls += 1
        if isinstance(self.outcome, Exception):
            raise self.outcome
        return self.outcome


def test_router_uses_primary_when_available():
    primary = StubLLM("self-hosted", "local answer")
    fallback = StubLLM("cloud", "cloud answer")
    router = LLMRouter(primary, fallback)

    assert router.generate("system", "prompt", 10) == "local answer"
    assert router.model == "self-hosted"
    assert fallback.calls == 0


def test_router_falls_back_on_transient_unavailability():
    primary = StubLLM("self-hosted", LLMUnavailableError("timeout"))
    fallback = StubLLM("cloud", "cloud answer")
    router = LLMRouter(primary, fallback)

    assert router.generate("system", "prompt", 10) == "cloud answer"
    assert router.model == "cloud"
    assert primary.calls == 1
    assert fallback.calls == 1


def test_router_does_not_hide_auth_or_bad_request_failures():
    primary = StubLLM("self-hosted", LLMRequestError("HTTP 401"))
    fallback = StubLLM("cloud", "cloud answer")
    router = LLMRouter(primary, fallback)

    with pytest.raises(LLMRequestError):
        router.generate("system", "prompt", 10)
    assert fallback.calls == 0


def test_factory_builds_corpus_independent_router():
    settings = Settings(
        _env_file=None,
        llm_provider="router",
        llm_primary_provider="vllm",
        llm_fallback_provider="local",
        vllm_api_key="secret-token",
    )

    llm = build_llm(settings)

    assert isinstance(llm, LLMRouter)
    assert llm.primary.model == settings.vllm_model
    assert llm.fallback.model == settings.local_llm_model
    assert "secret-token" not in repr(settings)


def test_factory_rejects_same_primary_and_fallback():
    settings = Settings(
        _env_file=None,
        llm_provider="router",
        llm_primary_provider="vllm",
        llm_fallback_provider="vllm",
    )

    with pytest.raises(ValueError, match="must differ"):
        build_llm(settings)
