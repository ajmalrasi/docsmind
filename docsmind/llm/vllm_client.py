"""OpenAI-compatible client for a self-hosted vLLM server.

vLLM exposes ``/v1/chat/completions`` using the same message structure as the
OpenAI Chat Completions API. This client keeps that provider-specific HTTP
contract behind DocsMind's small ``LLMClient`` interface.
"""

from __future__ import annotations

import httpx

from docsmind.llm.base import LLMClient


class VLLMClient(LLMClient):
    def __init__(
        self,
        model: str,
        base_url: str = "http://localhost:11434/v1",
        timeout: float = 300.0,
        client: httpx.Client | None = None,
    ) -> None:
        self.model = model
        self._base_url = base_url.rstrip("/")
        self._client = client or httpx.Client(timeout=timeout)

    def generate(self, system: str, prompt: str, max_tokens: int) -> str:
        response = self._client.post(
            f"{self._base_url}/chat/completions",
            json={
                "model": self.model,
                "messages": [
                    {"role": "system", "content": system},
                    {"role": "user", "content": prompt},
                ],
                "max_tokens": max_tokens,
                "stream": False,
            },
        )
        response.raise_for_status()
        return response.json()["choices"][0]["message"]["content"].strip()
