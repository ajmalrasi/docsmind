"""Candidate surfacing and label validation for forum answer-post review."""

from __future__ import annotations

import re
from typing import Any

from rank_bm25 import BM25Okapi

_WORD = re.compile(r"[a-z0-9]+")


def _tokens(text: str) -> list[str]:
    return _WORD.findall(text.lower())


def rank_answer_candidates(
    query: dict[str, Any],
    topic_posts: list[dict[str, Any]],
    *,
    top_k: int = 8,
    early_replies: int = 3,
) -> list[dict[str, Any]]:
    """Return BM25-ranked replies plus the earliest replies for human review.

    BM25 is only a review accelerator; it never creates relevance labels. Early
    replies are included because the accepted fix is often a short direct reply
    whose vocabulary differs from the owner's question.
    """
    if top_k < 1 or early_replies < 0:
        raise ValueError("top_k must be positive and early_replies non-negative")

    source_ids = {str(post_id) for post_id in query["relevant_post_ids"]}
    replies = [
        post for post in topic_posts if str(post["post_id"]) not in source_ids
    ]
    if not replies:
        return []

    tokenized = [_tokens(str(post["text"])) for post in replies]
    scores = BM25Okapi(tokenized).get_scores(_tokens(str(query["question"])))
    scored = sorted(
        zip(replies, scores, strict=True),
        key=lambda item: (
            -float(item[1]),
            int(item[0].get("post_number") or 0),
        ),
    )

    selected: dict[str, dict[str, Any]] = {}
    for post, score in scored[:top_k]:
        candidate = dict(post)
        candidate["review_score"] = float(score)
        candidate["candidate_reason"] = "bm25"
        selected[str(post["post_id"])] = candidate

    ordered_replies = sorted(
        replies,
        key=lambda post: (
            int(post.get("post_number") or 0),
            str(post.get("posted_at", "")),
        ),
    )
    score_by_id = {
        str(post["post_id"]): float(score) for post, score in scored
    }
    for post in ordered_replies[:early_replies]:
        post_id = str(post["post_id"])
        if post_id not in selected:
            candidate = dict(post)
            candidate["review_score"] = score_by_id[post_id]
            candidate["candidate_reason"] = "early_reply"
            selected[post_id] = candidate

    return sorted(
        selected.values(),
        key=lambda post: (
            -float(post["review_score"]),
            int(post.get("post_number") or 0),
        ),
    )


def build_reviewed_answer_eval(
    starter_dataset: dict[str, Any],
    labels: dict[str, list[str] | None],
    posts_by_id: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    """Validate human labels and build an answer-level evaluation artifact.

    An empty list means pending. ``None`` means the reviewer found no verified
    answer, so that query is documented but excluded from retrieval scoring.
    """
    query_ids = {str(item["id"]) for item in starter_dataset["queries"]}
    unknown = sorted(set(labels) - query_ids)
    if unknown:
        raise ValueError(f"labels contain unknown query ids: {unknown}")

    pending: list[str] = []
    reviewed_queries: list[dict[str, Any]] = []
    excluded_queries: list[dict[str, str]] = []
    for item in starter_dataset["queries"]:
        query_id = str(item["id"])
        selected = labels.get(query_id, [])
        if selected == []:
            pending.append(query_id)
            continue
        if selected is None:
            excluded_queries.append(
                {"id": query_id, "reason": "no_verified_answer_in_thread"}
            )
            continue
        if len(selected) != len(set(selected)):
            raise ValueError(f"query {query_id} contains duplicate post ids")

        normalized = [str(post_id) for post_id in selected]
        missing = [post_id for post_id in normalized if post_id not in posts_by_id]
        if missing:
            raise ValueError(f"query {query_id} references missing posts: {missing}")
        wrong_topic = [
            post_id
            for post_id in normalized
            if str(posts_by_id[post_id]["topic_id"]) != str(item["topic_id"])
        ]
        if wrong_topic:
            raise ValueError(
                f"query {query_id} labels posts from another topic: {wrong_topic}"
            )

        reviewed = dict(item)
        reviewed["source_problem_post_ids"] = reviewed.pop("relevant_post_ids")
        reviewed["relevant_post_ids"] = normalized
        reviewed_queries.append(reviewed)

    if pending:
        raise ValueError(
            f"review is incomplete; {len(pending)} pending queries: {pending}"
        )
    if not reviewed_queries:
        raise ValueError("review produced no answer-labelled queries")

    return {
        "corpus_version": starter_dataset["corpus_version"],
        "label_status": "human_reviewed_answer_posts",
        "description": "Post-level labels for replies or source posts containing a verified answer.",
        "queries": reviewed_queries,
        "excluded_queries": excluded_queries,
    }
