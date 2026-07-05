# The Problem and the Fix — Searching With the Wrong Shape of Text

**TL;DR:** we currently embed the *question* and hunt for nearby chunks. But
the index is full of *answer-shaped* text. HyDE bridges the gap by embedding a
fake answer instead — right shape, right vocabulary, right neighborhood.

## The problem it solves

At query time we embed the **question** and search for nearby chunks.
But questions and answers are *different kinds of text*.

"Why do astronauts float?" is short, interrogative, and contains none of the
vocabulary of the passage that answers it (microgravity, free fall, orbital
velocity). The question's vector sits in a slightly wrong neighborhood —
we're searching for a thing shaped like a question in an index full of things
shaped like answers.

```
embedding space (simplified):

   [question region]                [answer region]
   "Why do astronauts float?"       "Objects in orbit are in continuous
        ●  ← we search from here     free fall. In microgravity..."
                                          ● ● ●  ← the chunks live here
```

The gap is small — dense retrieval still mostly works, which is why Phase 1
shipped without HyDE. But on short, vague questions the gap is exactly what
pushes the right chunk from rank 1 to rank 3.

## The fix

**HyDE — Hypothetical Document Embeddings.** Ask an LLM to *write a fake
answer first*, embed **that**, and search with it.

The fake answer may be factually wrong — doesn't matter. It's the right *kind*
of text: declarative, answer-shaped, full of the domain vocabulary that real
answer chunks also use. Its vector lands in the answer neighborhood, and
nearest-neighbor search does the rest. The retrieved chunks are real; the fake
answer is thrown away before generation.

Plain version: instead of describing a suspect to the sketch artist, you draw
the sketch yourself — badly — and match it against the photo database. A bad
sketch of the right face beats a perfect description in the wrong medium.

## Why "wrong but useful" is the whole trick

| | Factually right? | Right vocabulary/shape? | Lands near real answers? |
|---|---|---|---|
| The question itself | n/a | ❌ interrogative, sparse vocab | approximately |
| LLM's fake answer | often not | ✅ declarative, domain terms | ✅ that's all retrieval needs |

Retrieval never fact-checks the query vector. It only measures angles
(see [04-vector-similarity](../04-vector-similarity/README.md)). A confidently
wrong paragraph about microgravity still *sounds like* the true chunk — and
sounding alike is what cosine similarity measures.

→ Next: **[code-seam-and-tradeoffs.md](code-seam-and-tradeoffs.md)**
