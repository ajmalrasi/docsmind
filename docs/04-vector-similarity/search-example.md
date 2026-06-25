# Search Example — Question to Top-k

**TL;DR:** A full walkthrough of one query through the retrieval layer —
from raw question text to ranked chunks with scores.

## Setup

We have 5 space documents, each one chunk, all stored in FAISS.

**Question:** *"How do black holes form?"*

---

## Step 1: Embed the question

```python
# docsmind/retrieval/retriever.py

query_vec = self._embedder.encode(["How do black holes form?"])[0]
# query_vec shape: (384,)
# query_vec is normalized (length = 1.0)
```

The same `bge-small-en-v1.5` model that encoded the chunks encodes the question.
Same model → same vector space → comparable vectors.

---

## Step 2: FAISS searches all vectors

```python
# docsmind/index/faiss_store.py

scores, indices = self._index.search(query_vec.reshape(1, -1), top_k=4)
```

FAISS computes the inner product (= cosine similarity) between the question
vector and all stored chunk vectors. Returns the 4 highest scores with their
positions (indices) in the stored array.

```
Internal FAISS result (real measured values):
  indices = [0, 4, 1, 2]                  # positions in the stored array
  scores  = [0.8141, 0.6333, 0.5691, 0.5240]
```

---

## Step 3: Look up the chunks at those positions

```python
for score, idx in zip(scores[0], indices[0]):
    chunk = self._chunks[idx]
    results.append(SearchResult(chunk=chunk, score=float(score)))
```

```
SearchResult #1  score=0.8141
  source: black_holes.md
  text: "A black hole is a region of spacetime where gravity is so strong that
         nothing — not even light — can escape... Stellar-mass black holes form
         when a massive star collapses in a supernova..."

SearchResult #2  score=0.6333
  source: stellar_lifecycle.md
  text: "A star much more massive than the Sun... collapses and rebounds in a
         supernova. The most massive cores collapse completely into a black
         hole..."

SearchResult #3  score=0.5691
  source: solar_system.md
  text: "The Sun is a main-sequence star that fuses hydrogen into helium...
         the gravitational anchor of the entire system..."

SearchResult #4  score=0.5240
  source: rocket_propulsion.md
  text: "To leave Earth's gravity entirely, a spacecraft must reach escape
         velocity, about 11.2 kilometers per second..."
```

Notice the pattern: `black_holes.md` is the strong hit (0.81), `stellar_lifecycle.md`
is genuinely related (0.63 — massive stars collapse into black holes), and the
last two are space-domain but off-topic, retrieved only because they're the
next-highest scores.

---

## Step 4: Hand off to the pipeline

These 4 chunks (with their sources and scores) go to `RAGPipeline.query()`,
which:
1. Formats them as numbered context passages `[1]`, `[2]`, `[3]`, `[4]`
2. Sends them + the question to the LLM
3. The LLM answers using only relevant passages and cites by number
4. The pipeline extracts citations and maps `[n]` back to `source` filenames

(In the real run, the model cited `[1]`, `[2]`, and `[3]` and ignored `[4]`.)

---

## The speed

For a handful of chunks: FAISS finishes in < 1 millisecond.
For 1 million chunks with a Flat index: ~100ms (linear scan).
For 1 million chunks with HNSW: ~1ms (approximate, graph traversal).

That's why Phase 2 adds approximate indexes — they matter at scale.

→ Back to: **[README.md](README.md)**
→ Next topic: **[05-faiss/README.md](../05-faiss/README.md)**
