# Volkswagen Wikipedia embedding evaluation

## Where this fits

This evaluation measures the **Embed → Search → BM25 → RRF** part of the query
pipeline:

```text
Question -> matching query embedder -> matching OpenSearch index -> dense rank
                                                     + BM25 rank -> RRF
```

It does not call the generator LLM and does not measure answer faithfulness.
The question is narrower: did retrieval return a chunk from an appropriate
Wikipedia article?

## Controlled comparison

The evaluation holds these variables constant:

- Volkswagen Wikipedia v1 snapshot
- 57 articles and 1,776 chunks
- Chunk size 512 and overlap 64
- AWS OpenSearch Serverless backend
- 20 source-labeled questions
- Rank depth five
- Hybrid candidate and RRF settings

It changes only the embedding model and its matching index:

| Label | Query embedder | Persisted index | Dimension |
|---|---|---|---:|
| Baseline | `BAAI/bge-small-en-v1.5` on Beast CPU | `docsmind-volkswagen-wikipedia-v1` | 384 |
| Candidate | `BAAI/bge-m3` through CPU TEI | `docsmind-volkswagen-wikipedia-bge-m3-v1` | 1,024 |

The indexes cannot be mixed. Each query must use the model that created its
index's document vectors.

## Labels and metrics

The versioned set at
`data/eval/volkswagen_wikipedia_queries.v1.json` contains 20 author-curated
questions. Each question lists one or more Wikipedia article titles considered
valid sources.

Metrics:

- **Hit@1:** a relevant article is the first result.
- **Hit@3:** a relevant article appears in the first three results.
- **MRR:** rewards the first relevant result more when it appears higher.
- **Latency:** end-to-end retriever time observed from Beast, including query
  embedding, the private tunnel for BGE-M3, and OpenSearch search.

These are source-level labels. They have not yet received an independent human
review, and 20 questions are enough for a development decision—not a universal
model ranking.

## Results

Measured on 2026-08-06:

| Model | Retrieval | Hit@1 | Hit@3 | MRR | Mean latency | p50 | p95 |
|---|---|---:|---:|---:|---:|---:|---:|
| bge-small | Dense | **0.75** | 0.85 | **0.824** | 852.68 ms | 818.78 ms | 1,151.77 ms |
| bge-small | Hybrid | 0.75 | 0.90 | 0.848 | 862.82 ms | 817.42 ms | 1,164.56 ms |
| BGE-M3 | Dense | 0.70 | **0.90** | 0.814 | 2,673.47 ms | 2,640.65 ms | 3,386.59 ms |
| BGE-M3 | Hybrid | **0.80** | **0.95** | **0.871** | 4,069.03 ms | 3,979.51 ms | 4,726.35 ms |

Bold values compare models within the same retrieval mode. The full per-query
rank details are preserved in `wikipedia-embedding-eval.json`.

## What the result says

### Dense versus dense

BGE-M3 is not automatically better merely because it is larger and
multilingual:

- bge-small had better Hit@1: 0.75 versus 0.70.
- BGE-M3 had better Hit@3: 0.90 versus 0.85.
- bge-small had slightly better MRR: 0.824 versus 0.814.

The candidate appears to retrieve relevant material into the candidate set but
does not place it first as consistently in dense-only mode.

### Hybrid versus hybrid

BGE-M3 plus BM25/RRF produced the best quality in this experiment:

- Hit@1 improved from 0.75 to 0.80.
- Hit@3 improved from 0.90 to 0.95.
- MRR improved from 0.848 to 0.871.

This matches the system design: dense embeddings capture meaning, BM25 recovers
exact automotive names and identifiers, and RRF combines ranks without mixing
incompatible raw scores.

### Latency trade-off

The CPU BGE-M3 path is substantially slower:

- Dense p50 was about 3.2 times the bge-small dense p50.
- Hybrid p50 was about 4.9 times the bge-small hybrid p50.

The numbers include a development-only multi-hop tunnel and remote CPU model
serving. They should not be generalized to a colocated GPU deployment. They do
show that the current CPU topology is too slow to adopt purely on a modest
quality gain without further optimization.

## Per-query weaknesses

Queries where the first relevant source was not rank one:

| Configuration | Query IDs |
|---|---|
| bge-small dense | `ppe_developers`, `emissions_defeat_device`, `traton_business`, `ducati_parent`, `ea827_family` |
| bge-small hybrid | `ppe_developers`, `emissions_defeat_device`, `traton_business`, `phaeton_positioning`, `ea827_family` |
| BGE-M3 dense | `mqb_layout`, `emissions_defeat_device`, `golf_mk7_platform`, `traton_business`, `ducati_parent`, `ea827_family` |
| BGE-M3 hybrid | `emissions_defeat_device`, `traton_business`, `phaeton_positioning`, `ea827_family` |

The recurring failures are more useful than the aggregate score alone. They
identify labels to review and questions that may need better corpus coverage,
chunk context, metadata-aware retrieval, or reranking.

## Decision

For this development corpus:

- Keep BGE-M3 as the production candidate for the **hybrid** path.
- Do not claim that BGE-M3 dense retrieval universally beats bge-small.
- Keep the old index until a larger, independently reviewed evaluation confirms
  the gain.
- Run the same BGE-M3 index/query workload on GPU and compare latency and cost.
- Evaluate the existing cross-encoder reranker after the CPU/GPU serving choice,
  using the same labels.

In an interview, the defensible statement is:

> I compared two embedding models on the same 1,776-chunk corpus and 20 labeled
> questions. BGE-M3 dense alone did not beat the smaller baseline at rank one,
> but BGE-M3 with BM25/RRF achieved the best Hit@1, Hit@3, and MRR. The CPU
> service was several times slower, so the next gate is the same evaluation on
> GPU—not adopting the larger model based on reputation.
