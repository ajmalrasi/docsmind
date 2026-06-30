"""Shared domain models and API schemas (pydantic v2)."""

from __future__ import annotations

from pydantic import BaseModel, Field


class Chunk(BaseModel):
    """A unit of indexed text with provenance."""

    id: str
    text: str
    source: str
    metadata: dict = Field(default_factory=dict)


class SearchResult(BaseModel):
    """A retrieved chunk plus its similarity score (cosine, higher is better)."""

    chunk: Chunk
    score: float


class Citation(BaseModel):
    """A source surfaced to the caller alongside an answer."""

    marker: int = Field(..., description="The [n] marker the model used in the answer.")
    source: str
    score: float
    snippet: str


class QueryRequest(BaseModel):
    question: str = Field(..., min_length=1)
    top_k: int | None = Field(default=None, ge=1, le=20)


class QueryResponse(BaseModel):
    answer: str
    citations: list[Citation]
    model: str
    grounded: bool = Field(
        ..., description="False when the model flagged the context as insufficient."
    )
    latency_ms: float


class HealthResponse(BaseModel):
    status: str
    index_size: int
    index_type: str
    retrieval_mode: str
    model: str
