# Cosine Similarity

**TL;DR:** Cosine similarity measures the angle between two vectors. Small
angle = similar meaning = high score (close to 1.0). Large angle = different
meaning = low score (close to 0.0).

## The geometric intuition

Think of each vector as an arrow pointing in 384-dimensional space:

```
  HNSW chunk A  →
  HNSW chunk B  →   (nearly same direction, small angle between them)
  Kubernetes  ↓     (very different direction, large angle)
```

Cosine similarity measures how much two arrows point in the same direction.
It doesn't care how long the arrows are (which is why normalization removes
length — we already don't want it to matter).

## The formula

For two vectors A and B:

```
cosine_similarity(A, B) = (A · B) / (‖A‖ × ‖B‖)
```

Where:
- `A · B` = dot product = A₁×B₁ + A₂×B₂ + ... + Aₙ×Bₙ
- `‖A‖` = length of A
- `‖B‖` = length of B

## Worked example (tiny 3-dim vectors)

```
A = [0.267, 0.535, 0.802]  (normalized, length = 1.0)
B = [0.278, 0.511, 0.813]  (normalized, length = 1.0)

Dot product = (0.267×0.278) + (0.535×0.511) + (0.802×0.813)
            = 0.074 + 0.273 + 0.652
            = 0.999

cosine_similarity = 0.999 / (1.0 × 1.0) = 0.999  ← very similar
```

Because both vectors are normalized (length = 1.0), the denominator is always
1.0 × 1.0 = 1.0. So cosine similarity simplifies to just the dot product:

```
cosine_similarity(A, B) = A · B     (when both are L2 normalized)
```

This is exactly what FAISS's `IndexFlatIP` (inner product) computes.
Normalize → use IndexFlatIP → you get cosine similarity.

## Python

```python
import numpy as np

A = np.array([0.267, 0.535, 0.802])
B = np.array([0.278, 0.511, 0.813])

# Both are normalized, so dot product = cosine similarity
similarity = np.dot(A, B)
print(f"Similarity: {similarity:.3f}")  # → 0.999
```

→ Next: **[similarity-scores.md](similarity-scores.md)**
