# 18 — LLM Security: PII, Injection, Jailbreaks, RBAC, Moderation (concept, roadmap)

**The big idea:** "add security" is not a single stage — say that out loud
first in an interview. Five distinct problems live at different pipeline
points, and DocsMind's one shipped guardrail (`INSUFFICIENT_CONTEXT`) covers
*none* of them: it's a faithfulness guardrail, not a security guardrail.

**Where in the pipeline:** several different points, not one.

```
ingest → chunk → embed → index → [ query → embed → search → rerank →
                                    filter → GENERATE → cite → eval ]
                                                ▲
                          DocsMind's one shipped guardrail lives here:
                          "answer only from context, or say INSUFFICIENT_CONTEXT"
                          — that's a hallucination guardrail, NOT a security guardrail.
```

## Files in this folder

| File | What it covers |
|------|----------------|
| [five-problems.md](five-problems.md) | PII, prompt injection, jailbreaks, RBAC, moderation — what each is and how each is solved differently |
| [code-seams.md](code-seams.md) | The exact insertion points in `pipeline.py` and `retriever.py`, and the config-toggle pattern |
| [red-team-validation.md](red-team-validation.md) | Guardrail cost, severity classes, why injection has no complete fix, and how you'd prove any of it works |

## 🎯 Interview Q&A

**Q: What's the difference between DocsMind's `INSUFFICIENT_CONTEXT`
guardrail and a security guardrail?**
One stops the model from inventing facts (faithfulness). The other stops
malicious input from manipulating or extracting data from the system.
Different failure modes, different fixes.

**Q: Why can't you rely on the LLM to enforce document permissions?**
The model knows nothing about your access-control system. Only your
retrieval code can filter candidates before they reach the prompt. Asking
nicely in the system prompt is not access control.

**Q: What's RAG's specific injection risk that a plain chatbot doesn't have?**
Untrusted content can enter through *retrieved chunks*, not just the user's
message. The attack surface is anything that gets concatenated into context
— including your own corpus, the moment ingestion accepts unvetted
documents.

**Q: What's the difference between prompt injection and a jailbreak?**
Injection hides instructions inside content the model *reads* (a chunk, a
webpage, a tool result). A jailbreak is the *user themselves* trying to
talk the model out of its instructions. Different entry points, different
defenses.

## Code

[docsmind/pipeline.py](../../docsmind/pipeline.py) — `SYSTEM_PROMPT` and
`_build_context()`, the two seams most defenses attach to.
[docsmind/retrieval/retriever.py](../../docsmind/retrieval/retriever.py) —
where an RBAC filter must live.

→ Next: **[19-fine-tuning/README.md](../19-fine-tuning/README.md)**
