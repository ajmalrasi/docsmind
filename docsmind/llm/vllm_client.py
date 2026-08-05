"""OpenAI-compatible client for a self-hosted vLLM server.

vLLM exposes ``/v1/chat/completions`` using the same message structure as the
OpenAI Chat Completions API. This client keeps that provider-specific HTTP
contract behind DocsMind's small ``LLMClient`` interface.
"""

from __future__ import annotations

import httpx

from docsmind.llm.base import LLMClient, LLMRequestError, LLMUnavailableError


class VLLMClient(LLMClient):
    def __init__(
        self,
        model: str,
        base_url: str = "http://localhost:11434/v1",
        api_key: str | None = None,
        timeout: float = 300.0,
        client: httpx.Client | None = None,
    ) -> None:
        self.model = model
        self._base_url = base_url.rstrip("/")
        self._headers = (
            {"Authorization": f"Bearer {api_key}"} if api_key else {}
        )
        self._client = client or httpx.Client(timeout=timeout)

    def generate(self, system: str, prompt: str, max_tokens: int) -> str:
        try:
            response = self._client.post(
                f"{self._base_url}/chat/completions",
                headers=self._headers,
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
        except httpx.HTTPStatusError as exc:
            status = exc.response.status_code
            if status in {408, 429} or status >= 500:
                raise LLMUnavailableError(
                    f"vLLM is temporarily unavailable (HTTP {status})"
                ) from exc
            raise LLMRequestError(
                f"vLLM rejected the request (HTTP {status}); check its URL, "
                "API key, model alias, and request format"
            ) from exc
        except (httpx.TimeoutException, httpx.TransportError) as exc:
            raise LLMUnavailableError(
                f"vLLM could not be reached at {self._base_url}"
            ) from exc

        try:
            return response.json()["choices"][0]["message"]["content"].strip()
        except (KeyError, IndexError, TypeError, ValueError) as exc:
            raise LLMRequestError("vLLM returned an invalid chat response") from exc
