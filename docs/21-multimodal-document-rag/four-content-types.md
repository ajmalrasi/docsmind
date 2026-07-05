# Four Content Types, Four Different Extraction Problems

**TL;DR:** tables lose their structure to naive extraction, scans have no
text at all, charts encode information visually, and plain digital PDFs are
the easy case you shouldn't overbuild for. Each needs a different extractor
— and knowing which is which *before* extracting is the design's core move.

## Where DocsMind stands today

`load_documents()` in
[`loaders.py`](../../docsmind/ingestion/loaders.py) does one thing:
`SimpleDirectoryReader` over `SUPPORTED_EXTS = [".md", ".txt", ".rst", ".py"]`.
For those files, "read the bytes as text" *is* the whole extraction
problem. None of the document types below fit that model.

## Tables

Naive text extraction turns a table into a wall of numbers.
Row/column structure is gone — which number belonged to which header is
lost. A chunk of raw scraped table text is close to useless, for retrieval
and for the LLM.

```
the table:                       naive extraction:
│ Planet │ Mass  │ Moons │       "Planet Mass Moons Mars 0.64 2
│ Mars   │ 0.64  │ 2     │        Jupiter 1898 95"
│ Jupiter│ 1898  │ 95    │        ← which number goes with what? gone.
```

The fix: a layout-aware parser (`unstructured`, Azure Document
Intelligence, LlamaIndex's table-aware loaders) reconstructs the table as
structured data first. Then serialize it to markdown — a text form that
keeps each number attached to its row and column — before it reaches the
chunker.

## Scanned documents

No text layer exists. It's a photo of a page.
**OCR** (optical character recognition — Tesseract, or a cloud OCR API) is
the mandatory first step.

And OCR quality caps everything downstream. A misread character becomes a
wrong fact that retrieval will confidently serve up. No later stage can
tell it was ever wrong. Garbage in at this stage is invisible garbage
everywhere after it.

## Charts and images

There's no text to extract at all — a chart's information *is* its visual
encoding. This needs a **vision-capable model** to write a text
*description* of the chart (trend, key values, axis labels) before it can
enter a text-based index.

This is lossy by nature. A description is not the chart. Name that
limitation explicitly instead of glossing over it — retrieval over the
description inherits whatever the vision model didn't notice.

## Regular digital-text PDFs

The easy case — worth naming so you don't overbuild for it.
These already have a text layer; a standard PDF text extractor is enough.
No OCR, no vision model. Which raises the real routing question: detecting
*which* case each document is, before picking an extraction strategy.

## Side by side

| Content type | What's missing | Extractor | Cost | Chief risk |
|---|---|---|---|---|
| Tables | structure, not text | layout-aware parser → markdown | moderate | structure silently flattened |
| Scans | text entirely | OCR | high | silent misreads compound |
| Charts | text entirely; info is visual | vision model → description | highest | inherently lossy |
| Digital PDFs | nothing | standard text extractor | cheap | overpaying by routing it to OCR |

→ Next: **[classify-route-normalize.md](classify-route-normalize.md)**
