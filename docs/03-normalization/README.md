# 03 — Normalization

**The big idea:** Before storing or comparing vectors, we scale each one so
its length is exactly 1.0. This is called *L2 normalization*. It makes cosine
similarity equal to a simple dot product — which is what FAISS's
`IndexFlatIP` computes. Faster math, fairer comparison.

## Files in this folder

| File | What it covers |
|------|----------------|
| [l2-normalization-math.md](l2-normalization-math.md) | Step-by-step: [1.0, 2.0, 3.0] → [0.27, 0.53, 0.80] |
| [why-length-1.md](why-length-1.md) | Why same-length vectors make comparison fair |
| [code-example.md](code-example.md) | How Phase 1 does it in one line |

## 🎯 Interview Q&A

**Q: Why L2 normalize?**
So that vector *length* doesn't affect similarity — only *direction* (meaning)
does. Two chunks about black holes should be close whether one is 50 words and
the other is 500. After normalization, all vectors have the same length (1.0), so
the only thing left to compare is the angle between them, which represents
meaning.

**Q: Cosine similarity vs Euclidean distance — which is better for text?**
Cosine similarity is better for text. Euclidean distance is sensitive to
vector *length* (a longer doc could produce a bigger vector and appear
"farther" from a short but identical-meaning doc). Cosine only cares about
*direction* — the angle between vectors — which is what semantic similarity
actually is. For text retrieval, direction = meaning, length = irrelevant.

**Q: What's the trick with IndexFlatIP?**
When vectors are L2-normalized (all have length 1.0), the inner product (dot
product) of two vectors equals their cosine similarity. FAISS's `IndexFlatIP`
computes inner products. So: normalize first → use IndexFlatIP → you get
cosine similarity, implemented as fast inner-product math. No special cosine
index needed.

**Q: What happens if you forget to normalize?**
Retrieval becomes biased toward longer chunks (more tokens → bigger raw
embedding magnitude → appears closer to everything). You'd get inconsistent
results that vary with chunk size, not meaning.

## Code
[docsmind/index/embeddings.py](../../docsmind/index/embeddings.py) — `normalize_embeddings=True`
[docsmind/index/faiss_store.py](../../docsmind/index/faiss_store.py) — `IndexFlatIP`

→ Next: **[04-vector-similarity/README.md](../04-vector-similarity/README.md)**
