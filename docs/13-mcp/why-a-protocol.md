# Why a Protocol — The Duplication Problem MCP Solves

**TL;DR:** without a standard, every tool integration is bespoke glue,
rewritten per project and unusable by anyone else's agent. MCP separates
"a tool exists and has a schema" from "an app wired it up."

## The problem it solves

Tool calling needs a schema for every function: name, description, JSON
parameters. Without a standard, every tool integration is bespoke.

You hand-write your `retrieve` schema. Someone else hand-writes their
`send_email` schema. Each one lives inside whichever app wired it up.
Build ten agent projects, and you write the same "GitHub tool" glue ten
times. And nobody else's agent can reuse yours.

```
the N × M problem:            with a standard:

 agent A ──┬── github glue     agent A ──┐
           ├── slack glue                ├── one protocol ── github server
 agent B ──┬── github glue     agent B ──┤                └─ slack server
           ├── slack glue                │
 agent C ──┴── ...             agent C ──┘
 (every pair hand-wired)       (any client ↔ any server)
```

**MCP (Model Context Protocol)** is Anthropic's open standard that fixes
this. It separates "a tool exists and has a schema" from "an app wired it
up." A **server** exposes tools (and resources, and prompts) over a common
protocol. A **client** — any agent framework, any app — speaks that
protocol. Any client can use *any* server. No custom code per pair.

Plain version: it's the shift USB made. Before USB, every peripheral needed
its own custom cable. After USB: one port, one plug shape, and every device
that follows the standard just works. MCP is that port, for tools.

## Why it's gaining popularity

Not because it adds a new capability. Underneath, it's still the same
"model requests, code executes" loop from
[12-tool-calling](../12-tool-calling/the-loop.md).

It's popular because it **decouples tool authors from agent authors**.
A company writes one MCP server for "our internal ticketing system."
Then every team's agent — LangGraph, CrewAI, a bespoke loop, whatever — can
use it by speaking the protocol. Nobody writes a per-team integration
against the ticketing API ever again.

The interview trap hiding here: "what is MCP" answered with "it lets LLMs
call tools" is wrong — tool calling already does that. MCP's contribution is
standardizing the *distribution*, so tools are shareable across agent
frameworks. Get the layer right and the rest of the answer writes itself.

→ Next: **[docsmind-as-a-server.md](docsmind-as-a-server.md)**
