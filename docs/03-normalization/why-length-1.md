# Why Same Length (1.0) Makes Comparison Fair

**TL;DR:** Without normalization, a longer chunk could have a bigger raw
vector and appear similar to everything — not because of meaning, but
because of size. Normalization removes this bias so only *meaning* (direction)
is compared.

## The problem without normalization

Imagine two chunks about black holes:

```
Chunk A (short, 20 words):   "A black hole traps light at its event horizon."
Chunk B (long, 200 words):   "A black hole traps light at its event horizon. It
                              is the point of no return; anything crossing it,
                              including light, can never get back out..."

Raw embedding_A: [0.5,  0.3,  0.8]   → length = √(0.25 + 0.09 + 0.64) = 0.99
Raw embedding_B: [1.2,  0.7,  1.9]   → length = √(1.44 + 0.49 + 3.61) = 2.35
```

Both chunks are *about* event horizons — same meaning, same direction. But Chunk
B's vector is **2.4× longer** just because it's a longer piece of text.

Now if a query comes in and we measure Euclidean distance:

```
Distance(query, Chunk A) = large  (raw vector is small)
Distance(query, Chunk B) = even larger (raw vector is big)
```

The ranking is polluted by chunk length, not meaning. Not what we want.

## After normalization

```
Normalized embedding_A: [0.505, 0.303, 0.808]  → length = 1.0
Normalized embedding_B: [0.510, 0.298, 0.809]  → length = 1.0
```

Both are now the same length. The only remaining difference is *direction* —
which is the angle between them, which is the meaning difference.

```
Cosine similarity(A, B) = 0.999  ← near-identical meaning, correctly detected
```

## The direction = meaning intuition

Think of each vector as an **arrow** in 384-dimensional space.

```
Before normalization:
  →    Chunk A (short arrow, same direction)
  ────────→  Chunk B (long arrow, same direction)

After normalization:
  →  Chunk A (length 1.0)
  →  Chunk B (length 1.0)  ← now identical
```

Both arrows point the same direction — same meaning. The only difference was
scale, which we removed. Now their similarity score is 0.999, correctly
reflecting that they're both about event horizons.

## The FAISS bonus

`IndexFlatIP` computes the **inner product** (dot product) of two vectors:

```
inner_product(A, B) = A₁×B₁ + A₂×B₂ + ... + Aₙ×Bₙ
```

When both vectors are normalized (length = 1.0), the inner product equals
the cosine similarity exactly. So:

- Normalize → use IndexFlatIP → get cosine similarity
- No special "cosine index" needed, inner product is enough
- Inner product is highly optimized in FAISS (SIMD, GPU) → fast

→ Next: **[code-example.md](code-example.md)**
