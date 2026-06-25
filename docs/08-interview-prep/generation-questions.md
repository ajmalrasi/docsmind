# Generation — Interview Questions

## Q: Why format chunks as numbered passages [1][2][3]?

The numbers are the citation mechanism. Claude is instructed to cite every
claim with `[n]`. After generation, the pipeline scans the response with a
regex (`\[(\d+)\]`), extracts the markers, and maps each one back to the
retrieved chunk — giving you source filename, similarity score, and a text
snippet. Without numbers, you'd get an answer but no traceability.

---

## Q: Why put the rules in the system prompt instead of the user message?

Claude assigns higher weight to the system message for behavioral constraints —
it's treated as a persistent role definition for the conversation. Instructions
like "answer only from context" and "cite with [n]" belong there, not buried
in the user message alongside the context and question. The user message stays
clean: just context + question.

---

## Q: What is INSUFFICIENT_CONTEXT and why use an exact string?

It's a sentinel value — a specific string the pipeline watches for in Claude's
response to detect when the retrieved context wasn't enough to answer.

```python
INSUFFICIENT = "INSUFFICIENT_CONTEXT"
grounded = INSUFFICIENT not in answer
```

It must be an exact string because the check is a substring search. If Claude
paraphrases ("I don't have enough information..."), the check misses it and
incorrectly marks the answer as grounded. Using the same constant `INSUFFICIENT`
in both the system prompt and the check ensures they can never drift apart.

---

## Q: What are the limits of this guardrail?

It's a soft guardrail — it works if Claude follows the system prompt.
Three ways it can fail:
1. Claude paraphrases instead of the exact string → check misses it
2. Claude answers from training memory (ignores "ONLY from context") without
   flagging it → undetected hallucination
3. Claude cites `[1]` but passage `[1]` doesn't actually support the claim
   → citation extracted but not verified

Phase 5 (LangGraph) adds a structural check — a second model call that verifies
each claim against its cited passage. Phase 6 (RAGAS) measures faithfulness
systematically on a golden eval set.

---

## Q: Why direct Anthropic SDK and not LangChain?

Direct SDK gives full control over every API parameter — system message,
max_tokens, streaming, prompt caching. No hidden retry logic or routing.
Simpler to debug. LangChain's `ChatAnthropic` is a convenience layer that's
useful when you need its ecosystem (chains, tool calling, callbacks) but adds
opacity for a simple generate() call. The `LLMClient` abstract interface means
the pipeline doesn't care what's underneath — Phase 4 swaps in a local vLLM
client without touching the pipeline.

---

## Q: What happens if Claude cites [7] when only 4 passages were provided?

The citation extractor bounds-checks every marker:

```python
cited_markers = {m for m in cited_markers if 1 <= m <= len(results)}
```

`[7]` is out of range and silently dropped. The answer still gets returned,
just without a citation for that marker. It's a guard against the model
hallucinating passage numbers.

---

## Q: How does latency break down and what's the bottleneck?

```
Embed question:   ~20ms  (bge-small CPU)
FAISS search:     ~1ms
Build context:    <1ms
Claude API:       ~700ms  ← bottleneck — always
Citation parse:   <1ms
Total:            ~720ms
```

The LLM API call dominates. To reduce: use claude-haiku-4-5 (3–5× faster
than Opus, much cheaper), reduce max_tokens, or add streaming so the user
sees partial output while generation continues.

---

## Q: How does streaming change the architecture?

With streaming, the Anthropic SDK returns tokens as they're generated. The
FastAPI endpoint uses `StreamingResponse` to forward them to the client. The
tradeoff: you can't do citation extraction until the full response is received,
so you'd either (a) stream the answer first and send citations after, or (b)
wait for the full response (no streaming) but you get citations inline. Phase 1
takes option (b) — wait for full response, then extract citations.
