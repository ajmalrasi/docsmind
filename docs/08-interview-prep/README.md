# 08 — Interview Prep

**The big idea:** Interviewers don't just ask "what is FAISS?" — they ask
"why FAISS over Pinecone?" and "when would you NOT use it?" These are the
tricky questions that separate someone who used a tool from someone who
understands it. This folder collects every "why X over Y" question by topic.

## Files in this folder

| File | What it covers |
|------|----------------|
| [chunking-questions.md](chunking-questions.md) | Chunk size, overlap, splitter type tradeoffs |
| [embedding-questions.md](embedding-questions.md) | Self-hosted vs cloud, bi-encoder vs cross-encoder, dimensions |
| [retrieval-questions.md](retrieval-questions.md) | FAISS vs Pinecone, Flat vs HNSW, exact vs approximate |
| [index-questions.md](index-questions.md) | Flat/IVF/HNSW/PQ with real benchmark numbers, Qdrant vs FAISS |
| [hybrid-questions.md](hybrid-questions.md) | BM25, RRF, cross-encoder reranking, eval results, debugging retrieval |
| [generation-questions.md](generation-questions.md) | Prompting Claude, citations, guardrail, latency, streaming |
| [pipeline-questions.md](pipeline-questions.md) | RAG vs fine-tuning, hallucination, top-k, LangChain vs SDK |
| [cheat-sheet.md](cheat-sheet.md) | One page — all key "why this" answers in 2 sentences each |

## How to use this

- Read the topic files when you want depth on a specific area.
- Read `cheat-sheet.md` the morning of an interview.
- For any question: lead with **what** the choice is, then **why** it beats
  the alternatives, then **when** you'd make a different choice.

→ Start with: **[cheat-sheet.md](cheat-sheet.md)** for a fast overview,
then drill into topic files for depth.
