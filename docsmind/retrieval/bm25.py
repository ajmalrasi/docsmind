"""BM25 sparse retrieval (Phase 3).

Where in the pipeline: this sits at the **Search** stage, beside dense retrieval.
Dense search matches on *meaning* (embedding proximity); BM25 matches on *exact
terms* (lexical overlap, weighted by term rarity). They fail differently — dense
misses rare tokens like error codes, version numbers, and proper nouns; BM25
misses paraphrases. Running both and fusing them is the point of hybrid search.

This index is rebuilt in-memory from the stored chunks at startup. That is fine
for a small corpus (build is microseconds). At scale you would persist a real
inverted index (Qdrant sparse vectors, OpenSearch) instead of recomputing it.
"""

from __future__ import annotations

import re

from rank_bm25 import BM25Okapi

from docsmind.schemas import Chunk, SearchResult

_TOKEN_RE = re.compile(r"[a-z0-9]+")


def _tokenize(text: str) -> list[str]:
    # Lowercase + alphanumeric tokens. Deliberately simple; tokenization is itself
    # a tuning knob (stemming, stopwords) you would revisit if BM25 underperforms.
    return _TOKEN_RE.findall(text.lower())


class BM25Index:
    def __init__(self, chunks: list[Chunk]) -> None:
        self._chunks = chunks
        self._bm25 = BM25Okapi([_tokenize(c.text) for c in chunks]) if chunks else None

    def search(self, query: str, top_k: int) -> list[SearchResult]:
        if self._bm25 is None:
            return []
        scores = self._bm25.get_scores(_tokenize(query))
        # Rank by score, take top_k, drop zero-score (no term overlap) chunks.
        ranked = sorted(
            range(len(scores)), key=lambda i: scores[i], reverse=True
        )[:top_k]
        return [
            SearchResult(chunk=self._chunks[i], score=float(scores[i]))
            for i in ranked
            if scores[i] > 0
        ]
