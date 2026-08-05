"""FastAPI app exposing the DocsMind web UI, health checks, and query API.

The pipeline (index + embedder + LLM) is built once at startup and reused across
requests.
"""

from __future__ import annotations

from contextlib import asynccontextmanager
import logging
from pathlib import Path

import httpx
from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse, JSONResponse
from opensearchpy.exceptions import OpenSearchException

from docsmind.config import get_settings
from docsmind.factory import build_pipeline
from docsmind.llm.base import LLMRequestError, LLMUnavailableError
from docsmind.schemas import HealthResponse, QueryRequest, QueryResponse

_state: dict = {}
_static_dir = Path(__file__).with_name("static")
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings = get_settings()
    _state["settings"] = settings
    try:
        _state["pipeline"] = build_pipeline(settings)
        _state["startup_error"] = None
    except Exception as exc:
        # Keep the process alive so /live and /ready explain a failed startup.
        # Do not expose exception text through the public API because provider
        # errors can include internal endpoints or credential metadata.
        logger.exception("DocsMind pipeline startup failed")
        _state["pipeline"] = None
        _state["startup_error"] = type(exc).__name__
    yield
    _state.clear()


app = FastAPI(title="DocsMind", version="0.1.0", lifespan=lifespan)


@app.get("/", include_in_schema=False)
def home() -> FileResponse:
    """Serve the dependency-free Volkswagen Group chat interface."""
    return FileResponse(_static_dir / "index.html")


@app.get("/live", include_in_schema=False)
def live() -> dict[str, str]:
    """Process-level liveness check used by ECS and the load balancer."""
    return {"status": "alive"}


@app.get("/ready", include_in_schema=False)
def ready():
    """Dependency readiness: OpenSearch index and pipeline loaded successfully."""
    if _state.get("pipeline") is None:
        return JSONResponse(
            status_code=503,
            content={
                "status": "not_ready",
                "reason": _state.get("startup_error", "pipeline_not_loaded"),
            },
        )
    return {"status": "ready"}


@app.get("/health", response_model=HealthResponse)
def health() -> HealthResponse:
    settings = _state["settings"]
    pipeline = _state.get("pipeline")
    store = pipeline._retriever._store if pipeline else None
    return HealthResponse(
        status="ok" if pipeline else "no_index",
        index_size=store.size if store else 0,
        index_type=store.index_type if store else settings.index_type,
        retrieval_mode=settings.retrieval_mode,
        model=pipeline._llm.model if pipeline else settings.llm_provider,
    )


@app.post("/query", response_model=QueryResponse)
def query(request: QueryRequest) -> QueryResponse:
    pipeline = _state.get("pipeline")
    if pipeline is None:
        raise HTTPException(
            status_code=503,
            detail="No index loaded. Run `make ingest` and restart the server.",
        )
    try:
        return pipeline.query(request.question, request.top_k)
    except (httpx.TimeoutException, httpx.TransportError, LLMUnavailableError) as exc:
        raise HTTPException(
            status_code=503,
            detail="A model service is temporarily unavailable. Try again shortly.",
        ) from exc
    except httpx.HTTPStatusError as exc:
        # TEI uses plain HTTP status handling; vLLM errors are translated by its
        # provider client before they reach this layer.
        raise HTTPException(
            status_code=503,
            detail="The embedding service could not process the question.",
        ) from exc
    except OpenSearchException as exc:
        raise HTTPException(
            status_code=503,
            detail="The search index is temporarily unavailable.",
        ) from exc
    except LLMRequestError as exc:
        raise HTTPException(
            status_code=502,
            detail="The generation service rejected the request configuration.",
        ) from exc
