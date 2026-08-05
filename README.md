# DocsMind

An agentic RAG platform over technical/ML documentation — built to demonstrate
production RAG, vector-DB tuning, hybrid retrieval, an agentic workflow,
evaluation/hallucination control, and LLMOps.

This is built phase by phase. Phases 1-3 provide baseline RAG, multiple vector
backends, hybrid retrieval, and reranking. Phase 4 now provides authenticated
vLLM generation with availability-based cloud fallback. AWS OpenSearch
Serverless is also available as the managed Index/Search backend.

## Architecture (target)

```
Ingestion (LlamaIndex)  →  Chunking
        ↓
Index layer:  FAISS / Qdrant / AWS OpenSearch  +  BM25  +  Neo4j graph
        ↓
Retrieval:  hybrid fusion  →  cross-encoder rerank  →  context assembly
        ↓
Agent (LangGraph):  plan → tool (retrieve/search/exec) → ground → cite
        ↓
LLM router:  self-hosted SLM (vLLM/Ollama)  ↔  cloud LLM fallback / judge
        ↓
Eval + Observability:  RAGAS · Langfuse · MLflow · cost/latency
        ↓
Serving:  FastAPI  →  Docker  →  Kubernetes  +  CI eval gate
```

## What Phase 1 ships

| Component | Implementation |
|---|---|
| Ingestion | LlamaIndex `SimpleDirectoryReader` + `SentenceSplitter` |
| Embeddings | self-hosted `sentence-transformers` (`bge-small`), cosine via normalized vectors |
| Vector store | FAISS, Qdrant, or AWS OpenSearch behind one `VectorStore` interface |
| Generation | Anthropic Claude (`claude-opus-4-8` by default), grounded with citations |
| Anti-hallucination | model must answer only from context or return `INSUFFICIENT_CONTEXT` |
| Serving | FastAPI `/health` + `/query` (pydantic schemas) |
| Tests | pytest (config, FAISS store, chunker, pipeline citation logic) |

## Repo layout

```
docsmind/
  ingestion/   loaders, chunker          (LlamaIndex)
  index/       embeddings, VectorStore, FAISS/Qdrant/OpenSearch backends
  retrieval/   retriever (dense; hybrid + rerank land in Phase 3)
  llm/         Anthropic/Ollama/vLLM clients + fallback router
  agent/       LangGraph agent            (Phase 5 stub)
  eval/        RAGAS + golden set + CI gate (Phase 6 stub)
  serving/     FastAPI app
  ops/         Docker / k8s               (Phase 7 stub)
  config.py    pydantic-settings
  pipeline.py  retrieve → generate → cite
  factory.py   composition root
data/sample_docs/   sample documents (space & astronomy)
scripts/            ingest.py, demo.py
tests/              offline pytest suite
```

## Setup

Requires Python 3.11+.

```bash
cp .env.example .env          # add your ANTHROPIC_API_KEY
make install                  # venv + editable install
make demo                     # builds the index, runs a sample query
```

`make demo` prints a grounded answer with citations. To run the API instead:

```bash
make ingest                   # build the configured vector index once
make serve                    # FastAPI on http://localhost:8000
```

```bash
curl -s localhost:8000/health
curl -s localhost:8000/query -H 'content-type: application/json' \
  -d '{"question":"How do black holes form?"}' | jq
```

## Technologies

### Current stack (Phases 1–4)

| Category | Technology | Purpose |
|----------|-----------|---------|
| **Language** | Python 3.11+ | Core implementation |
| **API Framework** | FastAPI | HTTP serving (`/health`, `/query`) |
| **Data Ingestion** | LlamaIndex | Document loading & semantic chunking |
| **Embeddings** | sentence-transformers (bge-small) | Self-hosted dense embeddings |
| **Vector Store** | FAISS, Qdrant, AWS OpenSearch | Pluggable local, self-hosted, or managed search |
| **LLM Generation** | vLLM + Anthropic Claude | Self-hosted primary with cloud fallback |
| **Config** | Pydantic Settings | Environment-driven configuration |
| **Testing** | pytest | Unit & integration tests |

### Future Phases

| Phase | Technology | Purpose |
|-------|-----------|---------|
| **Phase 2** | FAISS IVF/HNSW/PQ · Qdrant · AWS OpenSearch | Index optimization & alternative backends |
| **Phase 3** | BM25 · cross-encoder reranker | Hybrid retrieval & ranking |
| **Phase 4** | vLLM · Ollama | Authenticated self-hosted SLM + cloud fallback router |
| **Phase 5** | LangGraph | Agentic orchestration (plan → tool → cite) |
| **Phase 6** | RAGAS · Golden set | Evaluation & CI regression gates |
| **Phase 7** | Docker · Kubernetes · Langfuse · MLflow | Ops, observability, cost tracking |
| **Phase 8** | Neo4j | Knowledge graph RAG layer |

### Why These Choices?

- **LlamaIndex** (not LangChain): Purpose-built for RAG data pipelines; cleaner abstractions for load → chunk → embed → index.
- **FAISS** (not Pinecone/Weaviate): Self-hosted, no vendor lock-in; Phase 2 adds alternatives.
- **Anthropic Claude** (direct SDK, not LangChain wrapper): Full control, no abstraction tax, easier to add system-level features (caching, batching).
- **LangGraph** (Phase 5, not LangChain agents): Explicit state machines for safer agentic flows and guardrails.

## Running on DigitalOcean

The git repository remains on the development machine. Remote workloads run on
a DigitalOcean Droplet, while vLLM and other CUDA-dependent workloads require a
DigitalOcean GPU Droplet. The `make` targets synchronize the working tree and
run commands remotely:

```bash
make digitalocean-install     # sync + create venv + install
make digitalocean-demo        # sync + run the demo
make digitalocean-serve       # serve from the Droplet on :8000
```

Configure the SSH destination and project directory explicitly:

```bash
make digitalocean-install \
  DIGITALOCEAN_HOST=user@droplet-ip \
  DIGITALOCEAN_DIR=/home/docsmind/app
```

Use a firewall and a TLS-terminating reverse proxy or load balancer before
exposing the API publicly. Port `8000` should not be left open to the internet
as an unauthenticated production endpoint.

## Configuration

All settings are env-overridable (prefix `DOCSMIND_`); see `.env.example`. The
Anthropic key is read from `ANTHROPIC_API_KEY` by the SDK and never stored in
code. Swap the generation model to `claude-haiku-4-5` or `claude-sonnet-4-6` for
cheaper high-volume benchmarking.

For self-hosted-first generation, keep the endpoint and credentials in `.env`:

```bash
DOCSMIND_LLM_PROVIDER=router
DOCSMIND_LLM_PRIMARY_PROVIDER=vllm
DOCSMIND_LLM_FALLBACK_PROVIDER=cloud
DOCSMIND_VLLM_BASE_URL=https://your-vllm-host.example/v1
DOCSMIND_VLLM_API_KEY=your-secret
```

Then verify the model separately from the corpus, run a complete RAG query, and
benchmark serving performance:

```bash
make vllm-smoke
make vllm-demo ARGS='"How do black holes form?"'
make vllm-benchmark ARGS='--concurrency 1 2 4 --requests-per-level 4'
```

The router falls back only on timeouts, connection errors, HTTP 408/429, and
5xx responses. Authentication, model-name, and malformed-request failures stop
immediately so configuration problems are not hidden by a paid cloud call.

## Roadmap

- **Phase 2** — FAISS IVF/HNSW/PQ + Qdrant backend; recall@k / latency benchmarks.
- **Phase 3** — BM25 + fusion + cross-encoder reranker; retrieval-lift benchmark.
- **Phase 4** — authenticated vLLM/Ollama + `LLMRouter` availability fallback;
  next: quality routing and structured-output reliability evaluation.
- **Phase 5** — LangGraph agent (retrieve/web_search/code_exec/cite + guardrails).
- **Phase 6** — RAGAS eval, golden set, CI regression gate.
- **Phase 7** — Langfuse + MLflow, cost/latency dashboard, Docker, k8s.
- **Phase 8** — Neo4j GraphRAG layer.
