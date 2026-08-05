# DocsMind

DocsMind is a corpus-independent RAG and open-model serving project. It is built
to demonstrate the parts of GenAI systems that matter in production: ingestion,
hybrid retrieval, interchangeable vector stores, grounded generation,
evaluation, and self-hosted LLM inference.

The included astronomy documents and Briskoda forum tooling are example
corpora. They are deliberately separate from the RAG machinery, so the data can
change without redesigning retrieval or generation.

## What works today

The default query path already uses BM25. It is not a future feature.

```text
Ingest -> Chunk -> Embed -> Index
                            |
Question -> dense search ---+
Question -> BM25 search -----+-> RRF fusion -> optional rerank
                                               |
                                               v
                                      context -> LLM -> cited answer
```

| Pipeline stage | Current implementation |
|---|---|
| Ingest and chunk | LlamaIndex file loading and `SentenceSplitter`, plus Wikipedia, Briskoda, and WhatsApp corpus adapters |
| Embed | Local `bge-small` baseline, self-hosted BGE-M3 through TEI on AWS ECS/EC2, or optional Bedrock providers |
| Index and dense search | FAISS, Qdrant, or AWS OpenSearch behind one `VectorStore` interface |
| Sparse search | BM25 over the chunks exposed by the selected vector store |
| Fusion | Reciprocal Rank Fusion (RRF) combines dense and BM25 rankings |
| Rerank | Optional `ms-marco-MiniLM-L-6-v2` cross-encoder; disabled by default because it adds model and compute cost |
| Generate | Anthropic, Ollama, vLLM, or a vLLM-primary/cloud-fallback router |
| Ground and cite | Context-only prompt, inline source citations, and `INSUFFICIENT_CONTEXT` guardrail |
| Serve | FastAPI `/health` and `/query` endpoints |
| Evaluate | Retrieval benchmarks, labeled query sets, answer-review helpers, and vLLM latency/throughput benchmarks |

### Why BM25 and dense retrieval both exist

They operate at the same retrieval stage but catch different signals:

- Dense search matches meaning. It can connect a question to a relevant passage
  even when they use different words.
- BM25 matches exact terms. It is strong on names, identifiers, error messages,
  and domain vocabulary.
- RRF combines their rankings without pretending their raw scores are directly
  comparable.

`DOCSMIND_RETRIEVAL_MODE=hybrid` is the default. At pipeline startup,
`HybridRetriever` rebuilds its in-memory BM25 index from `store.chunks`, so it
works with FAISS, Qdrant, and OpenSearch. Set the mode to `dense` only when you
want a dense-only baseline for evaluation.

In an interview, the useful claim is not merely “I used BM25.” It is: “I tested
dense and hybrid retrieval at the same pipeline stage, measured Hit@k and MRR,
and kept hybrid as the default because exact-term recovery complemented semantic
search.”

## Delivery status

| Phase | Status | Evidence in the repository |
|---|---|---|
| 1 — Baseline RAG | **Complete** | Ingestion, chunking, BGE embeddings, FAISS Flat, grounded generation, citations, FastAPI, and tests |
| 2 — Index and vector-store choices | **Complete** | FAISS Flat/IVF/HNSW/IVFPQ benchmarks, Qdrant, and AWS OpenSearch implementations |
| 3 — Hybrid retrieval | **Complete** | BM25 + dense retrieval, RRF fusion, optional cross-encoder reranking, and retrieval evaluation |
| 4 — LLM routing and serving | **Serving path complete** | Authenticated vLLM client, availability-based cloud fallback, smoke test, and TTFT/throughput benchmark |
| 5 — Agent workflow | **Planned** | LangGraph workflow, tools, state, and guardrails |
| 6 — Answer-quality evaluation | **Partial** | Retrieval and human-label utilities exist; faithfulness, groundedness, generation regression, and CI gates remain |
| 7 — Production operations | **Partial** | Remote execution and serving benchmarks exist; containers, observability, deployment automation, and scaling remain |
| 8 — Graph RAG | **Planned** | Neo4j graph retrieval and routing |

Phase numbers describe when a capability was introduced. Completed phases stay
in this table as shipped work; they are not future roadmap items.

## Architecture

The implemented system is deliberately modular:

```text
Corpus
  -> loader / corpus adapter
  -> chunks
  -> configured embedding provider (local BGE | remote TEI/BGE-M3 | Bedrock)
  -> VectorStore (FAISS | Qdrant | OpenSearch)
  -> dense + BM25 retrieval
  -> RRF
  -> optional cross-encoder reranker
  -> grounded prompt
  -> LLM provider or availability router
  -> cited response
```

The planned LangGraph agent, answer-quality CI gate, observability stack, and
Neo4j layer extend this pipeline; they are not presented as already implemented.

## Repository layout

```text
docsmind/
  ingestion/   generic loaders and corpus-specific preparation
  index/       embeddings and FAISS/Qdrant/OpenSearch backends
  retrieval/   dense retrieval, BM25, RRF, and reranking
  llm/         Anthropic, Ollama, vLLM, and fallback routing
  eval/        retrieval and human-review evaluation utilities
  serving/     FastAPI application
  agent/       Phase 5 placeholder
  ops/         Phase 7 placeholder
  config.py    environment-driven settings
  pipeline.py  retrieve -> generate -> cite
  factory.py   component wiring
data/          sample corpus and labeled evaluation queries
scripts/       ingestion, evaluation, smoke, and benchmark commands
notebooks/     walkthrough and corpus/evaluation labs
tests/         offline test suite
```

## Quick start

Requires Python 3.11+.

```bash
cp .env.example .env
make install
make demo
```

The default LLM provider is Anthropic, so add `ANTHROPIC_API_KEY` to your
environment before running the demo. `make demo` builds the index when needed
and prints a grounded answer with citations.

To run the API:

```bash
make ingest
make serve
```

```bash
curl -s localhost:8000/health
curl -s localhost:8000/query \
  -H 'content-type: application/json' \
  -d '{"question":"How do black holes form?"}' | jq
```

## Changing the corpus

The corpus is an input, not an architectural dependency. Point
`DOCSMIND_DATA_DIR` at a different document directory and ingest again:

```bash
DOCSMIND_DATA_DIR=/path/to/new-corpus make ingest
```

Re-ingestion replaces or rebuilds the configured vector index. When the query
pipeline starts, BM25 is rebuilt from the chunks stored by that backend. The
embedding, retrieval, reranking, LLM, serving, and evaluation interfaces do not
need to change.

Use a corpus-specific adapter only when the source needs structure-aware
preparation—for example, preserving forum post metadata or turning messages
into conversation windows. That adapter still outputs the same `Document` and
chunk contracts consumed by the rest of DocsMind.

For the included Volkswagen Group Wikipedia corpus:

```bash
make wikipedia-corpus
DOCSMIND_DATA_DIR=data/wikipedia \
DOCSMIND_INDEX_DIR=data/index-wikipedia \
make ingest
```

The versioned manifest controls which articles belong to the corpus. The fetched
JSONL snapshot preserves section paths, tables, canonical URLs, page IDs, and
revision IDs. See [the corpus design and measurements](docs/13-wikipedia-volkswagen/README.md).

## Configuration

All DocsMind settings use the `DOCSMIND_` prefix and can be placed in `.env`.
See `.env.example` for the full list.

| Setting | Default | Meaning |
|---|---|---|
| `DOCSMIND_EMBEDDING_PROVIDER` | `local` | `local`, self-hosted `tei`, or managed `bedrock` embeddings |
| `DOCSMIND_TEI_EMBED_MODEL` | `BAAI/bge-m3` | Model identity expected from the remote TEI service |
| `DOCSMIND_TEI_BASE_URL` | `http://localhost:8080` | TEI endpoint; the AWS dev path uses an SSM tunnel |
| `DOCSMIND_TEI_EMBED_DIMENSIONS` | `1024` | BGE-M3 vector size; use a new index when switching models |
| `DOCSMIND_TEI_EMBED_BATCH_SIZE` | `8` | Documents sent per TEI call; must fit the service limit |
| `DOCSMIND_BEDROCK_EMBED_MODEL` | `amazon.titan-embed-text-v2:0` | AWS-native default; Cohere v4 is also supported |
| `DOCSMIND_BEDROCK_EMBED_REGION` | empty | Bedrock region; empty inherits `DOCSMIND_AWS_REGION` |
| `DOCSMIND_BEDROCK_EMBED_DIMENSIONS` | `1024` | Vector size; changing it requires a separate re-ingested index |
| `DOCSMIND_VECTOR_BACKEND` | `faiss` | `faiss`, `qdrant`, or `opensearch` |
| `DOCSMIND_INDEX_TYPE` | `flat` | FAISS `flat`, `ivf`, `hnsw`, or `ivfpq` |
| `DOCSMIND_RETRIEVAL_MODE` | `hybrid` | Dense + BM25 + RRF, or `dense` baseline |
| `DOCSMIND_RERANK_ENABLED` | `false` | Enable the cross-encoder after RRF |
| `DOCSMIND_LLM_PROVIDER` | `cloud` | `cloud`, `local`, `vllm`, or `router` |
| `DOCSMIND_DATA_DIR` | `data/sample_docs` | Corpus directory to ingest |

### Self-hosted vLLM with cloud fallback

```bash
DOCSMIND_LLM_PROVIDER=router
DOCSMIND_LLM_PRIMARY_PROVIDER=vllm
DOCSMIND_LLM_FALLBACK_PROVIDER=cloud
DOCSMIND_VLLM_BASE_URL=https://your-vllm-host.example/v1
DOCSMIND_VLLM_MODEL=your-model-alias
DOCSMIND_VLLM_API_KEY=your-secret
```

The router falls back only for availability failures: connection errors,
timeouts, HTTP 408/429, and 5xx responses. Authentication, invalid model names,
and malformed requests fail immediately so configuration mistakes are not
hidden by a cloud call.

```bash
make vllm-smoke
make vllm-demo ARGS='"How do black holes form?"'
make vllm-benchmark ARGS='--concurrency 1 2 4 --requests-per-level 4'
```

The serving benchmark records time to first token (TTFT), end-to-end latency,
per-request decode rate, and aggregate output throughput. Those numbers are the
evidence needed to discuss batching and capacity, rather than merely saying a
model was deployed.

## Evaluation and benchmarks

```bash
make test
make benchmark                         # FAISS recall/latency/memory trade-offs
make eval                              # dense versus hybrid retrieval
make eval ARGS=--rerank                # add cross-encoder reranking
make vllm-benchmark ARGS='--concurrency 1 2 4'
make aws-embedding-benchmark           # BGE-M3 latency/throughput through SSM
```

For retrieval, compare Hit@k and MRR at the same chunk size and labeled query
set. For serving, compare TTFT and throughput at increasing concurrency. In both
cases, the architectural choice should follow measured behavior, not the tool's
popularity.

## Deployment evidence

The measured self-hosted inference deployment runs on AWS EC2 `g6.xlarge` with
an NVIDIA L4 GPU. vLLM exposes a Bearer-authenticated, OpenAI-compatible HTTPS
endpoint; DocsMind uses that endpoint as its primary generator and can fall back
to a cloud model during transient availability failures.

See [the benchmark results](docs/12-vllm-serving/benchmark-results.md) for the
observed hardware, model runtime, TTFT, throughput, GPU memory, and cost
calculation. AWS OpenSearch Serverless is the managed vector-store deployment.

The embedding deployment is separate from generation: BGE-M3 runs in Hugging
Face TEI on one CPU `m7i.large` managed by ECS on EC2. The host has no inbound
security-group rules; development access uses an SSM port-forwarding session.
The measured CPU baseline and start/stop workflow are in
[the AWS embedding-service guide](docs/14-aws-embedding-service/README.md).

The Makefile still contains `digitalocean-*` targets from the earlier remote
development workflow. They are optional rsync/SSH helpers, not a requirement and
not the environment used for the recorded vLLM results.

Use a cloud firewall and TLS-terminating reverse proxy or load balancer before
exposing any deployment. Do not expose the unauthenticated FastAPI application
port directly to the internet.

## Why these choices

- **LlamaIndex for ingestion:** it provides focused document and chunking
  primitives without owning the whole application architecture.
- **One `VectorStore` interface:** FAISS is simple and exact for small local
  corpora; Qdrant adds self-hosted persistence; OpenSearch demonstrates a
  managed AWS backend. The pipeline does not change when the storage choice
  changes.
- **Hybrid retrieval:** dense search captures semantic similarity while BM25
  recovers exact terms. RRF combines ranks without score calibration.
- **Optional cross-encoder:** reranking is often the most reliable quality gain,
  but it adds latency and compute, so it is measured and explicitly enabled.
- **Direct provider clients:** Anthropic, Ollama, and vLLM remain visible behind
  a small interface, making failure policy and model routing testable.
- **LangGraph for the planned agent:** an explicit state graph is easier to
  inspect and constrain than an opaque autonomous loop.
