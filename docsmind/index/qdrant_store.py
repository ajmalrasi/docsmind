"""Qdrant-backed vector store (Phase 2b).

Same ``VectorStore`` contract as ``FaissVectorStore`` — the retriever and pipeline
never learn which one is underneath. What changes is *where the index lives*:

    FAISS   in-process, the vectors sit in this Python process's memory and are
            written to a file. One process owns them.
    Qdrant  a separate service. Here it runs in one of two modes:
              - local path : Qdrant persists to a directory, no server needed
                             (the default — keeps tests and `make demo` offline).
              - server URL : a Dockerized Qdrant (e.g. on beast) reachable over
                             HTTP, which is the "real" deployment shape.

Qdrant builds an HNSW graph internally for every collection, so its search is
approximate-by-default — the opposite of FAISS's exact ``flat``. That is the
teaching contrast of this phase: a library you embed vs. a service you talk to.

Vectors use cosine distance. Our embeddings are already L2-normalized, so cosine
and dot product agree; cosine is used for clarity.
"""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
from qdrant_client import QdrantClient, models

from docsmind.index.base import VectorStore
from docsmind.schemas import Chunk, SearchResult

_META_FILE = "meta.json"
_LOCAL_SUBDIR = "qdrant"  # where local-path Qdrant persists, under index_dir


class QdrantVectorStore(VectorStore):
    def __init__(
        self,
        dim: int,
        *,
        collection: str = "docsmind",
        url: str = "",
        path: Path | str | None = None,
        hnsw_m: int = 16,
        recreate: bool = False,
    ) -> None:
        self.dim = dim
        self._collection = collection
        self._url = url
        self._path = str(path) if path is not None else None
        self._hnsw_m = hnsw_m
        self._client = self._connect()
        self._ensure_collection(recreate=recreate)

    def _connect(self) -> QdrantClient:
        if self._url:
            return QdrantClient(url=self._url)
        if self._path is not None:
            return QdrantClient(path=self._path)
        # No url and no path => ephemeral in-memory (used by the test suite).
        return QdrantClient(":memory:")

    def _ensure_collection(self, *, recreate: bool) -> None:
        exists = self._client.collection_exists(self._collection)
        if exists and not recreate:
            return
        if exists:  # recreate => drop the stale collection first
            self._client.delete_collection(self._collection)
        self._client.create_collection(
            collection_name=self._collection,
            vectors_config=models.VectorParams(
                size=self.dim, distance=models.Distance.COSINE
            ),
            hnsw_config=models.HnswConfigDiff(m=self._hnsw_m),
        )

    def close(self) -> None:
        """Release the client. Local-path mode locks its directory, so the owning
        process must close before another opens the same path."""
        self._client.close()

    @property
    def size(self) -> int:
        return int(self._client.count(self._collection).count)

    @property
    def index_type(self) -> str:
        return "qdrant"

    @property
    def chunks(self) -> list[Chunk]:
        # Scroll the whole collection back out, ordered by the integer point id we
        # assigned at insertion, so BM25 sees chunks in a stable order.
        records, _ = self._client.scroll(
            self._collection,
            limit=max(self.size, 1),
            with_payload=True,
            with_vectors=False,
        )
        records.sort(key=lambda r: r.id)
        return [Chunk(**r.payload) for r in records]

    def add(self, chunks: list[Chunk], embeddings: np.ndarray) -> None:
        if len(chunks) != embeddings.shape[0]:
            raise ValueError(
                f"chunk/embedding count mismatch: {len(chunks)} vs {embeddings.shape[0]}"
            )
        base = self.size  # continue ids past whatever is already stored
        vectors = np.ascontiguousarray(embeddings, dtype=np.float32)
        points = [
            models.PointStruct(
                id=base + i,
                vector=vectors[i].tolist(),
                payload=chunk.model_dump(),
            )
            for i, chunk in enumerate(chunks)
        ]
        self._client.upsert(self._collection, points=points)

    def search(self, query_embedding: np.ndarray, top_k: int) -> list[SearchResult]:
        if self.size == 0:
            return []
        query = np.ascontiguousarray(query_embedding, dtype=np.float32).reshape(-1)
        hits = self._client.query_points(
            self._collection,
            query=query.tolist(),
            limit=min(top_k, self.size),
            with_payload=True,
        ).points
        return [
            SearchResult(chunk=Chunk(**hit.payload), score=float(hit.score))
            for hit in hits
        ]

    def save(self, path: Path | str) -> None:
        # Local-path and server Qdrant already persist the vectors themselves;
        # we only write a small marker so load() (and the demo's "is there an
        # index?" check) can find and reconnect to this collection.
        path = Path(path)
        path.mkdir(parents=True, exist_ok=True)
        meta = {
            "backend": "qdrant",
            "dim": self.dim,
            "collection": self._collection,
            "url": self._url,
            "path": self._path,
            "hnsw_m": self._hnsw_m,
        }
        (path / _META_FILE).write_text(json.dumps(meta), encoding="utf-8")

    @classmethod
    def load(cls, path: Path | str) -> "QdrantVectorStore":
        path = Path(path)
        meta_path = path / _META_FILE
        if not meta_path.exists():
            raise FileNotFoundError(
                f"No index found at {path}. Run `make ingest` first."
            )
        meta = json.loads(meta_path.read_text(encoding="utf-8"))
        return cls(
            dim=meta["dim"],
            collection=meta["collection"],
            url=meta.get("url", ""),
            path=meta.get("path"),
            hnsw_m=meta.get("hnsw_m", 16),
            recreate=False,
        )
