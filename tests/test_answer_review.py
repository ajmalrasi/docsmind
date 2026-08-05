import pytest

from docsmind.eval.answer_review import (
    build_reviewed_answer_eval,
    rank_answer_candidates,
)


def post(post_id, number, text, topic_id="topic"):
    return {
        "post_id": str(post_id),
        "post_number": number,
        "topic_id": topic_id,
        "text": text,
        "posted_at": f"2026-01-{number:02d}",
    }


def test_candidate_ranking_excludes_problem_and_keeps_early_reply():
    query = {
        "question": "How do I code a replacement battery?",
        "relevant_post_ids": ["problem"],
    }
    posts = [
        post("problem", 1, "My replacement battery needs coding."),
        post("early", 2, "Try a diagnostic tool."),
        post("best", 3, "Use VCDS battery adaptation to code the replacement battery."),
        post("other", 4, "My tyres are new."),
    ]

    candidates = rank_answer_candidates(query, posts, top_k=1, early_replies=1)

    assert {candidate["post_id"] for candidate in candidates} == {"best", "early"}
    assert all(candidate["post_id"] != "problem" for candidate in candidates)


def test_review_builder_rejects_pending_labels():
    starter = {
        "corpus_version": "v1",
        "queries": [
            {
                "id": "q1",
                "question": "Question?",
                "topic_id": "topic",
                "relevant_post_ids": ["problem"],
            }
        ],
    }

    with pytest.raises(ValueError, match="pending queries"):
        build_reviewed_answer_eval(starter, {"q1": []}, {},)


def test_review_builder_validates_topic_and_exports_answer_labels():
    starter = {
        "corpus_version": "v1",
        "queries": [
            {
                "id": "q1",
                "question": "Question?",
                "topic_id": "topic",
                "relevant_post_ids": ["problem"],
            }
        ],
    }
    posts_by_id = {
        "problem": post("problem", 1, "Problem"),
        "answer": post("answer", 2, "Answer"),
    }

    result = build_reviewed_answer_eval(
        starter, {"q1": ["answer"]}, posts_by_id
    )

    assert result["label_status"] == "human_reviewed_answer_posts"
    assert result["queries"][0]["source_problem_post_ids"] == ["problem"]
    assert result["queries"][0]["relevant_post_ids"] == ["answer"]
