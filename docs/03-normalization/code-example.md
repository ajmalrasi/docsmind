# Normalization in Code

**TL;DR:** Phase 1 normalizes in one line during encoding. FAISS is then set
up to use inner product, which equals cosine similarity on normalized vectors.

## Where it happens

```python
# docsmind/index/embeddings.py

def encode(self, texts: list[str]) -> np.ndarray:
    vectors = self._model.encode(
        texts,
        normalize_embeddings=True,   # ← L2 normalization applied here
        convert_to_numpy=True,
        show_progress_bar=False,
    )
    return np.asarray(vectors, dtype=np.float32)
```

`normalize_embeddings=True` is a flag from the `sentence-transformers` library.
It runs the L2 normalization automatically after the model produces raw vectors.

## And in FAISS

```python
# docsmind/index/faiss_store.py

import faiss

# IP = Inner Product (dot product)
# Works as cosine similarity because vectors are normalized
index = faiss.IndexFlatIP(dim)
```

If normalization was skipped, you'd use `IndexFlatL2` (Euclidean distance)
instead — but you'd lose the directional meaning comparison. `IndexFlatIP` on
normalized vectors is the standard pattern for semantic search.

## Verify it yourself

```python
import numpy as np
from sentence_transformers import SentenceTransformer

model = SentenceTransformer("BAAI/bge-small-en-v1.5")
embeddings = model.encode(["A black hole traps light at its event horizon"], normalize_embeddings=True)

length = np.linalg.norm(embeddings[0])
print(f"Length: {length:.6f}")
# → Length: 1.000000  ✓
```

→ Back to: **[README.md](README.md)**
→ Next topic: **[04-vector-similarity/README.md](../04-vector-similarity/README.md)**
