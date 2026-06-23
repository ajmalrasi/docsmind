"""LLM client interface.

Phase 1 has a single cloud client. Phase 4 introduces an LLMRouter that selects
between a self-hosted SLM and this cloud client behind the same contract.
"""

from __future__ import annotations

from abc import ABC, abstractmethod


class LLMClient(ABC):
    model: str

    @abstractmethod
    def generate(self, system: str, prompt: str, max_tokens: int) -> str:
        """Return the model's text completion for a system + user prompt."""
