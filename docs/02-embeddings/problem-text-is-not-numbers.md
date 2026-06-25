# The Problem: Text Is Not Numbers

**TL;DR:** Computers do math, not language. To search by meaning, we need to
turn text into numbers first.

## What computers can do with numbers

Given two numbers, a computer can tell you:
- Which is bigger
- How far apart they are
- How similar they are

Given two sentences in English, a computer can't do any of that without
first converting them.

## Keyword search — the old way

The simplest approach: does the word "HNSW" appear in this document?

```
Question: "When should I use HNSW?"
Document: "HNSW builds a multi-layer graph..."  → match ✅
Document: "Graph-based indexes navigate greedily..."  → no match ❌
```

The second document is *about* HNSW but doesn't use the word. Keyword search
misses it entirely. This is the fundamental limit of exact-match approaches
like BM25.

## What we need instead

We need a way to represent meaning so that:

```
"When should I use HNSW?"
         ≈
"Graph-based indexes navigate greedily..."
```

...are recognized as related, even though they share no words.

The solution is **embeddings** — turning each piece of text into a list of
numbers that represents its meaning in a way that similar meanings get similar
numbers.

→ Next: **[what-is-an-embedding.md](what-is-an-embedding.md)**
