"""Reciprocal Rank Fusion (Phase 3).

Where in the pipeline: between **Search** and **Rerank**. Dense and BM25 each
return a ranked list, but their scores live on different scales (cosine ~0–1 vs
BM25's unbounded term-frequency sums) — you cannot just add them. RRF sidesteps
that entirely by throwing away the scores and fusing on *rank position* only:

    score(doc) = sum over each list of  1 / (k + rank_in_that_list)

A document ranked highly by *both* retrievers floats to the top; one ranked
highly by only one still scores well. ``k`` (default 60, from the original paper)
softens the gap between rank 1 and rank 2 so a single list cannot dominate.

Documents are identified by ``chunk.id`` so the same chunk surfaced by both
retrievers is merged, not double-counted.
"""

from __future__ import annotations

from docsmind.schemas import SearchResult


def reciprocal_rank_fusion(
    result_lists: list[list[SearchResult]], k: int = 60
) -> list[SearchResult]:
    fused_scores: dict[str, float] = {}
    chunk_by_id: dict[str, SearchResult] = {}

    for results in result_lists:
        for rank, result in enumerate(results):
            cid = result.chunk.id
            fused_scores[cid] = fused_scores.get(cid, 0.0) + 1.0 / (k + rank)
            # Keep one representative SearchResult per chunk for the output.
            chunk_by_id.setdefault(cid, result)

    ordered_ids = sorted(fused_scores, key=lambda cid: fused_scores[cid], reverse=True)
    return [
        SearchResult(chunk=chunk_by_id[cid].chunk, score=fused_scores[cid])
        for cid in ordered_ids
    ]
