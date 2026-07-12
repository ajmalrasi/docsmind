# DocsMind — Learning Path

Everything you need to understand DocsMind, in the order it was taught.
Read **top to bottom the first time**. Come back to any file as a reference
anytime. Topics 1–8 cover Phase 1 (the core pipeline); 9–10 cover Phases
2–3 (better retrieval); 11–21 map the concepts the next phases and the
target role need.

```
documents → chunk → embed → normalize → store in FAISS
                                              ↓
question  → embed ──────────────────→ search FAISS → top-k chunks → Claude → answer + citations
```

## The core pipeline (Phase 1)

| # | Folder | What you learn |
|---|--------|----------------|
| 1 ✂️ | [01-chunks-and-overlap/](01-chunks-and-overlap/) | Why we split documents, what a chunk is, what overlap does |
| 2 🔢 | [02-embeddings/](02-embeddings/) | How text becomes numbers that capture meaning |
| 3 📐 | [03-normalization/](03-normalization/) | The vector math that makes search fair and fast |
| 4 🎯 | [04-vector-similarity/](04-vector-similarity/) | How we measure "closeness" between two vectors |
| 5 🗄️ | [05-faiss/](05-faiss/) | The engine that stores vectors and finds the closest ones |
| 6 💬 | [06-generation/](06-generation/) | Building context, prompting Claude, citations, guardrail |
| 7 🔗 | [07-full-pipeline/](07-full-pipeline/) | Every piece wired together, a real query end to end |
| 8 🎤 | [08-interview-prep/](08-interview-prep/) | Every "why X over Y" question an interviewer will ask |

## Better retrieval (Phases 2–3, built and measured)

| # | Folder | What you learn |
|---|--------|----------------|
| 9 ⚖️ | [09-hybrid-retrieval/](09-hybrid-retrieval/) | Dense + BM25 + RRF fusion + cross-encoder reranking, with real eval numbers |
| 10 🧩 | [10-qdrant/](10-qdrant/) | A second vector store behind the same interface |

## The advanced map (concepts for Phases 5–8 and the serving roadmap)

| # | Folder | What you learn |
|---|--------|----------------|
| 11 🔮 | [11-hyde/](11-hyde/) | Search with a fake answer — query transformations |
| 12 🛠️ | [12-tool-calling/](12-tool-calling/) | The LLM asks, your code answers — the agent's core mechanic |
| 13 🔌 | [13-mcp/](13-mcp/) | A USB port for tools — standardize the plug, not the electricity |
| 14 🕸️ | [14-agent-architectures/](14-agent-architectures/) | One loop vs many, and who's in charge |
| 15 ⚙️ | [15-llm-serving-internals/](15-llm-serving-internals/) | KV cache, continuous batching, speculative decoding |
| 16 🧵 | [16-python-concurrency/](16-python-concurrency/) | Sync, async, threads, processes — and why `/query` is a plain `def` |
| 17 🌐 | [17-fastapi-http-semantics/](17-fastapi-http-semantics/) | GET vs POST, and contracts that enforce themselves |
| 18 🛡️ | [18-llm-security/](18-llm-security/) | PII, injection, jailbreaks, RBAC, moderation — five problems, five fixes |
| 19 🎛️ | [19-fine-tuning/](19-fine-tuning/) | When RAG isn't the right tool — LoRA/QLoRA/PEFT/RLHF untangled |
| 20 📈 | [20-production-monitoring/](20-production-monitoring/) | Cost, latency, quality, drift — four signals, not one dashboard |
| 21 📄 | [21-multimodal-document-rag/](21-multimodal-document-rag/) | PDFs, tables, scans, charts — why it's an ingest problem |
| 22 🕸️ | [22-langgraph/](22-langgraph/) | State, nodes, edges — build the agent graph, and "show me a node" |

## How to use this

- **First time:** follow the numbers, 1 → 22. The pipeline (1–7) is the
  skeleton everything else hangs on.
- **Stuck on a concept:** each folder has a `README.md` overview that links
  to every file inside.
- **Interview prep:** go straight to `08-interview-prep/` — and note every
  section 9–22 ends its overview with a 🎯 Interview Q&A of its own.
- **See the real code:** every file links to the actual source file it's
  explaining, or names the exact seam where a not-yet-built feature lands.

→ Start here: **[01-chunks-and-overlap/README.md](01-chunks-and-overlap/README.md)**
