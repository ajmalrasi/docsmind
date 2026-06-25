# FAISS Code Walkthrough — Phase 1

**TL;DR:** The `FaissVectorStore` class wraps FAISS and keeps a parallel list
of chunks. FAISS handles the math; the class handles the mapping back to
human-readable text.

## The full class, annotated

```python
# docsmind/index/faiss_store.py

class FaissVectorStore(VectorStore):

    def __init__(self, dim: int, index_type: str = "flat") -> None:
        self.dim = dim                          # 384 for bge-small
        self._index_type = index_type
        self._index = faiss.IndexFlatIP(dim)   # the FAISS index (math layer)
        self._chunks: list[Chunk] = []         # parallel list (text layer)

    def add(self, chunks: list[Chunk], embeddings: np.ndarray) -> None:
        # embeddings shape: (N, 384)  N = number of chunks
        self._index.add(                       # give vectors to FAISS
            np.ascontiguousarray(embeddings, dtype=np.float32)
        )
        self._chunks.extend(chunks)            # remember the chunks in order
        # Now: self._chunks[i] ↔ FAISS position i  (always in sync)

    def search(self, query_embedding: np.ndarray, top_k: int) -> list[SearchResult]:
        if self.size == 0:
            return []                           # can't search an empty index

        query = query_embedding.reshape(1, -1)  # FAISS expects shape (1, 384)
        scores, indices = self._index.search(   # the actual search
            query, min(top_k, self.size)        # can't ask for more than we have
        )

        results = []
        for score, idx in zip(scores[0], indices[0]):
            if idx < 0:                         # FAISS pads with -1 if < top_k results
                continue
            results.append(
                SearchResult(chunk=self._chunks[idx], score=float(score))
            )
        return results

    def save(self, path: Path) -> None:
        path.mkdir(parents=True, exist_ok=True)
        faiss.write_index(self._index, str(path / "index.faiss"))  # binary file
        meta = {
            "dim": self.dim,
            "index_type": self._index_type,
            "chunks": [c.model_dump() for c in self._chunks],      # JSON
        }
        (path / "meta.json").write_text(json.dumps(meta))

    @classmethod
    def load(cls, path: Path) -> "FaissVectorStore":
        meta = json.loads((path / "meta.json").read_text())
        store = cls(dim=meta["dim"], index_type=meta["index_type"])
        store._index = faiss.read_index(str(path / "index.faiss"))
        store._chunks = [Chunk(**c) for c in meta["chunks"]]
        return store

    @property
    def size(self) -> int:
        return int(self._index.ntotal)          # how many vectors are stored
```

## The key design: pluggable interface

`FaissVectorStore` implements the abstract `VectorStore` base class
([base.py](../../docsmind/index/base.py)):

```python
class VectorStore(ABC):
    @abstractmethod
    def add(self, chunks, embeddings): ...
    @abstractmethod
    def search(self, query_embedding, top_k): ...
    @abstractmethod
    def save(self, path): ...
```

Phase 2's Qdrant backend will implement the same interface. The `Retriever`
class doesn't know or care whether it's talking to FAISS or Qdrant — it just
calls `.search()`. That's the abstraction working.

## What's stored where

```
data/index/
  ├── index.faiss    ← Binary. Contains the 50 float32 vectors (FAISS format).
  │                     ~75 KB for 50 chunks × 384 dims × 4 bytes
  └── meta.json      ← JSON. Contains dim, index_type, and the full
                        list of Chunk objects (id, text, source, metadata).
```

When the FastAPI server starts, `build_pipeline()` calls `FaissVectorStore.load()`
which reads both files and reconstructs the in-memory index. Queries then run
entirely in memory — no disk I/O per query.

→ Back to: **[README.md](README.md)**
→ Next topic: **[06-generation/README.md](../06-generation/README.md)**
