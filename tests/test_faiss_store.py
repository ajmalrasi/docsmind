import numpy as np

from docsmind.index.faiss_store import FaissVectorStore
from docsmind.schemas import Chunk


def _chunk(i: int) -> Chunk:
    return Chunk(id=str(i), text=f"chunk {i}", source="doc.md")


def test_add_and_search_returns_nearest():
    store = FaissVectorStore(dim=3, index_type="flat")
    embeddings = np.array(
        [[1, 0, 0], [0, 1, 0], [0, 0, 1]], dtype=np.float32
    )
    store.add([_chunk(0), _chunk(1), _chunk(2)], embeddings)

    assert store.size == 3
    results = store.search(np.array([0.9, 0.1, 0.0], dtype=np.float32), top_k=2)
    assert len(results) == 2
    assert results[0].chunk.id == "0"  # closest to [1,0,0]
    assert results[0].score >= results[1].score


def test_search_empty_store():
    store = FaissVectorStore(dim=3)
    assert store.search(np.zeros(3, dtype=np.float32), top_k=5) == []


def test_top_k_capped_to_size():
    store = FaissVectorStore(dim=2)
    store.add([_chunk(0)], np.array([[1, 0]], dtype=np.float32))
    results = store.search(np.array([1, 0], dtype=np.float32), top_k=10)
    assert len(results) == 1


def test_unsupported_index_type():
    import pytest

    with pytest.raises(NotImplementedError):
        FaissVectorStore(dim=4, index_type="bogus")


def test_unknown_param_rejected():
    import pytest

    with pytest.raises(TypeError):
        FaissVectorStore(dim=4, index_type="flat", nprbe=8)  # typo'd kwarg


def test_ivf_search_is_exact_when_probing_all_cells():
    # nprobe == nlist means every cell is searched, so IVF degenerates to exact.
    store = FaissVectorStore(dim=3, index_type="ivf", nlist=2, nprobe=2)
    embeddings = np.array([[1, 0, 0], [0, 1, 0], [0, 0, 1]], dtype=np.float32)
    store.add([_chunk(0), _chunk(1), _chunk(2)], embeddings)

    assert store.size == 3
    results = store.search(np.array([0.9, 0.1, 0.0], dtype=np.float32), top_k=1)
    assert results[0].chunk.id == "0"


def test_hnsw_search_returns_nearest():
    store = FaissVectorStore(dim=3, index_type="hnsw", hnsw_m=16, hnsw_ef_search=64)
    embeddings = np.array([[1, 0, 0], [0, 1, 0], [0, 0, 1]], dtype=np.float32)
    store.add([_chunk(0), _chunk(1), _chunk(2)], embeddings)

    results = store.search(np.array([0.9, 0.1, 0.0], dtype=np.float32), top_k=1)
    assert results[0].chunk.id == "0"


def test_ivf_save_and_load_roundtrips(tmp_path):
    store = FaissVectorStore(dim=3, index_type="ivf", nlist=2, nprobe=2)
    store.add(
        [_chunk(0), _chunk(1), _chunk(2)],
        np.array([[1, 0, 0], [0, 1, 0], [0, 0, 1]], dtype=np.float32),
    )
    store.save(tmp_path)

    loaded = FaissVectorStore.load(tmp_path)
    assert loaded.index_type == "ivf"
    assert loaded.size == 3
    results = loaded.search(np.array([0.9, 0.1, 0.0], dtype=np.float32), top_k=1)
    assert results[0].chunk.id == "0"


def test_save_and_load(tmp_path):
    store = FaissVectorStore(dim=2, index_type="flat")
    store.add([_chunk(0), _chunk(1)], np.array([[1, 0], [0, 1]], dtype=np.float32))
    store.save(tmp_path)

    loaded = FaissVectorStore.load(tmp_path)
    assert loaded.size == 2
    assert loaded.index_type == "flat"
    results = loaded.search(np.array([1, 0], dtype=np.float32), top_k=1)
    assert results[0].chunk.id == "0"
