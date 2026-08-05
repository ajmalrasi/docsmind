"""Pluggable embedding providers for corpus ingestion and query retrieval.

Document and query embeddings are separate operations on purpose. Retrieval
models such as Cohere Embed v4 add different task prefixes for corpus passages
(``search_document``) and user questions (``search_query``). Treating both as a
generic ``encode`` call silently loses that retrieval signal.
"""

from __future__ import annotations

import json
from abc import ABC, abstractmethod
from concurrent.futures import ThreadPoolExecutor
from functools import cached_property
from typing import Any

import numpy as np
import httpx


def _normalized(vectors: Any, *, expected_dim: int) -> np.ndarray:
    """Return a validated, L2-normalized ``float32`` embedding matrix."""
    array = np.asarray(vectors, dtype=np.float32)
    if array.ndim != 2 or array.shape[1] != expected_dim:
        raise RuntimeError(
            f"Embedding provider returned shape {array.shape}; "
            f"expected (N, {expected_dim})."
        )
    if not np.isfinite(array).all():
        raise RuntimeError("Embedding provider returned non-finite values.")
    norms = np.linalg.norm(array, axis=1, keepdims=True)
    if np.any(norms == 0):
        raise RuntimeError("Embedding provider returned a zero-length vector.")
    return np.ascontiguousarray(array / norms, dtype=np.float32)


class EmbeddingProvider(ABC):
    """Contract shared by local and managed embedding implementations."""

    model_name: str
    provider_name: str

    @property
    @abstractmethod
    def dim(self) -> int:
        """Vector dimension written to and expected from the vector store."""

    @abstractmethod
    def embed_documents(self, texts: list[str]) -> np.ndarray:
        """Embed corpus passages as an ``(N, dim)`` normalized matrix."""

    @abstractmethod
    def embed_query(self, text: str) -> np.ndarray:
        """Embed one retrieval query as a normalized ``(dim,)`` vector."""


class Embedder(EmbeddingProvider):
    """Local sentence-transformers provider (the original DocsMind path)."""

    provider_name = "local"

    def __init__(self, model_name: str, device: str | None = None) -> None:
        self.model_name = model_name
        self.device = device

    @cached_property
    def _model(self):
        # Imported lazily so importing this module doesn't pull in torch.
        from sentence_transformers import SentenceTransformer

        return SentenceTransformer(self.model_name, device=self.device)

    @property
    def dim(self) -> int:
        return int(self._model.get_sentence_embedding_dimension())

    def embed_documents(self, texts: list[str]) -> np.ndarray:
        if not texts:
            return np.empty((0, self.dim), dtype=np.float32)
        vectors = self._model.encode(
            texts,
            normalize_embeddings=True,
            convert_to_numpy=True,
            show_progress_bar=False,
        )
        return _normalized(vectors, expected_dim=self.dim)

    def embed_query(self, text: str) -> np.ndarray:
        return self.embed_documents([text])[0]

    def encode(self, texts: list[str]) -> np.ndarray:
        """Backward-compatible alias for older ingestion integrations."""
        return self.embed_documents(texts)


class BedrockCohereEmbedder(EmbeddingProvider):
    """Cohere Embed v4 through Amazon Bedrock's ``InvokeModel`` API."""

    provider_name = "bedrock"
    _ALLOWED_DIMENSIONS = {256, 512, 1024, 1536}

    def __init__(
        self,
        model_name: str = "cohere.embed-v4:0",
        *,
        dimension: int = 1024,
        region: str = "us-east-1",
        profile_name: str = "",
        batch_size: int = 96,
        max_retries: int = 5,
        client: Any | None = None,
    ) -> None:
        if dimension not in self._ALLOWED_DIMENSIONS:
            raise ValueError(
                "Cohere Embed v4 dimension must be one of 256, 512, 1024, 1536."
            )
        if not 1 <= batch_size <= 96:
            raise ValueError("Cohere Embed v4 batch_size must be between 1 and 96.")
        if max_retries < 0:
            raise ValueError("max_retries cannot be negative")

        self.model_name = model_name
        self._dim = dimension
        self._region = region
        self._profile_name = profile_name
        self._batch_size = batch_size
        self._max_retries = max_retries
        self._client_override = client

    @property
    def dim(self) -> int:
        return self._dim

    @cached_property
    def _client(self):
        if self._client_override is not None:
            return self._client_override

        # Keep AWS imports lazy so local-only use has no credential side effects.
        import boto3
        from botocore.config import Config

        session = boto3.Session(
            profile_name=self._profile_name or None,
            region_name=self._region,
        )
        return session.client(
            "bedrock-runtime",
            config=Config(
                retries={"mode": "adaptive", "max_attempts": self._max_retries},
            ),
        )

    def embed_documents(self, texts: list[str]) -> np.ndarray:
        return self._embed(texts, input_type="search_document")

    def embed_query(self, text: str) -> np.ndarray:
        return self._embed([text], input_type="search_query")[0]

    def _embed(self, texts: list[str], *, input_type: str) -> np.ndarray:
        if not texts:
            return np.empty((0, self.dim), dtype=np.float32)

        batches: list[np.ndarray] = []
        for start in range(0, len(texts), self._batch_size):
            batch = texts[start : start + self._batch_size]
            response = self._client.invoke_model(
                modelId=self.model_name,
                contentType="application/json",
                accept="application/json",
                body=json.dumps(
                    {
                        "texts": batch,
                        "input_type": input_type,
                        "embedding_types": ["float"],
                        "output_dimension": self.dim,
                        # Keep the beginning of over-length technical passages.
                        "truncate": "RIGHT",
                    }
                ),
            )
            response_body = response.get("body")
            if response_body is None:
                raise RuntimeError("Bedrock embedding response did not include a body.")
            raw = response_body.read() if hasattr(response_body, "read") else response_body
            payload = json.loads(raw)
            vectors = payload.get("embeddings")
            # Bedrock returns a list for one requested type. Accept the documented
            # multi-type shape too, so a provider-side response change fails safely.
            if isinstance(vectors, dict):
                vectors = vectors.get("float")
            if not isinstance(vectors, list) or len(vectors) != len(batch):
                count = len(vectors) if isinstance(vectors, list) else 0
                raise RuntimeError(
                    f"Bedrock returned {count} vectors for a batch of {len(batch)}."
                )
            batches.append(_normalized(vectors, expected_dim=self.dim))

        return np.ascontiguousarray(np.concatenate(batches, axis=0), dtype=np.float32)


class BedrockTitanEmbedder(EmbeddingProvider):
    """Amazon Titan Text Embeddings v2 through Bedrock ``InvokeModel``."""

    provider_name = "bedrock"
    _ALLOWED_DIMENSIONS = {256, 512, 1024}

    def __init__(
        self,
        model_name: str = "amazon.titan-embed-text-v2:0",
        *,
        dimension: int = 1024,
        region: str = "us-east-1",
        profile_name: str = "",
        concurrency: int = 2,
        max_retries: int = 5,
        client: Any | None = None,
    ) -> None:
        if dimension not in self._ALLOWED_DIMENSIONS:
            raise ValueError("Titan Embed v2 dimension must be one of 256, 512, 1024.")
        if max_retries < 0:
            raise ValueError("max_retries cannot be negative")
        if concurrency <= 0:
            raise ValueError("concurrency must be positive")
        self.model_name = model_name
        self._dim = dimension
        self._region = region
        self._profile_name = profile_name
        self._concurrency = concurrency
        self._max_retries = max_retries
        self._client_override = client

    @property
    def dim(self) -> int:
        return self._dim

    @cached_property
    def _client(self):
        if self._client_override is not None:
            return self._client_override

        import boto3
        from botocore.config import Config

        session = boto3.Session(
            profile_name=self._profile_name or None,
            region_name=self._region,
        )
        return session.client(
            "bedrock-runtime",
            config=Config(
                retries={"mode": "adaptive", "max_attempts": self._max_retries},
            ),
        )

    def embed_documents(self, texts: list[str]) -> np.ndarray:
        return self._embed(texts)

    def embed_query(self, text: str) -> np.ndarray:
        return self._embed([text])[0]

    def _embed(self, texts: list[str]) -> np.ndarray:
        if not texts:
            return np.empty((0, self.dim), dtype=np.float32)

        # boto3 clients are thread-safe. executor.map preserves input order, so
        # every returned vector remains aligned with its source chunk.
        with ThreadPoolExecutor(max_workers=min(self._concurrency, len(texts))) as pool:
            vectors = list(pool.map(self._embed_one, texts))

        return _normalized(vectors, expected_dim=self.dim)

    def _embed_one(self, text: str) -> list[float]:
        response = self._client.invoke_model(
            modelId=self.model_name,
            contentType="application/json",
            accept="application/json",
            body=json.dumps(
                {
                    "inputText": text,
                    "dimensions": self.dim,
                    "normalize": True,
                    "embeddingTypes": ["float"],
                }
            ),
        )
        response_body = response.get("body")
        if response_body is None:
            raise RuntimeError("Bedrock embedding response did not include a body.")
        raw = response_body.read() if hasattr(response_body, "read") else response_body
        payload = json.loads(raw)
        vector = payload.get("embedding")
        if not isinstance(vector, list):
            raise RuntimeError("Titan embedding response did not include a vector.")
        return vector


class TEIEmbedder(EmbeddingProvider):
    """Remote Hugging Face Text Embeddings Inference provider."""

    provider_name = "tei"

    def __init__(
        self,
        model_name: str = "BAAI/bge-m3",
        *,
        dimension: int = 1024,
        base_url: str = "http://localhost:8080",
        batch_size: int = 8,
        timeout: float = 60.0,
        client: httpx.Client | None = None,
    ) -> None:
        if dimension <= 0:
            raise ValueError("dimension must be positive")
        if timeout <= 0:
            raise ValueError("timeout must be positive")
        if batch_size <= 0:
            raise ValueError("batch_size must be positive")
        self.model_name = model_name
        self._dim = dimension
        self._base_url = base_url.rstrip("/")
        self._batch_size = batch_size
        self._timeout = timeout
        self._client_override = client

    @property
    def dim(self) -> int:
        return self._dim

    @cached_property
    def _client(self) -> httpx.Client:
        if self._client_override is not None:
            return self._client_override
        return httpx.Client(base_url=self._base_url, timeout=self._timeout)

    def embed_documents(self, texts: list[str]) -> np.ndarray:
        return self._embed(texts)

    def embed_query(self, text: str) -> np.ndarray:
        return self._embed([text])[0]

    def _embed(self, texts: list[str]) -> np.ndarray:
        if not texts:
            return np.empty((0, self.dim), dtype=np.float32)
        batches: list[np.ndarray] = []
        for start in range(0, len(texts), self._batch_size):
            batch = texts[start : start + self._batch_size]
            response = self._client.post(
                (
                    f"{self._base_url}/embed"
                    if self._client_override is not None
                    else "/embed"
                ),
                json={
                    "inputs": batch,
                    "normalize": True,
                    "truncate": True,
                },
            )
            response.raise_for_status()
            vectors = _normalized(response.json(), expected_dim=self.dim)
            if len(vectors) != len(batch):
                raise RuntimeError(
                    f"TEI returned {len(vectors)} vectors for a batch of {len(batch)}."
                )
            batches.append(vectors)
        return np.ascontiguousarray(np.concatenate(batches, axis=0), dtype=np.float32)
