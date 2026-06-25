# Pipeline — Interview Questions

## Q: Walk me through your RAG pipeline.

"Documents are loaded with LlamaIndex and split into 512-token sentence-aware
chunks with 64-token overlap. Each chunk is embedded by self-hosted bge-small
into a 384-dim L2-normalized vector stored in a FAISS flat index. At query
time, the question is embedded with the same model, FAISS returns the top-4
chunks by cosine similarity, and those are formatted as numbered context
passages sent to Claude. A system prompt forces the model to cite by passage
number and return `INSUFFICIENT_CONTEXT` if the context isn't sufficient. The
pipeline extracts citation markers from the response and maps them back to
source filenames."

---

## Q: RAG vs fine-tuning vs long-context LLMs?

| Approach | When it's right | Key weakness |
|---|---|---|
| **RAG (what we built)** | Knowledge in documents, changes often, needs citations, corpus too big for context window | Retrieval quality gates answer quality |
| **Fine-tuning** | Teach the model a skill or style, not updateable facts | Expensive to retrain, baked-in knowledge goes stale |
| **Long-context LLM** | Tiny corpus that fits in a context window, one-off use | Very expensive per query, no targeting — full corpus every time |

RAG is the right default for "answer questions from a document corpus" use cases.
Fine-tuning is for "change how the model writes or reasons."

---

## Q: How do you prevent hallucination?

Two layers in Phase 1:
1. **Prompt-level:** system prompt tells Claude to answer only from numbered
   context passages and return `INSUFFICIENT_CONTEXT` if context is insufficient.
2. **Pipeline-level:** if `INSUFFICIENT_CONTEXT` appears in the response,
   `grounded=false` is returned and no citations are extracted.

These are soft guardrails — they rely on the model following instructions.
Phase 6 adds RAGAS-based evaluation to measure hallucination rate
systematically. A harder structural guardrail is part of Phase 5 (LangGraph).

---

## Q: Why not just send all documents to the LLM?

Two reasons: **cost** and **quality**.
- Cost: LLMs charge per input token. Sending 100 docs on every query is
  prohibitively expensive at scale.
- Quality: LLMs degrade with overloaded context ("lost in the middle" problem —
  attention disperses on very long contexts). Retrieving 4 focused chunks gives
  the model exactly what it needs.

---

## Q: What happens if the user asks something not in the corpus?

FAISS still returns top-k (it always returns something). Similarity scores will
be low. If Claude follows the system prompt it returns `INSUFFICIENT_CONTEXT`.
To add a harder safety net: add a similarity score threshold — if all top-k
results are below e.g. 0.60, skip the LLM call entirely and return "I don't
have information about that."

---

## Q: How does latency break down?

```
Embed question:   ~20ms  (bge-small on CPU; ~2ms on GPU)
FAISS search:     ~1ms   (50 vectors, flat index)
Claude API call:  ~700ms (network + generation — dominates total latency)
Citation parsing: ~1ms

Total: ~720ms (CPU), ~700ms (GPU) — bottleneck is always the LLM API call
```

To reduce latency: use a smaller/faster model (claude-haiku-4-5 instead of
claude-opus-4-8), reduce max_tokens, or add streaming so the user sees
partial responses.

---

## Q: Why FastAPI and not Flask?

FastAPI gives you async support, automatic request/response validation via
Pydantic (the schemas are already defined in `schemas.py`), and automatic
OpenAPI docs at `/docs`. Flask would require manual validation and doesn't
support async natively. For a project that already uses Pydantic everywhere,
FastAPI is the natural choice.

---

## Q: Why LlamaIndex for ingestion and not LangChain?

LlamaIndex is purpose-built for the RAG data layer (load, chunk, embed, index).
Its abstractions are specifically designed for document ingestion pipelines.
LangChain is more general — chains, agents, tool use — and its data layer is
secondary. For the ingestion pipeline specifically, LlamaIndex is a cleaner fit.
LangGraph (LangChain's graph-based agent framework) is used in Phase 5 for
orchestration, where it excels over LangChain's older agent loop.
