# MCP — a USB port for tools, not another way to call them (concept, Phase 5)

**Where in the pipeline:** the same seam as [`12-tool-calling`](../12-tool-calling/README.md) — the model-asks-your-code-answers loop inside Generate.
MCP doesn't change *what* happens at that seam.
It changes *how the tool list gets there*, and *who maintains it*.
Read the tool-calling doc first. This one is a delta on top of it.

```
without MCP:  your app hardcodes a Python function + a hand-written JSON
              schema for every tool, one at a time, per project.

with MCP:     your app ← (MCP client, one protocol) ← MCP server (retrieve,
              web_search, github, slack, ...) — any MCP server plugs into any
              MCP client, no custom glue per pair.
```

## The problem it solves

Tool calling needs a schema for every function: name, description, JSON parameters.
Without a standard, every tool integration is bespoke.
You hand-write your `retrieve` schema. Someone else hand-writes their `send_email` schema.
Each one lives inside whichever app wired it up.
Build ten agent projects, and you write the same "GitHub tool" glue ten times.
And nobody else's agent can reuse yours.

**MCP (Model Context Protocol)** is Anthropic's open standard that fixes this.
It separates "a tool exists and has a schema" from "an app wired it up."
A **server** exposes tools (and resources, and prompts) over a common protocol.
A **client** — any agent framework, any app — speaks that protocol.
Any client can use *any* server. No custom code per pair.

Plain version: it's the shift USB made.
Before USB, every peripheral needed its own custom cable.
After USB: one port, one plug shape, and every device that follows the standard just works.
MCP is that port, for tools.

## Why it's gaining popularity

Not because it adds a new capability.
Underneath, it's still the same "model requests, code executes" loop from tool calling.

It's popular because it **decouples tool authors from agent authors**.
A company writes one MCP server for "our internal ticketing system."
Then every team's agent — LangGraph, CrewAI, a bespoke loop, whatever — can use it by speaking the protocol.
Nobody writes a per-team integration against the ticketing API ever again.

## Where it would slot into DocsMind

DocsMind's own `retrieve` capability could become an MCP **server**.
Concretely: wrap `HybridRetriever.retrieve()` in [`retriever.py`](../../docsmind/retrieval/retriever.py) behind the protocol.
Then *any* MCP-speaking agent — not just DocsMind's own LangGraph agent in `docsmind/agent/` — could call DocsMind's retrieval.
It wouldn't need to know anything about FAISS, BM25, or RRF fusion underneath.
That's the pitch: the retrieval internals stay hidden behind one schema, reusable outside this repo.

But today? If Phase 5's agent needs `retrieve` as a tool, the fastest path is still the hand-written schema from `12-tool-calling`.
MCP earns its keep once there's a *second* consumer of the tool.
Or a *third-party* tool (GitHub, Slack, a filesystem) whose schema you don't want to hand-write.

## Trade-offs (the interview meat)

- **It's not a new capability. It's a distribution mechanism.**
  Don't answer "what is MCP" with "it lets LLMs call tools" — tool calling already does that.
  MCP's contribution is standardizing the *packaging*, so tools are shareable across agent frameworks.
- **Overhead for a single, in-house tool.**
  If you're the only consumer of `retrieve`, wrapping it as an MCP server is extra indirection — a server process, a transport layer — for no benefit.
  It pays off when other agents, other teams, or third-party servers enter the picture.
- **Trust boundary.**
  An MCP server run by someone else is code you didn't write, executing with whatever permissions your client grants it.
  The caution in `18-llm-security` about not trusting tool arguments applies doubly here.
  You're now trusting the *server's* implementation too, not just the model's request.
- **How you'd validate it's worth adopting.**
  Count how many places the same tool schema would otherwise be duplicated.
  One consumer: marginal.
  Three agents across two frameworks needing the same tool: MCP earns its keep.

## The interview signals

- **What is MCP, in one line?**
  A standard protocol so any agent framework can use any tool server without custom integration glue.
  Same idea as USB: standardize the plug, not the electricity.
- **How is it different from function/tool calling?**
  Tool calling is the *mechanic* — model requests, code executes.
  MCP is the *packaging* around that mechanic: a shared schema and transport, so the tool-provider and the agent-builder don't have to be the same team.
- **When would you *not* reach for it?**
  A single in-house tool with one consumer.
  Hand-write the schema, ship it. Don't add a protocol layer you don't need yet.
