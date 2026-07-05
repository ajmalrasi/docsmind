# The Roadmap Case — Fixing Tool Calls, in Cost Order

**TL;DR:** DocsMind's planned open-model swap will break tool-call
reliability. The fix path is a strict cost ladder: prompting → constrained
decoding → QLoRA fine-tuning. Stating that order — and measuring each rung —
is itself the interview signal.

## The concrete scenario

Swap DocsMind's agentic tool calling (see
[12-tool-calling](../12-tool-calling/reliability-and-security.md)) from a
closed model to an open one on the beast GPU. Watch tool-call reliability
regress — schema drift, malformed arguments. Then fix it in a specific
**cost order**:

```
regression detected: tool-call validity 99% → 81% after model swap
        │
   1. prompting          hours   few-shot examples, tighter tool descriptions
        │ not enough?
   2. constrained        days    Outlines/XGrammar — invalid JSON becomes
      decoding                   *impossible* at the token level
        │ still short?
   3. QLoRA fine-tune    weeks   needs a training set of correct tool calls,
                                 GPU time, before/after eval
```

1. **Prompting changes first.** Cheapest to try. Few-shot examples of
   correct calls in the system prompt, tighter tool descriptions,
   explicit format warnings.
2. **Constrained decoding via Outlines/XGrammar.** Forces valid JSON
   structurally — the sampler literally cannot emit a token that would
   break the schema. No retraining needed. Fixes *malformed* output
   entirely; can't fix *wrong-tool* or *wrong-argument-value* choices.
3. **QLoRA fine-tuning on tool-call examples.** Last resort, only if the
   first two don't close the gap — typically when the model picks wrong
   tools or hallucinates argument values, which are judgment failures, not
   format failures.

That last distinction is worth having ready: constrained decoding fixes
**form**, fine-tuning fixes **judgment**. If validity is low because of
malformed JSON, step 2 ends the story. If the JSON is valid but the calls
are wrong, only step 3 (or a bigger model) changes the behavior.

## Why the ordering is itself the signal

Fine-tuning is expensive to iterate on: it needs a training set, GPU time,
and before/after evaluation. It's the tool you reach for after cheaper
fixes are exhausted — never the first move. An interviewer hearing
"we fine-tuned" wants the next sentence to be "after prompting and
constrained decoding plateaued at X%," not "because it seemed powerful."

## How you'd validate the fine-tune helped

Same eval discipline as everywhere else in this project: before/after on a
held-out task set, measuring the *specific* behavior targeted —
tool-call JSON validity rate, right-tool rate, first-try success rate.
Not "it feels better."

| Metric | Closed model | Open, raw | + prompting | + constrained | + QLoRA |
|---|---|---|---|---|---|
| JSON validity | 99% | 81% | 88% | **100%** (by construction) | 100% |
| Right tool chosen | 97% | 84% | 89% | 89% | measure → |
| First-try success | 96% | 70% | 79% | 87% | measure → |

(Illustrative numbers — the roadmap's whole point is to produce the real
ones on the beast and write them up. That before/after table *is* the
Auric entry-gate bullet: a non-trivial inference debug with a tool-call
regression.)

→ Next: **[20-production-monitoring/README.md](../20-production-monitoring/README.md)**
