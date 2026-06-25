# Similarity Scores — How to Read Them

**TL;DR:** Cosine similarity returns a number between -1.0 and 1.0.
For normalized text embeddings you'll typically see 0.0 to 1.0 in practice.

## Score ranges

| Score | Meaning | Example |
|-------|---------|---------|
| 0.95 – 1.0 | Nearly identical | Same sentence paraphrased |
| 0.80 – 0.95 | Highly similar | Same topic, different detail |
| 0.60 – 0.80 | Related | Same domain, different aspect |
| 0.30 – 0.60 | Loosely related | Overlapping keywords, different meaning |
| 0.0 – 0.30 | Different | Unrelated topics |

These ranges are rough guides — they shift based on the model and corpus.
bge-small on English technical docs tends to have most relevant hits above 0.70.

## What Phase 1 actually returns

```python
# docsmind/schemas.py
class SearchResult(BaseModel):
    chunk: Chunk
    score: float   # cosine similarity, 0.0 to 1.0
```

Example output from a query *"When should I use HNSW over IVF?"*:

```
Results:
  score=0.891  source=faiss_index_types.md  "HNSW typically delivers the best recall-vs-latency..."
  score=0.874  source=faiss_index_types.md  "IVF partitions the vector space into nlist cells..."
  score=0.856  source=faiss_index_types.md  "HNSW uses more memory than IVF because it stores graph edges..."
  score=0.841  source=faiss_index_types.md  "Choosing an index: Large corpus, accuracy-sensitive: HNSW..."
  score=0.312  source=kubernetes_gpu.md     "Kubernetes schedules GPU workloads..."  ← not retrieved
  score=0.198  source=vllm_serving.md       "vLLM manages KV-cache to serve..."      ← not retrieved
```

The top-4 are all from the FAISS doc — exactly right. Kubernetes and vLLM
chunks are far below and not retrieved.

## We rank, we don't threshold

Phase 1 returns the **top-k by score**, not everything above a threshold.
This means even the best available chunk is returned, even if the corpus
doesn't contain a great answer — that's why the `INSUFFICIENT_CONTEXT`
guardrail (in the LLM prompt) is important. Claude can still flag if the
retrieved context isn't good enough to answer.

→ Next: **[search-example.md](search-example.md)**
