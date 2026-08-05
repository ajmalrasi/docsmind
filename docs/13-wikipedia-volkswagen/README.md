# Volkswagen Wikipedia corpus

## Where this fits

This work happens at the first pipeline stage:

```text
Wikipedia -> Fetch snapshot -> Normalize sections -> Documents
  -> Chunk -> Embed -> Index -> Dense + BM25 -> RRF -> Generate -> Cite
```

Only the corpus adapter is new. Embeddings, vector stores, hybrid retrieval,
reranking, LLM routing, serving, and citation parsing keep their existing
interfaces.

## Corpus v1

The versioned manifest at
`data/wikipedia/volkswagen_pages.v1.json` selects Volkswagen Group material in
four groups:

- Group structure and brands
- Shared platforms such as MQB, MEB, MLB, MSB, and PPE
- Engines, transmissions, and four-wheel-drive systems
- Representative Volkswagen, Audi, Škoda, SEAT, and Cupra vehicles

The first fetched snapshot contains:

| Measurement | Result |
|---|---:|
| Unique articles | 57 |
| Heading-aware sections | 1,147 |
| Normalized text characters | 1,439,426 |
| Chunks at 512/64 | 1,776 |
| Unique citation URLs | 57 |
| Unknown citation sources | 0 |

## AWS OpenSearch deployment

The v1 snapshot was indexed on 2026-08-05 under the isolated OpenSearch
Serverless index `docsmind-volkswagen-wikipedia-v1`:

| Setting | Value |
|---|---|
| Stored chunks/vectors | 1,776 |
| Embedding model | `BAAI/bge-small-en-v1.5` |
| Vector dimension | 384 |
| Similarity | Cosine |
| OpenSearch vector engine | Faiss/HNSW selected by Serverless |
| Unique citation sources | 57 |

The existing `docsmind-chunks` index was not replaced. OpenSearch performs the
dense vector search. The default hybrid retriever then rebuilds its in-memory
BM25 index from the text payloads stored in this OpenSearch index and combines
the two rankings with RRF.

Remote hybrid smoke queries returned the expected source families:

- An ID.4 platform question returned the Volkswagen ID.4 and MEB platform
  articles.
- A 4motion/quattro relationship question returned both the quattro and
  4motion articles.

### Production embedding path

The embedding provider is a configuration seam, just like the vector store.
The free in-process `bge-small` index remains the baseline. The active AWS
development path self-hosts `BAAI/bge-m3` in Hugging Face Text Embeddings
Inference (TEI) on ECS backed by one CPU EC2 instance. BGE-M3 returns
1,024-dimensional vectors and is multilingual, which fits a Volkswagen corpus
that can later include English, German, and other European-language material.

At **Embed**, `TEIEmbedder` in `docsmind/index/embeddings.py` sends document or
query text to TEI's `/embed` endpoint. `build_embedder()` in
`docsmind/factory.py` selects it without changing chunking, OpenSearch, hybrid
retrieval, or generation:

```bash
make aws-embedding-start
make aws-embedding-tunnel  # keep this terminal open

DOCSMIND_EMBEDDING_PROVIDER=tei \
DOCSMIND_TEI_BASE_URL=http://localhost:8080 \
DOCSMIND_VECTOR_BACKEND=opensearch \
DOCSMIND_OPENSEARCH_INDEX=docsmind-volkswagen-wikipedia-bge-m3-v1 \
DOCSMIND_DATA_DIR=data/wikipedia \
DOCSMIND_INDEX_DIR=data/index-wikipedia-bge-m3-v1 \
python -m scripts.ingest
```

The deployed CPU profile accepts at most 2,048 tokens per input and eight texts
per client batch. DocsMind chunks are 512 tokens, so this does not truncate the
current corpus. BGE-M3 itself supports longer inputs; the smaller service limit
keeps development on an 8 GB `m7i.large`. See the
[deployment and measured CPU baseline](../14-aws-embedding-service/README.md).

Bedrock Titan v2 and Cohere Embed v4 clients remain implemented as alternative
providers, but neither is the active deployment. Titan on-demand calls were
throttled in this account, and Cohere Marketplace activation was blocked by the
account payment-instrument requirement. No Titan or Cohere vector index was
created. Keeping those attempts documented avoids presenting an unverified
managed path as deployed evidence.

The provider contract keeps **Embed document** and **Embed query** as distinct
operations. TEI currently sends both through the same BGE-M3 dense endpoint.
Cohere uses asymmetric `search_document` and `search_query` modes. Keeping the
split in the contract prevents a future provider switch from silently dropping
the correct instruction mode.

Changing an embedding model changes the vector space, even when two models
happen to produce the same number of dimensions. Therefore the ingestion job
writes `embedding.json` beside the vector-store marker. The query pipeline
checks provider, model, and dimension before retrieval. A mismatch fails early
instead of returning plausible-looking but meaningless nearest neighbours.

In an interview, the real question is not “did you use a larger embedding
model?” It is: “why did you select it, how did you size the service, and how did
you measure the retrieval change?” The `bge-small` and BGE-M3 indexes must be
separate so the next evaluation can compare Hit@1, Hit@3, MRR, latency, and cost
on the same corpus and labeled questions.

The manifest is the selection policy. The JSONL file is the reproducible content
snapshot. Keeping those separate means the topic can grow or change without
changing ingestion code.

## Fetch and ingest

```bash
make wikipedia-corpus

DOCSMIND_DATA_DIR=data/wikipedia \
DOCSMIND_INDEX_DIR=data/index-wikipedia \
make ingest
```

The fetcher is intentionally an ingestion-time job, not a query-time tool. It:

1. Reads the versioned page-title manifest.
2. Fetches each article sequentially through the MediaWiki API.
3. Sends a project-identifying User-Agent and retries 429/503 responses.
4. Resolves redirects and records the canonical page ID and revision ID.
5. Converts headings, paragraphs, lists, infoboxes, and tables into normalized
   section text.
6. Removes references, source lists, external links, navigation boxes, and
   markup artifacts that would add retrieval noise.
7. Rejects seed titles that resolve to the same canonical article.
8. Atomically replaces the output only when the complete fetch succeeds.

Override the manifest or output without modifying the script:

```bash
make wikipedia-corpus ARGS='\
  --manifest data/wikipedia/volkswagen_pages.v2.json \
  --output data/wikipedia/volkswagen-v2.wikipedia.jsonl'
```

For a small smoke fetch:

```bash
make wikipedia-corpus ARGS='--limit 3 --output /tmp/vw-wikipedia-smoke.jsonl'
```

## Why section-aware normalization

At **Chunk**, the generic `SentenceSplitter` still performs token-sized
splitting. Before that, the Wikipedia adapter preserves article and heading
boundaries. This matters for automotive pages because a page can discuss many
generations, platforms, and engines. The section path gives each chunk local
meaning, for example:

```text
Article: Volkswagen Golf Mk7
Section: Powertrain > Golf GTI
```

Tables are retained as pipe-delimited rows. Dropping tables would remove many
of the exact model, platform, engine, production, and dimension facts that make
this corpus useful.

## Provenance and licensing

Every section carries:

- Requested and canonical article title
- Canonical Wikipedia URL
- Page ID and revision ID
- Fetch timestamp and language
- `CC BY-SA 4.0` license marker

`chunk_documents()` prefers `source_url` when it creates a `Chunk`, so API
citations point to the article rather than the JSONL filename. The revision ID
makes an evaluation result explainable even after Wikipedia changes.

## Exact chunk and metadata contract

At the **Chunk** stage, the transformation is:

```text
Wikipedia JSONL article
  -> one LlamaIndex Document per retained heading section
  -> SentenceSplitter(chunk_size=512, chunk_overlap=64)
  -> DocsMind Chunk
  -> OpenSearch document plus 1,024-dimensional BGE-M3 vector
```

This is structure-aware sentence chunking, not semantic chunking. Headings set
the first boundary. `SentenceSplitter` then tries to keep sentences intact while
bounding a long section to approximately 512 tokens. Adjacent chunks repeat up
to 64 tokens so a statement crossing the boundary is not completely separated.
The final chunk in a section is usually shorter.

### Text sent to the chunker

`load_wikipedia_documents()` creates the exact section text below before
splitting:

```text
Article: Volkswagen Golf Mk7
Section: Powertrain > Golf GTI

<normalized section paragraphs, lists, and pipe-delimited tables>
```

The article and section header is part of the embedded text. It gives every
child chunk local meaning even when the passage itself starts halfway through a
long section.

### Complete Wikipedia metadata

Every section `Document`, and therefore every chunk created from it, carries:

| Field | Example | Purpose |
|---|---|---|
| `source_type` | `wikipedia` | Lets downstream code distinguish corpus adapters |
| `title` | `Volkswagen Golf Mk7` | Canonical article title |
| `requested_title` | `Volkswagen Golf (Mk7)` | Manifest seed before redirect resolution |
| `section` | `Powertrain > Golf GTI` | Heading path that localized the passage |
| `source_url` | `https://en.wikipedia.org/...` | Citation target returned by the API |
| `page_id` | `12345` | Stable MediaWiki page identity |
| `revision_id` | `987654321` | Exact article revision used for the index |
| `revision_timestamp` | ISO-8601 timestamp | When Wikipedia published that revision |
| `fetched_at` | ISO-8601 timestamp | When DocsMind captured the snapshot |
| `language` | `en` | Corpus language for future multilingual routing |
| `license` | `CC BY-SA 4.0` | Attribution and reuse provenance |

The section-level document ID is deterministic:

```text
wikipedia:<page_id>:<revision_id>:<section_index>
```

LlamaIndex creates a node ID for each split chunk. `chunk_documents()` maps the
node to DocsMind's backend-neutral contract:

```json
{
  "id": "<llamaindex-node-id>",
  "text": "Article: ...\nSection: ...\n\n...",
  "source": "https://en.wikipedia.org/wiki/...",
  "metadata": {"source_type": "wikipedia", "title": "..."}
}
```

`source` uses the first available value in this order:

```text
source_url -> file_name -> file_path -> title -> "unknown"
```

Wikipedia therefore resolves to its canonical URL. Other corpus adapters can
reuse the same `Chunk` schema without pretending that every source is a web
page.

### Record stored in OpenSearch

For each chunk, `OpenSearchVectorStore.add()` writes:

```json
{
  "_id": "<insertion_order>:<chunk_id>",
  "_source": {
    "insertion_order": 0,
    "chunk_id": "<llamaindex-node-id>",
    "text": "Article: ...\nSection: ...\n\n...",
    "source": "https://en.wikipedia.org/wiki/...",
    "metadata": {
      "source_type": "wikipedia",
      "title": "Volkswagen Golf Mk7",
      "requested_title": "Volkswagen Golf (Mk7)",
      "section": "Powertrain > Golf GTI",
      "source_url": "https://en.wikipedia.org/wiki/...",
      "page_id": 12345,
      "revision_id": 987654321,
      "revision_timestamp": "...",
      "fetched_at": "...",
      "language": "en",
      "license": "CC BY-SA 4.0"
    },
    "embedding": ["1,024 float values omitted"]
  }
}
```

`insertion_order` makes the complete chunk scan deterministic when the hybrid
retriever rebuilds BM25. Prefixing the OpenSearch `_id` with that order prevents
two repeated source IDs from overwriting each other.

The OpenSearch mapping sets `metadata` to `enabled=false`. The complete object
is preserved in `_source` and returned with citations, but OpenSearch does not
create a searchable field for every arbitrary metadata key. That prevents
mapping explosion across different corpus adapters. The trade-off is that a
future metadata filter such as `language=en` or `section=Powertrain` requires
promoting that field into the explicit mapping and re-indexing.

In an interview, the important question is not “did you use 512-token chunks?”
It is: “which boundaries were preserved, what provenance survived splitting,
how did IDs prevent overwrites, and what retrieval evidence justified 512/64?”
The current evaluation validates retrieval at 512/64. It does not yet prove
that this size beats 256/32 or semantic chunking; those require a controlled
comparison on the same labeled questions.

## What to measure

The first retrieval evaluation should compare these paths on the same labeled
questions and snapshot:

```text
dense
dense + BM25 -> RRF
dense + BM25 -> RRF -> cross-encoder
```

Use questions containing both concepts and exact identifiers:

- Which vehicles share the MQB platform?
- How are MEB and PPE different?
- What does DQ mean in a Volkswagen transmission context?
- Which Golf generation introduced a specified powertrain?
- What is the relationship between 4motion and quattro?

Measure Hit@1, Hit@3, and MRR before measuring answer quality. If retrieval
cannot surface the relevant article and section, generation cannot repair it.

In an interview, the depth signal is not “I downloaded Wikipedia.” It is: “I
versioned the selection manifest and article revisions, preserved tables and
section provenance, rejected canonical duplicates, and measured whether hybrid
retrieval improved exact-code questions over dense retrieval.”

## Trade-offs and failure modes

- **API snapshot versus full dump:** the API is appropriate for 57 curated
  articles. A full Wikipedia dump needs streaming XML ingestion and a scalable
  store; it should not be bolted onto this fetcher.
- **Freshness versus reproducibility:** refetching updates the corpus. Revision
  IDs record exactly which version produced an index or evaluation result.
- **Large sections:** the adapter preserves semantic section boundaries, while
  `SentenceSplitter` still divides long sections into bounded chunks.
- **Redirect duplication:** two seeds can resolve to one page. The fetcher fails
  rather than silently overweighting that article in retrieval.
- **Rate limits:** requests are sequential, delayed, identifiable, and retry
  `429`/`503` responses. Increase volume by using official dumps, not aggressive
  API concurrency.
- **Wikipedia accuracy:** Wikipedia is suitable for a learning corpus, but exact
  workshop specifications should later be checked against Volkswagen technical
  literature and service documentation.
