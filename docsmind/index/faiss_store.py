"""FAISS-backed vector store.

Phase 1 shipped the flat (exact) index. Phase 2 adds the approximate index
types — IVF, HNSW, and IVFPQ — behind the same ``VectorStore`` interface, so
callers (retriever, pipeline) never change. The only thing that varies is the
speed/recall/memory tradeoff of the index built underneath.

All indexes use inner product on L2-normalized vectors, which equals cosine
similarity. ``index_type`` selects the structure:

    flat    IndexFlatIP    exact brute-force scan          (Phase 1 baseline)
    ivf     IndexIVFFlat   k-means cells, probe a few      (needs training)
    hnsw    IndexHNSWFlat  navigable small-world graph     (no training)
    ivfpq   IndexIVFPQ     IVF + product quantization      (needs training)
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

# Search/build parameters, with defaults sensible for ~100k–1M vectors. They are
# tunable per store (and via Settings) so the benchmark can sweep them.
_DEFAULT_PARAMS = {
    "nlist": 100,  # IVF: number of k-means cells (partitions)
    "nprobe": 8,  # IVF: cells probed at query time (higher = better recall, slower)
    "hnsw_m": 32,  # HNSW: edges per node (higher = better recall, more memory)
    "hnsw_ef_construction": 200,  # HNSW: build-time search breadth
    "hnsw_ef_search": 64,  # HNSW: query-time search breadth (higher = better recall)
    "pq_m": 48,  # IVFPQ: sub-quantizers (must divide dim; 384 / 48 = 8 dims each)
    "pq_nbits": 8,  # IVFPQ: bits per sub-quantizer code (8 => 256 centroids)
}


class FaissVectorStore(VectorStore):
    def __init__(self, dim: int, index_type: str = "flat", **params) -> None:
        unknown = set(params) - set(_DEFAULT_PARAMS)
        if unknown:
            raise TypeError(f"unknown index params: {sorted(unknown)}")
        self.dim = dim
        self._index_type = index_type
        self._params = {**_DEFAULT_PARAMS, **params}
        self._index = self._build_index(dim, index_type)
        self._chunks: list[Chunk] = []

    def _build_index(self, dim: int, index_type: str) -> faiss.Index:
        p = self._params
        # Inner product on normalized vectors == cosine similarity, for all types.
        if index_type == "flat":
            return faiss.IndexFlatIP(dim)
        if index_type == "ivf":
            quantizer = faiss.IndexFlatIP(dim)
            index = faiss.IndexIVFFlat(
                quantizer, dim, p["nlist"], faiss.METRIC_INNER_PRODUCT
            )
            index.nprobe = p["nprobe"]
            return index
        if index_type == "hnsw":
            index = faiss.IndexHNSWFlat(dim, p["hnsw_m"], faiss.METRIC_INNER_PRODUCT)
            index.hnsw.efConstruction = p["hnsw_ef_construction"]
            index.hnsw.efSearch = p["hnsw_ef_search"]
            return index
        if index_type == "ivfpq":
            quantizer = faiss.IndexFlatIP(dim)
            index = faiss.IndexIVFPQ(
                quantizer, dim, p["nlist"], p["pq_m"], p["pq_nbits"],
                faiss.METRIC_INNER_PRODUCT,
            )
            index.nprobe = p["nprobe"]
            return index
        raise NotImplementedError(
            f"index_type={index_type!r} is not supported "
            "(use one of: flat, ivf, hnsw, ivfpq)."
        )

    @property
    def size(self) -> int:
        return int(self._index.ntotal)

    @property
    def index_type(self) -> str:
        return self._index_type

    @property
    def chunks(self) -> list[Chunk]:
        return self._chunks

    def add(self, chunks: list[Chunk], embeddings: np.ndarray) -> None:
        if len(chunks) != embeddings.shape[0]:
            raise ValueError(
                f"chunk/embedding count mismatch: {len(chunks)} vs {embeddings.shape[0]}"
            )
        vectors = np.ascontiguousarray(embeddings, dtype=np.float32)
        # IVF/IVFPQ must learn their cells (and PQ codebooks) before adding.
        # Flat and HNSW report is_trained == True and skip this.
        if not self._index.is_trained:
            self._index.train(vectors)
        self._index.add(vectors)
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
            "params": self._params,
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
        # params is absent in Phase 1 indexes; defaults fill in harmlessly since
        # the trained structure (nprobe, efSearch, codebooks) lives in the file.
        store = cls(
            dim=meta["dim"],
            index_type=meta["index_type"],
            **meta.get("params", {}),
        )
        store._index = faiss.read_index(str(index_path))
        store._chunks = [Chunk(**c) for c in meta["chunks"]]
        return store
