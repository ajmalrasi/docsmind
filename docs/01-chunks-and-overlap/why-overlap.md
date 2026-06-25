# Why Overlap?

**TL;DR:** Overlap repeats the last few words of one chunk at the start of the
next, so an idea that sits right on a boundary doesn't get cut in half.

## The boundary problem

Say your document has this passage:

```
...IVF requires a training step on a representative sample
before vectors can be added.

## HNSW
HNSW builds a multi-layer graph and navigates it greedily...
```

Without overlap, the splitter might end Chunk 1 right at *"...before vectors can
be added."* and start Chunk 2 at *"## HNSW"*.

Now someone asks: *"Does IVF need a training step before you can add vectors?"*

The answer is in the last sentence of Chunk 1. But Chunk 1's embedding covers the
whole IVF section — it's not specifically sharp on that one sentence. Chunk 2
doesn't contain it at all. The retriever might miss it.

## How overlap fixes it

With `chunk_overlap=64`, Chunk 2 **starts** by repeating the last 64 tokens of
Chunk 1:

```
Chunk 1: [...IVF explanation... before vectors can be added.]
                                          ↑
                          Last 64 tokens repeated ↓
Chunk 2: [...before vectors can be added. HNSW builds a multi-layer graph...]
```

Now the boundary idea — that IVF needs a training step — lives **fully inside
Chunk 2** as well. If someone asks about it, at least one chunk will carry the
complete context.

## Visual

```
Chunk 1:  [=============================== 512 tokens ===============================]
Chunk 2:                       [== 64 overlap ==][========== 512 tokens ============]
Chunk 3:                                                  [== 64 overlap ==][========
```

## The cost

The overlapped text is stored **twice** (end of Chunk 1, start of Chunk 2).
This means:
- Slightly more vectors in FAISS (a few extra chunks)
- Occasionally the same content retrieved twice in results

Neither is a problem at the scale of Phase 1 (50 chunks). At massive scale you'd
want deduplication in post-processing.

## Phase 1 settings

```python
chunk_size=512    # ~380 words per chunk
chunk_overlap=64  # ~48 words repeated → 12.5% overlap
```

12.5% is a typical value. If you're getting boundary misses, increase it. If
you're seeing too much duplication in results, decrease it — or add a
deduplication step after retrieval.

→ Next: **[real-examples.md](real-examples.md)**
