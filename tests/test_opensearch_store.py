"""OpenSearch backend contract tests. All AWS calls are mocked."""

import json
from unittest.mock import MagicMock, patch

import numpy as np
import pytest
from opensearchpy.helpers.errors import BulkIndexError

from docsmind.index.opensearch_store import OpenSearchVectorStore
from docsmind.schemas import Chunk


def _chunk(i: int) -> Chunk:
    return Chunk(
        id=f"chunk-{i}",
        text=f"chunk text {i}",
        source="doc.md",
        metadata={"page": i},
    )


def _client(*, exists: bool = True, dim: int = 3) -> MagicMock:
    client = MagicMock()
    client.indices.exists.return_value = exists
    client.indices.get_mapping.return_value = {
        "docsmind-chunks": {
            "mappings": {
                "properties": {"embedding": {"dimension": dim}}
            }
        }
    }
    client.count.return_value = {"count": 0}
    return client


def _store(client: MagicMock, **kwargs) -> OpenSearchVectorStore:
    return OpenSearchVectorStore(
        dim=3,
        endpoint="https://example.aoss.us-east-1.on.aws",
        client=client,
        **kwargs,
    )


def test_creates_nextgen_cosine_mapping_without_engine_parameters():
    client = _client(exists=False)
    _store(client)

    body = client.indices.create.call_args.kwargs["body"]
    vector = body["mappings"]["properties"]["embedding"]

    assert body["settings"]["index.knn"] is True
    assert vector == {
        "type": "knn_vector",
        "dimension": 3,
        "space_type": "cosinesimil",
    }
    assert "engine" not in vector
    assert body["mappings"]["properties"]["metadata"]["enabled"] is False


def test_connect_uses_named_profile_and_aoss_sigv4_service():
    credentials = object()
    session = MagicMock()
    session.get_credentials.return_value = credentials
    client = _client(exists=False)

    with (
        patch("docsmind.index.opensearch_store.boto3.Session", return_value=session),
        patch("docsmind.index.opensearch_store.AWSV4SignerAuth") as signer,
        patch("docsmind.index.opensearch_store.OpenSearch", return_value=client) as os,
    ):
        OpenSearchVectorStore(
            dim=3,
            endpoint="https://example.aoss.us-east-1.on.aws",
            region="us-east-1",
            profile_name="docsmind",
        )

    signer.assert_called_once_with(credentials, "us-east-1", "aoss")
    assert os.call_args.kwargs["hosts"] == [
        {"host": "example.aoss.us-east-1.on.aws", "port": 443}
    ]
    assert os.call_args.kwargs["http_compress"] is False
    assert os.call_args.kwargs["verify_certs"] is True
    assert os.call_args.kwargs["timeout"] == 60
    assert os.call_args.kwargs["max_retries"] == 5
    assert os.call_args.kwargs["retry_on_timeout"] is True


def test_reuses_existing_index_and_validates_dimension():
    client = _client(exists=True, dim=3)
    _store(client)

    client.indices.create.assert_not_called()
    client.indices.get_mapping.assert_called_once_with(index="docsmind-chunks")


def test_rejects_existing_index_with_wrong_dimension():
    client = _client(exists=True, dim=384)

    with pytest.raises(ValueError, match="has dimension 384"):
        _store(client)


def test_add_builds_bulk_documents_with_stable_insertion_order():
    client = _client()
    client.count.side_effect = [{"count": 2}, {"count": 4}]
    store = _store(client)
    chunks = [_chunk(2), _chunk(3)]
    embeddings = np.array([[1, 0, 0], [0, 1, 0]], dtype=np.float32)

    with patch("docsmind.index.opensearch_store.bulk") as bulk_mock:
        store.add(chunks, embeddings)

    actions = list(bulk_mock.call_args.args[1])
    assert [action["_id"] for action in actions] == [
        "2:chunk-2",
        "3:chunk-3",
    ]
    assert actions[0]["_source"] == {
        "insertion_order": 2,
        "chunk_id": "chunk-2",
        "text": "chunk text 2",
        "source": "doc.md",
        "metadata": {"page": 2},
        "embedding": [1.0, 0.0, 0.0],
    }
    assert bulk_mock.call_args.kwargs["chunk_size"] == 500
    assert bulk_mock.call_args.kwargs["request_timeout"] == 120
    assert "refresh" not in bulk_mock.call_args.kwargs


def test_new_index_add_skips_cold_start_count_request():
    client = _client(exists=False)
    client.count.return_value = {"count": 1}
    store = _store(client)

    with patch("docsmind.index.opensearch_store.bulk"):
        store.add([_chunk(0)], np.array([[1, 0, 0]], dtype=np.float32))

    # Only the post-bulk visibility check runs; no pre-bulk cold-start count.
    assert client.count.call_count == 1


def test_add_rejects_count_and_dimension_mismatches():
    store = _store(_client())

    with pytest.raises(ValueError, match="count mismatch"):
        store.add([_chunk(0)], np.zeros((2, 3), dtype=np.float32))

    with pytest.raises(ValueError, match="dimension mismatch"):
        store.add([_chunk(0)], np.zeros((1, 4), dtype=np.float32))


def test_bulk_failure_does_not_leak_chunk_or_vector_data():
    client = _client(exists=False)
    store = _store(client)
    failure = BulkIndexError(
        "one failed",
        [
            {
                "index": {
                    "error": {"reason": "mapping rejected"},
                    "data": {
                        "text": "PRIVATE CORPUS TEXT",
                        "embedding": [0.1, 0.2, 0.3],
                    },
                }
            }
        ],
    )

    with (
        patch("docsmind.index.opensearch_store.bulk", side_effect=failure),
        pytest.raises(RuntimeError) as exc_info,
    ):
        store.add([_chunk(0)], np.array([[1, 0, 0]], dtype=np.float32))

    message = str(exc_info.value)
    assert message == "OpenSearch rejected 1 document(s): mapping rejected"
    assert "PRIVATE" not in message
    assert "embedding" not in message


def test_search_sends_knn_query_and_rebuilds_chunk():
    client = _client()
    client.count.return_value = {"count": 3}
    client.transport.perform_request.return_value = {
        "hits": {
            "hits": [
                {
                    "_score": 0.97,
                    "_source": {
                        "insertion_order": 0,
                        "chunk_id": "chunk-0",
                        "text": "chunk text 0",
                        "source": "doc.md",
                        "metadata": {"page": 0},
                    },
                }
            ]
        }
    }
    store = _store(client)

    results = store.search(np.array([0.9, 0.1, 0], dtype=np.float32), top_k=2)

    method, path = client.transport.perform_request.call_args.args[:2]
    body = client.transport.perform_request.call_args.kwargs["body"]
    assert method == "POST"
    assert path == "/docsmind-chunks/_search"
    assert body["size"] == 2
    assert body["query"]["knn"]["embedding"] == {
        "vector": pytest.approx([0.9, 0.1, 0.0]),
        "k": 2,
    }
    assert body["_source"] == {"excludes": ["embedding"]}
    assert results[0].chunk == _chunk(0)
    assert results[0].score == pytest.approx(0.97)


def test_search_empty_index_avoids_search_request():
    client = _client()
    store = _store(client)

    assert store.search(np.zeros(3, dtype=np.float32), top_k=5) == []
    client.transport.perform_request.assert_not_called()


def test_chunks_pages_with_search_after_and_caches_result():
    client = _client()
    client.transport.perform_request.side_effect = [
        {
            "hits": {
                "hits": [
                    {"_source": _source(0), "sort": [0]},
                    {"_source": _source(1), "sort": [1]},
                ]
            }
        },
        {
            "hits": {
                "hits": [
                    {"_source": _source(2), "sort": [2]},
                ]
            }
        },
    ]
    store = _store(client, page_size=2)

    assert [chunk.id for chunk in store.chunks] == [
        "chunk-0",
        "chunk-1",
        "chunk-2",
    ]
    assert store.chunks[0].metadata == {"page": 0}
    assert client.transport.perform_request.call_count == 2
    second_body = client.transport.perform_request.call_args_list[1].kwargs["body"]
    assert second_body["search_after"] == [1]

    # The second property read uses the in-process cache for BM25 startup.
    _ = store.chunks
    assert client.transport.perform_request.call_count == 2


def _source(i: int) -> dict:
    return {
        "insertion_order": i,
        "chunk_id": f"chunk-{i}",
        "text": f"chunk text {i}",
        "source": "doc.md",
        "metadata": {"page": i},
    }


def test_save_and_load_roundtrip_reconnect_marker(tmp_path):
    client = _client()
    store = _store(client, bulk_size=50, page_size=75)
    store.save(tmp_path)

    marker = json.loads((tmp_path / "meta.json").read_text())
    assert marker["backend"] == "opensearch"
    assert "credentials" not in marker
    assert "secret" not in json.dumps(marker).lower()

    loaded = OpenSearchVectorStore.load(tmp_path, client=client)
    assert loaded.index_type == "opensearch"
    assert loaded.dim == 3
    assert loaded._bulk_size == 50
    assert loaded._page_size == 75
    assert loaded._request_timeout == 60
    assert loaded._max_retries == 5


def test_load_rejects_another_backends_marker(tmp_path):
    (tmp_path / "meta.json").write_text('{"backend": "qdrant"}')

    with pytest.raises(ValueError, match="not OpenSearch"):
        OpenSearchVectorStore.load(tmp_path, client=_client())
