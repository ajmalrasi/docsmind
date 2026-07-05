# Framework Comparison — Four Tools, Four Different Layers

**TL;DR:** LlamaIndex, LangChain, LangGraph, and CrewAI solve different
layers of the stack. Comparing them head-to-head is a category error — and
interviewers use it to check whether you understand the stack or just the
brand names.

## What each one actually is

| Framework | What it actually is | Where DocsMind uses it |
|---|---|---|
| **LlamaIndex** | Ingestion/indexing toolkit — loaders, chunkers, index abstractions | `docsmind/ingestion/` (`SimpleDirectoryReader`, `SentenceSplitter`) |
| **LangChain** | General-purpose LLM app toolkit — prompt templates, chains, many integrations | Not used; DocsMind calls the Anthropic SDK directly (see [pipeline-questions.md](../08-interview-prep/pipeline-questions.md) for why) |
| **LangGraph** | A *graph* execution engine for stateful, cyclic control flow — the loop itself | `docsmind/agent/` — this is the loop-builder for Phase 5 |
| **CrewAI** | A multi-agent framework — pre-built "roles," a "crew" of agents delegating tasks | Not used; relevant only if the multi-agent pattern is chosen |

The one-line version for an interview:

- LlamaIndex answers "how do I get documents into an index."
- LangChain answers "how do I compose LLM calls and integrations quickly."
- LangGraph answers "how do I model a loop or branching decision as an
  explicit graph with state."
- CrewAI answers "how do I get several role-playing agents cooperating out
  of the box."

## Where each sits in the pipeline

```
Ingest → Chunk → Embed → Index → [Search → Generate → Cite]
└────── LlamaIndex ──────┘         └── LangChain helps here ──┘

            the loop AROUND the whole thing:
            └── LangGraph (one loop) / CrewAI (many agents) ──┘
```

They're not four answers to one question — they're answers to four
questions. A project can sensibly use two of them at once (DocsMind:
LlamaIndex + LangGraph) and skip the other two *for stated reasons*, which
is exactly the depth an interviewer is fishing for.

## Why DocsMind picked its two

**LlamaIndex for ingestion:** loaders and chunkers are solved problems;
reimplementing `SentenceSplitter` teaches nothing and risks subtle bugs.

**LangGraph for the coming agent:** the Phase 5 loop needs explicit,
inspectable state — which node ran, what the model decided, where it went
next. LangGraph makes the control flow a *visible graph* instead of code
hidden inside a framework's agent class. When (not if) the loop misbehaves,
that visibility is the difference between reading a trace and guessing.

**Not LangChain:** DocsMind's LLM usage is one well-understood call pattern.
A direct SDK call is fewer layers to debug, and the repo *is* the
abstraction lesson — hiding it behind a chain would defeat the point.

**Not CrewAI:** no multi-agent problem exists here yet — see
[patterns.md](patterns.md) for when that changes.

→ Next: **[patterns.md](patterns.md)**
