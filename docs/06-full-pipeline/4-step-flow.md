# The 4-Step Flow

**TL;DR:** Two phases: **ingest** (run once, builds the index) and **query**
(runs on every request). Everything we've learned lives in these two phases.

## Phase A: Ingest (run once)

```
make ingest
```

```
Step 1: LOAD
  LlamaIndex SimpleDirectoryReader
  → reads all files in data/sample_docs/
  → produces: list of Document objects (raw text + filename)

         ↓

Step 2: CHUNK
  LlamaIndex SentenceSplitter (chunk_size=512, chunk_overlap=64)
  → splits each Document into overlapping pieces
  → produces: list of Chunk objects
              each has: id, text (~380 words), source (filename), metadata

         ↓

Step 3: EMBED
  sentence-transformers bge-small-en-v1.5
  → converts each chunk's text to a 384-float vector
  → normalizes each vector to length 1.0 (L2 normalization)
  → produces: numpy array of shape (N_chunks, 384)

         ↓

Step 4: INDEX
  FAISS IndexFlatIP
  → stores all N vectors in a flat array in memory
  → saves to disk: data/index/index.faiss + data/index/meta.json
  → produces: a searchable index ready for queries
```

## Phase B: Query (every request)

```
POST /query  {"question": "When should I use HNSW over IVF-PQ?"}
```

```
Step 1: EMBED QUESTION
  same bge-small model
  → "When should I use HNSW over IVF-PQ?" → 384-float vector, normalized
  → MUST use same model as ingest (same vector space)

         ↓

Step 2: RETRIEVE
  FAISS.search(query_vector, top_k=4)
  → computes inner product (= cosine similarity) vs all stored vectors
  → returns top-4 by score
  → looks up text/source for each position
  → produces: [SearchResult(chunk, score), ...]

         ↓

Step 3: BUILD CONTEXT
  RAGPipeline._build_context(results)
  → formats chunks as numbered passages:
      [1] (source: faiss_index_types.md)
      HNSW builds a multi-layer graph...

      [2] (source: faiss_index_types.md)
      IVF partitions the vector space...
  → produces: a single string for the LLM

         ↓

Step 4: GENERATE + CITE
  Anthropic Claude (claude-opus-4-8 by default)
  → receives: system prompt + context passages + question
  → system prompt enforces: cite with [1][2][3], reply INSUFFICIENT_CONTEXT
    if context is not enough
  → produces: answer string with inline citations

         ↓

Step 5: EXTRACT CITATIONS
  RAGPipeline._extract_citations(answer, results)
  → finds [1], [2], [3] markers in the answer text
  → maps each marker back to the chunk's source filename and score
  → produces: list of Citation objects

         ↓

RESPONSE
  QueryResponse {
    answer: "Use HNSW when accuracy matters and data fits in RAM [1].
             Use IVF-PQ for billion-scale, memory-constrained setups [2].",
    citations: [
      {marker: 1, source: "faiss_index_types.md", score: 0.891, snippet: "..."},
      {marker: 2, source: "faiss_index_types.md", score: 0.874, snippet: "..."}
    ],
    model: "claude-opus-4-8",
    grounded: true,
    latency_ms: 843.2
  }
```

## The guardrail

If Claude returns `INSUFFICIENT_CONTEXT` anywhere in the answer:
- `grounded = false`
- `citations = []`
- The raw `INSUFFICIENT_CONTEXT` string is returned as the answer

This is a soft guardrail: it relies on Claude following the system prompt.
Phase 5 (LangGraph agent) adds a harder structural guardrail.

→ Next: **[real-query-example.md](real-query-example.md)**
