"""Cross-encoder reranker (Phase 3).

Where in the pipeline: the **Rerank** stage, the last step before the chunks
reach the LLM. Fusion gives a good candidate set cheaply; the reranker reorders
that small set with a much stronger — and much slower — relevance model.

The key distinction to hold onto:

    bi-encoder  (the Embedder)      encodes query and document *separately*, then
                                    compares vectors. Fast, pre-computable, but
                                    the two never "see" each other.
    cross-encoder (this)            feeds (query, document) together through the
                                    transformer and outputs one relevance score.
                                    Far more accurate, but you must run the model
                                    once per candidate at query time — so you only
                                    ever apply it to the top ~20, never the corpus.

That cost is why this is gated behind ``rerank_enabled`` and meant for the beast
GPU. The model is loaded lazily so importing this module stays cheap.
"""

from __future__ import annotations

from functools import cached_property

from docsmind.schemas import SearchResult


class CrossEncoderReranker:
    def __init__(self, model_name: str) -> None:
        self.model_name = model_name

    @cached_property
    def _model(self):
        # Imported lazily so module import doesn't pull in torch.
        from sentence_transformers import CrossEncoder

        return CrossEncoder(self.model_name)

    def rerank(
        self, query: str, results: list[SearchResult], top_k: int
    ) -> list[SearchResult]:
        if not results:
            return []
        pairs = [(query, r.chunk.text) for r in results]
        scores = self._model.predict(pairs)
        reranked = sorted(
            zip(results, scores), key=lambda rs: rs[1], reverse=True
        )
        return [
            SearchResult(chunk=r.chunk, score=float(s)) for r, s in reranked[:top_k]
        ]
