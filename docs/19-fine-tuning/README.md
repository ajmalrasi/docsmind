# Fine-tuning — when RAG isn't the right tool (concept, roadmap)

**Where in the pipeline:** this is the one topic that lives **outside** the Ingest→...→Eval pipeline entirely.
Fine-tuning changes the *model itself*.
The result then drops into `LocalLLMClient` in [`local_client.py`](../../docsmind/llm/local_client.py) like any other model, via `model: str`.

The whole topic in one contrast:
RAG — everything else in this repo — changes what the model *sees at query time*.
Fine-tuning changes what's *baked into its weights*.

```
RAG (what DocsMind does):     frozen model + retrieved context at query time
fine-tuning (not done here):  same query-time prompt, but different weights
                               baked in ahead of time via extra training
```

## When you'd reach for fine-tuning instead of RAG

The honest answer most candidates get wrong: **fine-tuning is not "RAG but better."**
It solves a different problem.

**RAG fixes knowledge problems.**
"The model doesn't know this fact." "This fact changed yesterday."
New knowledge is added by updating the index, not the model.
That's exactly why DocsMind re-ingests `data/sample_docs/` when the corpus changes, instead of retraining anything.

**Fine-tuning fixes behavior problems.**
"The model doesn't format / behave / reason the way I need — no matter what facts I give it."
Consistent tone. A rigid output schema. Domain jargon fluency.
And the concrete case in this project's own roadmap: **tool-call reliability**.
An open-weight model that keeps emitting malformed JSON for tool arguments isn't missing facts.
It's missing a *habit*. Better retrieval can't fix a habit.

Plain version: RAG hands the model better notes to read before answering.
Fine-tuning changes how the model learned to write in the first place.
If the problem is "it doesn't know X" — bring better notes.
If the problem is "it never writes X correctly no matter what notes you give it" — notes won't help. You have to retrain the habit.

## LoRA, QLoRA, PEFT, RLHF — four different things, often conflated

| Term | What it actually is |
|---|---|
| **PEFT** (Parameter-Efficient Fine-Tuning) | The umbrella category: adapt a model by training a *small* number of new parameters instead of all of them |
| **LoRA** (Low-Rank Adaptation) | One specific PEFT method: freeze the original weights, inject small trainable low-rank matrices alongside them, train only those |
| **QLoRA** | LoRA + a memory trick: the frozen base model is loaded **quantized** (usually 4-bit) during training. This is what makes fine-tuning a 70B-class model feasible on one consumer GPU |
| **RLHF** (Reinforcement Learning from Human Feedback) | Not a parameter-efficiency technique at all — a *training objective*: use human preference comparisons to train a reward model, then optimize the LLM against it. This is how base models become "aligned" chat models |

The relationships, in one breath:
LoRA is one way to do PEFT.
QLoRA is LoRA plus quantization.
RLHF is a different axis entirely — *what you optimize for*, not *how many parameters you touch*.
They're not mutually exclusive: LoRA-based RLHF and full-parameter RLHF both exist.

## Where fine-tuning would slot into DocsMind's roadmap

The concrete, already-identified case:
swap DocsMind's agentic tool calling (see [`12-tool-calling`](../12-tool-calling/README.md)) from a closed model to an open one on the beast GPU.
Watch tool-call reliability regress — schema drift, malformed arguments.
Then fix it in a specific **cost order**:

1. Prompting changes first. Cheapest to try.
2. Constrained decoding via Outlines/XGrammar. Forces valid JSON structurally — no retraining needed.
3. **QLoRA fine-tuning on tool-call examples.** Last resort, only if the first two don't close the gap.

That ordering is itself an interview signal worth stating explicitly.
Fine-tuning is expensive to iterate on: it needs a training set, GPU time, and before/after evaluation.
It's the tool you reach for after cheaper fixes are exhausted — never the first move.

## Trade-offs (the interview meat)

- **Fine-tuning needs a dataset good enough to teach the behavior.**
  Garbage or too-small training data is the single most common reason fine-tuning projects fail.
  No solid example set (and no cheap way to generate one)? Then you don't have a fine-tuning project yet.
- **Full fine-tuning vs LoRA/QLoRA is a memory/cost trade.**
  Full fine-tuning updates every parameter: highest quality ceiling, most GPU memory, and a full new checkpoint per fine-tune.
  QLoRA trains a tiny adapter on a quantized frozen base: fits on far smaller hardware, and multiple task-specific adapters can share one base model in memory.
  The price: a small quality ceiling cost versus full fine-tuning.
- **Fine-tuning doesn't compose with fresh knowledge the way RAG does.**
  A fine-tuned model's knowledge freezes at training time.
  Facts change weekly? Then you're re-fine-tuning weekly.
  Re-ingesting a document into an index is a much lighter update loop.
- **How you'd validate a fine-tune actually helped.**
  Same eval discipline as everywhere else in this project: before/after on a held-out task set, measuring the *specific* behavior you targeted — e.g. tool-call JSON validity rate.
  Not "it feels better."
  The Auric-roadmap plan calls for exactly this: a before/after tool-call success rate write-up.

## The interview signals

- **Why do most fine-tuning projects fail?**
  Bad or insufficient training data — and, just as often, using fine-tuning on a *knowledge* problem that RAG would have solved more cheaply, without retraining.
- **When would you fine-tune instead of using RAG or prompt engineering?**
  When the gap is a *behavior* — format compliance, tool-call reliability, domain style — that persists no matter what you put in the prompt.
  And only after cheaper fixes (prompting, constrained decoding) were tried and measured as insufficient.
- **What's the mechanical difference between LoRA and QLoRA?**
  LoRA trains small low-rank adapter matrices on a frozen full-precision base.
  QLoRA does the same on a *quantized* (typically 4-bit) frozen base — cutting memory enough to fine-tune much larger models on consumer GPUs.
