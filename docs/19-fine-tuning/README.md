# 19 — Fine-Tuning: When RAG Isn't the Right Tool (concept, roadmap)

**The big idea:** RAG — everything else in this repo — changes what the
model *sees at query time*. Fine-tuning changes what's *baked into its
weights*. RAG fixes knowledge problems; fine-tuning fixes behavior problems.
"Fine-tuning is RAG but better" is the honest-answer trap most candidates
fall into.

**Where in the pipeline:** the one topic that lives **outside** the
Ingest→...→Eval pipeline entirely. Fine-tuning changes the *model itself*.
The result then drops into `LocalLLMClient` in
[`local_client.py`](../../docsmind/llm/local_client.py) like any other
model, via `model: str`.

```
RAG (what DocsMind does):     frozen model + retrieved context at query time
fine-tuning (not done here):  same query-time prompt, but different weights
                               baked in ahead of time via extra training
```

## Files in this folder

| File | What it covers |
|------|----------------|
| [rag-vs-fine-tuning.md](rag-vs-fine-tuning.md) | Knowledge problems vs behavior problems — which tool fixes which |
| [lora-qlora-peft-rlhf.md](lora-qlora-peft-rlhf.md) | Four conflated terms untangled, and the memory math that makes QLoRA matter |
| [tool-call-fix-path.md](tool-call-fix-path.md) | The roadmap's concrete case: fixing open-model tool calls, in cost order |

## 🎯 Interview Q&A

**Q: Why do most fine-tuning projects fail?**
Bad or insufficient training data — and, just as often, using fine-tuning
on a *knowledge* problem that RAG would have solved more cheaply, without
retraining.

**Q: When would you fine-tune instead of using RAG or prompt engineering?**
When the gap is a *behavior* — format compliance, tool-call reliability,
domain style — that persists no matter what you put in the prompt. And only
after cheaper fixes (prompting, constrained decoding) were tried and
measured as insufficient.

**Q: What's the mechanical difference between LoRA and QLoRA?**
LoRA trains small low-rank adapter matrices on a frozen full-precision
base. QLoRA does the same on a *quantized* (typically 4-bit) frozen base —
cutting memory enough to fine-tune much larger models on consumer GPUs.

**Q: How do you know a fine-tune helped?**
Before/after on a held-out task set, measuring the *specific* behavior you
targeted — e.g. tool-call JSON validity rate. Not "it feels better."

## Code

[docsmind/llm/local_client.py](../../docsmind/llm/local_client.py) — where
a fine-tuned model drops in, via `model: str`. No other code changes.

→ Next: **[20-production-monitoring/README.md](../20-production-monitoring/README.md)**
