import json

import pytest

from docsmind.index.embedding_manifest import (
    save_embedding_manifest,
    validate_embedding_manifest,
)


class FakeEmbedder:
    provider_name = "bedrock"
    model_name = "cohere.embed-v4:0"
    dim = 1024


def test_embedding_manifest_round_trip(tmp_path):
    save_embedding_manifest(tmp_path, FakeEmbedder())

    manifest = json.loads((tmp_path / "embedding.json").read_text())
    assert manifest == {
        "version": 1,
        "provider": "bedrock",
        "model": "cohere.embed-v4:0",
        "dimension": 1024,
    }
    validate_embedding_manifest(tmp_path, FakeEmbedder())


def test_embedding_manifest_rejects_same_dimension_different_model(tmp_path):
    save_embedding_manifest(tmp_path, FakeEmbedder())

    class WrongModel(FakeEmbedder):
        model_name = "another-1024-model"

    with pytest.raises(ValueError, match="Embedding/index mismatch"):
        validate_embedding_manifest(tmp_path, WrongModel())


def test_missing_manifest_keeps_legacy_indexes_loadable(tmp_path):
    validate_embedding_manifest(tmp_path, FakeEmbedder())
