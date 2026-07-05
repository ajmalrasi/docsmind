# DocsMind as an MCP Server — and Why Not Yet

**TL;DR:** DocsMind's `retrieve` could be exposed as an MCP server, hiding
FAISS/BM25/RRF behind one schema. But with a single consumer, that's
indirection with no payoff — MCP earns its keep at the *second* consumer.

## Where it would slot into DocsMind

DocsMind's own `retrieve` capability could become an MCP **server**.
Concretely: wrap `HybridRetriever.retrieve()` in
[`retriever.py`](../../docsmind/retrieval/retriever.py) behind the protocol.

Then *any* MCP-speaking agent — not just DocsMind's own LangGraph agent in
`docsmind/agent/` — could call DocsMind's retrieval. It wouldn't need to
know anything about FAISS, BM25, or RRF fusion underneath. That's the pitch:
the retrieval internals stay hidden behind one schema, reusable outside this
repo.

```
any MCP client (Claude Desktop, another team's agent, an IDE...)
        │  one protocol
        ▼
  MCP server: "docsmind-retrieve"
        │  ordinary function call
        ▼
  HybridRetriever.retrieve()   ← FAISS + BM25 + RRF + rerank, invisible above
```

This is the same pattern the repo already uses twice: `VectorStore` hides
FAISS-vs-Qdrant, `LLMClient` hides cloud-vs-local. MCP applies it one layer
higher — hiding the whole retrieval stack behind a schema.

## Why not yet

If Phase 5's agent needs `retrieve` as a tool, the fastest path is still the
hand-written schema from [12-tool-calling](../12-tool-calling/code-seam.md).

MCP earns its keep once there's a *second* consumer of the tool. Or a
*third-party* tool (GitHub, Slack, a filesystem) whose schema you don't want
to hand-write.

| Situation | Right call |
|---|---|
| One in-house tool, one consumer (DocsMind today) | Hand-written schema — a protocol layer is pure overhead |
| Same tool needed by 3 agents across 2 frameworks | MCP server — write the glue once |
| Consuming third-party tools (GitHub, Slack...) | MCP client — someone already wrote the server |

The validation question is countable: how many places would the same tool
schema otherwise be duplicated? One consumer: marginal. Three: MCP wins.

## The trust boundary

An MCP server run by someone else is code you didn't write, executing with
whatever permissions your client grants it.

The caution in [18-llm-security](../18-llm-security/README.md) about not
trusting tool arguments applies doubly here. With a hand-written tool, you
trust the model's *request* but you wrote the *implementation*. With a
third-party MCP server, you're trusting both — the request *and* an
implementation you've never read. Treat server selection like dependency
selection: pin versions, read what you can, grant minimal permissions.

→ Next: **[14-agent-architectures/README.md](../14-agent-architectures/README.md)**
