# Patterns — Single Agent vs Multi-Agent vs Supervisor

**TL;DR:** all three live at the same place: the loop that wraps the
pipeline. The difference is how many LLM loops exist, and who decides what
happens next.

## The three shapes

**Single agent.** One LLM, one loop, a set of tools
(see [12-tool-calling](../12-tool-calling/README.md)).
It plans, calls a tool, sees the result, and decides again — until it
answers. This is what `docsmind/agent/` is a stub for.

**Multi-agent (peer).** Several agents, each with a narrower toolset and
prompt, passing messages to each other directly. Nothing is globally in
charge. That makes failure loops easy to create — two agents endlessly
deferring to each other — and hard to debug.

**Supervisor-agent.** One "supervisor" LLM whose only job is *routing*:
decide which specialist sub-agent (or tool) handles this step. Every
sub-agent reports back to the supervisor, never to each other directly.
Most production multi-agent systems converge on this pattern.
Why: one point of control, one place to look when something goes wrong.

```
single:        [ agent ] ──uses──→ tools

peer:          [ agent A ] ↔ [ agent B ] ↔ [ agent C ]     (no one in charge)

supervisor:            [ supervisor ]
                       ↙      ↓      ↘
              [ agent A ] [ agent B ] [ agent C ]          (all report back up)
```

Plain version: a single agent is one person doing the research, writing,
and fact-checking themself, switching hats. A peer multi-agent system is
three people passing a document around with no editor. A supervisor system
is the same three people, plus an editor who decides who works next and
reviews what comes back.

## What each shape costs

| | Single | Peer multi-agent | Supervisor |
|---|---|---|---|
| LLM loops running | 1 | N | N + 1 |
| Where to look when it breaks | one trace | anywhere — A's call? B's reading of A? | the supervisor's routing log first |
| Coordination overhead | none | every hop is an LLM reinterpreting an LLM | every hop, plus routing calls |
| Failure loop risk | low (one max-iterations guard) | high — two agents deferring forever | contained — supervisor caps the routing |

**Multi-agent's real cost is coordination, not compute.**
Every hop between agents is a full LLM call reinterpreting another LLM's
output in natural language. That's a lossy channel. Each extra agent is a
place meaning can drift.

**Single agent is easier to debug.**
One trace, one loop, one place to look when the answer is wrong.
Multi-agent multiplies the hiding places.

## When multi-agent actually wins

Genuinely distinct specialties, with different tools, prompts, or context
windows. The tell: a single agent's system prompt turning into an
unmanageable pile of "if this kind of question, act like X; if that kind,
act like Y." When the prompt is a disguised router, promote it to a real
supervisor.

Reaching for multi-agent before you have more than one distinct role is
adding graph complexity with no matching problem.

→ Next: **[docsmind-choice.md](docsmind-choice.md)**
