import json

import pytest

from docsmind.eval.embedding_retrieval import (
    load_embedding_eval,
    score_post_rankings,
)


def test_score_collapses_duplicate_chunks_from_same_post():
    queries = [
        {"id": "q1", "question": "one", "relevant_post_ids": ["answer"]},
        {"id": "q2", "question": "two", "relevant_post_ids": ["target"]},
    ]
    rankings = [
        ["wrong", "wrong", "answer"],
        ["target", "other"],
    ]

    metrics = score_post_rankings(queries, rankings, recall_at=(1, 2), mrr_depth=2)

    assert metrics["recall@1"] == 0.5
    assert metrics["recall@2"] == 1.0
    assert metrics["mrr@2"] == 0.75


def test_loader_validates_duplicate_query_ids(tmp_path):
    path = tmp_path / "eval.json"
    item = {"id": "same", "question": "Question?", "relevant_post_ids": ["1"]}
    path.write_text(json.dumps({"queries": [item, item]}), encoding="utf-8")

    with pytest.raises(ValueError, match="duplicate query id"):
        load_embedding_eval(path)
