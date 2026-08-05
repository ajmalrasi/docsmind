import io
import json

import numpy as np
import pytest

from docsmind.index.embeddings import (
    BedrockCohereEmbedder,
    BedrockTitanEmbedder,
    Embedder,
)


class FakeBedrockClient:
    def __init__(self, dimension: int):
        self.dimension = dimension
        self.requests = []

    def invoke_model(self, **request):
        self.requests.append(request)
        body = json.loads(request["body"])
        vectors = []
        for index, _ in enumerate(body["texts"], start=1):
            vector = [0.0] * self.dimension
            vector[0] = 3.0
            vector[1] = 4.0 + index
            vectors.append(vector)
        payload = json.dumps({"embeddings": vectors}).encode()
        return {"body": io.BytesIO(payload)}


def test_bedrock_uses_document_and_query_task_types_and_batches():
    client = FakeBedrockClient(dimension=256)
    embedder = BedrockCohereEmbedder(
        dimension=256,
        batch_size=2,
        client=client,
    )

    documents = embedder.embed_documents(["one", "two", "three"])
    query = embedder.embed_query("which one?")

    assert documents.shape == (3, 256)
    assert query.shape == (256,)
    assert np.allclose(np.linalg.norm(documents, axis=1), 1.0)
    assert np.isclose(np.linalg.norm(query), 1.0)
    assert len(client.requests) == 3
    request_bodies = [json.loads(item["body"]) for item in client.requests]
    assert [body["input_type"] for body in request_bodies] == [
        "search_document",
        "search_document",
        "search_query",
    ]
    assert all(body["output_dimension"] == 256 for body in request_bodies)
    assert all(body["embedding_types"] == ["float"] for body in request_bodies)


def test_bedrock_rejects_bad_response_dimension():
    client = FakeBedrockClient(dimension=3)
    embedder = BedrockCohereEmbedder(dimension=256, client=client)

    with pytest.raises(RuntimeError, match=r"expected \(N, 256\)"):
        embedder.embed_documents(["one"])


class FakeTitanClient:
    def __init__(self, dimension: int):
        self.dimension = dimension
        self.requests = []

    def invoke_model(self, **request):
        self.requests.append(request)
        vector = [0.0] * self.dimension
        vector[0:2] = [3.0, 4.0]
        payload = json.dumps({"embedding": vector}).encode()
        return {"body": io.BytesIO(payload)}


def test_titan_uses_normalized_float_embeddings_for_documents_and_queries():
    client = FakeTitanClient(dimension=256)
    embedder = BedrockTitanEmbedder(dimension=256, client=client)

    documents = embedder.embed_documents(["one", "two"])
    query = embedder.embed_query("which one?")

    assert documents.shape == (2, 256)
    assert query.shape == (256,)
    assert np.allclose(documents[:, :2], [[0.6, 0.8], [0.6, 0.8]])
    bodies = [json.loads(item["body"]) for item in client.requests]
    assert [body["inputText"] for body in bodies] == ["one", "two", "which one?"]
    assert all(body["dimensions"] == 256 for body in bodies)
    assert all(body["normalize"] is True for body in bodies)


def test_local_provider_exposes_explicit_document_and_query_methods():
    class FakeModel:
        def get_sentence_embedding_dimension(self):
            return 3

        def encode(self, texts, **kwargs):
            return np.array([[3.0, 4.0, 0.0] for _ in texts], dtype=np.float32)

    embedder = Embedder("fake")
    embedder.__dict__["_model"] = FakeModel()

    assert embedder.embed_documents(["a", "b"]).shape == (2, 3)
    assert np.allclose(embedder.embed_query("q"), [0.6, 0.8, 0.0])
    assert np.allclose(embedder.encode(["legacy"]), [[0.6, 0.8, 0.0]])


@pytest.mark.parametrize("dimension", [1, 384, 2048])
def test_bedrock_rejects_unsupported_dimensions(dimension):
    with pytest.raises(ValueError, match="dimension"):
        BedrockCohereEmbedder(dimension=dimension, client=object())


@pytest.mark.parametrize("dimension", [1, 384, 1536])
def test_titan_rejects_unsupported_dimensions(dimension):
    with pytest.raises(ValueError, match="dimension"):
        BedrockTitanEmbedder(dimension=dimension, client=object())
