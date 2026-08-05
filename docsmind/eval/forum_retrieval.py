"""Evaluation helpers for hybrid and thread-aware forum retrieval."""

from __future__ import annotations

from collections import defaultdict
from typing import Any, Iterable


def rrf_fuse_ids(
    rankings: Iterable[list[str]],
    *,
    fusion_k: int = 60,
    top_k: int | None = None,
) -> list[str]:
    """Fuse ID rankings with Reciprocal Rank Fusion.

    Duplicate IDs inside one ranking are ignored so multiple chunks from one
    post cannot collect artificial extra votes.
    """
    if fusion_k < 1:
        raise ValueError("fusion_k must be positive")
    scores: dict[str, float] = defaultdict(float)
    best_rank: dict[str, int] = {}
    for ranking in rankings:
        seen: set[str] = set()
        for rank, item_id in enumerate(ranking, start=1):
            item_id = str(item_id)
            if item_id in seen:
                continue
            seen.add(item_id)
            scores[item_id] += 1.0 / (fusion_k + rank)
            best_rank[item_id] = min(best_rank.get(item_id, rank), rank)
    ordered = sorted(scores, key=lambda item_id: (-scores[item_id], best_rank[item_id], item_id))
    return ordered[:top_k] if top_k is not None else ordered


def collapse_chunks_to_posts(
    ranked_chunk_ids: Iterable[str],
    chunks_by_id: dict[str, dict[str, Any]],
) -> list[str]:
    """Collapse ranked chunks to the first occurrence of each source post."""
    posts: list[str] = []
    seen: set[str] = set()
    for chunk_id in ranked_chunk_ids:
        post_id = str(chunks_by_id[str(chunk_id)]["post_id"])
        if post_id not in seen:
            posts.append(post_id)
            seen.add(post_id)
    return posts


def expand_thread_neighbours(
    ranked_post_ids: Iterable[str],
    posts_by_id: dict[str, dict[str, Any]],
    posts_by_topic: dict[str, list[dict[str, Any]]],
    *,
    previous_posts: int = 1,
    next_posts: int = 2,
    top_k: int | None = None,
) -> list[str]:
    """Expand each hit with a bounded, deterministic conversation window.

    The seed remains first, followed by later replies and then earlier context.
    No relevance label is used. This models the production action "retrieve a
    post, then bring nearby conversation" without importing the whole thread.
    """
    if previous_posts < 0 or next_posts < 0:
        raise ValueError("thread window sizes cannot be negative")

    topic_positions: dict[str, dict[str, int]] = {}
    for topic_id, topic_posts in posts_by_topic.items():
        topic_positions[str(topic_id)] = {
            str(post["post_id"]): index for index, post in enumerate(topic_posts)
        }

    expanded: list[str] = []
    seen: set[str] = set()

    def append(post_id: str) -> bool:
        if post_id not in seen:
            expanded.append(post_id)
            seen.add(post_id)
        return top_k is not None and len(expanded) >= top_k

    for seed_id in ranked_post_ids:
        seed_id = str(seed_id)
        if seed_id not in posts_by_id:
            continue
        if append(seed_id):
            break
        seed = posts_by_id[seed_id]
        topic_id = str(seed["topic_id"])
        topic_posts = posts_by_topic[topic_id]
        position = topic_positions[topic_id][seed_id]
        for offset in range(1, next_posts + 1):
            candidate = position + offset
            if candidate < len(topic_posts) and append(str(topic_posts[candidate]["post_id"])):
                return expanded
        for offset in range(1, previous_posts + 1):
            candidate = position - offset
            if candidate >= 0 and append(str(topic_posts[candidate]["post_id"])):
                return expanded
    return expanded
