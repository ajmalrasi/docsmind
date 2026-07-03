# MCP — a USB port for tools, not another way to call them (concept, Phase 5)

**Where in the pipeline:** the same seam as [`12-tool-calling`](../12-tool-calling/README.md)
— the model-asks-your-code-answers loop inside Generate. MCP doesn't change
*what* happens at that seam. It changes *how the tool list gets there* and *who
maintains it*. Read the tool-calling doc first; this one only makes sense as a
delta on top of it.

```
without MCP:  your app hardcodes a Python function + a hand-written JSON
              schema for every tool, one at a time, per project.

with MCP:     your app ← (MCP client, one protocol) ← MCP server (retrieve,
              web_search, github, slack, ...) — any MCP server plugs into any
              MCP client, no custom glue per pair.
```

## The problem it solves

Tool calling (previous doc) needs a schema — name, description, JSON
parameters — for every function the model can invoke. Without a standard, each
tool integration is bespoke: your `retrieve` schema, someone else's `send_email`
schema, all written by hand, all living inside whichever app wired them up. If
you build ten agent projects, you write the same "GitHub tool," "Slack tool,"
"filesystem tool" schema-plus-glue-code ten times, and nobody else's agent can
reuse yours.

**MCP (Model Context Protocol)** is Anthropic's open standard that separates
"a tool exists and has a schema" from "an app wired it up." A **server**
exposes tools (and resources, and prompts) over a common protocol. A
**client** — any agent framework, any app — speaks that protocol and can use
*any* MCP server without custom code per server. It's the same shift USB made
over one custom cable per peripheral: one port, one plug shape, every device
that follows the standard just works.

## Why it's gaining popularity

Not because it lets you do anything tool calling couldn't already do — it's
the same underlying "model requests, code executes" loop. It's popular because
it **decouples tool authors from agent authors**. A company can write one MCP
server for "our internal ticketing system" once, and every team's agent —
regardless of framework (LangGraph, CrewAI, a bespoke loop) — can use it by
speaking the protocol, instead of every team writing its own integration
against that ticketing API.

## Where it would slot into DocsMind

Concretely: DocsMind's own `retrieve` capability could be exposed as an MCP
**server** — wrapping `HybridRetriever.retrieve()` in
[`retriever.py`](../../docsmind/retrieval/retriever.py) behind the protocol —
so that *any* MCP-speaking agent (not just DocsMind's own LangGraph agent in
`docsmind/agent/`) could call into DocsMind's retrieval without knowing
anything about FAISS, BM25, or RRF fusion underneath. That's the pitch: the
retrieval internals stay hidden behind one schema, reusable outside this repo.

Today, if Phase 5's agent needs `retrieve` as a tool, the fastest path is
still the hand-written schema from `12-tool-calling` — MCP is worth adopting
once there's a *second* consumer of that tool, or a *third-party* tool
(GitHub, Slack, a filesystem) you don't want to hand-write a schema for.

## Trade-offs (the interview meat)

- **It's not a new capability, it's a distribution mechanism.** Don't answer
  "what is MCP" with "it lets LLMs call tools" — tool calling already does
  that. MCP's contribution is standardizing the *packaging* so tools are
  shareable across agent frameworks.
- **Overhead for a single, in-house tool.** If you're the only consumer of
  `retrieve`, wrapping it as an MCP server is extra indirection (a server
  process, a transport layer) for no benefit. It pays off once other agents,
  other teams, or third-party servers enter the picture.
- **Trust boundary.** An MCP server run by someone else is code you didn't
  write, executing with whatever permissions your client grants it. The same
  caution in `18-llm-security` about not trusting tool arguments applies
  doubly here — you're also trusting the *server's* implementation now, not
  just the model's request.
- **How you'd validate it's worth adopting:** count how many places the same
  tool schema would otherwise be duplicated. One reuse point, marginal. Three
  agents across two frameworks needing the same tool, MCP earns its keep.

## The interview signals

- **What is MCP, in one line?** A standard protocol so any agent framework can
  use any tool server without custom integration glue — same idea as USB
  standardizing the plug, not the electricity.
- **How is it different from function/tool calling?** Tool calling is the
  *mechanic* (model requests, code executes). MCP is the *packaging* around
  that mechanic — a shared schema/transport so the tool-provider and the
  agent-builder don't have to be the same team, or write bespoke glue per pair.
- **When would you *not* reach for it?** A single in-house tool with one
  consumer — hand-write the schema, ship it, don't add a protocol layer you
  don't need yet.
