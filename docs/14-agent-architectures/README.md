# Agent architectures — one loop vs many, and who's in charge (concept, Phase 5)

**Where in the pipeline:** wraps *around* the whole Retrieve → Generate → Cite
path, not inside it. Today `RAGPipeline.query()` is the entire "agent" —
one retrieve, one generate, no decision-making. This doc is about what
replaces that single function once Phase 5 gives the system a planning loop,
and — separately — whether that loop is one agent or several talking to each
other. Framework choice (`docsmind/agent/`) and architecture pattern
(single vs multi-agent) are two different questions; keep them separate.

```
today (Phase 1-3):     question → retrieve → generate → answer   (no loop)

single agent (Phase 5): question → [ plan → tool? → observe → plan → ... ] → answer
                                     ▲ one LLM, one loop, DocsMind's target shape

multi-agent:            question → supervisor → routes to sub-agent(s) → merge → answer
                                     ▲ several LLM loops, one deciding who goes next
```

## Framework comparison: LangChain vs LlamaIndex vs LangGraph vs CrewAI

These solve different layers — comparing them head-to-head is a category
error interviewers use to check if you actually understand the stack, not
just the brand names.

| Framework | What it actually is | Where DocsMind uses it |
|---|---|---|
| **LlamaIndex** | Ingestion/indexing toolkit — loaders, chunkers, index abstractions | `docsmind/ingestion/` (`SimpleDirectoryReader`, `SentenceSplitter`) |
| **LangChain** | General-purpose LLM app toolkit — prompt templates, chains, many integrations | Not used; DocsMind calls the Anthropic SDK directly (see `pipeline-questions.md` in `08-interview-prep` for why) |
| **LangGraph** | A *graph* execution engine for stateful, cyclic control flow — the loop itself | `docsmind/agent/` — this is the loop-builder for Phase 5 |
| **CrewAI** | A multi-agent framework — pre-built "roles," a "crew" of agents delegating tasks | Not used in DocsMind; relevant only if the *multi-agent* pattern below is chosen |

The one-line version to give in an interview: LlamaIndex answers "how do I get
documents into an index," LangChain answers "how do I compose LLM calls and
integrations quickly," LangGraph answers "how do I model a loop or branching
decision as an explicit graph with state," and CrewAI answers "how do I get
several role-playing agents cooperating out of the box." DocsMind picked
LlamaIndex (ingestion) + LangGraph (the coming agent loop) deliberately,
because a **single agent with an explicit, inspectable loop** is the right
shape for DocsMind's problem — see the pattern comparison below for why.

## Pattern comparison: single agent vs multi-agent vs supervisor

**Single agent:** one LLM, one loop, a set of tools (see `12-tool-calling`).
It plans, calls a tool, sees the result, and decides again — until it answers.
This is what `docsmind/agent/` is a stub for.

**Multi-agent (peer):** several agents, each with a narrower toolset/prompt,
passing messages to each other directly. Harder to reason about — nothing is
globally in charge, so failure loops (two agents endlessly deferring to each
other) are easy to create and hard to debug.

**Supervisor-agent:** one "supervisor" LLM whose only job is *routing* —
decide which specialist sub-agent (or tool) should handle this step — and
each sub-agent reports back to the supervisor, never to each other directly.
This is the pattern most production multi-agent systems converge on, because
it keeps a single point of control and a single place to look when something
goes wrong.

Plain version: a single agent is one person doing research, writing, and
fact-checking themself, switching hats as needed. A peer multi-agent system is
three people passing a document back and forth with no editor. A
supervisor-agent system is the same three people, but with an editor who
decides who works on the doc next and reviews what comes back.

## Where it would slot into the real code

`docsmind/agent/__init__.py` is today just a docstring: *"Placeholder for the
LangGraph agent: planning loop with retrieve / web_search / code_exec / cite
tools and anti-hallucination guardrails."* That's a **single-agent** design —
one LangGraph loop, several tools, no sub-agents. For DocsMind's actual
problem (answer questions from one document corpus, with citations), that's
the right call: there's one job, not several specialist roles that would
benefit from a supervisor splitting work across them.

If DocsMind later added, say, a separate "web search agent" and a
"code-execution agent" with genuinely different tool access and prompting
needs, *then* a supervisor pattern would earn its complexity. Reaching for
multi-agent before you have more than one distinct role is adding graph
complexity with no matching problem.

## Trade-offs (the interview meat)

- **Single agent is easier to debug.** One trace, one loop, one place to look
  when the answer is wrong. Multi-agent multiplies the places a failure can
  hide — was it agent A's tool call, agent B's interpretation of A's output,
  or the supervisor's routing decision?
- **Multi-agent's real cost is coordination, not compute.** Every hop between
  agents is a full LLM call reinterpreting another LLM's output in natural
  language — a lossy channel. Each additional agent is a place meaning can
  drift.
- **When multi-agent actually wins:** genuinely distinct specialties with
  different tools/prompts/context windows, where a single agent's system
  prompt would become an unmanageable pile of "if this kind of question, act
  like X; if that kind, act like Y."
- **How you'd validate the choice:** an end-to-end eval (same discipline as
  Phase 3's retrieval eval and Phase 6's answer eval) run against both shapes
  on the same task set — if multi-agent's split doesn't measurably beat a
  single well-scoped agent, the extra complexity isn't earning its cost.

## The interview signals

- **When do you reach for a multi-agent system instead of one agent with
  tools?** When you have genuinely distinct roles that would otherwise
  collapse into one overloaded prompt — not by default, and not because it
  sounds more sophisticated.
- **What does a supervisor buy you over peer agents talking directly?** One
  place decisions get made and logged — debuggability, not raw capability.
- **Why LangGraph over CrewAI for DocsMind specifically?** DocsMind is one
  agent, one loop, explicit tools — LangGraph's job (model a loop as a graph
  with state) fits exactly; CrewAI's pre-built multi-role scaffolding solves a
  problem DocsMind doesn't have yet.
