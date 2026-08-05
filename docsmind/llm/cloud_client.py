"""Anthropic-backed cloud LLM client.

The Anthropic SDK reads ANTHROPIC_API_KEY from the environment — no key is passed
through code or stored on Settings.
"""

from __future__ import annotations

import anthropic

from docsmind.llm.base import LLMClient, LLMRequestError, LLMUnavailableError


class CloudLLMClient(LLMClient):
    def __init__(self, model: str) -> None:
        self.model = model
        self._client = anthropic.Anthropic()

    def generate(self, system: str, prompt: str, max_tokens: int) -> str:
        try:
            response = self._client.messages.create(
                model=self.model,
                max_tokens=max_tokens,
                system=system,
                messages=[{"role": "user", "content": prompt}],
            )
        except (
            anthropic.APIConnectionError,
            anthropic.APITimeoutError,
            anthropic.RateLimitError,
        ) as exc:
            raise LLMUnavailableError(
                f"Anthropic model {self.model} is temporarily unavailable"
            ) from exc
        except anthropic.APIStatusError as exc:
            if exc.status_code in {408, 429} or exc.status_code >= 500:
                raise LLMUnavailableError(
                    f"Anthropic model {self.model} is temporarily unavailable "
                    f"(HTTP {exc.status_code})"
                ) from exc
            raise LLMRequestError(
                f"Anthropic rejected the request (HTTP {exc.status_code})"
            ) from exc
        return "".join(
            block.text for block in response.content if block.type == "text"
        ).strip()
