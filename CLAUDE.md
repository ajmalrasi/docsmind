# DocsMind — Project Context

## What this is
DocsMind is a portfolio project proving GenAI/LLM-Architect skills: production RAG, vector DBs, hybrid retrieval, agentic workflow, eval/hallucination control, LLMOps. Corpus = space/astronomy docs, deliberately unrelated to the RAG machinery being taught, so the user can separate "content" from "plumbing." Built phase by phase (1–8); ship phases 1–3 first.

**User goals:**
1. Get comfortable with GenAI/LLM development
2. Learn production-grade RAG architecture and best practices
3. Build a portfolio project to land a job

This shapes how work should be framed: prioritize learning over shortcuts, explain architectural choices, highlight transferable skills, call out what would look good on a resume (production patterns, eval frameworks, ops pipelines). When suggesting work, ask: Does this teach something new? Is this a pattern seen on a real job? Could the user explain this in an interview?

## Locked architecture decisions
- RAG-heavy architect focus, hybrid self-host SLM + cloud LLM
- LlamaIndex for ingestion, LangGraph for the agent
- FAISS (flat→IVF/HNSW/PQ) + Qdrant behind one `VectorStore` interface
- Retrieval: dense + BM25 + rerank (RRF fusion)
- Cloud LLM = Anthropic Claude (default `claude-opus-4-8`, configurable)

## Phase status

**Phase 1 (done, 2026-06-23):** config (pydantic-settings), LlamaIndex ingest + SentenceSplitter chunking, self-hosted `bge-small` embeddings, FAISS flat behind pluggable `VectorStore`, Anthropic cloud generation with inline citations + `INSUFFICIENT_CONTEXT` guardrail, FastAPI `/health`+`/query`, pytest suite, `make demo`. Stubs exist for agent/eval/ops (not yet built out).

**GitHub:** https://github.com/ajmalrasi/docsmind (public, pushed 2026-06-23). Remote = `git@github.com:ajmalrasi/docsmind.git`. GitHub user = `ajmalrasi`; auth token stored in macOS Keychain under `gh:github.com`.

**Phase 2 — index types (done, 2026-06-26):** `FaissVectorStore` supports flat/ivf/hnsw/ivfpq behind the same interface (IVF/IVFPQ train on add; all use `METRIC_INNER_PRODUCT` for cosine). Tuning dials live in config (`ivf_nlist`/`ivf_nprobe`, `hnsw_m`/`hnsw_ef_*`, `pq_m`/`pq_nbits`). `scripts/benchmark.py` (+ `make benchmark`) measures recall@k/latency/memory on synthetic *clustered* vectors; real numbers are in `docs/05-faiss/benchmark-results.md`:
- At 50k vectors: flat = 0.78ms / 100% recall; ivf = 0.10ms / 90% recall; hnsw = 0.40ms / 86% recall / 1.18x memory; ivfpq = 0.09ms / 33% recall / 0.04x memory.
- flat scales O(N): 0.78ms@50k → 7.2ms@500k.
- Real pipeline stays on `flat` (corpus too small to need the others). 17 tests pass at this point.

**Phase 2b — Qdrant backend (done, 2026-06-28):** `QdrantVectorStore` behind the same `VectorStore` interface (`docsmind/index/qdrant_store.py`). Local-path persistence by default (offline, mirrors FAISS save/load under `index_dir/qdrant`), optional server via `qdrant_url` (Docker on beast). Cosine distance, Qdrant's built-in HNSW. Selected by new `vector_backend` setting (`faiss` default / `qdrant`). Tests use `:memory:`. Added a `chunks` property to the `VectorStore` ABC (Phase 3's BM25 reads it). `close()` releases the local-path lock.

**Phase 3 — Hybrid retrieval (done, 2026-06-28):** dense + BM25 → RRF → optional cross-encoder rerank. New files: `retrieval/bm25.py` (rank-bm25, rebuilt in-memory from stored chunks), `retrieval/fusion.py` (Reciprocal Rank Fusion, k=60), `retrieval/reranker.py` (`CrossEncoderReranker`, lazy-loaded), and `HybridRetriever` in `retrieval/retriever.py`. Default `retrieval_mode="hybrid"` is **ON** (BM25 fusion needs no model), but `rerank_enabled=False` by default (cross-encoder downloads a model → gated for beast GPU; model is `ms-marco-MiniLM-L-6-v2`). Dials: `candidate_k=20`, `fusion_k=60`. Existing FAISS index works with hybrid without re-ingest (chunks already persisted); switching to Qdrant needs re-ingest. 28 tests pass (was 17). Deps added: `qdrant-client`, `rank-bm25`.

**Retrieval eval (done, 2026-06-28):** `scripts/retrieval_eval.py` (+ `make eval` / `make beast-eval`, flags `--rerank`, `--chunk-size`) scores dense vs hybrid vs hybrid+rerank on a 15-query labeled set (`data/eval/retrieval_queries.json`, source-level relevance, metrics Hit@1/Hit@3/MRR). Real findings:
- At default `chunk_size=512` (5 chunks): dense == hybrid (0.93 Hit@1); adding rerank → 1.00.
- At `chunk_size=64` (72 chunks): hybrid 1.00 > dense 0.93 — BM25 recovered the exact term "supernova" that dense had ranked #2, and RRF fusion lifted it to #1.
- Honest takeaway: hybrid's gain is corpus-size/chunk-size dependent; the reranker is the most reliable win regardless. Ran locally on Mac (mps backend), models downloaded fine.

**Teaching docs (done, 2026-06-28):** `docs/09-hybrid-retrieval/` (README + eval-results.md with the real numbers above) and `docs/10-qdrant/` (README). Written in the plain-language teaching style (see below).

**Still not built:** answer-quality eval (faithfulness/hallucination — Phase 6, RAGAS/DeepEval; this grades LLM output, not retrieval). No Makefile target yet for running Dockerized Qdrant *server* on beast (local-path mode works without one).

**Next:** Phase 4 (LLM router — which *model* to call) or Phase 6 (answer eval).

## Dev workflow
Canonical git repo lives on the Mac at `/Users/ajmalrasi/docs_mind` — fast file edits, clean history for GitHub, source of truth. Heavy execution runs on the beast GPU box (below).

`make sync` rsyncs the working tree to `beast:~/projects/docsmind` (excludes `.git`, `.venv`, `data/index`, `__pycache__`). The `beast-*` Makefile targets (`beast-install`, `beast-ingest`, `beast-demo`, `beast-serve`, `beast-test`, `beast-eval`) sync then run over SSH. Override host with `BEAST=user@host`.

Why this split: lets the user work with native file tools + git on the Mac while running on the GPU box where it belongs. beast holds the venv + index; the Mac is the source of truth.

## The "beast" GPU box
`beast` = `ajmalrasi@192.168.3.226`, SSH key auth via `~/.ssh/id_ed25519` (authorized as of 2026-06-23).

Specs: Ubuntu 24.04 (kernel 6.17), NVIDIA RTX 3070 Ti Laptop GPU (8GB VRAM, driver 580), Python 3.12.3 (no conda), Docker 28.3.3, Ollama running (has `deepseek-coder-v2:16b` pulled). `/home` partition has ~614GB free — keep all project data/models there. Project lives at `~/projects/docsmind` on beast.

## Roadmap: target role and how DocsMind bridges to it
Target role the user wants to grow toward (saved 2026-06-29 as a learning/roadmap target, **not** to apply now): **Auric AI — LLM inference/serving engineer** for a sovereign Multi-INT defence platform (Indian defence/intel customers). Air-gapped, self-hosted open weights on customer hardware. Founder-direct, "we care about what you've shipped," degrees not required.

**Core of the role (NOT a RAG role — it's serving/inference):**
- Frontier→open migration: 13 agents, real eval set. Llama 3.3 / Mistral / Gemma, smallest quality drop within hardware budget.
- Tool-call & structured-output reliability — where the regression budget is spent. Fix via prompting / constrained decoding / model swap / fine-tune.
- Serving stack: vLLM first (then maybe TensorRT-LLM / SGLang). Batching, KV cache, prefix caching, tensor parallelism, quantization.
- Eval harness, per-agent + end-to-end ("highest-leverage part of the job").
- Heterogeneous serving across multi-node H100/A100 — decide what runs on 70B vs 12B.

**Non-negotiables (the senior bar):** 4+ yrs ML systems / 2+ on LLM inference; production 70B-class open model with real numbers; hands-on vLLM/TGI/TensorRT-LLM/SGLang; shipped tool-call + structured-output reliability (Outlines/XGrammar constrained decoding); quantization tradeoffs *measured* (AWQ/GPTQ/FP8/INT8); strong PyTorch + CUDA debugging; multi-node TP/PP.

**Entry gate — "Apply with one of" (overrides the years requirement):**
1. Project standing up an open model in production **with numbers**.
2. GitHub link to inference work (vLLM/TGI/transformers PRs = gold).
3. Paragraph on a non-trivial inference debug — **bonus if a tool-call regression**.

**How DocsMind bridges to it:** DocsMind is currently the retrieval half (FAISS/hybrid/rerank) — supporting evidence at best. To make entry-gate bullets #1 and #3 real on the beast (RTX 3070 Ti, 8GB — too small for 70B, fine for the *craft* at 7–12B):
- Stand up Llama 3.3 / Mistral / Gemma under **vLLM** (named specifically, beyond current Ollama). Measure tok/s, TTFT, throughput vs batch size, KV cache, INT8/AWQ. → bullet #1.
- Swap DocsMind's agentic tool-calling from closed→open model, watch tool calls break (schema drift, format collapse), fix with **Outlines/XGrammar constrained decoding**, write up before/after tool-call success rate. → bullet #3, and maps to their #1 interview topic.

Next step when ready: scope a new DocsMind topic folder "open-weights serving + tool-call reliability under vLLM."

## Roadmap: cloud deployment learning plan
The user is increasingly asked in interviews **"how did you deploy a model in production?"** Current DocsMind story is only half an answer (managed Anthropic API + Ollama on beast, which is a dev server, not a scalable production endpoint). Closing this gap is a top priority — it's the core skill for the Auric target role above.

**Assets:** AWS account with **$100 free credit** (created ~2026-06-28), and the **idle RTX 3070 Ti** on beast (8GB VRAM → 3B–7B *quantized* models, AWQ/GPTQ).

**Locked decision (2026-06-28): do NOT burn the $100 on Bedrock.** Bedrock is pay-per-token and so cheap you can't meaningfully spend $100 learning on it, and the user already has the managed-API skill via Anthropic. The $100 is scarce *cloud-only* currency.

**Allocation:**
- **Free, first (3070 Ti):** serve an open model with **vLLM** behind an OpenAI-compatible streaming endpoint; benchmark TTFT / throughput / GPU utilization. This is the missing "self-host & serve" skill. Mechanics (continuous batching, paged attention, KV cache, quantization) are identical at any GPU size.
- **$100 credit → cloud-only things that cost real money:** a `g5.xlarge` (24GB) cloud GPU to run a *bigger* model and earn the literal "deployed on AWS" claim; a managed vector store (OpenSearch / pgvector); app deploy (ECS Fargate / App Runner).
- **Bedrock:** a brief, cents-level taste only — for the managed-vs-self-hosted **cost-per-token comparison**.

**The interview payoff to aim for:** "I served the same model three ways — self-hosted on my own RTX 3070 Ti, on a cloud g5 GPU, and managed via Bedrock — and measured cost-per-token, TTFT, and throughput for each." Two of the three data points come from the free GPU.

This connects to Phase 4 (LLM router) — the provider-abstraction seam this plugs into.

## Teaching style (apply whenever explaining or writing docs in this repo)
The user learns by connecting new concepts to a mental map, not by memorizing isolated facts ("I don't learn facts. I connect dots.").

1. **Anchor to pipeline stage first, always, before any definition.** Use a consistent pipeline map as the skeleton: Ingest → Chunk → Embed → Index → [Query → Embed → Search → Rerank → Filter → Generate → Cite → Eval]. E.g. "This runs at retrieval time, between FAISS and the LLM" — stated before any definition.
2. **Show the exact insertion point in the real code** (file + function) when introducing a new technique — concrete over abstract, not just concept.
3. **When comparing two techniques, show them at the same pipeline stage** so the difference is structural, not abstract.
4. **Never define a term in isolation.** Always: "At stage X, we currently do Y. The new thing Z replaces/enhances Y because..."
5. **STRICT RULE — depth-signal teaching, no exceptions.** For every concept, also teach the interview depth signal behind it — the questions a real AI engineer must be able to answer:
   - Why did you choose *this* over alternatives?
   - How did you measure whether it worked?
   - What breaks, and how do you debug it?
   - What are the trade-offs?
   Frame it explicitly: "In an interview, the real question is not 'did you use FAISS?' — it's 'why FAISS, and how did you know it worked?'" When discussing any choice made in DocsMind (embedding model, chunk size, retrieval strategy), explicitly articulate *why that choice* and *what the alternative was*. When running benchmarks/evals, connect the metrics back to: "This is the evidence you'd cite in an interview when they ask how you validated it." Skipping this frame — even once — breaks the user's learning goal.
6. **Plain language, real terms (strict rule).** Explanations must be easy to understand — dense writing "feels like reading a research paper" and doesn't land. Never drop the technical term, but immediately make it click with plain words / a concrete everyday analogy. Keep sentences short, one idea per line. Prefer "X is basically Y" framing. Lead with the intuition, then attach the technical name — not the reverse. Goal: the user should be able to re-explain it in their own words AND say the correct term.
7. **No recap/callback phrases** ("Recall the gotcha:", "Remember when we said...", "As we covered earlier") — they feel condescending. Just say the thing directly.

## Teaching roadmap: "Robust RAG System" diagram
The user shared Brij Kishore Pandey's "Building a Robust RAG System" infographic and wants the `docs/` teaching folders to **eventually teach every concept in it**, mapped onto DocsMind's phases as they're built. The diagram is the canonical "menu" of advanced RAG techniques; covering it box-by-box gives a complete portfolio + interview-ready understanding. As each phase lands, add a teaching doc for the matching diagram box: decode the new term in one line, then show exactly where it slots into the real code (`pipeline.py` etc.) — concrete over abstract.

Diagram boxes → phases:
- Reranking → Phase 3 (cross-encoder, done); Refinement/compression → Phase 3/5
- RAG Types: Multi-Query, RAG Fusion, HyDE, Decomposition → Phase 5 (agent)
- Routing (which vector store) → Phase 5/8 — **distinct** from Phase 4 `LLMRouter` (which *model*); don't conflate the two
- Query Construction (text-to-SQL / text-to-Cypher) → Phase 8 (Neo4j)
- Advanced indexing: Semantic Split, Multi-Representation, ColBERT, RAPTOR → mostly unplanned/frontier
- Self-RAG / active retrieval → unplanned/research-grade
- Evals: RAGAS, Grouse, DeepEval → Phase 6

Highest-leverage, lowest-effort next teaching targets: **HyDE** and **reranking** (reranking exists in code but hasn't had its full depth-signal writeup yet).

## Interview-prep checklist / teaching roadmap
Source: a LinkedIn post (Santhosh Bandari) listing 20 questions that filter GenAI developers on production/system skills, not just RAG basics. Kept as reference — each question should map to a DocsMind phase/box to teach; use these to pressure-test what each phase actually teaches.

1. What causes hallucinations, and how do you reduce them?
2. Why isn't RAG enough for enterprise AI?
3. How do you evaluate an LLM beyond accuracy?
4. Explain precision, recall, faithfulness, and groundedness.
5. What happens internally when an LLM receives a prompt?
6. How do tokens, embeddings, and attention work together?
7. When should you fine-tune instead of using prompt engineering?
8. Why do most fine-tuning projects fail?
9. How would you design a scalable multi-agent system?
10. When should you use workflows instead of autonomous agents?
11. How do you prevent prompt injection and data leakage?
12. Explain LLM guardrails and security in production.
13. How would you debug a slow or expensive GenAI application?
14. Where does latency come from, and how do you optimize it?
15. How do you choose the right vector database?
16. Compare Pinecone, Weaviate, Milvus, FAISS, and pgvector.
17. How do you build enterprise-grade RAG pipelines?
18. Why do chunking and retrieval strategies matter?
19. How would you deploy a GenAI system serving 1M+ users?
20. How do you monitor LLM quality, cost, latency, and drift in production?

Theme: most candidates can call an LLM API; few can build reliable, scalable AI systems.
