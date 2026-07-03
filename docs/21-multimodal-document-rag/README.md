# Enterprise RAG over PDFs, tables, scans, and charts (system design, roadmap)

**Where in the pipeline:** almost entirely the **Ingest** stage — before
chunking even starts. DocsMind's whole pipeline downstream of ingestion
(chunk → embed → index → retrieve → generate) is content-agnostic; it doesn't
care whether text arrived from a `.md` file or a scanned PDF, as long as
ingestion produced clean text. The entire system-design question below is
"what has to happen before `load_documents()` can hand clean text to the rest
of the pipeline you've already built."

```
today:   .md/.txt/.rst/.py files → SimpleDirectoryReader → plain text → chunk...

needed:  PDF w/ tables → layout-aware parser → table → markdown/text
         PDF w/ scans  → OCR                 → text
         PDF w/ charts → vision model        → text description
                                    ↓ (all converge here)
                              same chunk → embed → index → ... pipeline
```

## Why this is an ingest-stage problem, not a new architecture

The interviewer's question sounds like it wants a totally different system.
It doesn't. Once any of these document types has been converted into clean
text (or text-with-structure-preserved, for tables), everything DocsMind
already has — chunking, hybrid retrieval, rerank, citation, the
`INSUFFICIENT_CONTEXT` guardrail — applies unchanged. The actual design work
is entirely about **getting from "a scanned PDF" to "text"** without losing
the information that made the document useful in the first place.

`load_documents()` in [`loaders.py`](../../docsmind/ingestion/loaders.py)
today does exactly one thing: `SimpleDirectoryReader` over a fixed
`SUPPORTED_EXTS = [".md", ".txt", ".rst", ".py"]` — plain text files where
"read the bytes as text" *is* the whole extraction problem. None of the
document types in this question fit that model.

## Four content types, four different extraction problems

**Tables.** Naive text extraction turns a table into a wall of numbers with
lost row/column structure — a chunk containing raw scraped table text is
close to useless for retrieval or the LLM to reason over. A layout-aware
parser (e.g. `unstructured`, Azure Document Intelligence, LlamaIndex's own
table-aware loaders) needs to reconstruct the table as structured data first,
then serialize it to markdown or a text form that preserves which number
belongs to which row/column header before it ever reaches the chunker.

**Scanned documents.** No text layer exists at all — it's an image of a page.
**OCR** (Tesseract, or a cloud OCR API) is a mandatory first step, and OCR
quality directly caps everything downstream: a misread character becomes a
wrong fact retrieval will confidently serve up, with no way for later pipeline
stages to know it was ever wrong. Garbage in at this stage is invisible
garbage everywhere after it.

**Charts and images.** There's no "text" to extract — a chart's information
*is* its visual encoding of data. This needs a **vision-capable model** to
generate a text *description* of the chart's content (trend, key values, axis
labels) before it can enter a text-based retrieval index at all. This is
lossy by nature — a description is not the chart — which is a real
limitation to name explicitly rather than gloss over.

**Regular digital-text PDFs** (the easy case, worth naming so you don't
overbuild for it) — these already have a text layer; a standard PDF text
extractor is enough, no OCR or vision model needed. Detecting *which* case
you're in (text layer present vs scanned image vs table-heavy) is itself a
necessary routing step before picking an extraction strategy.

## The design, stage by stage

1. **Classify** each incoming document/page: has a text layer? contains
   table-like regions? contains images/charts? (Simple heuristics or a
   layout model can do this cheaply before committing to expensive OCR/vision
   calls on pages that don't need them.)
2. **Route** to the matching extractor per the four cases above — this is
   the new logic that would replace `SimpleDirectoryReader`'s single-path
   assumption in `loaders.py`.
3. **Normalize** all four outputs into the same shape (`Document` objects
   LlamaIndex already expects) so the *existing* chunker, embedder, and index
   never need to know which extraction path produced the text.
4. **Everything from chunking onward is unchanged** — this is the payoff of
   DocsMind's `VectorStore`/`LLMClient` abstraction pattern applied one layer
   earlier: isolate the messy, format-specific part behind a clean interface,
   keep the rest of the system oblivious to it.

## Trade-offs and failure modes (the interview meat)

- **OCR errors are silent and compound.** A wrong digit in a scanned
  financial table becomes a confidently-cited wrong fact three stages later
  — there's no guardrail downstream that can detect "this text was probably
  misread," so accuracy has to be won at the OCR stage itself (or flagged
  with a confidence score carried alongside the text for later filtering).
- **Chart-to-text is inherently lossy** — be upfront about this rather than
  implying vision models "solve" charts. A generated description captures
  what the model noticed, not the full information in the image; retrieval
  over that description inherits its gaps.
- **Cost and latency stack per extraction type.** OCR and vision-model calls
  are expensive relative to reading a `.md` file — a real system needs the
  classify-then-route step precisely to avoid running OCR/vision on the
  (common) documents that don't need it.
- **Scalability and security both live at ingestion too.** At real enterprise
  scale, this becomes a queue-based pipeline (documents arrive continuously,
  extraction is parallelized across workers) rather than a batch script over
  `data_dir`. And if documents carry per-user or per-department access
  restrictions, that permission metadata has to be attached at ingestion time
  and enforced at retrieval — see the RBAC section in
  [`18-llm-security`](../18-llm-security/README.md); by the time a chunk is in
  the index, it's too late to decide who's allowed to see it.
- **How you'd validate this actually works:** a small labeled eval set of
  documents-with-known-answers spanning all four types (a table lookup, a
  scanned-doc fact, a chart-reading question, a plain-text question) — the
  same Hit@1/MRR discipline as `09-hybrid-retrieval`'s eval, just with a
  corpus deliberately including the hard cases instead of only clean text.

## The interview signals

- **Why isn't this a new retrieval architecture?** Because retrieval,
  fusion, rerank, and generation are all format-agnostic once ingestion
  produces clean text — the entire hard problem is upstream, at extraction,
  not in the parts of the pipeline that already generalize.
- **What's the single biggest risk in this design?** Silent extraction
  errors (bad OCR, a misread table cell) that look like normal, confidently
  retrievable text to every downstream stage — there's no guardrail that can
  catch "this fact came from a misread source" after the fact.
- **How do you avoid running expensive extraction (OCR/vision) on every
  document?** A cheap classification/routing step first — detect which of
  the four cases a document is before committing to its (expensive)
  extraction path.
