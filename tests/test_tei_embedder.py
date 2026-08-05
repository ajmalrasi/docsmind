import json

import httpx
import numpy as np
import pytest

from docsmind.index.embeddings import TEIEmbedder


def test_tei_embeds_documents_and_query_with_normalized_vectors():
    requests = []

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        body = request.read().decode()
        count = body.count("passage") or 1
        return httpx.Response(200, json=[[3.0, 4.0, 0.0]] * count)

    client = httpx.Client(transport=httpx.MockTransport(handler))
    embedder = TEIEmbedder(
        dimension=3,
        base_url="http://tei.internal:8080",
        client=client,
    )

    documents = embedder.embed_documents(["passage one", "passage two"])
    query = embedder.embed_query("question")

    assert documents.shape == (2, 3)
    assert np.allclose(documents, [[0.6, 0.8, 0.0], [0.6, 0.8, 0.0]])
    assert np.allclose(query, [0.6, 0.8, 0.0])
    assert all(request.url.path == "/embed" for request in requests)
    assert b'"normalize":true' in requests[0].content
    assert b'"truncate":true' in requests[0].content


def test_tei_rejects_wrong_dimension():
    client = httpx.Client(
        transport=httpx.MockTransport(
            lambda request: httpx.Response(200, json=[[1.0, 2.0]])
        )
    )
    embedder = TEIEmbedder(dimension=3, client=client)

    with pytest.raises(RuntimeError, match=r"expected \(N, 3\)"):
        embedder.embed_query("question")


def test_tei_batches_documents_and_preserves_order():
    requests: list[list[str]] = []

    def handler(request: httpx.Request) -> httpx.Response:
        inputs = json.loads(request.content)["inputs"]
        requests.append(inputs)
        return httpx.Response(200, json=[[float(text)] for text in inputs])

    client = httpx.Client(transport=httpx.MockTransport(handler))
    embedder = TEIEmbedder(dimension=1, batch_size=2, client=client)

    vectors = embedder.embed_documents(["1", "2", "3", "4", "5"])

    assert requests == [["1", "2"], ["3", "4"], ["5"]]
    assert vectors.shape == (5, 1)
    assert np.allclose(vectors, np.ones((5, 1)))


def test_tei_propagates_http_errors_without_leaking_inputs():
    client = httpx.Client(
        transport=httpx.MockTransport(
            lambda request: httpx.Response(503, json={"error": "loading"})
        )
    )
    embedder = TEIEmbedder(dimension=3, client=client)

    with pytest.raises(httpx.HTTPStatusError) as exc_info:
        embedder.embed_query("private question")

    assert "private question" not in str(exc_info.value)
