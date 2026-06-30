"""HybridRetriever tests with a fake embedder + real FAISS store + BM25.

Offline: the embedder is faked (no model download); FAISS flat and rank-bm25 run
in-process.
"""

import numpy as np

from docsmind.index.faiss_store import FaissVectorStore
from docsmind.retrieval.retriever import HybridRetriever
from docsmind.schemas import Chunk, SearchResult


class FakeEmbedder:
    """Returns a fixed query vector so dense ranking is deterministic."""

    def __init__(self, query_vec):
        self._q = np.array([query_vec], dtype=np.float32)

    def encode(self, texts):
        return self._q


def _store() -> FaissVectorStore:
    store = FaissVectorStore(dim=3, index_type="flat")
    chunks = [
        Chunk(id="0", text="black holes bend spacetime", source="a.md"),
        Chunk(id="1", text="IVF partitions vectors into Voronoi cells", source="b.md"),
        Chunk(id="2", text="galaxies cluster along cosmic filaments", source="c.md"),
    ]
    vecs = np.array([[1, 0, 0], [0, 1, 0], [0, 0, 1]], dtype=np.float32)
    store.add(chunks, vecs)
    return store


def test_hybrid_fuses_dense_and_sparse_signals():
    # Dense query points at chunk 0; the words "Voronoi cells" only hit chunk 1
    # via BM25. A good fusion surfaces BOTH in the top results.
    retriever = HybridRetriever(
        FakeEmbedder([0.9, 0.1, 0.0]), _store(), candidate_k=10
    )
    results = retriever.retrieve("what are Voronoi cells", top_k=2)
    ids = {r.chunk.id for r in results}
    assert ids == {"0", "1"}


def test_reranker_reorders_candidates():
    # A fake reranker that prefers chunk 2 should pull it to the front regardless
    # of the fused order.
    class FakeReranker:
        def rerank(self, query, results, top_k):
            ordered = sorted(results, key=lambda r: r.chunk.id == "2", reverse=True)
            return [SearchResult(chunk=r.chunk, score=1.0) for r in ordered[:top_k]]

    retriever = HybridRetriever(
        FakeEmbedder([0.9, 0.1, 0.0]),
        _store(),
        candidate_k=10,
        reranker=FakeReranker(),
    )
    results = retriever.retrieve("anything", top_k=3)
    assert results[0].chunk.id == "2"
