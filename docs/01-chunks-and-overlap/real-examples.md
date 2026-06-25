# Real Examples — Chunking Your Docs

**TL;DR:** Here's what the chunker actually does to
[black_holes.md](../../data/sample_docs/black_holes.md) with
`chunk_size=512, chunk_overlap=64`.

## The original document (abridged)

```
# Black Holes

A black hole is a region of spacetime where gravity is so strong that nothing —
not even light — can escape once it crosses the boundary...

## The event horizon
The event horizon is the boundary of a black hole, not a physical surface. It is
the point of no return: anything that crosses it, including light, can never get
back out...

## The singularity
At the very center lies the singularity, a point where matter is crushed to
infinite density and the known laws of physics break down...

## How black holes form
Stellar-mass black holes form when a massive star — typically more than about 20
times the mass of the Sun — exhausts its fuel and collapses under its own gravity
in a supernova...

## Accretion disks and Hawking radiation
Matter spiraling toward a black hole forms a superheated accretion disk...
```

This doc is short (~300 words), so the splitter produces **1 chunk**. A longer
document would produce several. To show the boundary behavior, imagine it were
long enough to split into 2 — the example below shows where overlap appears.

---

## Chunk 1

```
Chunk {
    id:     "node_001",
    source: "black_holes.md",
    text:   "# Black Holes

             A black hole is a region of spacetime where gravity is so strong
             that nothing — not even light — can escape once it crosses the
             boundary.

             ## The event horizon
             The event horizon is the boundary of a black hole, not a physical
             surface. It is the point of no return: anything that crosses it,
             including light, can never get back out...

             ## The singularity
             At the very center lies the singularity, a point where matter is
             crushed to infinite density and the known laws of physics break
             down."
}
```

*This chunk ends at the singularity section.*

---

## Chunk 2 (with overlap)

```
Chunk {
    id:     "node_002",
    source: "black_holes.md",
    text:   "At the very center lies the singularity, a point where matter is   ← overlap!
             crushed to infinite density and the known laws of physics break
             down.

             ## How black holes form
             Stellar-mass black holes form when a massive star — typically more
             than about 20 times the mass of the Sun — exhausts its fuel and
             collapses under its own gravity in a supernova...

             ## Accretion disks and Hawking radiation
             Matter spiraling toward a black hole forms a superheated accretion
             disk that emits intense X-rays before crossing the horizon."
}
```

*The first sentence of Chunk 2 is the last sentence of Chunk 1 — that's the overlap.*

---

## What happens at query time

Question: *"What is at the center of a black hole?"*

1. The question gets embedded → a vector
2. FAISS compares it to all chunk vectors
3. **A chunk containing the singularity description** scores high
4. The model reads it and answers: *"The singularity, a point of infinite
   density [1]"*
5. `[1]` maps back to `source: black_holes.md` → citation shown to user

The `source` field is the thread that ties the answer back to the exact file.

→ Back to: **[README.md](README.md)**
→ Next topic: **[02-embeddings/README.md](../02-embeddings/README.md)**
