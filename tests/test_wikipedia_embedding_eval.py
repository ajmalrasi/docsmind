from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace

from scripts.wikipedia_embedding_eval import _score


class _FakeRetriever:
    def __init__(self, titles_by_query: dict[str, list[str]]) -> None:
        self._titles_by_query = titles_by_query

    def retrieve(self, question: str, k: int):
        return [
            SimpleNamespace(chunk=SimpleNamespace(metadata={"title": title}))
            for title in self._titles_by_query[question][:k]
        ]


def test_score_uses_any_labeled_source_title() -> None:
    queries = [
        {
            "id": "one",
            "question": "q1",
            "relevant_titles": ["Article A", "Article B"],
            "kind": "exact",
        },
        {
            "id": "two",
            "question": "q2",
            "relevant_titles": ["Article C"],
            "kind": "paraphrase",
        },
    ]
    retriever = _FakeRetriever(
        {"q1": ["Article B", "Other"], "q2": ["Other", "Article C"]}
    )

    metrics = _score(retriever, queries, k=2)

    assert metrics["hit@1"] == 0.5
    assert metrics["hit@3"] == 1.0
    assert metrics["mrr"] == 0.75
    assert metrics["details"][1]["first_relevant_rank"] == 2


def test_all_eval_labels_exist_in_versioned_snapshot() -> None:
    root = Path(__file__).parents[1]
    payload = json.loads(
        (root / "data/eval/volkswagen_wikipedia_queries.v1.json").read_text(
            encoding="utf-8"
        )
    )
    corpus_titles = {
        json.loads(line)["title"]
        for line in (
            root / "data/wikipedia/volkswagen.wikipedia.jsonl"
        ).read_text(encoding="utf-8").splitlines()
        if line.strip()
    }
    query_ids = [item["id"] for item in payload["queries"]]

    assert len(query_ids) == len(set(query_ids))
    assert len(query_ids) >= 20
    assert all(
        set(item["relevant_titles"]).issubset(corpus_titles)
        for item in payload["queries"]
    )
