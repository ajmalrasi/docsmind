# Retrieval-Augmented Generation (RAG)

RAG grounds a language model's answers in an external corpus, reducing
hallucination and letting the model cite sources.

## The pipeline

1. **Ingest** — load documents and split them into chunks.
2. **Embed** — convert each chunk into a dense vector with an embedding model.
3. **Index** — store the vectors in a vector database for similarity search.
4. **Retrieve** — embed the user's question and fetch the most similar chunks.
5. **Rerank** (optional) — reorder retrieved chunks with a cross-encoder.
6. **Generate** — pass the retrieved context to the LLM and ask it to answer
   using only that context, with inline citations.

## Hybrid retrieval

Dense retrieval captures semantic similarity but can miss exact keyword matches.
Combining dense vectors with a sparse method such as BM25 — then fusing the two
result lists — improves recall. A cross-encoder reranker applied to the fused
candidates further lifts precision at the top ranks.

## Reducing hallucination

Instruct the model to answer strictly from the provided context and to signal
when the context is insufficient rather than guessing. Evaluation metrics such as
faithfulness, context precision, and context recall quantify how well the system
stays grounded.
