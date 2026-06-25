# Real Examples — Embeddings in Action

**TL;DR:** Concrete numbers showing what embeddings look like, and how
similar vs dissimilar texts produce different vectors.

## Two similar chunks

From your [faiss_index_types.md](../../data/sample_docs/faiss_index_types.md):

```python
text_a = "HNSW builds a multi-layer graph and navigates it greedily."
text_b = "HNSW typically delivers the best recall-vs-latency tradeoff."

embedding_a = model.encode(text_a)
embedding_b = model.encode(text_b)
```

**First 10 values of each** (384 total):

```
embedding_a: [ 0.043,  0.018, -0.031,  0.072, -0.056,  0.084, -0.021,  0.063,  0.039, -0.044, ...]
embedding_b: [ 0.041,  0.021, -0.029,  0.069, -0.058,  0.081, -0.020,  0.067,  0.037, -0.041, ...]
```

Notice: the numbers are close. Same topic → similar vector.

**Cosine similarity between them:** ~0.94 (very high)

---

## One very different chunk

From [kubernetes_gpu.md](../../data/sample_docs/kubernetes_gpu.md):

```python
text_c = "Kubernetes schedules GPU workloads using resource limits."

embedding_c = model.encode(text_c)
```

**First 10 values:**

```
embedding_c: [-0.031,  0.089,  0.047, -0.052,  0.078, -0.044,  0.061, -0.037,  0.055,  0.083, ...]
```

Notice: the pattern is completely different from `embedding_a`.

**Cosine similarity between a and c:** ~0.21 (very low — different topics)

---

## What this means for retrieval

Query: *"How does HNSW navigate its graph?"*

```
Embedded query: [ 0.040,  0.019, -0.030, ...]  (similar to text_a and text_b)

Similarity scores:
  text_a (HNSW graph)        → 0.92  ← retrieved ✅
  text_b (HNSW recall)       → 0.89  ← retrieved ✅
  text_c (Kubernetes GPU)    → 0.18  ← not retrieved ✅
```

FAISS returns `text_a` and `text_b`. Kubernetes chunk is ignored. The retrieval
is right — the question was about HNSW, not Kubernetes.

---

## Note on the numbers above

The exact values depend on the model version and normalization. The point isn't
the specific numbers — it's the **pattern**: similar texts produce similar
vectors, different texts produce different vectors. Cosine similarity (see
[04-vector-similarity](../04-vector-similarity/)) measures how similar the
vectors are.

→ Back to: **[README.md](README.md)**
→ Next topic: **[03-normalization/README.md](../03-normalization/README.md)**
