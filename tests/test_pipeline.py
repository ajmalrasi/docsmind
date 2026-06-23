"""Pipeline tests with a fake retriever + fake LLM (fully offline)."""

from docsmind.config import Settings
from docsmind.llm.base import LLMClient
from docsmind.pipeline import INSUFFICIENT, RAGPipeline
from docsmind.schemas import Chunk, SearchResult


class FakeRetriever:
    def __init__(self, results):
        self._results = results

    def retrieve(self, question, top_k):
        return self._results[:top_k]


class FakeLLM(LLMClient):
    def __init__(self, reply):
        self.model = "fake-model"
        self._reply = reply

    def generate(self, system, prompt, max_tokens):
        return self._reply


def _results():
    return [
        SearchResult(chunk=Chunk(id="a", text="HNSW is a graph index.", source="x.md"), score=0.9),
        SearchResult(chunk=Chunk(id="b", text="IVF partitions space.", source="y.md"), score=0.8),
    ]


def _pipeline(results, reply):
    return RAGPipeline(FakeRetriever(results), FakeLLM(reply), Settings(_env_file=None))


def test_grounded_answer_extracts_cited_markers():
    pipe = _pipeline(_results(), "HNSW is a graph-based index [1]. IVF uses cells [2].")
    resp = pipe.query("how do indexes work?", top_k=2)
    assert resp.grounded is True
    assert {c.marker for c in resp.citations} == {1, 2}
    assert resp.citations[0].source == "x.md"


def test_only_valid_markers_kept():
    # [3] is out of range for 2 retrieved passages and must be dropped.
    pipe = _pipeline(_results(), "Answer with bogus citation [3] and good one [1].")
    resp = pipe.query("q", top_k=2)
    assert {c.marker for c in resp.citations} == {1}


def test_insufficient_context_is_not_grounded():
    pipe = _pipeline(_results(), INSUFFICIENT)
    resp = pipe.query("q", top_k=2)
    assert resp.grounded is False
    assert resp.citations == []


def test_no_results_short_circuits():
    pipe = _pipeline([], "should not be used")
    resp = pipe.query("q", top_k=2)
    assert resp.grounded is False
    assert resp.answer == INSUFFICIENT
    assert resp.citations == []
