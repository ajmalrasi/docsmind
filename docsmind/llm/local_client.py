"""Self-hosted LLM client backed by Ollama.

Talks to an Ollama server over its HTTP API (default http://localhost:11434).
This is the local arm of what becomes the Phase 4 LLMRouter — it implements the
same LLMClient contract as the cloud client, so the pipeline is unaffected.
"""

from __future__ import annotations

import httpx

from docsmind.llm.base import LLMClient


class LocalLLMClient(LLMClient):
    def __init__(
        self,
        model: str,
        base_url: str = "http://localhost:11434",
        timeout: float = 300.0,
    ) -> None:
        self.model = model
        self._base_url = base_url.rstrip("/")
        self._client = httpx.Client(timeout=timeout)

    def generate(self, system: str, prompt: str, max_tokens: int) -> str:
        response = self._client.post(
            f"{self._base_url}/api/chat",
            json={
                "model": self.model,
                "messages": [
                    {"role": "system", "content": system},
                    {"role": "user", "content": prompt},
                ],
                "stream": False,
                "options": {"num_predict": max_tokens},
            },
        )
        response.raise_for_status()
        return response.json()["message"]["content"].strip()
