# DocsMind

An agentic RAG platform over technical/ML documentation — built to demonstrate
production RAG, vector-DB tuning, hybrid retrieval, an agentic workflow,
evaluation/hallucination control, and LLMOps.

This is being built phase by phase. **Phase 1 (current): baseline RAG** — a full
ingest → chunk → embed → index → retrieve → generate path with inline citations,
served behind a FastAPI endpoint.

## Architecture (target)

```
Ingestion (LlamaIndex)  →  Chunking
        ↓
Index layer:  FAISS (flat → IVF/HNSW/PQ)  +  BM25  +  Neo4j graph
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
| Vector store | FAISS flat, behind a pluggable `VectorStore` interface |
| Generation | Anthropic Claude (`claude-opus-4-8` by default), grounded with citations |
| Anti-hallucination | model must answer only from context or return `INSUFFICIENT_CONTEXT` |
| Serving | FastAPI `/health` + `/query` (pydantic schemas) |
| Tests | pytest (config, FAISS store, chunker, pipeline citation logic) |

## Repo layout

```
docsmind/
  ingestion/   loaders, chunker          (LlamaIndex)
  index/       embeddings, VectorStore interface, faiss_store
  retrieval/   retriever (dense; hybrid + rerank land in Phase 3)
  llm/         LLMClient interface, cloud_client (Anthropic)
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
make ingest                   # build the FAISS index once
make serve                    # FastAPI on http://localhost:8000
```

```bash
curl -s localhost:8000/health
curl -s localhost:8000/query -H 'content-type: application/json' \
  -d '{"question":"How do black holes form?"}' | jq
```

## Technologies

### Phase 1 (Current)

| Category | Technology | Purpose |
|----------|-----------|---------|
| **Language** | Python 3.11+ | Core implementation |
| **API Framework** | FastAPI | HTTP serving (`/health`, `/query`) |
| **Data Ingestion** | LlamaIndex | Document loading & semantic chunking |
| **Embeddings** | sentence-transformers (bge-small) | Self-hosted dense embeddings |
| **Vector Store** | FAISS (flat index) | Exact nearest-neighbor search |
| **LLM Generation** | Anthropic Claude | Cloud-based answer generation |
| **Config** | Pydantic Settings | Environment-driven configuration |
| **Testing** | pytest | Unit & integration tests |

### Future Phases

| Phase | Technology | Purpose |
|-------|-----------|---------|
| **Phase 2** | FAISS IVF/HNSW/PQ · Qdrant | Index optimization & alternative backends |
| **Phase 3** | BM25 · cross-encoder reranker | Hybrid retrieval & ranking |
| **Phase 4** | vLLM · Ollama | Self-hosted SLM fallback + router |
| **Phase 5** | LangGraph | Agentic orchestration (plan → tool → cite) |
| **Phase 6** | RAGAS · Golden set | Evaluation & CI regression gates |
| **Phase 7** | Docker · Kubernetes · Langfuse · MLflow | Ops, observability, cost tracking |
| **Phase 8** | Neo4j | Knowledge graph RAG layer |

### Why These Choices?

- **LlamaIndex** (not LangChain): Purpose-built for RAG data pipelines; cleaner abstractions for load → chunk → embed → index.
- **FAISS** (not Pinecone/Weaviate): Self-hosted, no vendor lock-in; Phase 2 adds alternatives.
- **Anthropic Claude** (direct SDK, not LangChain wrapper): Full control, no abstraction tax, easier to add system-level features (caching, batching).
- **LangGraph** (Phase 5, not LangChain agents): Explicit state machines for safer agentic flows and guardrails.

## Running on the GPU box (`beast`)

The git repo lives on the dev machine; heavy work runs on `beast`
(RTX 3070 Ti, Ollama, Docker). The `make` targets mirror the tree over and run
remotely:

```bash
make beast-install            # sync + create venv + install on beast
make beast-demo               # sync + run the demo on beast (GPU embeddings)
make beast-serve              # serve from beast on the LAN (:8000)
```

Configure the host with `BEAST=user@host` / `BEAST_DIR=...` if it differs.

## Configuration

All settings are env-overridable (prefix `DOCSMIND_`); see `.env.example`. The
Anthropic key is read from `ANTHROPIC_API_KEY` by the SDK and never stored in
code. Swap the generation model to `claude-haiku-4-5` or `claude-sonnet-4-6` for
cheaper high-volume benchmarking.

## Roadmap

- **Phase 2** — FAISS IVF/HNSW/PQ + Qdrant backend; recall@k / latency benchmarks.
- **Phase 3** — BM25 + fusion + cross-encoder reranker; retrieval-lift benchmark.
- **Phase 4** — self-hosted SLM via vLLM/Ollama + `LLMRouter` (cloud fallback/judge).
- **Phase 5** — LangGraph agent (retrieve/web_search/code_exec/cite + guardrails).
- **Phase 6** — RAGAS eval, golden set, CI regression gate.
- **Phase 7** — Langfuse + MLflow, cost/latency dashboard, Docker, k8s.
- **Phase 8** — Neo4j GraphRAG layer.
