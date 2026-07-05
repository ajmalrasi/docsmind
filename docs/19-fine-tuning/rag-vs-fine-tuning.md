# RAG vs Fine-Tuning — Knowledge Problems vs Behavior Problems

**TL;DR:** RAG fixes "the model doesn't know this." Fine-tuning fixes "the
model doesn't *behave* this way, no matter what I tell it." Choosing between
them starts with classifying which problem you actually have.

## Two different problems

**RAG fixes knowledge problems.**
"The model doesn't know this fact." "This fact changed yesterday."
New knowledge is added by updating the index, not the model.
That's exactly why DocsMind re-ingests `data/sample_docs/` when the corpus
changes, instead of retraining anything.

**Fine-tuning fixes behavior problems.**
"The model doesn't format / behave / reason the way I need — no matter what
facts I give it."
Consistent tone. A rigid output schema. Domain jargon fluency.
And the concrete case in this project's own roadmap: **tool-call
reliability**. An open-weight model that keeps emitting malformed JSON for
tool arguments isn't missing facts. It's missing a *habit*. Better
retrieval can't fix a habit.

Plain version: RAG hands the model better notes to read before answering.
Fine-tuning changes how the model learned to write in the first place.
If the problem is "it doesn't know X" — bring better notes.
If the problem is "it never writes X correctly no matter what notes you
give it" — notes won't help. You have to retrain the habit.

## The decision table

| Symptom | Problem class | Right tool |
|---|---|---|
| Wrong or missing facts | knowledge | RAG — update the index |
| Facts go stale weekly | knowledge, recurring | RAG — re-ingest is a light loop |
| Ignores format instructions intermittently | behavior, mild | prompt engineering first |
| Malformed JSON/tool calls persistently | behavior, structural | constrained decoding, then fine-tuning |
| Wrong tone/style for the domain | behavior | fine-tuning (if prompting plateaued) |
| Both wrong facts *and* wrong style | both | RAG **and** fine-tuning — they compose |

That last row matters: RAG and fine-tuning are not rivals. A fine-tuned
model can sit behind the same retrieval pipeline — the fine-tune fixes how
it writes, retrieval fixes what it knows.

## Why fine-tuning doesn't substitute for RAG

A fine-tuned model's knowledge freezes at training time.
Facts change weekly? Then you're re-fine-tuning weekly — a training run,
an eval pass, and a redeploy per update. Re-ingesting a document into an
index is a much lighter update loop: seconds, no GPU, no eval regression
risk.

There's also an attribution problem: RAG can *cite* the chunk an answer
came from (DocsMind's inline `[1][2]` citations). Weights can't cite.
For any application where "where did this claim come from?" matters,
fine-tuned knowledge is a liability, not a feature.

## Why fine-tuning projects fail

The single most common reason: **the training data isn't good enough to
teach the behavior.** Garbage or too-small example sets. No solid example
set (and no cheap way to generate one)? Then you don't have a fine-tuning
project yet — you have a data-collection project.

The second most common: fine-tuning a knowledge problem RAG would have
solved for a fraction of the cost. Classify the problem first; the table
above is the whole method.

→ Next: **[lora-qlora-peft-rlhf.md](lora-qlora-peft-rlhf.md)**
