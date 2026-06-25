# DocsMind — Learning Path

Everything you need to understand Phase 1 of DocsMind, in the order it was
taught. Read **top to bottom the first time**. Come back to any file as a
reference anytime.

```
documents → chunk → embed → normalize → store in FAISS
                                              ↓
question  → embed ──────────────────→ search FAISS → top-k chunks → Claude → answer + citations
```

## Topics (in order)

| # | Folder | What you learn |
|---|--------|----------------|
| 1 | [01-chunks-and-overlap/](01-chunks-and-overlap/) | Why we split documents, what a chunk is, what overlap does |
| 2 | [02-embeddings/](02-embeddings/) | How text becomes numbers that capture meaning |
| 3 | [03-normalization/](03-normalization/) | The vector math that makes search fair and fast |
| 4 | [04-vector-similarity/](04-vector-similarity/) | How we measure "closeness" between two vectors |
| 5 | [05-faiss/](05-faiss/) | The engine that stores vectors and finds the closest ones |
| 6 | [06-generation/](06-generation/) | Building context, prompting Claude, citations, guardrail |
| 7 | [07-full-pipeline/](07-full-pipeline/) | Every piece wired together, a real query end to end |
| 8 | [08-interview-prep/](08-interview-prep/) | Every "why X over Y" question an interviewer will ask |

## How to use this

- **First time:** follow the numbers, 1 → 7.
- **Stuck on a concept:** each folder has a `README.md` that links to every file inside.
- **Interview prep:** go straight to `08-interview-prep/` — it has crisp answers for every tradeoff question.
- **See the real code:** every file links to the actual source file it's explaining.

→ Start here: **[01-chunks-and-overlap/README.md](01-chunks-and-overlap/README.md)**
