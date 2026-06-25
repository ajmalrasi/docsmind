# 07 — Full Pipeline

**The big idea:** Every piece we've studied connects into one flow. A document
goes in at ingest time and a grounded answer with citations comes out at query
time. This section ties everything together.

## Files in this folder

| File | What it covers |
|------|----------------|
| [4-step-flow.md](4-step-flow.md) | The full ingest → chunk → embed → index → retrieve → generate flow |
| [real-query-example.md](real-query-example.md) | One real question traced through every component |
| [phase1-end-to-end.md](phase1-end-to-end.md) | How the code components wire together (factory, pipeline, API) |

## 🎯 Interview Q&A

**Q: Walk me through your RAG pipeline.**
"Documents are loaded with LlamaIndex and split into 512-token, sentence-aware
chunks with 64-token overlap. Each chunk is embedded with self-hosted bge-small
into a 384-dim L2-normalized vector and stored in a FAISS flat index. At query
time, the question is embedded with the same model, and FAISS returns the top-4
chunks by cosine similarity. Those chunks are formatted as numbered context
passages and sent to Claude with a system prompt that forces citation by passage
number and returns `INSUFFICIENT_CONTEXT` if the context isn't enough to answer.
The pipeline extracts the citation markers from the answer and maps them back to
source filenames."

**Q: Why not just send all documents to the LLM?**
Two reasons: cost and quality. Cost: LLMs charge per token — sending 100 full
documents per query is expensive. Quality: LLMs have a finite context window and
degrade when it's overloaded with irrelevant text. RAG retrieves only the relevant
few chunks, so the model sees focused, useful context.

**Q: How do you prevent hallucination?**
Two layers. First, the system prompt explicitly tells Claude to answer only from
the numbered context passages and to reply `INSUFFICIENT_CONTEXT` if the context
isn't enough. Second, the pipeline checks the response — if `INSUFFICIENT_CONTEXT`
appears, it returns `grounded=false` and no citations. Phase 6 adds RAGAS-based
eval to measure hallucination rate systematically.

**Q: What happens if the user asks something outside the corpus?**
FAISS still returns the top-k most similar chunks (it always returns k results).
But the similarity scores will be low and the chunks won't actually be relevant.
If Claude follows the system prompt, it returns `INSUFFICIENT_CONTEXT`. If you
want a harder safety net, add a similarity threshold filter — drop results below
e.g. 0.60 before passing to the LLM.

**Q: RAG vs fine-tuning vs long-context LLMs?**

| Approach | When to use | Weakness |
|---|---|---|
| **RAG (what we built)** | Knowledge is in documents, changes often, needs citations | Retrieval quality affects answer quality |
| **Fine-tuning** | Teach the model a new skill or style, not facts | Expensive to retrain, knowledge bakes in and goes stale |
| **Long-context LLM** | Small enough corpus to fit in context window | Very expensive per query, no targeting (all context every time) |

RAG is the right default for "chat with your docs" use cases.

## Code — key files

| File | Role |
|------|------|
| [config.py](../../docsmind/config.py) | All settings (model, chunk size, paths) |
| [factory.py](../../docsmind/factory.py) | Wires all components together |
| [pipeline.py](../../docsmind/pipeline.py) | retrieve → build context → generate → cite |
| [serving/app.py](../../docsmind/serving/app.py) | FastAPI: /health, /query |

→ Next: **[08-interview-prep/README.md](../08-interview-prep/README.md)**
