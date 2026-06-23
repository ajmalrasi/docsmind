"""The RAG pipeline: retrieve -> assemble grounded context -> generate -> cite.

This wires the retriever and LLM together. It enforces a light anti-hallucination
contract now (the model must flag insufficient context); Phase 5 expands this into
a full agentic guardrail.
"""

from __future__ import annotations

import re
import time

from docsmind.config import Settings
from docsmind.llm.base import LLMClient
from docsmind.retrieval.retriever import Retriever
from docsmind.schemas import Citation, QueryResponse, SearchResult

INSUFFICIENT = "INSUFFICIENT_CONTEXT"

SYSTEM_PROMPT = (
    "You are DocsMind, a question-answering assistant for technical and ML "
    "documentation. Answer ONLY from the numbered context passages provided. "
    "Cite every claim with its passage number in square brackets, e.g. [1] or "
    "[2][3]. Do not use outside knowledge. If the context does not contain enough "
    f"information to answer, reply with exactly: {INSUFFICIENT}"
)

_MARKER_RE = re.compile(r"\[(\d+)\]")


class RAGPipeline:
    def __init__(self, retriever: Retriever, llm: LLMClient, settings: Settings) -> None:
        self._retriever = retriever
        self._llm = llm
        self._settings = settings

    @staticmethod
    def _build_context(results: list[SearchResult]) -> str:
        blocks = []
        for i, result in enumerate(results, start=1):
            blocks.append(f"[{i}] (source: {result.chunk.source})\n{result.chunk.text}")
        return "\n\n".join(blocks)

    def query(self, question: str, top_k: int | None = None) -> QueryResponse:
        top_k = top_k or self._settings.top_k
        started = time.perf_counter()

        results = self._retriever.retrieve(question, top_k)

        if not results:
            return QueryResponse(
                answer=INSUFFICIENT,
                citations=[],
                model=self._llm.model,
                grounded=False,
                latency_ms=(time.perf_counter() - started) * 1000,
            )

        context = self._build_context(results)
        prompt = f"Context passages:\n\n{context}\n\nQuestion: {question}\n\nAnswer:"
        answer = self._llm.generate(SYSTEM_PROMPT, prompt, self._settings.max_tokens)

        grounded = INSUFFICIENT not in answer
        citations = self._extract_citations(answer, results) if grounded else []

        return QueryResponse(
            answer=answer,
            citations=citations,
            model=self._llm.model,
            grounded=grounded,
            latency_ms=(time.perf_counter() - started) * 1000,
        )

    @staticmethod
    def _extract_citations(
        answer: str, results: list[SearchResult]
    ) -> list[Citation]:
        cited_markers = {int(m) for m in _MARKER_RE.findall(answer)}
        # Keep only valid markers that map to a retrieved passage.
        cited_markers = {m for m in cited_markers if 1 <= m <= len(results)}
        citations = []
        for marker in sorted(cited_markers):
            result = results[marker - 1]
            snippet = result.chunk.text[:240].strip()
            citations.append(
                Citation(
                    marker=marker,
                    source=result.chunk.source,
                    score=round(result.score, 4),
                    snippet=snippet,
                )
            )
        return citations
