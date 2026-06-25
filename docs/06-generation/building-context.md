# Building the Context

**TL;DR:** The 4 chunks from FAISS are formatted into numbered passages
`[1]`, `[2]`, `[3]`, `[4]`. These numbers are what make citations possible —
Claude cites by number, and the pipeline maps each number back to a file.

## The raw FAISS output

After FAISS search, the pipeline has:

```python
results = [
    SearchResult(chunk=Chunk(text="HNSW builds a multi-layer graph...",
                             source="faiss_index_types.md"), score=0.891),
    SearchResult(chunk=Chunk(text="IVF partitions the vector space...",
                             source="faiss_index_types.md"), score=0.874),
    SearchResult(chunk=Chunk(text="HNSW uses more memory than IVF...",
                             source="faiss_index_types.md"), score=0.856),
    SearchResult(chunk=Chunk(text="Large corpus: HNSW. Memory-constrained: IVF-PQ.",
                             source="faiss_index_types.md"), score=0.841),
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
[1] (source: faiss_index_types.md)
HNSW builds a multi-layer graph and navigates it greedily. It typically
delivers the best recall-vs-latency tradeoff for in-memory search...

[2] (source: faiss_index_types.md)
IVF partitions the vector space into `nlist` cells using k-means and, at
query time, only searches the `nprobe` cells nearest to the query...

[3] (source: faiss_index_types.md)
HNSW uses more memory than IVF because it stores graph edges in addition
to the vectors...

[4] (source: faiss_index_types.md)
Large corpus, accuracy-sensitive, fits in RAM: HNSW.
Very large corpus, memory-constrained: IVF-PQ.
```

## Then the full prompt to Claude

```python
prompt = f"Context passages:\n\n{context}\n\nQuestion: {question}\n\nAnswer:"
```

Which produces:

```
Context passages:

[1] (source: faiss_index_types.md)
HNSW builds a multi-layer graph...

[2] (source: faiss_index_types.md)
IVF partitions the vector space...

[3] (source: faiss_index_types.md)
HNSW uses more memory than IVF...

[4] (source: faiss_index_types.md)
Large corpus: HNSW. Memory-constrained: IVF-PQ.

Question: When should I use HNSW over IVF-PQ?

Answer:
```

## Why number them?

Claude is told in the system prompt to cite with `[n]`. When it writes
*"Use HNSW for in-memory search [1]"*, the pipeline later extracts `[1]`
and maps it back to `results[0]` — which has the source filename, the
similarity score, and a text snippet. That's what becomes the `Citation`
object returned to the user.

Without the numbers, Claude would still answer — but you'd have no way
to trace which claim came from which file.

→ Next: **[system-prompt.md](system-prompt.md)**
