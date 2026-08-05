from contextlib import asynccontextmanager

from fastapi.testclient import TestClient

from docsmind.schemas import Citation, QueryResponse
from docsmind.serving import app as serving


class StubPipeline:
    def query(self, question: str, top_k: int | None = None) -> QueryResponse:
        return QueryResponse(
            answer="The Golf Mk7 uses MQB [1].",
            citations=[
                Citation(
                    marker=1,
                    source="https://en.wikipedia.org/wiki/Volkswagen_Golf_Mk7",
                    score=0.91,
                    snippet="The Golf Mk7 uses the MQB platform.",
                )
            ],
            model="openclaw",
            grounded=True,
            latency_ms=12.5,
        )


def _client(monkeypatch, pipeline=StubPipeline(), startup_error=None):
    @asynccontextmanager
    async def lifespan(app):
        serving._state["pipeline"] = pipeline
        serving._state["startup_error"] = startup_error
        yield
        serving._state.clear()

    monkeypatch.setattr(serving.app.router, "lifespan_context", lifespan)
    return TestClient(serving.app)


def test_home_serves_chat_ui(monkeypatch):
    with _client(monkeypatch) as client:
        response = client.get("/")

    assert response.status_code == 200
    assert "Ask the <span>Volkswagen Group</span> corpus" in response.text


def test_readiness_reflects_pipeline_startup(monkeypatch):
    with _client(monkeypatch, pipeline=None, startup_error="RuntimeError") as client:
        assert client.get("/live").status_code == 200
        response = client.get("/ready")

    assert response.status_code == 503
    assert response.json() == {"status": "not_ready", "reason": "RuntimeError"}


def test_query_returns_grounded_answer(monkeypatch):
    with _client(monkeypatch) as client:
        response = client.post("/query", json={"question": "Which platform?"})

    assert response.status_code == 200
    assert response.json()["grounded"] is True
    assert response.json()["citations"][0]["marker"] == 1
