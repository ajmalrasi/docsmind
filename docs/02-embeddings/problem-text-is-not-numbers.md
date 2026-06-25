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

The simplest approach: does the word "black hole" appear in this document?

```
Question: "What stops light from escaping a black hole?"
Document: "Nothing can escape a black hole's gravity..."  → match ✅
Document: "Beyond the event horizon, not even light gets out..."  → no match ❌
```

The second document is *about* exactly this, but doesn't use the words "black
hole" or "escape." Keyword search misses it entirely. This is the fundamental
limit of exact-match approaches like BM25.

## What we need instead

We need a way to represent meaning so that:

```
"What stops light from escaping a black hole?"
         ≈
"Beyond the event horizon, not even light gets out..."
```

...are recognized as related, even though they share almost no words.

The solution is **embeddings** — turning each piece of text into a list of
numbers that represents its meaning in a way that similar meanings get similar
numbers.

→ Next: **[what-is-an-embedding.md](what-is-an-embedding.md)**
