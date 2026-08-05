import pytest

from docsmind.eval.forum_retrieval import (
    collapse_chunks_to_posts,
    expand_thread_neighbours,
    rrf_fuse_ids,
)


def post(post_id, number, topic_id="t"):
    return {"post_id": str(post_id), "post_number": number, "topic_id": topic_id}


def test_rrf_rewards_ids_present_in_both_rankings():
    fused = rrf_fuse_ids(
        [["dense-only", "both"], ["both", "bm25-only"]], fusion_k=60
    )

    assert fused[0] == "both"


def test_collapse_chunks_keeps_first_rank_per_post():
    chunks = {
        "a0": {"post_id": "a"},
        "a1": {"post_id": "a"},
        "b0": {"post_id": "b"},
    }

    assert collapse_chunks_to_posts(["a0", "a1", "b0"], chunks) == ["a", "b"]


def test_thread_expansion_prefers_later_replies_then_previous_context():
    topic = [post("one", 1), post("two", 2), post("three", 3), post("four", 4)]
    by_id = {item["post_id"]: item for item in topic}

    expanded = expand_thread_neighbours(
        ["two"], by_id, {"t": topic}, previous_posts=1, next_posts=2
    )

    assert expanded == ["two", "three", "four", "one"]


def test_thread_expansion_rejects_negative_window():
    with pytest.raises(ValueError, match="cannot be negative"):
        expand_thread_neighbours([], {}, {}, previous_posts=-1)
