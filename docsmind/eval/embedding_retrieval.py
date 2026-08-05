"""Small, model-independent helpers for labelled dense-retrieval evaluation."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Iterable


def load_embedding_eval(path: Path | str) -> dict[str, Any]:
    """Load and validate the BRISKODA embedding benchmark labels."""
    with Path(path).open(encoding="utf-8") as handle:
        dataset = json.load(handle)

    queries = dataset.get("queries")
    if not isinstance(queries, list) or not queries:
        raise ValueError("evaluation file must contain a non-empty queries list")

    seen_ids: set[str] = set()
    for position, item in enumerate(queries, start=1):
        query_id = str(item.get("id", "")).strip()
        question = str(item.get("question", "")).strip()
        relevant = item.get("relevant_post_ids")
        if not query_id or not question:
            raise ValueError(f"query {position} needs id and question")
        if query_id in seen_ids:
            raise ValueError(f"duplicate query id: {query_id}")
        if not isinstance(relevant, list) or not relevant:
            raise ValueError(f"query {query_id} needs relevant_post_ids")
        item["relevant_post_ids"] = [str(post_id) for post_id in relevant]
        seen_ids.add(query_id)
    return dataset


def score_post_rankings(
    queries: list[dict[str, Any]],
    ranked_post_ids: Iterable[list[str]],
    *,
    recall_at: tuple[int, ...] = (5, 10),
    mrr_depth: int = 10,
) -> dict[str, float]:
    """Score post-level rankings with Recall@k and MRR.

    Duplicate chunks from the same post are collapsed before scoring so a long
    post cannot occupy several ranks and make the metric look artificially good.
    """
    rankings = list(ranked_post_ids)
    if len(rankings) != len(queries):
        raise ValueError("one ranking is required for every evaluation query")

    recall_sums = {k: 0.0 for k in recall_at}
    reciprocal_rank_sum = 0.0
    for item, ranking in zip(queries, rankings, strict=True):
        unique_ranking = list(dict.fromkeys(str(post_id) for post_id in ranking))
        relevant = set(item["relevant_post_ids"])
        for k in recall_at:
            recall_sums[k] += len(relevant.intersection(unique_ranking[:k])) / len(
                relevant
            )
        first_rank = next(
            (
                rank
                for rank, post_id in enumerate(unique_ranking[:mrr_depth], start=1)
                if post_id in relevant
            ),
            None,
        )
        if first_rank is not None:
            reciprocal_rank_sum += 1.0 / first_rank

    count = len(queries)
    metrics = {f"recall@{k}": recall_sums[k] / count for k in recall_at}
    metrics[f"mrr@{mrr_depth}"] = reciprocal_rank_sum / count
    return metrics
