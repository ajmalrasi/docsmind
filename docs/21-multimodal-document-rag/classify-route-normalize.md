# The Design — Classify, Route, Normalize

**TL;DR:** classify each document cheaply, route it to the right extractor,
normalize everything into the same `Document` shape — and the rest of the
pipeline never learns which path the text took. It's DocsMind's abstraction
pattern applied one layer earlier.

## The design, stage by stage

1. **Classify** each incoming document or page.
   Has a text layer? Table-like regions? Images or charts?
   Cheap heuristics or a layout model can answer this before committing to
   expensive OCR/vision calls.
2. **Route** to the matching extractor, per the four cases in
   [four-content-types.md](four-content-types.md).
   This is the new logic that replaces `SimpleDirectoryReader`'s
   single-path assumption in
   [`loaders.py`](../../docsmind/ingestion/loaders.py).
3. **Normalize** all four outputs into the same shape — the `Document`
   objects LlamaIndex already expects. The existing chunker, embedder, and
   index never learn which extraction path produced the text.
4. **Everything from chunking onward is unchanged.**

```
            incoming document
                  │
             [ classify ]        ← cheap: text layer? tables? images?
        ┌────┬────┴────┬─────┐
   digital  table    scan   chart
     text  parser    OCR    vision
        └────┴────┬────┴─────┘
             [ normalize ]       ← all become LlamaIndex Document objects
                  │
        chunk → embed → index → ...   (existing pipeline, untouched)
```

This is DocsMind's `VectorStore`/`LLMClient` abstraction pattern, applied
one layer earlier: isolate the messy, format-specific part behind a clean
interface, keep the rest of the system oblivious.

## Failure modes worth naming unprompted

- **OCR errors are silent and compound.** A wrong digit in a scanned
  financial table becomes a confidently-cited wrong fact three stages
  later. No downstream guardrail can detect "this text was probably
  misread." Accuracy has to be won at the OCR stage itself — or flagged
  with a confidence score carried alongside the text, for filtering later.
- **Chart-to-text is inherently lossy.** A generated description captures
  what the model noticed, not the full information in the image. Retrieval
  over that description inherits its gaps. Be upfront about this rather
  than implying vision models "solve" charts.
- **Cost and latency stack per extraction type.** OCR and vision-model
  calls are expensive next to reading a `.md` file. The classify-then-route
  step exists precisely so you don't run OCR/vision on the (common)
  documents that don't need it.

## Scale and security live at ingestion too

At enterprise scale this becomes a queue-based pipeline — documents arrive
continuously, extraction runs in parallel across workers — not a batch
script over `data_dir`.

And if documents carry per-user access restrictions, that permission
metadata must be attached at ingestion time and enforced at retrieval (see
the RBAC treatment in
[18-llm-security/code-seams.md](../18-llm-security/code-seams.md)).
By the time a chunk is in the index, it's too late to decide who may see it.

## How you'd validate this actually works

A small labeled eval set of documents-with-known-answers spanning all four
types: a table lookup, a scanned-doc fact, a chart-reading question, a
plain-text question.

Same Hit@1/MRR discipline as
[09-hybrid-retrieval's eval](../09-hybrid-retrieval/eval-results.md) — just
with a corpus that deliberately includes the hard cases. The per-type
breakdown is the diagnostic: if plain-text questions score 0.95 and
scanned-doc questions score 0.60, the OCR stage — not retrieval — is where
the next week of work goes.

→ Back to: **[the site overview](../README.md)**
