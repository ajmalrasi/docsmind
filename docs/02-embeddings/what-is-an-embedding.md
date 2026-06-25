# What Is an Embedding?

**TL;DR:** An embedding is a list of 384 numbers that represents the *meaning*
of a piece of text. Produced by a neural network trained to put similar
meanings close together in that 384-dimensional space.

## The transformation

```
Text:      "The event horizon is the boundary of a black hole"
              ↓  (bge-small-en-v1.5 model)
Embedding: [0.12, -0.45, 0.78, 0.32, -0.21, 0.05, ..., 0.18]
            └─────────────────────────────────────────────────┘
                           384 numbers total
```

That list of 384 numbers is called a **vector**. The text and the vector
represent the same thing — one is for humans to read, the other is for
the computer to do math on.

## What do the 384 numbers mean?

Each position is a learned feature — some hidden pattern the model discovered
during training on millions of text pairs. You don't get to name them. Together,
the 384 numbers place the text at one specific *point* in a 384-dimensional
space.

A rough intuition (positions don't actually mean this, but it helps):

```
Position 0: "Is this about astronomy?"     → 0.12 (somewhat yes)
Position 1: "Is this about motion/speed?"  → -0.45 (not particularly)
Position 2: "Is this about gravity?"       → 0.78 (strongly yes)
Position 3: "Is this about light?"         → 0.32 (a bit)
...
Position 383: (some other learned pattern) → 0.18
```

## Why 384 dimensions?

`bge-small-en-v1.5` was designed with 384 dimensions — small enough to be fast
and light on memory, large enough to capture the nuance needed for English
technical text. Larger models (bge-large = 1024 dims, OpenAI = 3072 dims) have
more capacity but cost more to compute and store. 384 is a practical sweet spot
for this use case.

## The same model for everything

At ingest time:  chunk text → embedding (stored in FAISS)
At query time:   question   → embedding (used to search FAISS)

Both must use the **exact same model**. If you used different models, the
vectors would live in different spaces and comparing them would be meaningless —
like comparing GPS coordinates in two different coordinate systems.

→ Next: **[similar-text-similar-vectors.md](similar-text-similar-vectors.md)**
