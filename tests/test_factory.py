"""Composition-root tests for vector backend selection."""

from unittest.mock import patch

import pytest

from docsmind.config import Settings
from docsmind.factory import load_store, new_store


def _settings(**updates) -> Settings:
    base = {
        "vector_backend": "opensearch",
        "opensearch_endpoint": "https://example.aoss.us-east-1.on.aws",
        "opensearch_index": "test-chunks",
        "aws_region": "us-east-1",
        "aws_profile": "docsmind",
    }
    return Settings(_env_file=None, **(base | updates))


def test_new_store_wires_opensearch_settings():
    with patch(
        "docsmind.index.opensearch_store.OpenSearchVectorStore"
    ) as store_class:
        result = new_store(_settings(), dim=384)

    assert result is store_class.return_value
    store_class.assert_called_once_with(
        dim=384,
        endpoint="https://example.aoss.us-east-1.on.aws",
        index_name="test-chunks",
        region="us-east-1",
        profile_name="docsmind",
        bulk_size=500,
        page_size=1000,
        request_timeout=60,
        max_retries=5,
        recreate=True,
    )


def test_load_store_reconnects_with_current_non_secret_settings(tmp_path):
    settings = _settings(index_dir=tmp_path)
    with patch(
        "docsmind.index.opensearch_store.OpenSearchVectorStore.load"
    ) as load:
        result = load_store(settings)

    assert result is load.return_value
    load.assert_called_once_with(
        tmp_path,
        endpoint="https://example.aoss.us-east-1.on.aws",
        index_name="test-chunks",
        region="us-east-1",
        profile_name="docsmind",
    )


@pytest.mark.parametrize("operation", [new_store, load_store])
def test_unknown_backend_fails_closed(operation):
    settings = Settings(_env_file=None, vector_backend="typo")

    with pytest.raises(ValueError, match="Unknown vector_backend"):
        if operation is new_store:
            operation(settings, dim=3)
        else:
            operation(settings)
