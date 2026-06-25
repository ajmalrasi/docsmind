# 06 — Generation

**The big idea:** After FAISS returns the top-k chunks, the pipeline turns
them into a grounded answer. It formats the chunks as numbered passages, sends
them to Claude with a strict system prompt, parses the citations from the
response, and checks whether the answer is grounded or not.

## Files in this folder

| File | What it covers |
|------|----------------|
| [building-context.md](building-context.md) | How chunks become numbered `[1][2][3]` passages |
| [system-prompt.md](system-prompt.md) | Why the prompt is designed the way it is |
| [claude-generates.md](claude-generates.md) | What Claude does with the context |
| [citation-extraction.md](citation-extraction.md) | How `[n]` markers are parsed and mapped back to source files |
| [guardrail.md](guardrail.md) | `INSUFFICIENT_CONTEXT` — what it is, limits, and what Phase 5 improves |

## 🎯 Interview Q&A

**Q: Why not just send the raw chunks to Claude without numbering them?**
The numbers are what make citations possible. Claude is instructed to cite
every claim with `[n]`. After generation, the pipeline scans the response for
those markers and maps each back to the source filename and similarity score.
Without numbered passages, you'd get an answer but no traceability.

**Q: How do you prevent hallucination?**
Two layers: (1) the system prompt tells Claude to answer only from the numbered
passages and return `INSUFFICIENT_CONTEXT` if they're not enough; (2) the
pipeline checks the response and sets `grounded=false` if that string appears.
These are soft guardrails — they rely on the model following instructions.
Phase 5 (LangGraph) adds a structural guardrail. Phase 6 (RAGAS) measures
hallucination rate systematically on an eval set.

**Q: What happens if Claude ignores the system prompt and answers from memory?**
The Phase 1 guardrail won't catch it — it only checks for `INSUFFICIENT_CONTEXT`
in the response text. A harder approach: compare the answer against the retrieved
chunks using an LLM judge (a second model call that scores faithfulness). That's
part of Phase 6's RAGAS evaluation.

**Q: Why is the system prompt a system message and not part of the user message?**
Claude gives higher weight to the system message for role definition and
behavioral constraints. Putting "answer only from context" in the system message
makes it a persistent rule for the conversation, not just a one-off instruction
the model might deprioritize. It also keeps the user message clean — just
context + question.

**Q: What is the latency breakdown?**
```
Embed question:   ~20ms  (bge-small on CPU)
FAISS search:     ~1ms
Build context:    <1ms
Claude API call:  ~700ms  ← dominates
Citation parse:   <1ms
Total:            ~720ms
```
The LLM API call is always the bottleneck. To reduce: use claude-haiku-4-5
(faster, cheaper), reduce max_tokens, or stream the response so the user
sees partial output while generation continues.

## Code
[docsmind/pipeline.py](../../docsmind/pipeline.py)
[docsmind/llm/cloud_client.py](../../docsmind/llm/cloud_client.py)
[docsmind/llm/base.py](../../docsmind/llm/base.py)

→ Next: **[07-full-pipeline/README.md](../07-full-pipeline/README.md)**
