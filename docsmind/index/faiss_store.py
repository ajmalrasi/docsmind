"""FAISS-backed vector store.

Phase 1 implements the flat (exact) index. The index-type switch and persistence
format are built to accommodate IVF/HNSW/PQ in Phase 2 without changing callers.
"""

from __future__ import annotations

import json
from pathlib import Path

import faiss
import numpy as np

from docsmind.index.base import VectorStore
from docsmind.schemas import Chunk, SearchResult

_INDEX_FILE = "index.faiss"
_META_FILE = "meta.json"


class FaissVectorStore(VectorStore):
    def __init__(self, dim: int, index_type: str = "flat") -> None:
        self.dim = dim
        self._index_type = index_type
        self._index = self._build_index(dim, index_type)
        self._chunks: list[Chunk] = []

    @staticmethod
    def _build_index(dim: int, index_type: str) -> faiss.Index:
        if index_type == "flat":
            # Inner product on normalized vectors == cosine similarity.
            return faiss.IndexFlatIP(dim)
        raise NotImplementedError(
            f"index_type={index_type!r} is not supported in Phase 1 "
            "(IVF/HNSW/PQ arrive in Phase 2)."
        )

    @property
    def size(self) -> int:
        return int(self._index.ntotal)

    @property
    def index_type(self) -> str:
        return self._index_type

    def add(self, chunks: list[Chunk], embeddings: np.ndarray) -> None:
        if len(chunks) != embeddings.shape[0]:
            raise ValueError(
                f"chunk/embedding count mismatch: {len(chunks)} vs {embeddings.shape[0]}"
            )
        self._index.add(np.ascontiguousarray(embeddings, dtype=np.float32))
        self._chunks.extend(chunks)

    def search(self, query_embedding: np.ndarray, top_k: int) -> list[SearchResult]:
        if self.size == 0:
            return []
        query = np.ascontiguousarray(query_embedding, dtype=np.float32).reshape(1, -1)
        scores, indices = self._index.search(query, min(top_k, self.size))
        results: list[SearchResult] = []
        for score, idx in zip(scores[0], indices[0]):
            if idx < 0:  # FAISS pads with -1 when fewer than top_k results exist.
                continue
            results.append(SearchResult(chunk=self._chunks[idx], score=float(score)))
        return results

    def save(self, path: Path | str) -> None:
        path = Path(path)
        path.mkdir(parents=True, exist_ok=True)
        faiss.write_index(self._index, str(path / _INDEX_FILE))
        meta = {
            "dim": self.dim,
            "index_type": self._index_type,
            "chunks": [c.model_dump() for c in self._chunks],
        }
        (path / _META_FILE).write_text(json.dumps(meta), encoding="utf-8")

    @classmethod
    def load(cls, path: Path | str) -> "FaissVectorStore":
        path = Path(path)
        meta_path = path / _META_FILE
        index_path = path / _INDEX_FILE
        if not meta_path.exists() or not index_path.exists():
            raise FileNotFoundError(
                f"No index found at {path}. Run `make ingest` first."
            )
        meta = json.loads(meta_path.read_text(encoding="utf-8"))
        store = cls(dim=meta["dim"], index_type=meta["index_type"])
        store._index = faiss.read_index(str(index_path))
        store._chunks = [Chunk(**c) for c in meta["chunks"]]
        return store
