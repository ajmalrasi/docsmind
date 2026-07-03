# Enterprise RAG over PDFs, tables, scans, and charts (system design, roadmap)

**Where in the pipeline:** almost entirely the **Ingest** stage — before chunking even starts.
Everything downstream of ingestion (chunk → embed → index → retrieve → generate) is content-agnostic.
It doesn't care whether text came from a `.md` file or a scanned PDF, as long as ingestion produced clean text.
So the whole system-design question below reduces to:
"what has to happen before `load_documents()` can hand clean text to the pipeline you've already built."

```
today:   .md/.txt/.rst/.py files → SimpleDirectoryReader → plain text → chunk...

needed:  PDF w/ tables → layout-aware parser → table → markdown/text
         PDF w/ scans  → OCR                 → text
         PDF w/ charts → vision model        → text description
                                    ↓ (all converge here)
                              same chunk → embed → index → ... pipeline
```

## Why this is an ingest-stage problem, not a new architecture

The interviewer's question *sounds* like it wants a totally different system.
It doesn't.

Once any of these document types is converted into clean text — or text with structure preserved, for tables — everything DocsMind already has applies unchanged: chunking, hybrid retrieval, rerank, citation, the `INSUFFICIENT_CONTEXT` guardrail.
The actual design work is getting from "a scanned PDF" to "text" without losing the information that made the document useful.

Look at where DocsMind stands today.
`load_documents()` in [`loaders.py`](../../docsmind/ingestion/loaders.py) does one thing: `SimpleDirectoryReader` over `SUPPORTED_EXTS = [".md", ".txt", ".rst", ".py"]`.
For those files, "read the bytes as text" *is* the whole extraction problem.
None of the document types in this question fit that model.

## Four content types, four different extraction problems

**Tables.**
Naive text extraction turns a table into a wall of numbers.
Row/column structure is gone — which number belonged to which header is lost.
A chunk of raw scraped table text is close to useless, for retrieval and for the LLM.
The fix: a layout-aware parser (`unstructured`, Azure Document Intelligence, LlamaIndex's table-aware loaders) reconstructs the table as structured data first.
Then serialize it to markdown — a text form that keeps each number attached to its row and column — before it reaches the chunker.

**Scanned documents.**
No text layer exists. It's a photo of a page.
**OCR** (optical character recognition — Tesseract, or a cloud OCR API) is the mandatory first step.
And OCR quality caps everything downstream.
A misread character becomes a wrong fact that retrieval will confidently serve up.
No later stage can tell it was ever wrong.
Garbage in at this stage is invisible garbage everywhere after it.

**Charts and images.**
There's no text to extract at all — a chart's information *is* its visual encoding.
This needs a **vision-capable model** to write a text *description* of the chart (trend, key values, axis labels) before it can enter a text-based index.
This is lossy by nature. A description is not the chart.
Name that limitation explicitly instead of glossing over it.

**Regular digital-text PDFs.**
The easy case — worth naming so you don't overbuild for it.
These already have a text layer; a standard PDF text extractor is enough. No OCR, no vision model.
Which raises the real routing question: detecting *which* case each document is, before picking an extraction strategy.

## The design, stage by stage

1. **Classify** each incoming document or page.
   Has a text layer? Table-like regions? Images or charts?
   Cheap heuristics or a layout model can answer this before committing to expensive OCR/vision calls.
2. **Route** to the matching extractor, per the four cases above.
   This is the new logic that replaces `SimpleDirectoryReader`'s single-path assumption in `loaders.py`.
3. **Normalize** all four outputs into the same shape — the `Document` objects LlamaIndex already expects.
   The existing chunker, embedder, and index never learn which extraction path produced the text.
4. **Everything from chunking onward is unchanged.**
   This is DocsMind's `VectorStore`/`LLMClient` abstraction pattern, applied one layer earlier:
   isolate the messy, format-specific part behind a clean interface, keep the rest of the system oblivious.

## Trade-offs and failure modes (the interview meat)

- **OCR errors are silent and compound.**
  A wrong digit in a scanned financial table becomes a confidently-cited wrong fact three stages later.
  No downstream guardrail can detect "this text was probably misread."
  Accuracy has to be won at the OCR stage itself — or flagged with a confidence score carried alongside the text, for filtering later.
- **Chart-to-text is inherently lossy.**
  A generated description captures what the model noticed, not the full information in the image.
  Retrieval over that description inherits its gaps.
  Be upfront about this rather than implying vision models "solve" charts.
- **Cost and latency stack per extraction type.**
  OCR and vision-model calls are expensive next to reading a `.md` file.
  The classify-then-route step exists precisely so you don't run OCR/vision on the (common) documents that don't need it.
- **Scalability and security both live at ingestion too.**
  At enterprise scale this becomes a queue-based pipeline — documents arrive continuously, extraction runs in parallel across workers — not a batch script over `data_dir`.
  And if documents carry per-user access restrictions, that permission metadata must be attached at ingestion time and enforced at retrieval (see the RBAC section in [`18-llm-security`](../18-llm-security/README.md)).
  By the time a chunk is in the index, it's too late to decide who may see it.
- **How you'd validate this actually works.**
  A small labeled eval set of documents-with-known-answers spanning all four types: a table lookup, a scanned-doc fact, a chart-reading question, a plain-text question.
  Same Hit@1/MRR discipline as `09-hybrid-retrieval`'s eval — just with a corpus that deliberately includes the hard cases.

## The interview signals

- **Why isn't this a new retrieval architecture?**
  Retrieval, fusion, rerank, and generation are all format-agnostic once ingestion produces clean text.
  The entire hard problem is upstream, at extraction.
- **What's the single biggest risk in this design?**
  Silent extraction errors — bad OCR, a misread table cell — that look like normal, confidently retrievable text to every downstream stage.
  Nothing after ingestion can catch "this fact came from a misread source."
- **How do you avoid running expensive extraction (OCR/vision) on every document?**
  A cheap classification/routing step first.
  Detect which of the four cases a document is, then commit to its (expensive) extraction path only if needed.
