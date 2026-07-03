# Agent architectures — one loop vs many, and who's in charge (concept, Phase 5)

**Where in the pipeline:** wraps *around* the whole Retrieve → Generate → Cite path, not inside it.
Today, `RAGPipeline.query()` is the entire "agent": one retrieve, one generate, no decisions.
This doc is about what replaces that single function once Phase 5 adds a planning loop.
Two separate questions hide in here:
which **framework** builds the loop (`docsmind/agent/`), and whether the loop is **one agent or several**.
Keep them separate. Interviewers mix them on purpose to see if you will too.

```
today (Phase 1-3):     question → retrieve → generate → answer   (no loop)

single agent (Phase 5): question → [ plan → tool? → observe → plan → ... ] → answer
                                     ▲ one LLM, one loop, DocsMind's target shape

multi-agent:            question → supervisor → routes to sub-agent(s) → merge → answer
                                     ▲ several LLM loops, one deciding who goes next
```

## Framework comparison: LangChain vs LlamaIndex vs LangGraph vs CrewAI

These four solve different layers.
Comparing them head-to-head is a category error — and interviewers use it to check whether you understand the stack or just the brand names.

| Framework | What it actually is | Where DocsMind uses it |
|---|---|---|
| **LlamaIndex** | Ingestion/indexing toolkit — loaders, chunkers, index abstractions | `docsmind/ingestion/` (`SimpleDirectoryReader`, `SentenceSplitter`) |
| **LangChain** | General-purpose LLM app toolkit — prompt templates, chains, many integrations | Not used; DocsMind calls the Anthropic SDK directly (see `pipeline-questions.md` in `08-interview-prep` for why) |
| **LangGraph** | A *graph* execution engine for stateful, cyclic control flow — the loop itself | `docsmind/agent/` — this is the loop-builder for Phase 5 |
| **CrewAI** | A multi-agent framework — pre-built "roles," a "crew" of agents delegating tasks | Not used; relevant only if the *multi-agent* pattern below is chosen |

The one-line version for an interview:

- LlamaIndex answers "how do I get documents into an index."
- LangChain answers "how do I compose LLM calls and integrations quickly."
- LangGraph answers "how do I model a loop or branching decision as an explicit graph with state."
- CrewAI answers "how do I get several role-playing agents cooperating out of the box."

DocsMind picked LlamaIndex (ingestion) + LangGraph (the coming agent loop) deliberately.
A **single agent with an explicit, inspectable loop** is the right shape for this problem.
The pattern comparison below is the why.

## Pattern comparison: single agent vs multi-agent vs supervisor

All three live at the same place: the loop that wraps the pipeline.
The difference is how many LLM loops exist, and who decides what happens next.

**Single agent.** One LLM, one loop, a set of tools (see `12-tool-calling`).
It plans, calls a tool, sees the result, and decides again — until it answers.
This is what `docsmind/agent/` is a stub for.

**Multi-agent (peer).** Several agents, each with a narrower toolset and prompt, passing messages to each other directly.
Nothing is globally in charge.
That makes failure loops easy to create — two agents endlessly deferring to each other — and hard to debug.

**Supervisor-agent.** One "supervisor" LLM whose only job is *routing*: decide which specialist sub-agent (or tool) handles this step.
Every sub-agent reports back to the supervisor, never to each other directly.
Most production multi-agent systems converge on this pattern.
Why: one point of control, one place to look when something goes wrong.

Plain version: a single agent is one person doing the research, writing, and fact-checking themself, switching hats.
A peer multi-agent system is three people passing a document around with no editor.
A supervisor system is the same three people, plus an editor who decides who works next and reviews what comes back.

## Where it would slot into the real code

`docsmind/agent/__init__.py` is today just a docstring:
*"Placeholder for the LangGraph agent: planning loop with retrieve / web_search / code_exec / cite tools and anti-hallucination guardrails."*

That's a **single-agent** design. One LangGraph loop, several tools, no sub-agents.
For DocsMind's actual problem — answer questions from one document corpus, with citations — that's the right call.
There's one job here, not several specialist roles that need a supervisor splitting work.

When would that change?
If DocsMind later added a separate "web search agent" and a "code-execution agent," with genuinely different tool access and prompting needs — *then* a supervisor would earn its complexity.
Reaching for multi-agent before you have more than one distinct role is adding graph complexity with no matching problem.

## Trade-offs (the interview meat)

- **Single agent is easier to debug.**
  One trace, one loop, one place to look when the answer is wrong.
  Multi-agent multiplies the hiding places: was it agent A's tool call? Agent B's reading of A's output? The supervisor's routing?
- **Multi-agent's real cost is coordination, not compute.**
  Every hop between agents is a full LLM call reinterpreting another LLM's output in natural language.
  That's a lossy channel. Each extra agent is a place meaning can drift.
- **When multi-agent actually wins.**
  Genuinely distinct specialties, with different tools, prompts, or context windows.
  The tell: a single agent's system prompt turning into an unmanageable pile of "if this kind of question, act like X; if that kind, act like Y."
- **How you'd validate the choice.**
  An end-to-end eval, run against both shapes on the same task set — the same discipline as Phase 3's retrieval eval and Phase 6's answer eval.
  If multi-agent doesn't measurably beat a single well-scoped agent, the extra complexity isn't earning its cost.

## The interview signals

- **When do you reach for multi-agent instead of one agent with tools?**
  When you have genuinely distinct roles that would otherwise collapse into one overloaded prompt.
  Not by default. Not because it sounds more sophisticated.
- **What does a supervisor buy you over peer agents talking directly?**
  One place where decisions get made and logged.
  It buys debuggability, not raw capability.
- **Why LangGraph over CrewAI for DocsMind specifically?**
  DocsMind is one agent, one loop, explicit tools.
  LangGraph's job — model a loop as a graph with state — fits exactly.
  CrewAI's pre-built multi-role scaffolding solves a problem DocsMind doesn't have yet.
