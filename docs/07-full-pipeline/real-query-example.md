# Real Query Example — End to End

**TL;DR:** One question traced through every single step, with actual values
at each stage.

## The question

```
"When should I use HNSW over IVF-PQ?"
```

---

## 1. Embed the question

```python
embedder.encode(["When should I use HNSW over IVF-PQ?"])
# Output (first 8 of 384 values, normalized):
# [0.038, -0.021, 0.071, -0.044, 0.083, -0.015, 0.062, 0.039, ...]
# length: 1.0 ✓
```

---

## 2. FAISS search

FAISS compares the question vector to all 50 chunk vectors.
Top-4 by inner product (= cosine similarity):

```
Score   Position   Source
0.891   pos 12     faiss_index_types.md   ← HNSW section
0.874   pos 3      faiss_index_types.md   ← IVF section
0.856   pos 8      faiss_index_types.md   ← HNSW memory note
0.841   pos 15     faiss_index_types.md   ← "Choosing an index" section
0.312   pos 22     kubernetes_gpu.md      ← not returned (below top-4)
0.198   pos 31     vllm_serving.md        ← not returned
```

---

## 3. Build context

```
[1] (source: faiss_index_types.md)
HNSW builds a multi-layer graph and navigates it greedily. It typically
delivers the best recall-vs-latency tradeoff for in-memory search. The key
parameters are `M` (graph connectivity) and `efSearch` (search breadth —
higher means better recall and higher latency).

[2] (source: faiss_index_types.md)
IVF partitions the vector space into `nlist` cells using k-means and, at
query time, only searches the `nprobe` cells nearest to the query. Increasing
`nprobe` raises recall at the cost of latency. IVF requires a training step
on a representative sample before vectors can be added.

[3] (source: faiss_index_types.md)
HNSW uses more memory than IVF because it stores graph edges in addition
to the vectors.

[4] (source: faiss_index_types.md)
Choosing an index: Large corpus, accuracy-sensitive, fits in RAM: HNSW.
Very large corpus, memory-constrained: IVF-PQ.
```

---

## 4. Send to Claude

**System prompt:**
```
You are DocsMind, a question-answering assistant for technical and ML
documentation. Answer ONLY from the numbered context passages provided.
Cite every claim with its passage number in square brackets, e.g. [1] or
[2][3]. Do not use outside knowledge. If the context does not contain enough
information to answer, reply with exactly: INSUFFICIENT_CONTEXT
```

**User message:**
```
Context passages:

[1] (source: faiss_index_types.md)
HNSW builds a multi-layer graph...

[2] (source: faiss_index_types.md)
IVF partitions the vector space...

[3] (source: faiss_index_types.md)
HNSW uses more memory than IVF...

[4] (source: faiss_index_types.md)
Choosing an index: Large corpus...

Question: When should I use HNSW over IVF-PQ?

Answer:
```

---

## 5. Claude's response

```
Use HNSW when your corpus fits in RAM and you prioritize recall and low
query latency [1][4]. HNSW typically delivers the best recall-vs-latency
tradeoff for in-memory search [1], though it uses more memory than IVF
because it stores graph edges [3].

Use IVF-PQ when your corpus is very large and memory is constrained [4].
IVF partitions the vector space and only searches the nearest cells at
query time [2], and when combined with Product Quantization (IVF-PQ), it
dramatically reduces memory at the cost of some recall.
```

---

## 6. Extract citations

Parse `[1]`, `[2]`, `[3]`, `[4]` from the answer text:

```python
cited_markers = {1, 2, 3, 4}  # found in the answer

citations = [
    Citation(marker=1, source="faiss_index_types.md", score=0.891,
             snippet="HNSW builds a multi-layer graph and navigates..."),
    Citation(marker=2, source="faiss_index_types.md", score=0.874,
             snippet="IVF partitions the vector space into `nlist` cells..."),
    Citation(marker=3, source="faiss_index_types.md", score=0.856,
             snippet="HNSW uses more memory than IVF because it stores..."),
    Citation(marker=4, source="faiss_index_types.md", score=0.841,
             snippet="Large corpus, accuracy-sensitive, fits in RAM: HNSW..."),
]
```

---

## 7. Final response (JSON from API)

```json
{
  "answer": "Use HNSW when your corpus fits in RAM and you prioritize recall...",
  "citations": [
    {"marker": 1, "source": "faiss_index_types.md", "score": 0.891, "snippet": "..."},
    {"marker": 2, "source": "faiss_index_types.md", "score": 0.874, "snippet": "..."},
    {"marker": 3, "source": "faiss_index_types.md", "score": 0.856, "snippet": "..."},
    {"marker": 4, "source": "faiss_index_types.md", "score": 0.841, "snippet": "..."}
  ],
  "model": "claude-opus-4-8",
  "grounded": true,
  "latency_ms": 843.2
}
```

Every claim in the answer is traceable to a specific file, a specific chunk,
and a specific similarity score. That's what "grounded RAG" means.

→ Next: **[phase1-end-to-end.md](phase1-end-to-end.md)**
