# Fine-tuning — when RAG isn't the right tool (concept, roadmap)

**Where in the pipeline:** this is the one topic that lives **outside** the
Ingest→...→Eval pipeline entirely — fine-tuning changes the *model itself*,
which then gets dropped into `LocalLLMClient` in
[`local_client.py`](../../docsmind/llm/local_client.py) exactly like any other
model, via `model: str`. RAG (everything else in this repo) changes what the
model *sees at query time*; fine-tuning changes what's baked into its
weights. That distinction is the whole topic.

```
RAG (what DocsMind does):     frozen model + retrieved context at query time
fine-tuning (not done here):  same query-time prompt, but different weights
                               baked in ahead of time via extra training
```

## When you'd reach for fine-tuning instead of RAG

The honest answer most candidates get wrong: **fine-tuning is not "RAG but
better."** It solves a different problem.

- **RAG fixes "the model doesn't know this fact / this fact changed
  yesterday."** New knowledge is added by updating the index, not the model —
  exactly why DocsMind re-ingests `data/sample_docs/` rather than retraining
  anything when the corpus changes.
- **Fine-tuning fixes "the model doesn't behave/format/reason the way I need,
  regardless of what facts it's given."** Consistent tone, a rigid output
  schema, a reasoning style, domain jargon fluency, or — the concrete case in
  this project's own roadmap — **tool-call reliability**: an open-weight model
  that keeps emitting malformed JSON for tool arguments isn't missing facts,
  it's missing a *behavior*, and no amount of better retrieval fixes that.

Plain version: RAG hands the model better notes to read from before it
answers. Fine-tuning changes how the model was trained to write in the first
place. If the problem is "it doesn't know X," bring better notes. If the
problem is "it never writes X correctly no matter what notes you give it,"
notes won't help — you have to retrain the habit.

## LoRA, QLoRA, PEFT, RLHF — four different things, often conflated

| Term | What it actually is |
|---|---|
| **PEFT** (Parameter-Efficient Fine-Tuning) | The umbrella category: adapt a model by training a *small* number of new parameters instead of all of them |
| **LoRA** (Low-Rank Adaptation) | A specific PEFT method: freeze the original weights, inject small trainable low-rank matrices alongside them, train only those |
| **QLoRA** | LoRA, plus the frozen base model is loaded in **quantized** (usually 4-bit) form during training — the trick that makes fine-tuning a 70B-class model feasible on a single consumer GPU |
| **RLHF** (Reinforcement Learning from Human Feedback) | Not a parameter-efficiency technique at all — a *training objective*: use human preference comparisons to train a reward model, then optimize the LLM against it. This is how base models become "aligned" chat models in the first place, orthogonal to LoRA/QLoRA/full fine-tuning as a *method* of doing it |

The relationship: LoRA is one way to do PEFT; QLoRA is LoRA plus a memory
trick; RLHF is a different axis entirely (what you're optimizing *for*, not
how many parameters you touch) — you could in principle do LoRA-based RLHF,
or full-parameter RLHF, they're not mutually exclusive categories.

## Where fine-tuning would slot into DocsMind's roadmap

The concrete, already-identified case: swapping DocsMind's agentic tool
calling (see [`12-tool-calling`](../12-tool-calling/README.md)) from a closed
model to an open one on the beast GPU, watching tool-call reliability
regress (schema drift, malformed arguments), and fixing it in a specific
**cost order**: prompting changes first (cheapest), then constrained decoding
via Outlines/XGrammar (forces valid JSON structurally, no retraining needed),
and only reaching for **QLoRA fine-tuning on tool-call examples** as the last
resort if the first two don't close the gap. That ordering — not jumping
straight to fine-tuning — is itself a signal worth stating explicitly in an
interview: fine-tuning is expensive to iterate on (needs a training set,
GPU time, evaluation before/after) and should be the tool you reach for after
cheaper fixes are exhausted, not the first move.

## Trade-offs (the interview meat)

- **Fine-tuning needs a labeled dataset good enough to teach the behavior** —
  garbage or too-small training data is the single most common reason
  fine-tuning projects fail. If you don't have (or can't cheaply generate) a
  solid example set, you don't have a fine-tuning project yet.
- **Full fine-tuning vs LoRA/QLoRA is a memory/cost trade, not just a size
  trade.** Full fine-tuning updates every parameter — most accurate ceiling,
  most GPU memory and storage (a full new checkpoint per fine-tune). QLoRA
  trains a tiny adapter on top of a quantized frozen base — fits on far
  smaller hardware, multiple task-specific adapters can share one base model
  in memory, at a small quality ceiling cost versus full fine-tuning.
- **Fine-tuning doesn't compose with fresh knowledge the way RAG does.**
  A fine-tuned model's knowledge is frozen at training time; if facts change
  weekly, you're re-fine-tuning weekly, which is a much heavier update loop
  than re-ingesting a document into an index.
- **How you'd validate a fine-tune actually helped:** the same eval discipline
  as everywhere else in this project — before/after on a held-out task set
  measuring the *specific* behavior you targeted (e.g. tool-call JSON validity
  rate), not a vague "it feels better." The Auric-roadmap plan explicitly
  calls for a before/after tool-call success rate write-up for exactly this
  reason.

## The interview signals

- **Why do most fine-tuning projects fail?** Bad or insufficient training
  data, and — just as often — using fine-tuning to solve a *knowledge* problem
  that RAG would have solved more cheaply and without retraining.
- **When would you fine-tune instead of using RAG or prompt engineering?**
  When the gap is a *behavior* (format compliance, tool-call reliability,
  domain style) that persists no matter what you put in the prompt or context
  — and only after cheaper fixes (better prompting, constrained decoding)
  have been tried and measured as insufficient.
- **What's the actual mechanical difference between LoRA and QLoRA?** LoRA
  trains small low-rank adapter matrices on a frozen full-precision base;
  QLoRA does the same but with the frozen base quantized (typically 4-bit),
  cutting the memory footprint enough to fine-tune much larger models on
  consumer-class GPUs.
