# The LLM Generates the Answer

**TL;DR:** The LLM receives the system prompt + numbered context + question.
It produces a grounded answer with `[n]` citation markers. The pipeline can call
either a cloud model (Anthropic, direct SDK) or a local model (Ollama) behind the
same `LLMClient` interface.

## The two clients

```python
# docsmind/llm/cloud_client.py  — cloud path (Anthropic)
class CloudLLMClient(LLMClient):
    def __init__(self, model: str) -> None:
        self.model = model
        self._client = anthropic.Anthropic()  # reads ANTHROPIC_API_KEY from env

    def generate(self, system: str, prompt: str, max_tokens: int) -> str:
        response = self._client.messages.create(
            model=self.model, max_tokens=max_tokens,
            system=system, messages=[{"role": "user", "content": prompt}],
        )
        return "".join(b.text for b in response.content if b.type == "text").strip()
```

```python
# docsmind/llm/local_client.py  — local path (Ollama)
class LocalLLMClient(LLMClient):
    def __init__(self, model: str, base_url: str = "http://localhost:11434") -> None:
        self.model = model
        self._base_url = base_url.rstrip("/")
        self._client = httpx.Client(timeout=300.0)

    def generate(self, system: str, prompt: str, max_tokens: int) -> str:
        r = self._client.post(f"{self._base_url}/api/chat", json={
            "model": self.model,
            "messages": [{"role": "system", "content": system},
                         {"role": "user", "content": prompt}],
            "stream": False, "options": {"num_predict": max_tokens},
        })
        r.raise_for_status()
        return r.json()["message"]["content"].strip()
```

`factory.build_llm()` picks one based on `DOCSMIND_LLM_PROVIDER` (`cloud` or
`local`). The pipeline never knows which — it just calls `.generate()`.

## What the LLM receives

```
SYSTEM:
  You are DocsMind... Answer ONLY from numbered context passages...
  Cite every claim with [n]... reply INSUFFICIENT_CONTEXT if needed.

USER:
  Context passages:

  [1] (source: black_holes.md)
  A black hole is a region of spacetime where gravity is so strong that nothing —
  not even light — can escape. Stellar-mass black holes form when a massive star
  collapses in a supernova...

  [2] (source: stellar_lifecycle.md)
  A star much more massive than the Sun... collapses and rebounds in a supernova;
  the most massive cores collapse into a black hole...

  [3] (source: solar_system.md)
  The Sun is a main-sequence star that fuses hydrogen into helium...

  [4] (source: rocket_propulsion.md)
  To leave Earth's gravity, a spacecraft must reach escape velocity...

  Question: How do black holes form?

  Answer:
```

## What the LLM returns (real output from the local model)

```
Black holes form when matter is compressed into a small enough volume that its
escape velocity exceeds the speed of light [1]. This occurs in two main ways:
stellar-mass black holes form from the collapse of massive stars, typically more
than about 20 times the mass of the Sun, following a supernova event [1][2], and
supermassive black holes form at the centers of galaxies, including our Milky
Way, with masses in the millions to billions of times that of the Sun [1][3].
```

Every claim is pinned to a passage number. The pipeline extracts `{1, 2, 3}`
from the text and maps them to sources. Note the model used `[1]`, `[2]`, `[3]`
and ignored `[4]` (the rocket passage) — it only cited what it actually needed.

## Why direct Anthropic SDK and not LangChain?

For the cloud path, using the SDK directly means:
- No abstraction tax — full access to every Anthropic API parameter
- No hidden retry logic or model routing you didn't ask for
- Easy to add system-level features (batching, prompt caching, streaming)
- Simpler to debug — fewer layers between you and the API response

LangChain's `ChatAnthropic` wrapper is a convenience layer. For a project
where the LLM call is a critical-path component, direct SDK gives more
control and less mystery.

## The pluggable interface

```python
# docsmind/llm/base.py

class LLMClient(ABC):
    model: str

    @abstractmethod
    def generate(self, system: str, prompt: str, max_tokens: int) -> str: ...
```

Both `CloudLLMClient` and `LocalLLMClient` implement this. The local client was
added to run without an API key — a minimal preview of the Phase 4 `LLMRouter`,
which will add automatic local→cloud fallback and model benchmarking.

## Configuring the backend

```bash
# .env — local (no API key needed)
DOCSMIND_LLM_PROVIDER=local
DOCSMIND_LOCAL_LLM_MODEL=deepseek-coder-v2:16b-lite-instruct-q4_K_M
DOCSMIND_OLLAMA_BASE_URL=http://localhost:11434

# .env — cloud (needs ANTHROPIC_API_KEY)
DOCSMIND_LLM_PROVIDER=cloud
DOCSMIND_CLOUD_LLM_MODEL=claude-haiku-4-5-20251001   # faster, cheaper
```

For keyless local testing, use the local provider. For top quality, point at a
cloud model. Same pipeline either way.

→ Next: **[citation-extraction.md](citation-extraction.md)**
