# Costs, Severity, and Proving It Works

**TL;DR:** guardrails aren't free — each is a classifier pass with latency
and false positives. RBAC is the one you cannot skip and patch later. And
no claim of "it's secure" counts without a red-team eval set that proves
the guardrail held.

## Guardrails aren't free

Each of the five is usually its own model call or classifier pass — stack
all five and you've added real latency.

Apply the same cheap-first funnel as reranking
(see [09-hybrid-retrieval](../09-hybrid-retrieval/reranking-deep-dive.md)):
fast regex PII detection before a heavier classifier. Not five LLM calls
per request.

| Guardrail | Typical cost | Cheap first pass |
|---|---|---|
| PII masking | regex ≈ free; NER model = ms | regex patterns for emails/SSNs/phones |
| Injection detection | classifier pass per chunk | heuristics: imperative phrases, "ignore previous..." |
| Jailbreak detection | classifier pass per question | template matching on known jailbreak framings |
| RBAC | a `WHERE` clause — effectively free | — already cheap; just do it |
| Output moderation | one classifier pass per answer | keyword screen before the model |

## Not all failures are the same severity

**RBAC is the one you cannot skip and patch later.**
A hallucination guardrail failing gives a wrong answer.
An RBAC failure leaks a document to someone who shouldn't see it.
Different severity class entirely. Filter at retrieval; never rely on the
LLM's cooperation for access control.

This severity split is the interview answer to "where do you start?":
start with the failure that can't be apologized for.

## Prompt injection has no complete fix

Only mitigations: treat retrieved and tool content as untrusted data,
separate it structurally in the prompt, monitor for anomalous outputs.

Treat any claim of a fully solved defense skeptically — in your own
interview answers too. Saying "injection is mitigated, not solved, and
here's my monitoring story" is stronger than claiming a fix that doesn't
exist.

## How you'd validate any of this

A red-team eval set: adversarial inputs — injection attempts, jailbreak
templates, PII-bearing questions — run through the pipeline, scored on
whether the guardrail held.

```
red-team set (labeled)          run through pipeline          score
─────────────────────           ───────────────────           ─────
20 injection payloads      →    did any change behavior?  →   held / broke
20 jailbreak templates     →    did any bypass refusal?   →   held / broke
20 PII-bearing questions   →    did PII reach the LLM/logs? → held / broke
RBAC probe set             →    any cross-user leakage?   →   held / broke
```

Same eval-first discipline as retrieval
([09-hybrid-retrieval/eval-results.md](../09-hybrid-retrieval/eval-results.md))
and, eventually, faithfulness (Phase 6). You don't get to claim "it's
secure" without a test set proving it — and the test set, like every other
eval in this repo, gets built *before* the feature so the day-one number is
a real baseline.

→ Next: **[19-fine-tuning/README.md](../19-fine-tuning/README.md)**
