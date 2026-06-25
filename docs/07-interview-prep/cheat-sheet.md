# Cheat Sheet — One Page, Every Key Answer

Read this the morning of an interview. For depth, go to the topic files.

---

## Chunking

**Why chunk?**
Embedding a whole doc averages all its topics into a blurry vector. Small
focused chunks give sharp, precise embeddings and focused retrieval.

**Big vs small chunks?**
Small = sharper retrieval, less context. Large = fuzzier retrieval, more context.
512 tokens is a common sweet spot. Tune it with an eval set.

**Why 512 specifically?**
Matches bge-small's 512-token max input. Bigger chunks get silently truncated.
Never set chunk size above your embedding model's max sequence length.

**Why overlap?**
Prevents ideas at chunk boundaries from being split. A sentence at the end of
chunk N appears again at the start of chunk N+1, so it's always fully inside
at least one chunk. Costs ~12% duplication.

---

## Embeddings

**Why self-hosted bge-small over OpenAI?**
Embedding is a bulk job — you encode the whole corpus at ingest. Paid per-token
APIs cost money and send your data externally. Self-hosted is free, private, and
no vendor lock-in. The Embedder class makes it a one-line swap.

**Why same model for documents and queries?**
Each model has its own vector space. Cross-model comparison is meaningless.

**Dense vs BM25?**
Neither alone — hybrid wins. Dense captures meaning, BM25 captures exact terms.
Hybrid + reranking (Phase 3) beats either.

**Bi-encoder vs cross-encoder?**
Bi-encoder = fast, scalable, precomputable (used for retrieval).
Cross-encoder = accurate but must run per query-doc pair (used as reranker).

---

## Normalization

**Why L2 normalize?**
Makes all vectors length 1.0 so only direction (meaning) affects similarity,
not length (word count). Also makes dot product = cosine similarity, so
IndexFlatIP gives you cosine similarity for free.

**Cosine vs Euclidean?**
Cosine cares about direction (meaning), not magnitude (length). Euclidean is
affected by magnitude. For text retrieval, cosine is always the right choice.

---

## FAISS & Retrieval

**FAISS vs Pinecone?**
FAISS = in-process library, free, no data egress, no filtering. Pinecone =
managed cloud service, rich filtering, any scale, but costs money and sends data
externally. Qdrant = open-source managed DB (Phase 2) — best of both.

**IndexFlatIP vs HNSW?**
Flat = exact, 100% recall, O(N) time. Right for < 100k vectors.
HNSW = approximate, ~98% recall, O(log N) time. Right for millions of vectors.
Phase 1 uses Flat because 50 chunks doesn't need approximation.

**Recall@k?**
Fraction of truly relevant chunks that appear in your top-k results. ANN indexes
trade ~1–5% recall for huge speed gains. Usually acceptable for RAG.

---

## Pipeline

**Walk me through your RAG pipeline.**
Load docs with LlamaIndex → 512-token sentence-aware chunks (64 overlap) →
embed with bge-small (384 dims, normalized) → store in FAISS flat index →
at query: embed question → FAISS returns top-4 → format as numbered passages →
Claude answers with citations → extract citations → return grounded response.

**RAG vs fine-tuning?**
RAG = knowledge in docs, updatable, citable. Right for "chat with your docs."
Fine-tuning = teach a skill or style, bakes in static knowledge. Not for
frequently changing facts.

**How do you prevent hallucination?**
System prompt forces citation with [n] markers and `INSUFFICIENT_CONTEXT` if
context is insufficient. Pipeline checks the response and sets `grounded=false`.
Phase 6 adds RAGAS evaluation to measure it systematically.

**Why not send all docs to the LLM?**
Cost (tokens) and quality ("lost in the middle" — attention disperses over very
long contexts). Retrieval focuses the model on exactly what's relevant.

**Latency bottleneck?**
Always the LLM API call (~700ms). FAISS search is < 1ms. Embed is ~20ms on CPU.
To reduce: use a smaller model, add streaming, or reduce max_tokens.

**LlamaIndex not LangChain?**
LlamaIndex is purpose-built for RAG data pipelines. LangChain is general-purpose
(chains, agents). For ingestion, LlamaIndex is cleaner. LangGraph (Phase 5)
handles orchestration where graph-based state machines are the right tool.
