# S3 data ingestion with Airflow and a live embedding service

## Status

This is the planned architecture. DocsMind currently has the parsing,
chunking, embedding, OpenSearch, and live FastAPI query pieces, but it does not
yet have the S3 event, Airflow DAG, manifest store, or ingestion worker. The
design below is the next production-shaped extension.

## Pipeline position

This architecture automates the **Ingest → Chunk → Embed → Index** side of the
system. It does not replace the online query path:

```text
New source file
  → S3 (versioned bucket)
  → S3 notification
  → SQS queue + dead-letter queue
  → Airflow DAG / ingestion worker
  → parse and normalize
  → chunk
  → content/version check
  → embedding service
  → OpenSearch upsert
  → manifest/status update

User question
  → FastAPI
  → embedding service
  → OpenSearch dense + BM25 + RRF
  → vLLM
  → cited answer
```

Airflow is the orchestrator. It schedules and retries work; it is not the
embedding server and it does not run inside the FastAPI request path.

## Can Airflow use the live embedding endpoint?

Yes. An Airflow task can send bounded batches of chunks to the same private TEI
or embedding API used by FastAPI. This is appropriate for small or occasional
updates:

```text
FastAPI online query ─┐
                      ├─→ private embedding endpoint ─→ OpenSearch
Airflow batch job ────┘
```

The two callers must be treated as different workloads. User queries need low
tail latency. Ingestion needs throughput. A large batch must not consume all
embedding concurrency and make the UI slow.

## Recommended AWS topology

```text
S3 bucket (versioning enabled)
  → S3 Event Notification
  → SQS ingestion queue
       └→ SQS dead-letter queue
  → Airflow sensor or scheduled drain DAG
  → ECS ingestion task
       ├→ S3 download and parser
       ├→ manifest/idempotency store (DynamoDB)
       ├→ private TEI embedding service
       └→ OpenSearch Serverless bulk API

FastAPI ECS task ───────────────→ same embedding service for user questions
```

Airflow can run on MWAA, a dedicated Airflow deployment, or an existing
platform. For this project, the DAG should launch an ECS task for the actual
work rather than embedding thousands of chunks inside the Airflow scheduler or
worker process.

## Why SQS is between S3 and Airflow

S3 notifications can be duplicated and can arrive out of order. SQS provides:

- durable buffering when files arrive faster than embeddings can run;
- visibility timeouts and retries;
- a dead-letter queue for poison files;
- back-pressure independent of the web application;
- a stable unit of work for Airflow to drain.

For a low-volume first version, Airflow can periodically list S3 and compare
objects against the manifest. The S3 → SQS path is preferable once uploads are
frequent or reliability matters.

## Object and manifest contracts

Use a stable key layout, for example:

```text
s3://docsmind-corpus/volkswagen/<source>/<document-id>.json
```

Enable S3 versioning. Each event should carry the bucket, object key, version
ID, and ETag. A manifest record should contain at least:

```text
source_id
s3_uri
s3_version_id
content_hash
parser_version
chunking_version
embedding_model
embedding_revision
vector_dimension
chunk_ids
status
updated_at
error_code
```

The content hash and version are the idempotency key. If Airflow retries the
same event, the worker sees that the exact version is already complete and
skips duplicate embedding.

## DAG shape

One DAG run can process many queue messages, but each document should have a
bounded task unit:

```text
drain_sqs
  → download_document
  → parse_document
  → normalize_and_hash
  → short_circuit_if_unchanged
  → chunk_document
  → embed_chunks
  → bulk_upsert_opensearch
  → remove_superseded_chunks
  → mark_manifest_complete
```

A practical DAG should configure:

- an Airflow pool such as `embedding_pool` with a small slot count;
- retry with exponential backoff for TEI, S3, and OpenSearch transient errors;
- a task timeout longer than the largest expected document;
- an SQS visibility timeout longer than that task timeout;
- alerts for failed DAG runs and dead-letter messages;
- a reconciliation DAG that scans S3 and repairs missed notifications.

Airflow tasks should pass object references and job IDs, not large document
contents through XCom.

## Incremental processing

Only new or changed material should be embedded:

| Event | Action |
|---|---|
| New object | Parse, chunk, embed, and upsert |
| Same version delivered again | Skip as already complete |
| Changed object | Embed new version, then retire old chunks |
| Deleted object | Delete or tombstone its chunks |
| Parser/chunker version changed | Reprocess affected documents |
| Embedding model/revision changed | Build a new compatible index |

Chunk IDs should be deterministic, for example:

```text
hash(source_id + document_version + chunk_position + chunking_version)
```

This makes OpenSearch bulk writes idempotent and prevents duplicate vectors.

## Safe OpenSearch updates

For ordinary document updates:

1. parse and embed the new version;
2. bulk upsert the new chunk IDs;
3. validate bulk responses and vector dimensions;
4. mark the new version active in the manifest;
5. delete or tombstone the old version's chunk IDs.

Do not delete the old chunks before the replacement is successfully indexed.

For a large rebuild, use a versioned index and an alias:

```text
docsmind-volkswagen-v18  ← build and validate privately
          ↓
docsmind-volkswagen-current  ← atomic alias switch
```

This prevents users from searching a half-built index.

## Sharing the live endpoint safely

The initial implementation can share the endpoint:

```text
FastAPI: one question at a time, high priority, small request
Airflow: bounded chunk batches, low priority, limited concurrency
```

Controls required before enabling it:

- Airflow pool limiting embedding tasks;
- maximum batch size matching TEI configuration;
- request timeout and retry policy;
- separate metrics for online latency and batch throughput;
- rate limiting or priority queues so online traffic wins;
- circuit breaking when TEI is overloaded;
- OpenSearch bulk-size limits and retry handling.

The current CPU TEI profile uses small batches for development. The prepared
GPU TEI profile is designed for larger batches. The endpoint can be the same
model and revision in both cases, but the batch envelope must be configured for
the actual hardware.

## When to split batch embedding from online embedding

Sharing is reasonable when ingestion is occasional and the corpus is small.
Split the services when ingestion is frequent, documents are large, or query
latency has a real SLO:

```text
Online service: always available, low concurrency, low tail latency
Batch service: scale-to-zero, larger batches, throughput optimized
```

Both services should use the same pinned model revision, pooling method, vector
dimension, and text normalization. Otherwise chunks embedded by Airflow and
questions embedded by FastAPI will not occupy the same vector space.

In the current AWS design, the natural split is:

- FastAPI queries use the always-on CPU TEI service until GPU quota is
  available;
- Airflow can later call the GPU TEI service for bulk ingestion;
- after retrieval evaluation and latency checks, online queries can also move
  to GPU TEI.

## Validation and observability

Before marking a document complete, validate:

- non-empty parsed text;
- expected chunk count range;
- metadata presence;
- embedding dimension equals 1,024;
- model and revision match the manifest and target index;
- zero failed OpenSearch bulk items;
- a sample retrieval returns the new content.

Track these metrics by `job_id`, `source_id`, and model revision:

- documents received, skipped, completed, and failed;
- chunks created and embedded;
- embedding latency and throughput;
- TEI queue depth and error rate;
- OpenSearch bulk latency and rejection count;
- end-to-end ingestion age;
- online embedding p50/p95/p99 latency while a batch is running.

The operational question is not simply “did the DAG finish?” It is whether new
content became searchable without duplicate vectors, stale chunks, degraded
online latency, or an untraceable partial update.

## Recommended implementation order

1. Add deterministic chunk IDs and an ingestion manifest.
2. Add an idempotent command that processes one S3 object.
3. Add SQS notifications and a dead-letter queue.
4. Wrap the command in an Airflow DAG that launches an ECS worker.
5. Add Airflow pools, retries, timeouts, and alerts.
6. Add online-versus-batch embedding metrics.
7. Run a small shared-endpoint test.
8. Split batch embedding to the GPU TEI service once AWS quota permits it.
9. Add versioned-index/alias rebuilds for model or chunking changes.

This preserves the existing FastAPI query path while making S3 data arrival
incremental, recoverable, and measurable.
