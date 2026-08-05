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
