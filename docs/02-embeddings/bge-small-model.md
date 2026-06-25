# The bge-small Model — Why This One?

**TL;DR:** `bge-small-en-v1.5` is a self-hosted, open-source English embedding
model that's fast, free, private, and good enough for technical docs. The key
decision was self-hosted over a cloud API — driven by cost, privacy, and no
vendor lock-in.

## What bge-small is

- **bge** = BAAI General Embeddings, published by Beijing Academy of AI
- **small** = the smallest variant in the family (384 dims vs large at 1024 dims)
- **en** = English
- **v1.5** = version; the v1.5 family improved significantly over v1
- **License:** MIT — free to use commercially, no restrictions
- **Max input:** 512 tokens (chunk_size in Phase 1 is set to match this)

## Why self-hosted over a cloud API

Embedding is a **bulk operation**. At ingest time, you encode your entire corpus.
If you have 100,000 chunks:

| | Self-hosted bge-small | Cloud API (OpenAI etc.) |
|---|---|---|
| Cost | Free after download | Pay per token, ~$0.13/1M tokens → adds up |
| Privacy | Data stays on your machine | All your docs sent to a third party |
| Rate limits | None | Provider throttles you at scale |
| Network | No round-trips | Latency on every request |
| Vendor lock-in | None (swap models freely) | Tied to provider + their versioning |
| Quality | Strong for English tech docs | Often higher, especially multilingual |

The `Embedder` class ([embeddings.py](../../docsmind/index/embeddings.py)) is
a single abstraction point — swapping to a different model is a one-line
config change (`embed_model` in `.env`), not a rewrite.

## When you'd choose a cloud model instead

- You need **multilingual** support (bge-small is English-only)
- Your content is very diverse and needs the highest possible retrieval quality
- You're prototyping and don't want to manage local model weights
- You can accept the cost and data-egress tradeoff

## The model in code

```python
# docsmind/index/embeddings.py
from sentence_transformers import SentenceTransformer

model = SentenceTransformer("BAAI/bge-small-en-v1.5")

embeddings = model.encode(
    texts,
    normalize_embeddings=True,   # L2 normalization — see 03-normalization
    convert_to_numpy=True,
    show_progress_bar=False,
)
# shape: (N, 384) — N texts, each → 384 floats
```

The model is loaded **lazily** (`@cached_property`) — it's not pulled into
memory until the first `encode()` call. After that it's cached for the
lifetime of the process.

→ Next: **[real-examples.md](real-examples.md)**
