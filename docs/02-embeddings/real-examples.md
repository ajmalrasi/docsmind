# Real Examples — Embeddings in Action

**TL;DR:** Concrete numbers showing what embeddings look like, and how
similar vs dissimilar texts produce different vectors.

## Two similar chunks

From [black_holes.md](../../data/sample_docs/black_holes.md):

```python
text_a = "The event horizon is the boundary of a black hole; nothing escapes it."
text_b = "Once light crosses the horizon of a black hole, it can never get back out."

embedding_a = model.encode(text_a)
embedding_b = model.encode(text_b)
```

**First 10 values of each** (384 total):

```
embedding_a: [ 0.043,  0.018, -0.031,  0.072, -0.056,  0.084, -0.021,  0.063,  0.039, -0.044, ...]
embedding_b: [ 0.041,  0.021, -0.029,  0.069, -0.058,  0.081, -0.020,  0.067,  0.037, -0.041, ...]
```

Notice: the numbers are close. Same topic → similar vector.

**Cosine similarity between them:** ~0.90 (very high)

---

## One very different chunk

From [the_iss.md](../../data/sample_docs/the_iss.md):

```python
text_c = "The ISS orbits Earth roughly every 90 minutes in low Earth orbit."

embedding_c = model.encode(text_c)
```

**First 10 values:**

```
embedding_c: [-0.031,  0.089,  0.047, -0.052,  0.078, -0.044,  0.061, -0.037,  0.055,  0.083, ...]
```

Notice: the pattern is completely different from `embedding_a`. Both are about
space — but one is about black-hole gravity and the other about an orbiting
station, so the meanings (and the vectors) diverge.

**Cosine similarity between a and c:** ~0.40 (low — same domain, different topic)

---

## What this means for retrieval

Query: *"What is the boundary of a black hole?"*

```
Embedded query: [ 0.040,  0.019, -0.030, ...]  (similar to text_a and text_b)

Similarity scores:
  text_a (event horizon)   → 0.91  ← retrieved ✅
  text_b (light crosses)   → 0.88  ← retrieved ✅
  text_c (ISS orbit)       → 0.38  ← ranked far below ✅
```

FAISS ranks the two black-hole chunks at the top. The ISS chunk sits far below.
The retrieval is right — the question was about black holes, not the space
station.

---

## Note on the numbers above

The exact values depend on the model version and normalization. The point isn't
the specific numbers — it's the **pattern**: similar texts produce similar
vectors, different texts produce different vectors. Cosine similarity (see
[04-vector-similarity](../04-vector-similarity/)) measures how similar the
vectors are.

→ Back to: **[README.md](README.md)**
→ Next topic: **[03-normalization/README.md](../03-normalization/README.md)**
