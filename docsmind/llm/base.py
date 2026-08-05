"""LLM client interface.

All providers implement this contract. Phase 4's LLMRouter selects between a
self-hosted SLM and a cloud fallback without coupling generation to the corpus.
"""

from __future__ import annotations

from abc import ABC, abstractmethod


class LLMClient(ABC):
    model: str

    @abstractmethod
    def generate(self, system: str, prompt: str, max_tokens: int) -> str:
        """Return the model's text completion for a system + user prompt."""


class LLMError(RuntimeError):
    """Base error for failures at the Generate stage."""


class LLMUnavailableError(LLMError):
    """A transient provider failure that may safely trigger fallback."""


class LLMRequestError(LLMError):
    """A non-transient request/configuration failure that needs intervention."""
