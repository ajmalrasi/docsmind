# L2 Normalization — Step by Step

**TL;DR:** Divide each number in the vector by the vector's total length, so
the new length becomes exactly 1.0.

## The formula

Given a vector **v**, its L2 norm (length) is:

```
‖v‖ = √(v₁² + v₂² + v₃² + ... + vₙ²)
```

The normalized vector is:

```
v̂ = v / ‖v‖
```

Each element is divided by the total length.

---

## Worked example

**Original vector:**
```
v = [1.0, 2.0, 3.0]
```

**Step 1 — Calculate the length:**
```
‖v‖ = √(1.0² + 2.0² + 3.0²)
    = √(1.0 + 4.0 + 9.0)
    = √14.0
    ≈ 3.742
```

**Step 2 — Divide each element by the length:**
```
v̂ = [1.0/3.742,  2.0/3.742,  3.0/3.742]
   = [0.267,      0.535,      0.802]
```

**Step 3 — Verify the new length is 1.0:**
```
‖v̂‖ = √(0.267² + 0.535² + 0.802²)
     = √(0.071 + 0.286 + 0.643)
     = √1.000
     = 1.0  ✓
```

---

## What changed and what didn't

| Property | Before | After |
|----------|--------|-------|
| Values | [1.0, 2.0, 3.0] | [0.267, 0.535, 0.802] |
| Length | 3.742 | 1.0 |
| Direction | same | same ← this is what matters |

The *direction* of the vector — which encodes meaning — is unchanged.
Only the *scale* is removed.

---

## Why "L2"?

L2 refers to the **L2 norm** (also called Euclidean norm) — square root of the
sum of squared elements. The "2" means we square each element.

There's also an L1 norm (sum of absolute values) but L2 is standard for
embeddings because it corresponds to the Euclidean distance most people
intuitively understand.

→ Next: **[why-length-1.md](why-length-1.md)**
