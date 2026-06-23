"""Anthropic-backed cloud LLM client.

The Anthropic SDK reads ANTHROPIC_API_KEY from the environment — no key is passed
through code or stored on Settings.
"""

from __future__ import annotations

import anthropic

from docsmind.llm.base import LLMClient


class CloudLLMClient(LLMClient):
    def __init__(self, model: str) -> None:
        self.model = model
        self._client = anthropic.Anthropic()

    def generate(self, system: str, prompt: str, max_tokens: int) -> str:
        response = self._client.messages.create(
            model=self.model,
            max_tokens=max_tokens,
            system=system,
            messages=[{"role": "user", "content": prompt}],
        )
        return "".join(
            block.text for block in response.content if block.type == "text"
        ).strip()
