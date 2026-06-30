"""Reciprocal Rank Fusion tests (pure logic, fully offline)."""

from docsmind.retrieval.fusion import reciprocal_rank_fusion
from docsmind.schemas import Chunk, SearchResult


def _r(cid: str, score: float) -> SearchResult:
    return SearchResult(chunk=Chunk(id=cid, text=f"text {cid}", source="d.md"), score=score)


def test_doc_in_both_lists_outranks_doc_in_one():
    # "b" is rank-2 in each list; "a" is rank-1 in only the first. Appearing in
    # both lists should lift "b" above the single-list "a".
    dense = [_r("a", 0.9), _r("b", 0.8)]
    sparse = [_r("c", 5.0), _r("b", 4.0)]
    fused = reciprocal_rank_fusion([dense, sparse], k=60)
    ids = [r.chunk.id for r in fused]
    assert ids[0] == "b"
    assert set(ids) == {"a", "b", "c"}  # merged, not double-counted


def test_score_is_sum_of_reciprocal_ranks():
    # "a" is rank 0 in both lists => 1/60 + 1/60.
    fused = reciprocal_rank_fusion([[_r("a", 1.0)], [_r("a", 9.9)]], k=60)
    assert len(fused) == 1
    assert fused[0].score == 2 * (1.0 / 60)


def test_empty_lists_yield_empty():
    assert reciprocal_rank_fusion([[], []]) == []
