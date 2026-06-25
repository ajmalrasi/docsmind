# Citation Extraction

**TL;DR:** After Claude responds, the pipeline scans the answer text for
`[n]` markers using a regex, maps each number to the corresponding retrieved
chunk, and builds a list of `Citation` objects that get returned alongside
the answer.

## The code

```python
# docsmind/pipeline.py

_MARKER_RE = re.compile(r"\[(\d+)\]")   # matches [1], [2], [12], etc.

@staticmethod
def _extract_citations(answer: str, results: list[SearchResult]) -> list[Citation]:
    # Find all [n] markers in the answer text
    cited_markers = {int(m) for m in _MARKER_RE.findall(answer)}

    # Only keep valid markers — ones that map to an actual retrieved chunk
    cited_markers = {m for m in cited_markers if 1 <= m <= len(results)}

    citations = []
    for marker in sorted(cited_markers):
        result = results[marker - 1]   # [1] → results[0], [2] → results[1], etc.
        snippet = result.chunk.text[:240].strip()
        citations.append(
            Citation(
                marker=marker,
                source=result.chunk.source,
                score=round(result.score, 4),
                snippet=snippet,
            )
        )
    return citations
```

## Step-by-step example

The model returned (real output for *"How do black holes form?"*):

```
"Black holes form when matter is compressed... exceeds the speed of light [1].
Stellar-mass black holes form from collapsing massive stars [1][2], and
supermassive black holes form at the centers of galaxies [1][3]."
```

**Step 1 — Find all markers:**
```python
_MARKER_RE.findall(answer)
# → ['1', '1', '2', '1', '3']

cited_markers = {int(m) for m in ...}
# → {1, 2, 3}   (set removes duplicates)
```

**Step 2 — Validate (only keep markers that map to real chunks):**
```python
# We have 4 chunks (results[0..3]), so valid = {1, 2, 3, 4}
# {1, 2, 3} are all valid — keep them all
# If the model hallucinated [7], it would be filtered out here
cited_markers = {1, 2, 3}
```

**Step 3 — Build Citation objects:**
```python
Citation(marker=1, source="black_holes.md", score=0.8141,
         snippet="A black hole is a region of spacetime where gravity is so strong...")

Citation(marker=2, source="stellar_lifecycle.md", score=0.6333,
         snippet="A star much more massive than the Sun... collapses in a supernova...")

Citation(marker=3, source="solar_system.md", score=0.5691,
         snippet="The Sun is a main-sequence star that fuses hydrogen into helium...")
```

Notice: `[4]` (the rocket passage) is not in the citations because the model
didn't use it. FAISS retrieved 4 chunks but the model only needed 3. That's normal.

## The Citation schema

```python
# docsmind/schemas.py

class Citation(BaseModel):
    marker: int      # the [n] number as it appears in the answer
    source: str      # filename the chunk came from
    score: float     # cosine similarity score from FAISS
    snippet: str     # first 240 chars of the chunk text
```

This is what gets returned to the user in the API response. A UI would
display these as clickable footnotes — click `[1]` and see the source file
and the exact text passage that supported the claim.

## What the validation step protects against

The model might occasionally hallucinate a citation marker — writing `[7]` when
only 4 passages were provided. The bounds check
`if 1 <= m <= len(results)` silently drops invalid markers rather than
crashing or returning a bogus citation. It's a small but important guard.

→ Next: **[guardrail.md](guardrail.md)**
