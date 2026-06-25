# Building the Context

**TL;DR:** The 4 chunks from FAISS are formatted into numbered passages
`[1]`, `[2]`, `[3]`, `[4]`. These numbers are what make citations possible —
the model cites by number, and the pipeline maps each number back to a file.

## The raw FAISS output

After FAISS search, the pipeline has (real values for *"How do black holes
form?"*):

```python
results = [
    SearchResult(chunk=Chunk(text="A black hole is a region of spacetime where gravity...",
                             source="black_holes.md"), score=0.8141),
    SearchResult(chunk=Chunk(text="A star much more massive than the Sun... supernova...",
                             source="stellar_lifecycle.md"), score=0.6333),
    SearchResult(chunk=Chunk(text="The Sun is a main-sequence star that fuses hydrogen...",
                             source="solar_system.md"), score=0.5691),
    SearchResult(chunk=Chunk(text="To leave Earth's gravity, a spacecraft must reach escape velocity...",
                             source="rocket_propulsion.md"), score=0.5240),
]
```

Just a list of chunks with scores. The LLM can't use this directly.

## Building the numbered context string

```python
# docsmind/pipeline.py

@staticmethod
def _build_context(results: list[SearchResult]) -> str:
    blocks = []
    for i, result in enumerate(results, start=1):
        blocks.append(
            f"[{i}] (source: {result.chunk.source})\n{result.chunk.text}"
        )
    return "\n\n".join(blocks)
```

Output:

```
[1] (source: black_holes.md)
A black hole is a region of spacetime where gravity is so strong that nothing —
not even light — can escape. Stellar-mass black holes form when a massive star,
typically more than about 20 times the mass of the Sun, collapses in a supernova...

[2] (source: stellar_lifecycle.md)
A star much more massive than the Sun burns through its fuel quickly and becomes
a red supergiant. When its core can no longer support itself, it collapses and
rebounds in a supernova; the most massive cores collapse into a black hole...

[3] (source: solar_system.md)
The Sun is a main-sequence star that fuses hydrogen into helium in its core,
the gravitational anchor of the entire system...

[4] (source: rocket_propulsion.md)
To leave Earth's gravity entirely, a spacecraft must reach escape velocity,
about 11.2 kilometers per second...
```

## Then the full prompt to the LLM

```python
prompt = f"Context passages:\n\n{context}\n\nQuestion: {question}\n\nAnswer:"
```

Which produces:

```
Context passages:

[1] (source: black_holes.md)
A black hole is a region of spacetime where gravity...

[2] (source: stellar_lifecycle.md)
A star much more massive than the Sun... supernova...

[3] (source: solar_system.md)
The Sun is a main-sequence star...

[4] (source: rocket_propulsion.md)
To leave Earth's gravity... escape velocity...

Question: How do black holes form?

Answer:
```

## Why number them?

The model is told in the system prompt to cite with `[n]`. When it writes
*"Stellar-mass black holes form from collapsing massive stars [1][2]"*, the
pipeline later extracts `[1]` and `[2]` and maps them back to `results[0]` and
`results[1]` — each with the source filename, similarity score, and a text
snippet. That's what becomes the `Citation` object returned to the user.

Without the numbers, the model would still answer — but you'd have no way
to trace which claim came from which file.

→ Next: **[system-prompt.md](system-prompt.md)**
