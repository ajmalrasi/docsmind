# 13 — MCP: A USB Port for Tools (concept, Phase 5)

**The big idea:** MCP doesn't give models a new capability — tool calling
already lets them request functions. MCP standardizes the *packaging*: a
server exposes tools over a common protocol, and any agent framework that
speaks the protocol can use them. Same idea as USB — standardize the plug,
not the electricity.

**Where in the pipeline:** the same seam as
[12-tool-calling](../12-tool-calling/README.md) — the
model-asks-your-code-answers loop inside Generate. MCP doesn't change *what*
happens at that seam. It changes *how the tool list gets there*, and *who
maintains it*. Read the tool-calling section first; this one is a delta on
top of it.

```
without MCP:  your app hardcodes a Python function + a hand-written JSON
              schema for every tool, one at a time, per project.

with MCP:     your app ← (MCP client, one protocol) ← MCP server (retrieve,
              web_search, github, slack, ...) — any MCP server plugs into any
              MCP client, no custom glue per pair.
```

## Files in this folder

| File | What it covers |
|------|----------------|
| [why-a-protocol.md](why-a-protocol.md) | The duplication problem MCP solves, the USB analogy, and why it caught on |
| [docsmind-as-a-server.md](docsmind-as-a-server.md) | Wrapping `HybridRetriever` as an MCP server — and why *not* to, yet |

## 🎯 Interview Q&A

**Q: What is MCP, in one line?**
A standard protocol so any agent framework can use any tool server without
custom integration glue. Same idea as USB: standardize the plug, not the
electricity.

**Q: How is it different from function/tool calling?**
Tool calling is the *mechanic* — model requests, code executes. MCP is the
*packaging* around that mechanic: a shared schema and transport, so the
tool-provider and the agent-builder don't have to be the same team.

**Q: When would you *not* reach for it?**
A single in-house tool with one consumer. Hand-write the schema, ship it.
Don't add a protocol layer you don't need yet.

**Q: What's the trust concern with third-party MCP servers?**
It's code you didn't write, executing with whatever permissions your client
grants it. You're trusting the server's implementation, not just the model's
request — the tool-argument caution from
[18-llm-security](../18-llm-security/README.md) applies doubly.

## Code

[docsmind/retrieval/retriever.py](../../docsmind/retrieval/retriever.py) —
`HybridRetriever.retrieve()`, the capability that would be wrapped as a
server.

→ Next: **[14-agent-architectures/README.md](../14-agent-architectures/README.md)**
