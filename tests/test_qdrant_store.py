"""Qdrant backend tests. In-memory mode keeps them offline and server-free."""

import numpy as np

from docsmind.index.qdrant_store import QdrantVectorStore
from docsmind.schemas import Chunk


def _chunk(i: int) -> Chunk:
    return Chunk(id=str(i), text=f"chunk {i}", source="doc.md")


def _embeddings() -> np.ndarray:
    return np.array([[1, 0, 0], [0, 1, 0], [0, 0, 1]], dtype=np.float32)


def test_add_search_and_chunks():
    store = QdrantVectorStore(dim=3)  # in-memory
    store.add([_chunk(0), _chunk(1), _chunk(2)], _embeddings())

    assert store.size == 3
    assert store.index_type == "qdrant"
    assert [c.id for c in store.chunks] == ["0", "1", "2"]

    results = store.search(np.array([0.9, 0.1, 0.0], dtype=np.float32), top_k=2)
    assert results[0].chunk.id == "0"  # closest to [1,0,0]
    assert results[0].score >= results[1].score


def test_search_empty_store():
    store = QdrantVectorStore(dim=3)
    assert store.search(np.zeros(3, dtype=np.float32), top_k=5) == []


def test_save_and_load_roundtrips_local_path(tmp_path):
    store = QdrantVectorStore(
        dim=3, path=tmp_path / "qdrant", recreate=True
    )
    store.add([_chunk(0), _chunk(1), _chunk(2)], _embeddings())
    store.save(tmp_path)
    store.close()  # release the local-path lock before reconnecting

    loaded = QdrantVectorStore.load(tmp_path)
    assert loaded.size == 3
    assert loaded.index_type == "qdrant"
    results = loaded.search(np.array([0.9, 0.1, 0.0], dtype=np.float32), top_k=1)
    assert results[0].chunk.id == "0"
    loaded.close()
