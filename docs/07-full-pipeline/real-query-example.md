# Real Query Example — End to End

**TL;DR:** One question traced through every single step, with the *actual*
values measured from the running system (space corpus, local model).

## The question

```
"How do black holes form?"
```

---

## 1. Embed the question

```python
embedder.encode(["How do black holes form?"])
# Output (first 8 of 384 values, normalized):
# [0.038, -0.021, 0.071, -0.044, 0.083, -0.015, 0.062, 0.039, ...]
# length: 1.0 ✓
```

---

## 2. FAISS search

FAISS compares the question vector to all 5 chunk vectors.
Top-4 by inner product (= cosine similarity), real measured scores:

```
Score   Source
0.8141  black_holes.md        ← direct hit
0.6333  stellar_lifecycle.md  ← genuinely related (massive stars → black holes)
0.5691  solar_system.md       ← same domain, off-topic
0.5240  rocket_propulsion.md  ← same domain, off-topic
0.5140  the_iss.md            ← 5th place, not in top-4
```

---

## 3. Build context

```
[1] (source: black_holes.md)
A black hole is a region of spacetime where gravity is so strong that nothing —
not even light — can escape once it crosses the boundary. Stellar-mass black
holes form when a massive star, typically more than about 20 times the mass of
the Sun, exhausts its fuel and collapses in a supernova. Supermassive black
holes, millions to billions of times the mass of the Sun, sit at the centers of
most galaxies.

[2] (source: stellar_lifecycle.md)
A star much more massive than the Sun burns through its fuel quickly and becomes
a red supergiant. When its core can no longer support itself, it collapses and
rebounds in a supernova; the most massive cores collapse completely into a
black hole.

[3] (source: solar_system.md)
The Sun is a main-sequence star that fuses hydrogen into helium in its core,
the gravitational anchor of the entire system.

[4] (source: rocket_propulsion.md)
To leave Earth's gravity entirely, a spacecraft must reach escape velocity,
about 11.2 kilometers per second.
```

---

## 4. Send to the LLM

**System prompt:**
```
You are DocsMind, a question-answering assistant for technical and ML
documentation. Answer ONLY from the numbered context passages provided.
Cite every claim with its passage number in square brackets, e.g. [1] or
[2][3]. Do not use outside knowledge. If the context does not contain enough
information to answer, reply with exactly: INSUFFICIENT_CONTEXT
```

**User message:** the 4 context passages above + the question.

---

## 5. The LLM's response (real output, local model)

```
Black holes form when matter is compressed into a small enough volume that its
escape velocity exceeds the speed of light [1]. This occurs in two main ways:
stellar-mass black holes form from the collapse of massive stars, typically more
than about 20 times the mass of the Sun, following a supernova event [1][2], and
supermassive black holes are believed to form at the centers of galaxies,
including our Milky Way, with masses ranging in the millions to billions of times
that of the Sun [1][3].
```

The model synthesized passages [1], [2], and [3] into one grounded answer.
It ignored [4] (the rocket passage) — irrelevant to formation.

---

## 6. Extract citations

Parse `[1]`, `[2]`, `[3]` from the answer text:

```python
cited_markers = {1, 2, 3}  # found in the answer

citations = [
    Citation(marker=1, source="black_holes.md", score=0.8141,
             snippet="A black hole is a region of spacetime where gravity..."),
    Citation(marker=2, source="stellar_lifecycle.md", score=0.6333,
             snippet="A star much more massive than the Sun... supernova..."),
    Citation(marker=3, source="solar_system.md", score=0.5691,
             snippet="The Sun is a main-sequence star that fuses hydrogen..."),
]
```

---

## 7. Final response (JSON from API)

```json
{
  "answer": "Black holes form when matter is compressed into a small enough volume...",
  "citations": [
    {"marker": 1, "source": "black_holes.md", "score": 0.8141, "snippet": "..."},
    {"marker": 2, "source": "stellar_lifecycle.md", "score": 0.6333, "snippet": "..."},
    {"marker": 3, "source": "solar_system.md", "score": 0.5691, "snippet": "..."}
  ],
  "model": "deepseek-coder-v2:16b-lite-instruct-q4_K_M",
  "grounded": true,
  "latency_ms": 14637.0
}
```

Every claim in the answer is traceable to a specific file, a specific chunk,
and a specific similarity score. That's what "grounded RAG" means.

→ Next: **[phase1-end-to-end.md](phase1-end-to-end.md)**
