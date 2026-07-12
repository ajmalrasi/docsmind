# 21 — Multimodal Document RAG: PDFs, Tables, Scans, Charts (system design, roadmap)

**The big idea:** the interviewer's question *sounds* like it wants a
totally different architecture. It doesn't. Everything downstream of
ingestion (chunk → embed → index → retrieve → generate) is
content-agnostic. The entire hard problem is upstream: getting from "a
scanned PDF" to "clean text" without losing the information that made the
document useful.

**Where in the pipeline:** almost entirely the **Ingest** stage — before
chunking even starts.

```
today:   .md/.txt/.rst/.py files → SimpleDirectoryReader → plain text → chunk...

needed:  PDF w/ tables → layout-aware parser → table → markdown/text
         PDF w/ scans  → OCR                 → text
         PDF w/ charts → vision model        → text description
                                    ↓ (all converge here)
                              same chunk → embed → index → ... pipeline
```

## Files in this folder

| File | What it covers |
|------|----------------|
| [four-content-types.md](four-content-types.md) | Tables, scans, charts, digital text — four different extraction problems |
| [classify-route-normalize.md](classify-route-normalize.md) | The design: classify → route → normalize, plus failure modes and validation |

## 🎯 Interview Q&A

**Q: Why isn't this a new retrieval architecture?**
Retrieval, fusion, rerank, and generation are all format-agnostic once
ingestion produces clean text. The entire hard problem is upstream, at
extraction.

**Q: What's the single biggest risk in this design?**
Silent extraction errors — bad OCR, a misread table cell — that look like
normal, confidently retrievable text to every downstream stage. Nothing
after ingestion can catch "this fact came from a misread source."

**Q: How do you avoid running expensive extraction (OCR/vision) on every
document?**
A cheap classification/routing step first. Detect which of the four cases
a document is, then commit to its (expensive) extraction path only if
needed.

**Q: How would you validate the whole design?**
A small labeled eval set spanning all four types — a table lookup, a
scanned-doc fact, a chart-reading question, a plain-text question — scored
with the same Hit@1/MRR discipline as the retrieval eval.

## Code

[docsmind/ingestion/loaders.py](../../docsmind/ingestion/loaders.py) —
`load_documents()`, whose single-path `SimpleDirectoryReader` +
`SUPPORTED_EXTS` assumption is exactly what this design replaces.

→ Next: **[22-langgraph/README.md](../22-langgraph/README.md)**
