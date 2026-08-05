# BGE-M3 Volkswagen ingestion run — 2026-08-05

This is the detailed record of the first full BGE-M3 ingestion attempt for the
versioned Volkswagen Wikipedia corpus. It describes the live state captured
while the job was still embedding. Final OpenSearch counts and retrieval
evaluation results must be appended only after those steps complete.

## Current status at the latest snapshot

| Item | Observed value |
|---|---:|
| Ingestion process | Running |
| Remote shell process | PID `528600` |
| Python process | PID `528601` |
| Elapsed time | 2,400 seconds / 40 minutes |
| Estimated embeddings completed | 1,480 of 1,776 |
| Progress | 83.3% |
| Average sustained rate | 0.617 chunks/second |
| Estimated remaining time | About 8 minutes |
| ECS failed tasks during this run | 0 |

The completion estimate is based on the cumulative TEI `te_embed_count`
counter minus its value immediately before this run. It is an estimate until
the ingestion process returns and OpenSearch reports the final document count.

## Exactly what is running where

The ingestion job is not running BGE-M3 on Beast. Responsibility is split:

```text
Beast: /home/ajmalrasi/projects/docsmind
  Linux user: ajmalrasi
  Python process: .venv/bin/python -m scripts.ingest
  AWS data identity: arn:aws:iam::740940193664:user/docsmind-beast
  Work: load files, create chunks, send HTTP requests, receive vectors,
        and write the completed vector set to OpenSearch

                private reverse SSH tunnel
Beast localhost:8080 --------------------------> Mac localhost:8080
                                                       |
                                                       | private SSM tunnel
                                                       v
AWS EC2 host localhost:8080 --------------------> TEI container port 80
  Instance: m7i.large
  Work: tokenize text and run BGE-M3 ONNX inference on two vCPUs

After every embedding is available in Beast memory:
Beast ------------------------------------------------> OpenSearch Serverless
  Target index: docsmind-volkswagen-wikipedia-bge-m3-v1
```

Beast was selected as the ingestion coordinator because its existing
`docsmind-beast` IAM user is authorized by the OpenSearch Serverless data-access
policy. The Mac's AWS login resolves to the account root and is deliberately not
used for the OpenSearch data path.

## Network path

The ECS host has no inbound security-group rules. Port 8080 is not exposed to
the internet.

Two tunnels provide the temporary development path:

1. An AWS Systems Manager port-forwarding session maps Mac
   `localhost:8080` to EC2 `localhost:8080`.
2. An SSH reverse tunnel maps Beast `localhost:8080` back to Mac
   `localhost:8080`.

The effective route is:

```text
Beast -> reverse SSH -> Mac -> SSM -> EC2 host -> TEI container
```

Before ingestion, Beast called `http://localhost:8080/info` through this path.
TEI returned:

| Setting | Verified value |
|---|---|
| Model | `BAAI/bge-m3` |
| Model revision | `5617a9f61b028005a4858fdac845db406aefb181` |
| TEI version | `1.9.3` |
| Dtype | `float32` |
| Pooling | `cls` |
| Vector dimension | 1,024 |
| Maximum input length | 2,048 tokens |
| Maximum batch tokens | 2,048 tokens |
| Maximum concurrent requests | 8 |
| Maximum backend batch requests | 8 |
| Maximum client batch size | 8 texts |

No API key is required because the service is reachable only through the
private tunnel chain. This topology is for development. An AWS-hosted
production application should use private service discovery or an internal
load balancer.

## Source corpus

The input is the committed, reproducible snapshot:

```text
data/wikipedia/volkswagen.wikipedia.jsonl
```

It contains:

| Corpus measurement | Value |
|---|---:|
| Wikipedia articles | 57 |
| Heading-aware section documents | 1,147 |
| Normalized characters | 1,439,426 |
| Citation URLs | 57 |
| Chunk size | 512 tokens |
| Chunk overlap | 64 tokens |
| Produced chunks | 1,776 |

The fetch stage is not running during ingestion. The job reads the versioned
JSONL snapshot already stored on Beast. Each section retains its article title,
section path, canonical Wikipedia URL, page ID, revision ID, language, fetch
timestamp, and `CC BY-SA 4.0` marker.

## Exact ingestion configuration

The job was launched on Beast from:

```text
/home/ajmalrasi/projects/docsmind
```

The effective command is:

```bash
DOCSMIND_EMBEDDING_PROVIDER=tei \
DOCSMIND_TEI_BASE_URL=http://localhost:8080 \
DOCSMIND_TEI_EMBED_MODEL=BAAI/bge-m3 \
DOCSMIND_TEI_EMBED_DIMENSIONS=1024 \
DOCSMIND_TEI_EMBED_BATCH_SIZE=8 \
DOCSMIND_VECTOR_BACKEND=opensearch \
DOCSMIND_OPENSEARCH_INDEX=docsmind-volkswagen-wikipedia-bge-m3-v1 \
DOCSMIND_DATA_DIR=data/wikipedia \
DOCSMIND_INDEX_DIR=data/index-wikipedia-bge-m3-v1 \
DOCSMIND_AWS_PROFILE=docsmind \
DOCSMIND_AWS_REGION=us-east-1 \
.venv/bin/python -m scripts.ingest
```

No credentials or API keys appear in the command. boto3 resolves the restricted
`docsmind` profile from Beast's local AWS credential files.

## Application call path

`scripts/ingest.py` performs these steps in order:

1. `load_documents()` detects the `*.wikipedia.jsonl` snapshot.
2. `load_wikipedia_documents()` creates one LlamaIndex `Document` per retained
   Wikipedia section.
3. `chunk_documents()` uses LlamaIndex `SentenceSplitter` with a 512-token size
   and 64-token overlap.
4. `build_embedder()` selects `TEIEmbedder` because the provider is `tei`.
5. `TEIEmbedder.embed_documents()` sends bounded HTTP requests to TEI.
6. Only after all vectors return, `new_store()` constructs the isolated
   OpenSearch store with `recreate=True` for the new index name.
7. `store.add()` bulk-writes chunks and vectors.
8. `store.save()` writes reconnect metadata under
   `data/index-wikipedia-bge-m3-v1/meta.json` on Beast.
9. `save_embedding_manifest()` writes provider, model, and dimension identity
   under `data/index-wikipedia-bge-m3-v1/embedding.json`.

The ordering means the target OpenSearch index does not exist during the long
embedding phase. Existing indexes cannot be partially overwritten by a failed
embedding request.

## How batching works

### Application batch

`TEIEmbedder` slices the 1,776 texts into sequential lists of at most eight:

```text
1776 / 8 = 222 HTTP requests when every request is full
```

There is one request in flight from this ingestion process at a time. The
application does not launch eight simultaneous HTTP calls. The setting
`max_concurrent_requests=8` is server admission capacity, not the number of
parallel calls generated by this job.

Each request sends:

```json
{
  "inputs": ["up to eight chunk texts"],
  "normalize": true,
  "truncate": true
}
```

For every response, DocsMind validates:

- The response is a two-dimensional numeric array.
- Every vector has exactly 1,024 values.
- The number of returned vectors equals the number of input texts.
- Vectors are L2-normalized.

Vectors from successive requests are concatenated in original chunk order.
Preserving order is essential because each vector must remain attached to the
chunk that produced it.

### Hardware batch

The HTTP client batch and TEI inference batch are not the same thing.

Eight chunks can each approach 512 tokens, producing roughly 4,096 potential
tokens in one HTTP request. TEI's hardware limit is 2,048 total batch tokens.
TEI therefore schedules the request's inputs into smaller inference batches
that fit the token ceiling.

This distinction is why both settings exist:

| Limit | Meaning | Value |
|---|---|---:|
| Client batch size | Texts accepted in one HTTP call | 8 |
| Maximum input length | Tokens allowed in one text | 2,048 |
| Maximum batch tokens | Total tokens TEI may infer together | 2,048 |
| Concurrent requests | HTTP admission/backpressure permits | 8 |

The current 512-token chunks do not hit the per-input truncation limit. They do
affect how densely TEI can pack the hardware batch.

## CPU and memory behavior

During sustained real-corpus ingestion, Docker reported:

```text
CPU:    199.46%
Memory: 1.916 GiB / 6.836 GiB (28.02%)
```

Approximately 200% CPU means both vCPUs are fully occupied. The job is
compute-bound. More application concurrency would add queueing but would not
create more CPU capacity.

Memory remained stable far below the container limit. This differs from the
first deployment, where an 8,192-token warm-up envelope caused four exit-137
OOM failures. The working 2,048-token envelope removed that peak-memory failure.

## Why real ingestion is slower than the short benchmark

The short synthetic benchmark used brief automotive sentences and measured up
to 5.91 texts/second at client batch eight. The Wikipedia corpus contains many
much longer passages approaching the 512-token chunk limit.

The live run averaged about 0.617 chunks/second at the latest snapshot. Longer
transformer sequences require substantially more computation, so short-text
throughput must not be used to estimate long-document ingestion cost.

This is the relevant capacity conclusion:

- CPU batch-one query embeddings are usable for development.
- CPU bulk ingestion works but is slow for long chunks.
- Frequent or much larger re-indexing is the strongest reason to move BGE-M3
  ingestion to GPU.

## OpenSearch destination

The existing baseline was verified before the run:

```text
docsmind-volkswagen-wikipedia-v1
dimension: 384
model: BAAI/bge-small-en-v1.5
documents: 1,776
```

The isolated destination is:

```text
docsmind-volkswagen-wikipedia-bge-m3-v1
dimension: 1,024
model: BAAI/bge-m3
expected documents: 1,776
```

The old index is not a deletion or recreation target. Even if two embedding
models had the same dimension, they would still require separate indexes
because their vector coordinate spaces are not compatible.

After embedding finishes, OpenSearch will receive approximately four bulk
operations at the configured maximum of 500 records:

```text
500 + 500 + 500 + 276 = 1,776
```

The index mapping uses a 1,024-dimensional `knn_vector` with cosine similarity.
OpenSearch Serverless supplies its vector-search engine behind the DocsMind
`VectorStore` interface.

## AWS authorization changes made for this run

The original OpenSearch data-access policy authorized only:

```text
arn:aws:iam::740940193664:user/docsmind-beast
```

The Mac root login could administer the policy but could not use the data path
reliably and was not retained. CloudFormation now also creates:

```text
arn:aws:iam::740940193664:role/docsmind-opensearch-ingestion
```

The data policy currently allows the existing Beast user and this restricted
role. Root was removed. The role has `aoss:APIAccessAll` only on the
`docsmind-dev` collection and is intended for a future normal IAM/SSO principal;
AWS root sessions cannot assume roles.

## Remote source synchronization

Only project source, tests, public documentation, infrastructure definitions,
and the public Wikipedia snapshot were synchronized to Beast.

The following were not copied or overwritten:

- `.env`
- AWS credentials
- `data/private`
- Existing runtime indexes
- `.git`
- `.venv`

An initial rsync command flattened directory contents into the remote project
root. Those exact duplicate copies were removed, the five named project
directories were resynchronized with their topology intact, representative
file hashes were compared, and remote imports were verified before ingestion.

## Failure and restart behavior

The current implementation is atomic with respect to index creation but is not
resumable with respect to embedding computation:

- All 1,776 embeddings are accumulated in Beast memory.
- The OpenSearch index is created only after the complete array exists.
- If the process or either tunnel dies before that point, computed vectors are
  lost and ingestion must restart from chunk one.
- If OpenSearch bulk writing fails after index creation, the isolated target may
  exist with a partial count and should be recreated on the next full run.

A production ingestion pipeline that runs frequently should checkpoint batches
to durable storage or use an idempotent queue keyed by chunk ID and embedding
model revision. This development run keeps the implementation simple while
making the limitation explicit.

## What happens after the Python process returns

Completion is not established by reaching 1,776 on the TEI counter alone. The
following checks are required:

1. The ingestion process exits with status zero.
2. OpenSearch reports exactly 1,776 documents in the BGE-M3 index.
3. The OpenSearch mapping reports vector dimension 1,024.
4. The local reconnect marker names the expected index.
5. The embedding manifest reports provider `tei`, model `BAAI/bge-m3`, and
   dimension 1,024.
6. Representative dense and hybrid queries return relevant article titles.
7. The labeled evaluation compares the old and new indexes without re-embedding
   either corpus.

## Planned retrieval evaluation

The versioned evaluation set is:

```text
data/eval/volkswagen_wikipedia_queries.v1.json
```

It contains 20 author-curated questions with one or more relevant source
article titles. `scripts/wikipedia_embedding_eval.py` will compare:

```text
bge-small query -> existing 384-dimensional index -> dense and hybrid
BGE-M3 query    -> new 1,024-dimensional index    -> dense and hybrid
```

Reported metrics are Hit@1, Hit@3, MRR, mean latency, p50 latency, and p95
latency. The corpus snapshot, chunking, OpenSearch backend, query set, rank
depth, and hybrid configuration remain fixed. Only the embedding model and its
matching index change.

These are source-level labels, not answer-faithfulness labels. They evaluate
whether retrieval finds an appropriate article, not whether an LLM later writes
a grounded answer.

## Cost during this run

The CPU host costs roughly $0.11/hour while running, including approximate
compute, public IPv4, and prorated root-volume cost before small logging charges.
At about 48 minutes for the projected embedding phase, the EC2 cost of this run
is only a few cents. The important cost is engineering time and slow iteration,
which is why the same workload should later be repeated on GPU.

The service will be scaled to zero after ingestion verification and evaluation.
Scale-to-zero terminates the root EBS volume, so the next cold start downloads
the pinned model again.

## Evidence available so far

- Existing bge-small OpenSearch index: 1,776 documents
- New BGE-M3 index before this run: absent
- TEI model identity and revision: verified from Beast
- OpenSearch access as `docsmind-beast`: verified
- BGE-small 384-dimensional query vector: verified and normalized
- BGE-M3 1,024-dimensional query vector: previously verified and normalized
- ECS task during ingestion: healthy, zero failed tasks
- CPU during ingestion: both cores saturated
- Memory during ingestion: stable at approximately 1.92 GiB
- Latest ingestion snapshot: 1,480 of 1,776 estimated embeddings

Final index and evaluation evidence is still pending at the timestamp represented
by this document.
