# Implementing `OpenSearchVectorStore`

Date implemented: 2026-07-16

## Pipeline insertion point

```text
Ingest -> Chunk -> Embed -> Index -> Query -> Embed -> Search -> Rerank -> Generate
                            ^                         ^
                            |                         |
                   OpenSearch.add()          OpenSearch.search()
```

OpenSearch replaces FAISS or Qdrant only at the **Index/Search** stage. The
insertion points are:

- `docsmind/factory.py::new_store()` during ingestion;
- `docsmind/factory.py::load_store()` during query startup;
- `docsmind/index/opensearch_store.py::OpenSearchVectorStore` for storage and search.

The rest of the pipeline continues to depend on the existing `VectorStore`
interface.

## What was added

- `docsmind/index/opensearch_store.py`
- OpenSearch settings in `docsmind/config.py`
- factory routing in `docsmind/factory.py`
- `boto3` and `opensearch-py` dependencies in `pyproject.toml`
- environment examples in `.env.example`
- offline AWS contract tests in `tests/test_opensearch_store.py`
- backend-selection tests in `tests/test_factory.py`

The configured backend is selected with:

```env
DOCSMIND_VECTOR_BACKEND=opensearch
DOCSMIND_OPENSEARCH_ENDPOINT=https://<collection-id>.aoss.us-east-1.on.aws
DOCSMIND_OPENSEARCH_INDEX=docsmind-chunks
DOCSMIND_AWS_REGION=us-east-1
DOCSMIND_AWS_PROFILE=docsmind
```

Credentials are resolved by boto3. They are not fields on `Settings` and are
not stored in the repository.

## Index mapping

The actual mapping is structurally equivalent to:

```json
{
  "settings": {
    "index.knn": true
  },
  "mappings": {
    "dynamic": "strict",
    "properties": {
      "insertion_order": {"type": "long"},
      "chunk_id": {"type": "keyword"},
      "text": {"type": "text"},
      "source": {"type": "keyword"},
      "metadata": {"type": "object", "enabled": false},
      "embedding": {
        "type": "knn_vector",
        "dimension": 384,
        "space_type": "cosinesimil"
      }
    }
  }
}
```

Why these choices:

- `dimension=384` must match `BAAI/bge-small-en-v1.5`.
- `cosinesimil` matches normalized sentence-transformer embeddings.
- NextGen Serverless selects its Faiss/HNSW engine, so the mapping does not set
  Classic collection `engine` or `mode` parameters.
- `dynamic=strict` catches accidental schema drift.
- `metadata.enabled=false` preserves provenance in `_source` without creating
  an unbounded set of mapping fields from arbitrary loader metadata.
- `insertion_order` lets the backend return every chunk deterministically for
  the existing in-memory BM25 index.

## Ingestion path

`OpenSearchVectorStore.add()`:

1. Validates `(N, 384)` embedding shape and chunk count.
2. Assigns a stable integer insertion order.
3. Builds bulk index actions containing chunk payload plus vector.
4. Sends batches of 500 documents through the OpenSearch Bulk API.
5. Polls `_count` until the Serverless refresh cycle exposes every document.
6. Writes only non-secret reconnect metadata to `data/index/meta.json`.

Bulk failures are caught and re-raised with only the failure count and service
reason. The normal `BulkIndexError` embeds complete failed source documents and
vectors; allowing that exception into logs would leak the private corpus.

## Query path

`OpenSearchVectorStore.search()` sends:

```json
{
  "size": 4,
  "_source": {"excludes": ["embedding"]},
  "query": {
    "knn": {
      "embedding": {
        "vector": ["<384 floats>"],
        "k": 4
      }
    }
  }
}
```

The vector is excluded from returned `_source` because retrieval needs the
chunk payload and score, not another 384 floats over the network.

The hybrid path remains:

```text
OpenSearch dense k-NN ----+
                          +-> RRF -> optional reranker
in-memory BM25 -----------+
```

At startup, `store.chunks` pages the remote index with `search_after`, sorted by
`insertion_order`. Those chunks build the existing `BM25Index`. This preserves
the current production behavior, although native OpenSearch BM25 is a logical
future optimization.

## Real AWS failures and fixes

The offline suite passed before the first cloud run. Three issues appeared only
against NextGen OpenSearch Serverless.

### 1. Cold search compute exceeded the default timeout

Observed:

```text
ReadTimeout: read timeout=10
```

The index was created, but the immediate count request hit the client's default
10-second timeout while Serverless warmed its search compute.

Fix:

- request timeout: 60 seconds;
- maximum retries: 5;
- retry timeouts and transient `429/502/503/504` responses;
- skip the pre-ingestion count when a new index is known to contain zero docs.

### 2. `refresh=wait_for` is unsupported

Observed:

```text
wait_for refresh policy is not supported
```

That bulk option works on normal OpenSearch domains but not this Serverless
collection.

Fix:

- submit ordinary bulk requests;
- poll `_count` after all batches;
- finish ingestion only when all expected documents are visible.

### 3. Compressed signed search bodies failed checksum verification

Observed:

```text
403 Request Content Checksum Verification Failed
```

Identity, IAM, and count requests worked. JSON search bodies failed when the
client compressed them.

Fix:

- explicitly use `POST <index>/_search`;
- set `http_compress=False` for this NextGen Serverless client.

The corpus is small enough that correctness is worth more than gzip savings.

## Verified results

Recorded remote-ingestion result:

```text
loaded_documents=2098
produced_chunks=3207
embedding_dimension=384
indexed_vectors=3207
backend=opensearch
```

Real production retrieval using the existing question:

```text
vector_count=3207
chunk_count=3207
result_count=4
top_source=VAGBAY/2026-03-22/window-00002
relevant_phrase_found=True
```

The test suite after the cloud fixes:

```text
52 passed
```

Recorded read-only smoke timing after ingestion (`5` runs, collection already
warm):

```text
bm25_payload_load_ms=12704.39
dense_ms  min=667.58 median=720.35 mean=760.75
hybrid_ms min=638.64 median=684.93 mean=737.33
```

The 12.7-second payload load is startup work: four paginated requests fetch all
3,207 chunk payloads so local BM25 can be built. It is cached for the life of the
process. The dense and hybrid timings are network-dominated at this corpus size;
the small difference between their medians is normal run-to-run variance, not
evidence that hybrid computation is free.

## Trade-offs

Compared at the same Index/Search stage:

| Backend | Strength | Cost/constraint |
|---|---|---|
| FAISS flat | Exact, fast, free, simple | One process; manual persistence/scaling |
| Qdrant | Self-hosted service and filters | Operate the service yourself |
| OpenSearch Serverless | Managed scaling, IAM, vector and lexical engine | Network/cold-start latency and AWS cost |

The current hybrid implementation downloads all chunk payloads once to rebuild
BM25. At 3,207 chunks this is reasonable. At millions of chunks, BM25 should move
into OpenSearch and dense plus lexical results should be fused from remote
queries instead.

## Interview depth signal

The useful story is not “I connected OpenSearch.” It is:

> I preserved a backend-neutral vector-store contract, used a NextGen-compatible
> cosine mapping, signed with `aoss`, bulk-ingested 3,207 private-but-anonymized
> chunks, and validated hybrid retrieval. Real integration exposed cold-start,
> refresh-policy, and signed-body checksum differences that mocks missed; I fixed
> each at the client boundary and retained a 52-test offline suite.

The next evidence to collect is cold-versus-warm query latency, ingestion
throughput, retrieval recall against FAISS, and actual AWS cost.

Run the repeatable, content-safe smoke benchmark with:

```bash
make digitalocean-opensearch-smoke \
  DIGITALOCEAN_HOST=user@droplet-ip
```

It prints counts and latency summaries but never chunk text.
