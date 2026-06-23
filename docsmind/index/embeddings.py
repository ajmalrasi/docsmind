"""Embedding model wrapper.

Uses a self-hosted sentence-transformers model. Embeddings are L2-normalized so
that inner-product search (FAISS IndexFlatIP) is equivalent to cosine similarity.
"""

from __future__ import annotations

from functools import cached_property

import numpy as np


class Embedder:
    def __init__(self, model_name: str) -> None:
        self.model_name = model_name

    @cached_property
    def _model(self):
        # Imported lazily so importing this module doesn't pull in torch.
        from sentence_transformers import SentenceTransformer

        return SentenceTransformer(self.model_name)

    @property
    def dim(self) -> int:
        return int(self._model.get_sentence_embedding_dimension())

    def encode(self, texts: list[str]) -> np.ndarray:
        """Return an (N, dim) float32 array of normalized embeddings."""
        vectors = self._model.encode(
            texts,
            normalize_embeddings=True,
            convert_to_numpy=True,
            show_progress_bar=False,
        )
        return np.asarray(vectors, dtype=np.float32)
