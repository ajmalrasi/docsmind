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

## Index Types (Phase 2 — real benchmark numbers)

**Flat vs IVF vs HNSW vs IVFPQ?**
At 50k vectors: flat 0.78ms/100% recall; IVF 0.10ms/90%; HNSW 0.40ms/86%
(1.18x memory); IVFPQ 0.09ms/33% recall but **25x less memory**. Flat scales
O(N): 0.78ms@50k → 7.2ms@500k — that line is why ANN indexes exist.

**Which does your pipeline use?**
Flat. Corpus is tiny; exact search in <1ms. Switching to HNSW would be
premature optimization. The skill is knowing where flat crosses your latency
budget — I measured it.

**What are nprobe / ef_search?**
The recall-vs-speed dial on IVF / HNSW, turned at query time: spend more
compute per query, recover more recall.

**Why benchmark on clustered synthetic vectors?**
Real embeddings cluster. Uniform random vectors flatter IVF and hide
production recall loss. Benchmark on data shaped like your data.

---

## Qdrant vs FAISS (Phase 2b)

**Why add Qdrant?**
Operations, not speed: many API replicas share one store, live upserts,
metadata filtering while searching. FAISS = one process's memory.

**What did the switch cost?**
A network hop per query, a service to run, and exact flat search became
approximate (Qdrant builds HNSW by default).

**How is it swappable?**
Both behind one `VectorStore` interface, chosen by a `vector_backend` config
setting. Pipeline never knows which is underneath.

---

## Hybrid & Reranking (Phase 3 — real eval numbers)

**Why hybrid?**
Dense and BM25 fail differently: dense blurs rare exact terms, BM25 misses
paraphrase. Measured win: "supernova" query — dense ranked it #2, BM25 caught
the exact term, RRF lifted it to #1. Hit@1 0.93 → 1.00 at fine chunking.

**How do you fuse two score scales?**
You don't — RRF uses only rank position: `1/(k+rank)` summed across lists,
k=60. No normalization, no per-corpus tuning.

**Bi-encoder vs cross-encoder?**
Bi-encoder embeds question and chunk separately — fast, precomputable.
Cross-encoder reads the pair together — accurate but per-pair cost, so it
only reranks the ~20 fused candidates. A funnel: cheap scan → careful check.

**What did reranking buy?**
The most reliable win: fixed the one miss in every configuration tested
(Hit@1 0.93 → 1.00). Hybrid's gain depended on chunk size; the reranker's
didn't.

**Your metrics disagreed — explain.**
Hybrid+rerank raised Hit@1/MRR but lowered Recall@5/NDCG@5: better single
best chunk, less same-doc coverage. Pointed Q&A wants Hit@1; summarization
wants recall. Pick the metric that matches the task.

**How did you validate retrieval?**
15 labeled queries (exact-term + paraphrase mix), same metrics across
dense / hybrid / hybrid+rerank, one command (`make eval`). Change one
variable, re-run, compare.

---

## Generation

**Why number the context passages [1][2][3]?**
The numbers are what make citations traceable. Claude is instructed to cite
every claim with [n]. The pipeline then extracts those markers with a regex
and maps each back to the source filename and similarity score. Without
numbers, you get an answer but can't trace any claim to a file.

**Why put rules in the system prompt and not the user message?**
Claude treats the system message as a persistent behavioral contract, giving
it higher precedence than instructions embedded in the user message. "Answer
only from context" belongs in the system message.

**What is INSUFFICIENT_CONTEXT?**
An exact string the pipeline uses as a sentinel. If Claude can't answer from
the retrieved chunks, it returns this string. The pipeline checks
`"INSUFFICIENT_CONTEXT" not in answer` and sets `grounded=false`. The exact
string is defined once as a constant and used in both the prompt and the check.

**Why direct Anthropic SDK and not LangChain's wrapper?**
Direct SDK = full control over every API parameter, no hidden retry logic or
routing, easier to add caching or streaming. The `LLMClient` interface means
swapping to vLLM (Phase 4) is a one-class change with no pipeline edits.

**What if Claude hallucinate-cites [7] when only 4 passages exist?**
The citation extractor bounds-checks: `if 1 <= m <= len(results)`. Invalid
markers are silently dropped. It's a small but important guard.

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
