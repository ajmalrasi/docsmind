# LoRA, QLoRA, PEFT, RLHF — Four Different Things, Often Conflated

**TL;DR:** PEFT is the umbrella (train few parameters). LoRA is one PEFT
method (small adapter matrices on a frozen base). QLoRA is LoRA on a
*quantized* base (the consumer-GPU unlock). RLHF is a different axis
entirely — *what* you optimize, not *how many* parameters you touch.

## The four terms

| Term | What it actually is |
|---|---|
| **PEFT** (Parameter-Efficient Fine-Tuning) | The umbrella category: adapt a model by training a *small* number of new parameters instead of all of them |
| **LoRA** (Low-Rank Adaptation) | One specific PEFT method: freeze the original weights, inject small trainable low-rank matrices alongside them, train only those |
| **QLoRA** | LoRA + a memory trick: the frozen base model is loaded **quantized** (usually 4-bit) during training. This is what makes fine-tuning a 70B-class model feasible on one consumer GPU |
| **RLHF** (Reinforcement Learning from Human Feedback) | Not a parameter-efficiency technique at all — a *training objective*: use human preference comparisons to train a reward model, then optimize the LLM against it. This is how base models become "aligned" chat models |

The relationships, in one breath:
LoRA is one way to do PEFT.
QLoRA is LoRA plus quantization.
RLHF is a different axis entirely — *what you optimize for*, not *how many
parameters you touch*.
They're not mutually exclusive: LoRA-based RLHF and full-parameter RLHF
both exist.

```
     how many parameters?                what objective?
   ┌──────────────────────┐          ┌──────────────────────┐
   │ full fine-tune (all) │          │ supervised (SFT)     │
   │ PEFT (few)           │    ×     │ preference (RLHF/DPO)│
   │  └─ LoRA             │          └──────────────────────┘
   │      └─ QLoRA        │       any row pairs with any column
   └──────────────────────┘
```

## The memory math that makes QLoRA matter

Why full fine-tuning is out of reach on consumer hardware: training needs
the weights, the gradients, *and* optimizer state — roughly 4× the memory
of just running the model. A 7B model in fp16 is ~14 GB to *serve*; full
fine-tuning wants ~56 GB+. The beast's 3070 Ti has 8.

LoRA freezes the base (no gradients or optimizer state for it) and trains
adapters that are typically <1% of the parameters. QLoRA then shrinks the
frozen base itself to 4-bit:

| Approach | 7B model, approx. training memory | Fits 8GB? |
|---|---|---|
| Full fine-tune (fp16) | ~56+ GB | ❌ not close |
| LoRA (fp16 base, frozen) | ~16–20 GB | ❌ |
| QLoRA (4-bit base, frozen) | ~6–10 GB | ✅ borderline — 7B is realistic |

(Orders of magnitude, not exact numbers — the point is which side of 8 GB
each lands on.)

A bonus that matters in production: multiple task-specific LoRA adapters
can share one base model in memory. One 7B base + five 30 MB adapters
serves five specialized models for barely more than the cost of one.

## The trade-off

Full fine-tuning updates every parameter: highest quality ceiling, most
GPU memory, and a full new checkpoint per fine-tune. QLoRA trains a tiny
adapter on a quantized frozen base: fits on far smaller hardware. The
price: a small quality-ceiling cost versus full fine-tuning — usually
worth it, occasionally not, and only an eval can tell you which
(see [tool-call-fix-path.md](tool-call-fix-path.md)).

→ Next: **[tool-call-fix-path.md](tool-call-fix-path.md)**
