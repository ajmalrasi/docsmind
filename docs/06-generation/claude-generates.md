# Claude Generates the Answer

**TL;DR:** Claude receives the system prompt + numbered context + question.
It produces a grounded answer with `[n]` citation markers. The pipeline
calls the Anthropic SDK directly — no LangChain wrapper.

## The LLM call

```python
# docsmind/llm/cloud_client.py

class CloudLLMClient(LLMClient):
    def __init__(self, model: str) -> None:
        self.model = model
        self._client = anthropic.Anthropic()  # reads ANTHROPIC_API_KEY from env

    def generate(self, system: str, prompt: str, max_tokens: int) -> str:
        response = self._client.messages.create(
            model=self.model,
            max_tokens=max_tokens,
            system=system,
            messages=[{"role": "user", "content": prompt}],
        )
        return "".join(
            block.text for block in response.content if block.type == "text"
        ).strip()
```

## What Claude receives

```
SYSTEM:
  You are DocsMind... Answer ONLY from numbered context passages...
  Cite every claim with [n]... reply INSUFFICIENT_CONTEXT if needed.

USER:
  Context passages:

  [1] (source: faiss_index_types.md)
  HNSW builds a multi-layer graph and navigates it greedily...

  [2] (source: faiss_index_types.md)
  IVF partitions the vector space into nlist cells...

  [3] (source: faiss_index_types.md)
  HNSW uses more memory than IVF...

  [4] (source: faiss_index_types.md)
  Large corpus: HNSW. Memory-constrained: IVF-PQ.

  Question: When should I use HNSW over IVF-PQ?

  Answer:
```

## What Claude returns

```
Use HNSW [1][4] when your dataset fits in RAM and you need low query
latency — it typically delivers the best recall-vs-latency tradeoff for
in-memory search [1]. Note that HNSW uses more memory than IVF because it
stores graph edges alongside the vectors [3].

Use IVF-PQ [4] when memory is the primary constraint. IVF only searches
the nearest cluster cells at query time [2], and combining it with Product
Quantization compresses the vectors significantly for billion-scale corpora.
```

Every claim is pinned to a passage number. The pipeline can now extract
`{1, 2, 3, 4}` from the text and map them to sources.

## Why direct Anthropic SDK and not LangChain?

Using the SDK directly means:
- No abstraction tax — full access to every Anthropic API parameter
- No hidden retry logic or model routing you didn't ask for
- Easy to add system-level features (batching, prompt caching, streaming)
- Simpler to debug — fewer layers between you and the API response

LangChain's `ChatAnthropic` wrapper is a convenience layer. For a project
where the LLM call is a critical path component, direct SDK gives more
control and less mystery.

## The pluggable interface

```python
# docsmind/llm/base.py

class LLMClient(ABC):
    @property
    @abstractmethod
    def model(self) -> str: ...

    @abstractmethod
    def generate(self, system: str, prompt: str, max_tokens: int) -> str: ...
```

`CloudLLMClient` implements this. Phase 4 will add `LocalLLMClient` (vLLM /
Ollama) behind the same interface. The pipeline doesn't know whether it's
talking to Claude or a local model — it just calls `.generate()`.

## Configuring the model

```bash
# .env
DOCSMIND_CLOUD_LLM_MODEL=claude-haiku-4-5-20251001   # faster, cheaper
DOCSMIND_CLOUD_LLM_MODEL=claude-sonnet-4-6           # balanced
DOCSMIND_CLOUD_LLM_MODEL=claude-opus-4-8             # default, most capable
```

For high-volume benchmarking (Phase 6 eval), swap to Haiku to reduce cost.
For production quality, use Sonnet or Opus.

→ Next: **[citation-extraction.md](citation-extraction.md)**
