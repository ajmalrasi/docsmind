"""BM25 sparse retrieval tests (offline — rank-bm25 is pure Python)."""

from docsmind.retrieval.bm25 import BM25Index
from docsmind.schemas import Chunk


def _chunks() -> list[Chunk]:
    return [
        Chunk(id="0", text="HNSW builds a navigable small world graph", source="a.md"),
        Chunk(id="1", text="IVF partitions the space into Voronoi cells", source="b.md"),
        Chunk(id="2", text="product quantization compresses each vector", source="c.md"),
    ]


def test_exact_term_match_ranks_first():
    bm25 = BM25Index(_chunks())
    results = bm25.search("Voronoi cells", top_k=3)
    assert results[0].chunk.id == "1"  # the only chunk with those rare terms


def test_zero_overlap_returns_nothing():
    bm25 = BM25Index(_chunks())
    # No shared tokens with any chunk => no positive BM25 score => empty.
    assert bm25.search("kubernetes deployment yaml", top_k=3) == []


def test_empty_corpus_is_safe():
    assert BM25Index([]).search("anything", top_k=5) == []
