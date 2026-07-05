# Reliability and Security — Where the Real Work Is

**TL;DR:** the API plumbing is easy. The hard part is the model emitting
well-formed arguments that match your schema, every single time — and not
trusting those arguments just because they parsed.

## Reliability is the hard part, not wiring

The hard part is the model emitting well-formed arguments that match your
JSON schema, every single time, even for oddly-phrased questions.

Closed models are strong here. Open models often regress:

| Failure | What it looks like |
|---|---|
| Schema drift | Arguments that *almost* match — `"query_text"` instead of `"query"` |
| Malformed JSON | Truncated braces, single quotes, trailing commentary |
| Wrong tool | Calling `web_search` when the answer needed `retrieve` |
| Format collapse | The model narrates "I would call retrieve..." instead of emitting the structured call |

How you close that gap is the single highest-signal topic for an
inference/serving role. The fix path, in cost order:

1. **Prompting** — few-shot examples of correct calls, tighter tool
   descriptions. Cheapest; try first.
2. **Constrained decoding** — Outlines/XGrammar force the output to be valid
   JSON matching the schema, *structurally*, at the token level. The model
   literally cannot emit an invalid character. No retraining.
3. **Fine-tuning** on tool-call examples — last resort
   (see [19-fine-tuning](../19-fine-tuning/README.md)).

This exact regression — swap closed model for open model, watch tool calls
break, fix it, write up before/after success rate — is the roadmap's planned
Auric-target project on the beast GPU.

## The metric: tool-call success rate

Track it as its own metric, separate from answer quality.
Did the model call the *right* tool? With *valid* arguments? In *one* try,
not three? That metric is the one that breaks first when you swap models —
answer quality can look fine on easy questions while tool-call validity has
quietly dropped from 99% to 80%.

Same eval-first discipline as retrieval: build the labeled task set *before*
swapping models, or you'll have no baseline to measure the regression against.

## Security surface

The model now chooses what code runs, and with what arguments.
Any tool that touches the filesystem, a shell, or an external API needs its
own validation. **Never trust `response.tool_input` just because it matched a
schema** — a schema checks shape, not intent:

- `retrieve(query="...")` is harmless at any argument value.
- `code_exec(source="...")` is a remote-code-execution feature by design;
  it needs sandboxing, not just schema validation.
- Anything writing data needs an allowlist of what the model may touch.

And the arguments themselves can be attacker-influenced: a prompt-injected
chunk can steer the model into calling a tool with hostile arguments. The
full treatment of that attack surface is in
[18-llm-security](../18-llm-security/README.md).

→ Next: **[13-mcp/README.md](../13-mcp/README.md)**
