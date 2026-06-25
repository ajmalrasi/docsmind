# The System Prompt

**TL;DR:** The system prompt is the set of rules Claude must follow. It does
three things: constrains the answer to the context only, forces citation by
passage number, and defines the fallback when context is insufficient.

## The prompt

```python
# docsmind/pipeline.py

INSUFFICIENT = "INSUFFICIENT_CONTEXT"

SYSTEM_PROMPT = (
    "You are DocsMind, a question-answering assistant for technical and ML "
    "documentation. Answer ONLY from the numbered context passages provided. "
    "Cite every claim with its passage number in square brackets, e.g. [1] or "
    "[2][3]. Do not use outside knowledge. If the context does not contain enough "
    f"information to answer, reply with exactly: {INSUFFICIENT}"
)
```

## Breaking it down — every sentence matters

**"Answer ONLY from the numbered context passages provided."**
This is the anti-hallucination instruction. Claude has vast training knowledge
and would happily answer from memory. This line tells it not to — the only
valid source is what's in `[1]`, `[2]`, `[3]`, `[4]`.

**"Cite every claim with its passage number in square brackets, e.g. [1] or [2][3]."**
Forces traceability. Every factual claim must be pinned to a passage. This
makes the citation extraction step possible and makes the answer auditable —
a user can check which file each claim came from.

**"Do not use outside knowledge."**
Redundant with "ONLY from context" but worth repeating. Reinforces the boundary.

**"If the context does not contain enough information to answer, reply with exactly: INSUFFICIENT_CONTEXT"**
The exact string matters. The pipeline checks:
```python
grounded = "INSUFFICIENT_CONTEXT" not in answer
```
If Claude paraphrases ("I don't have enough context...") instead of using
the exact string, the check fails and the pipeline incorrectly marks it as
grounded. The word "exactly" in the prompt minimizes this — but it's still
a soft guardrail.

## Why system message and not user message?

Claude treats the system message as a persistent role definition and behavioral
contract for the whole conversation. The user message is the variable input.
Putting the rules in the system message gives them higher precedence than if
they were buried in the user message alongside the context and question.

## What this prompt does NOT do

- It does not guarantee Claude won't hallucinate. It reduces the likelihood.
- It does not verify that cited passages actually support the claim.
- It does not handle adversarial inputs ("ignore previous instructions...").

These are the limits of prompt-level guardrails. Phase 6 (RAGAS) adds a
faithfulness metric that checks whether each claim is actually supported by
its cited passage. Phase 5 (LangGraph) adds structural enforcement around
the answer.

→ Next: **[claude-generates.md](claude-generates.md)**
