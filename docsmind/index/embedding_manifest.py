"""Persist the embedding identity next to a vector-store reconnect marker."""

from __future__ import annotations

import json
from pathlib import Path

from docsmind.index.embeddings import EmbeddingProvider

_FILE_NAME = "embedding.json"


def save_embedding_manifest(path: Path | str, embedder: EmbeddingProvider) -> None:
    """Record which embedding space produced an index."""
    directory = Path(path)
    directory.mkdir(parents=True, exist_ok=True)
    manifest = {
        "version": 1,
        "provider": embedder.provider_name,
        "model": embedder.model_name,
        "dimension": embedder.dim,
    }
    (directory / _FILE_NAME).write_text(
        json.dumps(manifest, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def validate_embedding_manifest(
    path: Path | str, embedder: EmbeddingProvider
) -> None:
    """Reject query/index model mismatches; allow pre-manifest legacy indexes."""
    manifest_path = Path(path) / _FILE_NAME
    if not manifest_path.exists():
        return
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    expected = (
        embedder.provider_name,
        embedder.model_name,
        embedder.dim,
    )
    actual = (
        manifest.get("provider"),
        manifest.get("model"),
        manifest.get("dimension"),
    )
    if actual != expected:
        raise ValueError(
            "Embedding/index mismatch: index was built with "
            f"provider={actual[0]!r}, model={actual[1]!r}, dimension={actual[2]!r}; "
            "the query path is configured for "
            f"provider={expected[0]!r}, model={expected[1]!r}, "
            f"dimension={expected[2]!r}. Reconfigure or re-ingest into a new index."
        )
