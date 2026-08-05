"""Availability-based model routing at the Generate stage.

The router is deliberately independent of ingestion and retrieval. It receives
the same assembled prompt as any other ``LLMClient``, tries the configured
primary provider, and uses the fallback only for transient availability errors.
"""

from __future__ import annotations

from contextvars import ContextVar
import logging

from docsmind.llm.base import LLMClient, LLMUnavailableError

logger = logging.getLogger(__name__)


class LLMRouter(LLMClient):
    """Use a primary model and fall back when that provider is unavailable."""

    def __init__(self, primary: LLMClient, fallback: LLMClient) -> None:
        if primary is fallback:
            raise ValueError("Primary and fallback LLM clients must differ")
        self.primary = primary
        self.fallback = fallback
        self._selected: ContextVar[LLMClient] = ContextVar(
            f"llm_router_selected_{id(self)}", default=primary
        )

    @property
    def model(self) -> str:
        """Model used by the current request, safe across concurrent contexts."""
        return self._selected.get().model

    def generate(self, system: str, prompt: str, max_tokens: int) -> str:
        self._selected.set(self.primary)
        try:
            return self.primary.generate(system, prompt, max_tokens)
        except LLMUnavailableError as exc:
            self._selected.set(self.fallback)
            logger.warning(
                "Primary LLM %s unavailable; falling back to %s: %s",
                self.primary.model,
                self.fallback.model,
                exc,
            )
            return self.fallback.generate(system, prompt, max_tokens)
