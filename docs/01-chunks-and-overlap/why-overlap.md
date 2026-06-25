# Why Overlap?

**TL;DR:** Overlap repeats the last few words of one chunk at the start of the
next, so an idea that sits right on a boundary doesn't get cut in half.

## The boundary problem

Say a long black-hole document has this passage:

```
...Supermassive black holes, millions to billions of times the mass of the
Sun, sit at the centers of most galaxies.

## Accretion disks
Matter spiraling toward a black hole forms a superheated accretion disk...
```

Without overlap, the splitter might end Chunk 1 right at *"...centers of most
galaxies."* and start Chunk 2 at *"## Accretion disks"*.

Now someone asks: *"What is the black hole at the center of the Milky Way
called?"*

If the answer sentence ("the one at the heart of the Milky Way is called
Sagittarius A*") sits exactly on that boundary, it can get split — half in one
chunk, half in the next. Neither chunk's embedding is sharp on it, and the
retriever might miss it.

## How overlap fixes it

With `chunk_overlap=64`, Chunk 2 **starts** by repeating the last 64 tokens of
Chunk 1:

```
Chunk 1: [...supermassive black holes... centers of most galaxies.]
                                                  ↑
                                  Last 64 tokens repeated ↓
Chunk 2: [...centers of most galaxies; Sagittarius A*. Accretion disks form...]
```

Now the boundary idea lives **fully inside Chunk 2** as well. If someone asks
about it, at least one chunk carries the complete context.

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

Neither is a problem at the scale of Phase 1 (a handful of chunks). At massive
scale you'd want deduplication in post-processing.

## Phase 1 settings

```python
chunk_size=512    # ~380 words per chunk
chunk_overlap=64  # ~48 words repeated → 12.5% overlap
```

12.5% is a typical value. If you're getting boundary misses, increase it. If
you're seeing too much duplication in results, decrease it — or add a
deduplication step after retrieval.

→ Next: **[real-examples.md](real-examples.md)**
