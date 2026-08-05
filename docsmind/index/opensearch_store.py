"""AWS OpenSearch Serverless vector-store backend.

This backend occupies the same Index/Search seam as FAISS and Qdrant. Vectors
and chunk payloads live in an OpenSearch Serverless index; callers continue to
use the backend-agnostic ``VectorStore`` contract.

The collection created for DocsMind is a NextGen vector-search collection. Its
mapping therefore declares a ``knn_vector`` and cosine similarity, while AWS
selects the Faiss/HNSW engine. Requests are signed with SigV4 service ``aoss``.

Hybrid retrieval still runs BM25 in-process. The ``chunks`` property pages all
stored payloads back with ``search_after`` in insertion order so the existing
BM25 implementation works without learning about OpenSearch.
"""

from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any, Iterator
from urllib.parse import quote, urlparse

import boto3
import numpy as np
from opensearchpy import AWSV4SignerAuth, OpenSearch, RequestsHttpConnection
from opensearchpy.helpers import bulk
from opensearchpy.helpers.errors import BulkIndexError

from docsmind.index.base import VectorStore
from docsmind.schemas import Chunk, SearchResult

_META_FILE = "meta.json"
_VECTOR_FIELD = "embedding"
_ORDER_FIELD = "insertion_order"


class OpenSearchVectorStore(VectorStore):
    """Store normalized vectors and chunks in AWS OpenSearch Serverless."""

    def __init__(
        self,
        dim: int,
        *,
        endpoint: str,
        index_name: str = "docsmind-chunks",
        region: str = "us-east-1",
        profile_name: str = "",
        bulk_size: int = 500,
        page_size: int = 1000,
        request_timeout: int = 60,
        max_retries: int = 5,
        recreate: bool = False,
        client: Any | None = None,
    ) -> None:
        if dim <= 0:
            raise ValueError("dim must be positive")
        if not endpoint:
            raise ValueError(
                "OpenSearch endpoint is required. Set DOCSMIND_OPENSEARCH_ENDPOINT."
            )
        if bulk_size <= 0 or page_size <= 0 or request_timeout <= 0:
            raise ValueError("bulk_size, page_size, and request_timeout must be positive")
        if max_retries < 0:
            raise ValueError("max_retries cannot be negative")

        self.dim = dim
        self._endpoint = endpoint.rstrip("/")
        self._index_name = index_name
        self._region = region
        self._profile_name = profile_name
        self._bulk_size = bulk_size
        self._page_size = page_size
        self._request_timeout = request_timeout
        self._max_retries = max_retries
        self._client = client or self._connect()
        self._chunks_cache: list[Chunk] | None = None
        self._next_order: int | None = None
        self._ensure_index(recreate=recreate)

    def _connect(self) -> OpenSearch:
        parsed = urlparse(
            self._endpoint
            if "://" in self._endpoint
            else f"https://{self._endpoint}"
        )
        if not parsed.hostname:
            raise ValueError(f"Invalid OpenSearch endpoint: {self._endpoint!r}")

        session = boto3.Session(
            profile_name=self._profile_name or None,
            region_name=self._region,
        )
        credentials = session.get_credentials()
        if credentials is None:
            raise RuntimeError(
                "AWS credentials were not found. Configure the requested profile "
                "or another standard boto3 credential source."
            )

        auth = AWSV4SignerAuth(credentials, self._region, "aoss")
        return OpenSearch(
            hosts=[{"host": parsed.hostname, "port": parsed.port or 443}],
            http_auth=auth,
            # NextGen AOSS currently rejects SigV4-signed JSON search bodies
            # when RequestsHttpConnection gzips them (content checksum mismatch).
            # Keep compression off for correctness; our corpus is small enough
            # that the extra transfer is negligible.
            http_compress=False,
            use_ssl=True,
            verify_certs=True,
            connection_class=RequestsHttpConnection,
            pool_maxsize=20,
            timeout=self._request_timeout,
            max_retries=self._max_retries,
            retry_on_timeout=True,
            retry_on_status=(429, 502, 503, 504),
        )

    def _ensure_index(self, *, recreate: bool) -> None:
        exists = bool(self._client.indices.exists(index=self._index_name))
        if exists and not recreate:
            self._validate_existing_dimension()
            return
        if exists:
            self._client.indices.delete(index=self._index_name)

        self._client.indices.create(
            index=self._index_name,
            body={
                "settings": {"index.knn": True},
                "mappings": {
                    "dynamic": "strict",
                    "properties": {
                        _ORDER_FIELD: {"type": "long"},
                        "chunk_id": {"type": "keyword"},
                        "text": {"type": "text"},
                        "source": {"type": "keyword"},
                        # Preserve arbitrary provenance without creating one
                        # OpenSearch mapping field per metadata key.
                        "metadata": {"type": "object", "enabled": False},
                        _VECTOR_FIELD: {
                            "type": "knn_vector",
                            "dimension": self.dim,
                            "space_type": "cosinesimil",
                        },
                    },
                },
            },
        )
        # A new/recreated index is known to contain zero documents. Avoid an
        # immediate count request while Serverless is still warming its search
        # compute after index creation.
        self._next_order = 0

    def _validate_existing_dimension(self) -> None:
        mapping = self._client.indices.get_mapping(index=self._index_name)
        index_mapping = mapping.get(self._index_name, mapping)
        properties = index_mapping.get("mappings", {}).get("properties", {})
        stored_dim = properties.get(_VECTOR_FIELD, {}).get("dimension")
        if stored_dim is not None and int(stored_dim) != self.dim:
            raise ValueError(
                f"OpenSearch index {self._index_name!r} has dimension "
                f"{stored_dim}, but the embedder produces {self.dim}. Re-ingest "
                "with the matching embedding model or recreate the index."
            )

    @property
    def size(self) -> int:
        return int(self._client.count(index=self._index_name)["count"])

    @property
    def index_type(self) -> str:
        return "opensearch"

    @property
    def chunks(self) -> list[Chunk]:
        if self._chunks_cache is None:
            self._chunks_cache = list(self._iter_chunks())
        return self._chunks_cache

    def _iter_chunks(self) -> Iterator[Chunk]:
        search_after: list[Any] | None = None
        while True:
            body: dict[str, Any] = {
                "size": self._page_size,
                "query": {"match_all": {}},
                "sort": [{_ORDER_FIELD: "asc"}],
                "_source": {"excludes": [_VECTOR_FIELD]},
            }
            if search_after is not None:
                body["search_after"] = search_after

            response = self._perform_search(body)
            hits = response.get("hits", {}).get("hits", [])
            if not hits:
                return

            for hit in hits:
                yield self._chunk_from_source(hit["_source"])

            if len(hits) < self._page_size:
                return
            search_after = hits[-1]["sort"]

    def add(self, chunks: list[Chunk], embeddings: np.ndarray) -> None:
        vectors = self._validate_embeddings(chunks, embeddings)
        if not chunks:
            return

        base = self._next_order if self._next_order is not None else self.size

        def actions() -> Iterator[dict[str, Any]]:
            for offset, (chunk, vector) in enumerate(zip(chunks, vectors)):
                order = base + offset
                yield {
                    "_op_type": "index",
                    "_index": self._index_name,
                    # Include insertion order so repeated source chunk IDs do not
                    # overwrite an earlier indexed document.
                    "_id": f"{order}:{chunk.id}",
                    "_source": {
                        _ORDER_FIELD: order,
                        "chunk_id": chunk.id,
                        "text": chunk.text,
                        "source": chunk.source,
                        "metadata": chunk.metadata,
                        _VECTOR_FIELD: vector.tolist(),
                    },
                }

        try:
            bulk(
                self._client,
                actions(),
                chunk_size=self._bulk_size,
                request_timeout=max(self._request_timeout, 120),
                raise_on_error=True,
                raise_on_exception=True,
            )
        except BulkIndexError as exc:
            # BulkIndexError includes the complete failed source documents by
            # default. Do not let private chunk text or vectors spill into logs.
            first = exc.errors[0] if exc.errors else {}
            operation = next(iter(first.values()), {})
            error = operation.get("error", {})
            reason = error.get("reason", "unknown OpenSearch bulk error")
            raise RuntimeError(
                f"OpenSearch rejected {len(exc.errors)} document(s): {reason}"
            ) from None

        expected_size = base + len(chunks)
        self._wait_until_visible(expected_size)
        self._next_order = expected_size
        self._chunks_cache = None

    def _wait_until_visible(self, expected_size: int) -> None:
        """Wait for Serverless's asynchronous refresh without unsupported APIs."""
        timeout = max(120, self._request_timeout * 2)
        deadline = time.monotonic() + timeout
        last_count = -1
        while time.monotonic() < deadline:
            last_count = self.size
            if last_count >= expected_size:
                return
            time.sleep(2)
        raise TimeoutError(
            f"OpenSearch accepted the bulk request, but only {last_count} of "
            f"{expected_size} documents became visible within {timeout} seconds."
        )

    def _validate_embeddings(
        self, chunks: list[Chunk], embeddings: np.ndarray
    ) -> np.ndarray:
        vectors = np.asarray(embeddings, dtype=np.float32)
        if vectors.ndim != 2:
            raise ValueError(
                f"embeddings must have shape (N, {self.dim}); got {vectors.shape}"
            )
        if len(chunks) != vectors.shape[0]:
            raise ValueError(
                f"chunk/embedding count mismatch: {len(chunks)} vs {vectors.shape[0]}"
            )
        if vectors.shape[1] != self.dim:
            raise ValueError(
                f"embedding dimension mismatch: expected {self.dim}, "
                f"got {vectors.shape[1]}"
            )
        return np.ascontiguousarray(vectors, dtype=np.float32)

    def search(self, query_embedding: np.ndarray, top_k: int) -> list[SearchResult]:
        if top_k <= 0:
            return []
        total = self.size
        if total == 0:
            return []

        query = np.asarray(query_embedding, dtype=np.float32).reshape(-1)
        if query.shape[0] != self.dim:
            raise ValueError(
                f"query dimension mismatch: expected {self.dim}, got {query.shape[0]}"
            )

        limit = min(top_k, total)
        response = self._perform_search(
            {
                "size": limit,
                "_source": {"excludes": [_VECTOR_FIELD]},
                "query": {
                    "knn": {
                        _VECTOR_FIELD: {
                            "vector": query.tolist(),
                            "k": limit,
                        }
                    }
                },
            }
        )
        return [
            SearchResult(
                chunk=self._chunk_from_source(hit["_source"]),
                score=float(hit["_score"]),
            )
            for hit in response.get("hits", {}).get("hits", [])
        ]

    def _perform_search(self, body: dict[str, Any]) -> dict[str, Any]:
        """Use POST explicitly; AOSS rejects signed GET requests with bodies."""
        index_path = quote(self._index_name, safe="")
        return self._client.transport.perform_request(
            "POST",
            f"/{index_path}/_search",
            body=body,
        )

    @staticmethod
    def _chunk_from_source(source: dict[str, Any]) -> Chunk:
        return Chunk(
            id=source["chunk_id"],
            text=source["text"],
            source=source["source"],
            metadata=source.get("metadata", {}),
        )

    def save(self, path: Path | str) -> None:
        """Write only reconnect metadata; OpenSearch already persists the index."""
        path = Path(path)
        path.mkdir(parents=True, exist_ok=True)
        marker = {
            "backend": "opensearch",
            "dim": self.dim,
            "endpoint": self._endpoint,
            "index_name": self._index_name,
            "region": self._region,
            "profile_name": self._profile_name,
            "bulk_size": self._bulk_size,
            "page_size": self._page_size,
            "request_timeout": self._request_timeout,
            "max_retries": self._max_retries,
        }
        (path / _META_FILE).write_text(json.dumps(marker), encoding="utf-8")

    @classmethod
    def load(
        cls,
        path: Path | str,
        *,
        endpoint: str | None = None,
        index_name: str | None = None,
        region: str | None = None,
        profile_name: str | None = None,
        client: Any | None = None,
    ) -> "OpenSearchVectorStore":
        meta_path = Path(path) / _META_FILE
        if not meta_path.exists():
            raise FileNotFoundError(
                f"No index marker found at {path}. Run `make ingest` first."
            )
        marker = json.loads(meta_path.read_text(encoding="utf-8"))
        if marker.get("backend") != "opensearch":
            raise ValueError(
                f"Index marker at {meta_path} is for "
                f"{marker.get('backend', 'another backend')!r}, not OpenSearch."
            )
        return cls(
            dim=int(marker["dim"]),
            endpoint=endpoint or marker["endpoint"],
            index_name=index_name or marker["index_name"],
            region=region or marker["region"],
            profile_name=(
                marker.get("profile_name", "")
                if profile_name is None
                else profile_name
            ),
            bulk_size=int(marker.get("bulk_size", 500)),
            page_size=int(marker.get("page_size", 1000)),
            request_timeout=int(marker.get("request_timeout", 60)),
            max_retries=int(marker.get("max_retries", 5)),
            recreate=False,
            client=client,
        )

    def close(self) -> None:
        close = getattr(self._client, "close", None)
        if close is not None:
            close()
