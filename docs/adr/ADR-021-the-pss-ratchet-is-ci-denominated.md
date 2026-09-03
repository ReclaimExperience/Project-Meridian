# ADR-021 — Amends ADR-018 §3: the PSS ratchet is CI-denominated

**Status:** Accepted
**Amends:** ADR-018 §3
**Source:** owner decision, 2026-09-03, on the paired run in issue #32

---

**Problem:** ADR-018 §3 seeded the ratchet at 576 MiB, which was **GPU-measured**.
The ratchet runs in CI, which is **llvmpipe**, and llvmpipe's software-render cost
is anonymous memory that PSS counts. A healthy build reads ~755, so the ratchet
fires at +179 on every pull request. This is the same
one-renderer-baseline / other-renderer-measurement error ADR-017 fixed for idle
RAM, reappearing one instrument over.

**Decision:**

1. **The ratchet is a CI/llvmpipe instrument and its baseline is
   llvmpipe-denominated.** Interim seed = **755.3 MiB** (measured llvmpipe, paired
   with GPU 574.0; build and date recorded). Once ≥ 10 main-branch nightly runs
   exist, the baseline becomes the **rolling median of the last 10, measured
   directly in CI** — the seed retires and **no offset persists**.

2. **Threshold unchanged at +25 MiB.** It is a *delta*, and denomination-
   independent to first order: real creep — a new resident service — adds the same
   anonymous memory under both renderers, and llvmpipe's overhead cancels in the
   subtraction.

3. **GPU PSS 574.0 is retained as informational, and as the M-gate pairing check
   only.** It does not gate per-PR, because no per-PR GPU runs exist. If per-build
   GPU perf is ever added it gets its **own** GPU baseline — the two are **never
   cross-compared**.

4. **Re-pair at each M-gate.** A shift of more than 25% in the llvmpipe − GPU gap
   is itself a finding (a rendering-stack change) to investigate before adoption —
   ADR-020 §3's discipline applied to this instrument.

**Why the asymmetry with the steady gate is deliberate.** `steady`'s CI gate stays
a computed sum (product + offset) *forever*, because its canonical value is the
GPU/product number and CI must always translate into it. The ratchet's canonical
value **is** the CI history — it is a relative detector of change over time in the
place it runs — so it is measured directly in its own denomination and the offset
is only a bootstrap. One instrument translates permanently; the other translates
once and then stops needing to.

**Consequences:**

- CI stops failing healthy builds, which is the immediate point. A gate that is
  red on every PR is worse than no gate: it trains people to merge past it, and
  then it is red on the one PR that mattered.
- The seed is explicitly temporary and the mechanism must retire it. A "temporary"
  constant with nothing arranged to remove it is permanent, so the rolling window
  is part of this decision rather than a follow-up.
- Because the baseline will be CI history, a slow collective drift across ten
  nightlies moves the baseline with it and the ratchet stops seeing it. That is the
  known limit of a rolling detector; the absolute `steady` gate is what catches
  the accumulation. Neither instrument substitutes for the other, which is why
  ADR-020 kept both.
