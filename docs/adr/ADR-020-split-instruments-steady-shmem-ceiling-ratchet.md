# ADR-020 — Supersedes ADR-019 §§0–3 (never adopted, per its own trigger): split instruments

**Status:** Accepted
**Supersedes:** ADR-019 §§0–3. Amends ADR-018 §2.
**Source:** owner decision, 2026-09-03, on the instrumented breakdown in issue #32

---

**Decision:**

1. **Three instruments, three natures.** Every run still records everything.

   **a. `steady`** = `AnonPages + SUnreclaim + KernelStack + PageTables`. A tight
   absolute gate, median of 3 full boots. Derived from the instrumented set
   (757.4 / 766.7 / 762.6 — median 762.6, spread 9.3):

   ```
   gate   = round_up_25(median + 2 × spread) = round_up_25(781.2) = 800 MiB
   target = round_up_25(median + 1 × spread) = round_up_25(771.9) = 775 MiB
   ```

   **b. `shmem` ceiling** = **250 MiB** — `round_up_25` of twice the observed
   maximum (117.8). Sampled as the **minimum over a 60 s post-settle window**,
   because the thing worth bounding is the *resting* pool, not a transient peak
   that happened to coincide with a sample. Provisional pending §4, and
   renderer-agnostic pending §3's pair.

   **c. `ratchet`** — unchanged. Userspace PSS, 576 + 25, against the rolling
   baseline. Quiet at 573.4.

   `MemTotal − MemAvailable` and total committed are recorded per run,
   **informational, gating nothing**. ADR-018's 1200 retires with this adoption.

2. **Acceptance hygiene.** The numbers above are *derived from* the run set that
   produced them, so acceptance may **not** be declared on that set. One fresh
   median-of-3 under this ADR closes ADR-018 clause 7 **iff** `steady` ≤ 800,
   `shmem`-min ≤ 250, and the ratchet is quiet. Expected headroom ≈ 37 MiB against
   a ≈ 9 MiB spread — **decisive in both directions, which is the property every
   prior gate lacked.**

3. **Offset:** re-paired once in the `steady` denomination (GPU/llvmpipe); the CI
   gate remains a computed sum, never a literal. The shmem ceiling applies
   unadjusted on both renderers unless the paired run shows a systematic gap, in
   which case it gets its own pair.

4. **Run-1's 117.8 outlier** — first-boot behaviour vs an unsettled pool vs
   bimodality — is queued as S-size and non-gating, beside ADR-018 §5's
   investigation list. Its answer may tighten §1b later; it blocks nothing now.

5. **ADR-019's executed dispositions stand:** WP-02 closed under waiver (resolved
   by §2's fresh run), WP-04 authorized, the WP-12 row + issue #33 + ZT-23
   recorded.

**Why:** the previous three budgets all shared one defect — a single number tried
to bound quantities with different natures, and inherited the worst behaviour of
whichever term was noisiest. `MemTotal − MemAvailable` mixed reclaimable cache
into the claim. Total committed then mixed a transient graphics buffer pool into
process memory, which is why ADR-019's own trigger rejected it: committed's 59.2
MiB spread *was* Shmem's 64.4, while every other term held to under 1 MiB.

Splitting them lets each be gated the way its nature allows. Process memory is
stable to ±9.3 MiB and can carry a tight gate that means something. The buffer
pool is not stable and never will be, so it gets a ceiling rather than a budget,
and is sampled at its floor so the number describes the resting state.

**Consequences:**

- The absolute gate finally has headroom several times its own noise. A failure
  now means something changed, and a pass means it did not — neither was true of
  1126, 1200, or the committed denomination.
- Three instruments is more to explain than one. That is the cost of the previous
  three being wrong in the same way.
- The shmem ceiling is deliberately loose (2× observed max). It is a tripwire
  against a genuine buffer-pool regression, not a budget anyone should tune
  against. §4 may tighten it once the outlier is understood.
- `MemTotal − MemAvailable` keeps being recorded because it is what `free` shows
  and what a user would quote back to us. It is the number in the conversation
  even though it is not the number in the gate.
