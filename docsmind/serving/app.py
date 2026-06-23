"""FastAPI app exposing /health and /query.

The pipeline (index + embedder + LLM) is built once at startup and reused across
requests.
"""

from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException

from docsmind.config import get_settings
from docsmind.factory import build_pipeline
from docsmind.schemas import HealthResponse, QueryRequest, QueryResponse

_state: dict = {}


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings = get_settings()
    _state["settings"] = settings
    try:
        _state["pipeline"] = build_pipeline(settings)
    except FileNotFoundError:
        # Serve /health with a clear error rather than crashing on boot.
        _state["pipeline"] = None
    yield
    _state.clear()


app = FastAPI(title="DocsMind", version="0.1.0", lifespan=lifespan)


@app.get("/health", response_model=HealthResponse)
def health() -> HealthResponse:
    settings = _state["settings"]
    pipeline = _state.get("pipeline")
    index_size = pipeline._retriever._store.size if pipeline else 0
    return HealthResponse(
        status="ok" if pipeline else "no_index",
        index_size=index_size,
        index_type=settings.index_type,
        model=settings.cloud_llm_model,
    )


@app.post("/query", response_model=QueryResponse)
def query(request: QueryRequest) -> QueryResponse:
    pipeline = _state.get("pipeline")
    if pipeline is None:
        raise HTTPException(
            status_code=503,
            detail="No index loaded. Run `make ingest` and restart the server.",
        )
    return pipeline.query(request.question, request.top_k)
