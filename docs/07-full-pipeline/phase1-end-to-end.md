# Phase 1 — How the Code Wires Together

**TL;DR:** Three Python entry points (ingest, demo, serve) and four key files
(config, factory, pipeline, app). Everything flows through `factory.py`.

## The key files

```
docsmind/
  config.py       ← all settings in one place (env-overridable)
  factory.py      ← wires Embedder + VectorStore + Retriever + LLM + Pipeline
  pipeline.py     ← retrieve → build context → generate → extract citations
  serving/app.py  ← FastAPI: /health and /query endpoints
```

## config.py — single source of truth

```python
class Settings(BaseSettings):
    cloud_llm_model: str = "claude-opus-4-8"   # change via DOCSMIND_CLOUD_LLM_MODEL=
    embed_model: str = "BAAI/bge-small-en-v1.5"
    index_type: str = "flat"
    top_k: int = 4
    chunk_size: int = 512
    chunk_overlap: int = 64
    data_dir: Path = Path("data/sample_docs")
    index_dir: Path = Path("data/index")
```

All components read from this. To change the model or chunk size, set an
env var — no code changes needed.

## factory.py — the composition root

```python
def build_pipeline(settings: Settings) -> RAGPipeline:
    embedder = Embedder(settings.embed_model)
    store = FaissVectorStore.load(settings.index_dir)
    retriever = Retriever(embedder, store)
    llm = CloudLLMClient(settings.cloud_llm_model)
    return RAGPipeline(retriever, llm, settings)
```

One function. Reads settings, builds every component, wires them together,
returns a ready `RAGPipeline`. This is called once at server startup.

## pipeline.py — the core logic

```python
class RAGPipeline:
    def query(self, question: str, top_k: int = None) -> QueryResponse:
        results = self._retriever.retrieve(question, top_k)

        if not results:
            return QueryResponse(answer=INSUFFICIENT, grounded=False, ...)

        context = self._build_context(results)   # numbered passages [1],[2],...
        prompt = f"Context passages:\n\n{context}\n\nQuestion: {question}\n\nAnswer:"
        answer = self._llm.generate(SYSTEM_PROMPT, prompt, max_tokens)

        grounded = INSUFFICIENT not in answer
        citations = self._extract_citations(answer, results) if grounded else []

        return QueryResponse(answer=answer, citations=citations, grounded=grounded, ...)
```

## serving/app.py — the API

```python
@app.post("/query", response_model=QueryResponse)
def query(request: QueryRequest) -> QueryResponse:
    return pipeline.query(request.question, request.top_k)
```

One line. The pipeline object is built at startup (via `lifespan`) and reused
for every request. No rebuilding, no reloading the model per request.

## The three entry points

```bash
# 1. Build the index (ingest)
make ingest
# → runs scripts/ingest.py
# → loads docs, chunks, embeds, stores to data/index/

# 2. Run a query in the terminal (demo)
make demo
# → runs scripts/demo.py
# → builds pipeline, runs one question, prints answer + citations

# 3. Serve the API (production-ish)
make serve
# → starts uvicorn on localhost:8000
# → loads pipeline from disk
# → handles POST /query requests
```

## Dependency graph

```
Settings
   ↓
   ├── Embedder (bge-small)
   ├── FaissVectorStore (loaded from disk)
   │     ↑ built by Embedder during ingest
   ├── Retriever (Embedder + VectorStore)
   ├── CloudLLMClient (Anthropic SDK)
   └── RAGPipeline (Retriever + LLMClient + Settings)
         ↑ served by FastAPI app
```

Every component is constructed once, injected into the one that needs it
(dependency injection). No global state, no singletons — easy to test in
isolation.

→ Back to: **[README.md](README.md)**
→ Next topic: **[08-interview-prep/README.md](../08-interview-prep/README.md)**
