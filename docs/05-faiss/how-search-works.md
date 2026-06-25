# How FAISS Search Works — Step by Step

**TL;DR:** You hand FAISS a query vector and k. It returns the k most similar
vectors (by inner product) and their positions. You use positions to look up
the actual chunk text.

## The full search flow

```
1. RAGPipeline.query("How do black holes form?")
       ↓
2. Retriever.retrieve(question, top_k=4)
       ↓
3. Embedder.encode(["How do black holes form?"]) → query_vec (384 floats)
       ↓
4. FaissVectorStore.search(query_vec, top_k=4)
       ↓
5. faiss.IndexFlatIP.search(query_vec.reshape(1,-1), k=4)
       → scores  = [[0.8141, 0.6333, 0.5691, 0.5240]]
       → indices = [[0,      4,      1,      2     ]]
       ↓
6. Look up self._chunks[0], self._chunks[4], self._chunks[1], self._chunks[2]
       ↓
7. Return [SearchResult(chunk=..., score=0.8141), ...]
```

## FAISS only knows positions

FAISS stores vectors, not text. When it returns `indices = [12, 3, 8, 15]`,
those are positions in the flat array. The `FaissVectorStore` class maintains
a parallel list `self._chunks` that maps position → chunk object:

```python
# docsmind/index/faiss_store.py

def add(self, chunks: list[Chunk], embeddings: np.ndarray) -> None:
    self._index.add(embeddings)   # FAISS stores vectors
    self._chunks.extend(chunks)   # we store chunks, in the same order

def search(self, query_embedding, top_k):
    scores, indices = self._index.search(query, top_k)
    return [
        SearchResult(chunk=self._chunks[idx], score=float(score))
        for score, idx in zip(scores[0], indices[0])
        if idx >= 0  # FAISS pads with -1 if fewer than top_k results exist
    ]
```

The `idx >= 0` guard handles the edge case where the index has fewer than
`top_k` vectors — FAISS pads missing results with index `-1`.

## Persistence

After building the index, it's saved to disk so it doesn't need to be
rebuilt on every server restart:

```python
def save(self, path):
    faiss.write_index(self._index, str(path / "index.faiss"))  # binary
    json.dump({"chunks": [...], "dim": 384, ...}, open(path / "meta.json"))

@classmethod
def load(cls, path):
    store = cls.__new__(cls)
    store._index = faiss.read_index(str(path / "index.faiss"))
    meta = json.load(open(path / "meta.json"))
    store._chunks = [Chunk(**c) for c in meta["chunks"]]
    return store
```

`make ingest` writes the index. `make serve` loads it. The loaded index is
kept in memory for the lifetime of the FastAPI process.

→ Next: **[phase1-vs-phase2.md](phase1-vs-phase2.md)**
