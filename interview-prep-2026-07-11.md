# Interview Prep — Applied ML Engineer (AWS + Document Intelligence)

**Interview: tomorrow (2026-07-11).** Private study doc — do NOT put on your portfolio site.

---

## 0. Read the room: what this role actually is

This is **not a RAG role.** It's an **applied ML engineer** role weighted toward:

1. **AWS production deployment** — SageMaker, Lambda, Step Functions (required, not nice-to-have)
2. **Document intelligence** — OCR, PDF/image processing, classification/extraction (insurance/healthcare docs)
3. **End-to-end ML pipelines** you built and shipped
4. **Cost + scalability** in the cloud
5. **~80% hands-on** — they want a builder, not an architect who delegates

GenAI (prompt eng, model selection, eval, monitoring) is required but *general*. RAG/LLMs/transformers are explicitly **"nice to have."**

**Your DocsMind is strong exactly where this JD is weakest (RAG) and thin exactly where it's strongest (AWS deploy + OCR).** So your whole strategy is: lead with the *transferable* parts (end-to-end pipeline, eval frameworks, model selection, cost thinking), be honest about the AWS/OCR gaps, and show a clear trajectory closing them. Do NOT oversell RAG — pivot RAG stories into "pipeline / eval / cost" language they care about.

---

## 1. JD → your experience map (know your honest position on each)

### Required — where you're solid
| JD asks | Your honest claim (DocsMind) |
|---|---|
| End-to-end ML pipelines | **Strong.** Full pipeline: ingest → chunk → embed → index → retrieve → rerank → generate → cite → eval. LlamaIndex ingestion, pluggable components. This is your best story. |
| Model selection & evaluation | **Strong.** Built a labeled eval set (15 queries, Hit@1/Hit@3/MRR), compared dense vs hybrid vs rerank, made data-driven calls. Chose embedding model (bge-small), chunk size, retrieval strategy *with measured evidence.* |
| Prompt engineering | **Solid.** Inline-citation prompting + an `INSUFFICIENT_CONTEXT` guardrail to suppress hallucination when retrieval is weak. |
| Python + ML libraries | **Strong.** LlamaIndex, FAISS, sentence-transformers, rank-bm25, cross-encoders, FastAPI, pytest. |
| Scalability & cost optimization | **Solid conceptually.** Benchmarked FAISS index types (flat/IVF/HNSW/PQ) on recall vs latency vs memory; reasoned about self-host vs managed cost-per-token. |

### Required — where you have GAPS (be honest, show trajectory)
| JD asks | Reality | How to answer |
|---|---|---|
| **Deploy ML models to production** | You have Anthropic managed API + Ollama on a dev box. Not a scalable prod endpoint yet. | "I've shipped a working service (FastAPI, tested), and I'm honest that my current serving is a dev server. I have a concrete plan to serve an open model under vLLM behind a streaming endpoint and measure TTFT/throughput — that's my active next step." Don't claim production AWS serving you haven't done. |
| **AWS for ML (SageMaker, Lambda, Step Functions)** | Limited. You have an AWS account + $100 credit, a deployment learning plan, but haven't shipped on SageMaker/Step Functions. | "I've architected the deployment path and I understand the tradeoffs — managed vs self-hosted cost-per-token, when to use Lambda vs a persistent GPU endpoint. Hands-on AWS is where I'm actively investing. I can talk through *how* I'd deploy this pipeline on SageMaker + Step Functions." Then actually be able to (see Q8). |
| **SQL + data modeling** | Not central to DocsMind. | Don't bluff depth. "Comfortable with SQL for analysis and data modeling; my recent project was vector/document-heavy rather than relational, but I can design schemas and write non-trivial queries." Brush up joins/window functions/CTEs tonight if rusty. |

### Nice-to-have — bonus points where you can honestly claim
- **RAG / transformers / LLMs** — this is your strength; mention it but don't let it dominate.
- **Processing large PDFs** — you ingest/chunk PDFs via LlamaIndex; you can speak to PyMuPDF-class problems even if you used LlamaIndex's loaders.
- **Evaluation frameworks / experimentation** — strong (your eval harness, RAGAS/DeepEval planned for answer-quality/faithfulness).

### Nice-to-have — honest gaps (fine to not have)
- Multimodal (text+image), Textract/Azure DI, OpenCV/Pillow, doc classification/segmentation, Redshift/EMR/Glue, insurance/healthcare domain.
- **Strategy:** for OCR/doc-intelligence, connect the dots: "I haven't used Textract specifically, but document *ingestion, chunking, and extraction quality* is exactly the problem I solved in DocsMind — different tools, same failure modes (noisy text, layout loss, chunk boundaries destroying meaning)." That's a real bridge, not a bluff.

---

## 2. Your 3 anchor stories (rehearse these cold)

Interviewers ask "tell me about a project." Have three tight (~90 sec) stories ready. Each ends with a *measured result* and a *decision you can defend.*

**Story A — End-to-end pipeline (your headline).**
"I built DocsMind, a production-pattern RAG system end to end: document ingestion and chunking, self-hosted embeddings, a vector index behind a pluggable interface, hybrid retrieval with reranking, an LLM generation step with citations and a hallucination guardrail, a FastAPI service, and an evaluation harness. The point wasn't the content — it was proving I can build every stage of an ML pipeline and defend each choice with measurements."

**Story B — Model selection with evidence (hits "model selection & evaluation").**
"I didn't just pick a retrieval strategy — I built a labeled eval set and measured it. Dense vs hybrid vs hybrid+rerank on Hit@1/Hit@3/MRR. At my default chunk size, dense and hybrid tied at 0.93 Hit@1, and adding a cross-encoder reranker took it to 1.00. That told me the reranker was the reliable win, not the BM25 fusion, which only helped at small chunk sizes. The lesson I'd bring to an interview: the evidence you cite for a choice matters more than the choice."

**Story C — Cost/scalability tradeoff (hits "cost optimization").**
"I benchmarked FAISS index types — flat, IVF, HNSW, product quantization — on recall vs latency vs memory. Flat gave 100% recall but scales linearly, ~7ms at 500k vectors. IVFPQ cut memory to 4% of flat but recall collapsed to 33%. For my corpus size, flat was correct — and being able to say *why I did NOT need the fancy index* is a stronger signal than reaching for it. Same discipline I'd apply to cloud cost: right-size to the actual load."

---

## 3. MOCK Q&A DRILL — likely questions with model answers

> Answer structure to keep in your head: **(1) direct answer → (2) how you'd measure/validate → (3) tradeoff or what breaks.** That's the "depth signal" senior interviewers listen for.

**Q1. Walk me through an ML pipeline you built end to end.**
→ Use Story A. Then, if pushed, name the stages and one decision per stage: chunk size (measured against retrieval quality), embedding model (bge-small — small, fast, self-hosted, good enough vs. a paid API embedding), index (flat, justified by corpus size), guardrail (INSUFFICIENT_CONTEXT to avoid confident wrong answers). End on the eval harness.

**Q2. How do you deploy a model to production? / How would you deploy THIS on AWS?**
→ Be honest about current state, strong on the design:
"Today my service is FastAPI with a managed LLM API and a self-hosted embedding model — tested, but a dev-grade server. To productionize on AWS I'd containerize the service, put inference behind a SageMaker endpoint (or an ECS/Fargate service for the API layer), orchestrate the batch ingestion pipeline with Step Functions — extract → OCR → chunk → embed → upsert to the vector store as discrete states with retries — and use Lambda for the lightweight event-driven glue like 'new document landed in S3.' I'd separate the always-on API from the bursty ingestion so I'm not paying for idle GPU. That separation is the main cost lever."
→ If they ask what you've actually shipped on AWS: "Hands-on AWS is my current growth edge. I have the account and a concrete plan; I can reason through the architecture and tradeoffs now, and I close gaps fast — DocsMind is me teaching myself production ML patterns one phase at a time."

**Q3. How do you evaluate an LLM / GenAI system beyond accuracy?**
→ "Two layers. Retrieval quality — Hit@k, MRR — did we fetch the right evidence. And answer quality — faithfulness/groundedness: is the answer actually supported by the retrieved context, not just fluent. Accuracy alone misses hallucination; a confident, well-written, *wrong* answer scores fine on surface metrics. I use a guardrail that returns INSUFFICIENT_CONTEXT rather than guess, and for answer-grading I'd use a framework like RAGAS or DeepEval to score faithfulness against the source."

**Q4. Explain precision, recall, faithfulness, and groundedness.**
→ "Precision: of what I returned, how much was relevant. Recall: of all the relevant stuff, how much I found. Faithfulness/groundedness (LLM-specific): is every claim in the answer actually supported by the retrieved context — it's precision applied to *generated claims* vs. *source evidence.* You can have perfect retrieval and still hallucinate at the generation step, which is why you measure both."

**Q5. What causes hallucinations and how do you reduce them?**
→ "Model fills gaps when context is missing, ambiguous, or contradictory, and it's trained to sound confident. Reduce it by: retrieving better evidence (hybrid + rerank so the right chunk is actually in context), a guardrail that refuses when context is weak (my INSUFFICIENT_CONTEXT path), citation-forced prompting so claims are traceable, and faithfulness eval to catch it in testing rather than production."

**Q6. How do you choose a vector database? Compare FAISS/pgvector/Pinecone/etc.**
→ "Start from constraints: scale, self-host vs managed, filtering needs, ops budget. FAISS: a library, not a database — fastest, in-process, you own persistence and ops, great when you don't need a service. pgvector: reuse Postgres you already run, transactional, good at moderate scale, simplest ops. Pinecone/managed: pay to not run infra, scales, less control. For DocsMind I used FAISS behind a pluggable interface and added Qdrant behind the same interface — so I can swap without touching the rest of the pipeline. The interview point: I abstracted the store so the *choice* is reversible."

**Q7. Why do chunking and retrieval strategies matter?**
→ "Chunk boundaries decide whether a coherent idea survives into the index. Too big: retrieval gets diluted, you pull in irrelevant text. Too small: you shred context and the model loses the thread. I measured it — at 64-token chunks, BM25 recovered an exact term ('supernova') that dense embeddings had ranked #2, and fusion lifted it to #1. So the *right* strategy is corpus- and query-dependent, and the only way to know is to measure on a labeled set."

**Q8. (Doc intelligence pivot) Have you worked with OCR / Textract / large PDF processing?**
→ "Not Textract specifically. But document ingestion and extraction quality is exactly what I worked on — parsing documents, preserving structure through chunking, and measuring downstream whether extraction was good enough for the task. The tools differ (Textract/PyMuPDF/OpenCV vs. my loaders) but the failure modes are the same: noisy or misread text, lost layout, and chunk boundaries that destroy meaning. I'd approach an insurance-doc extraction pipeline the same way — extract, then *evaluate extraction quality with a labeled set* before trusting it downstream."

**Q9. How do you optimize cost and latency in a GenAI app?**
→ "Latency sources: retrieval, model TTFT (time to first token), and generation length. Optimize by caching, reranking a small candidate set instead of the whole corpus, right-sizing the index, and picking the smallest model that passes eval. Cost: separate always-on from bursty compute, batch where you can, self-host small models when volume makes managed APIs expensive, and quantize (INT8/AWQ) to fit cheaper hardware. The discipline is the same as my FAISS call — don't buy capacity the workload doesn't need."

**Q10. Tell me about a hard technical decision and how you validated it.**
→ Use Story B or C. The interviewer wants the *validation*, so spend your words on the eval set and the numbers, not the setup.

**Q11. (Behavioral) This is ~80% hands-on and autonomous. Are you a self-starter?**
→ "DocsMind is self-directed — I scoped it in phases, set my own learning targets, and shipped each phase with tests and benchmarks before moving on. I taught myself production ML patterns by building them, not by taking a course. That's how I work: pick the next highest-leverage gap, build it, measure it."

**Q12. Where are you weakest for this role / what would you need to ramp on?**
→ Answer honestly — they respect it and it's an obvious question given your profile: "Hands-on AWS ML services and OCR-specific tooling. I understand the architecture and tradeoffs, and I've been deliberately closing the deployment gap. I won't pretend I've shipped on SageMaker in production — but I ramp fast and I can already reason through the design."

---

## 4. Tonight's checklist (highest leverage first)

1. **Rehearse the 3 anchor stories out loud** until they're 90 seconds and end on a number.
2. **Memorize Q2 (AWS deploy) and Q8 (OCR pivot)** — these are your two gap questions; they *will* probe here.
3. **Skim SQL** — joins, GROUP BY, window functions, CTEs. Be able to write one non-trivial query.
4. **One-line each AWS service** so you're not blank: SageMaker = managed train/host endpoints; Lambda = serverless event glue; Step Functions = orchestrate a multi-step pipeline with retries; S3 = object store / data lake; Glue = ETL; Redshift = data warehouse.
5. **Prep 2 questions to ask them:** e.g. "What does the current doc-processing pipeline look like, and where does it break?" and "Is the GenAI work greenfield or replacing a rules-based extraction system?" — signals you think about systems, not just models.

## 5. Framing rules for the whole interview
- Lead with **pipeline / eval / cost** language, not "RAG." RAG is your evidence, not your headline.
- Every claim ends with **how you measured it.** That single habit is what separates you from candidates who "can call an API."
- On gaps: **honest + trajectory.** "Haven't shipped that; here's the adjacent thing I did and how I'd close it." Never bluff depth you don't have — a good interviewer finds it in one follow-up.
