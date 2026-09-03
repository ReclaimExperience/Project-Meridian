# ADR-018 — Amends ADR-017: measurement protocol, two-tier gating, budget re-set, OSK rework

**Status:** Accepted
**Amends:** ADR-017
**Source:** owner decision, 2026-09-03, on the evidence in issue #32

---

**Decision:**

1. **Protocol.** The product metric is the **median of 3 consecutive protocol
   runs** (2-minute settle each). All three values are recorded, not just the
   median. Applies to product and CI measurements alike.

2. **Budget (absolute, blocking).** `ram.idle.product` = **1200 MiB**, target
   **1100**. Basis: the measured post-trim floor — mean 1139.9, median 1123.1
   from runs 1123.1 / 1122.4 / 1174.1 on 2026-09-03 — plus one observed
   noise-spread of headroom. The former **950 target is reclassified as an
   aspiration**, contingent on clause 5's investigation list; it predates
   GPU-measured evidence. `ram.idle.ci` remains `product + offset` computed per
   ADR-017 clause 2, and the fresh paired offset **186.5 MiB** is adopted here
   with its provenance. CI gate is therefore **1386.5 MiB**.

3. **Regression ratchet (relative, sensitive).** CI additionally records the
   summed userspace-PSS statistic. Post-trim baseline ≈ **576 MiB**; the rolling
   baseline is the median of the last 10 main-branch nightly runs. A PR that
   raises it by **more than 25 MiB** over baseline fails until the delta is
   explicitly acknowledged in the PR with a reason. **This, not the absolute
   gate, is the creep detector.**

4. **Anti-ratchet.** The absolute budget changes only by ADR, with measured floor
   provenance, exactly as this one does. Floor-versus-gate drift is reviewed at
   every M-gate.

5. **Commissioned investigation** (S-size, knowledge only, gates nothing):
   Xwayland on-demand feasibility `[VERIFY kwin support]`, a kded module audit,
   and KRunner preload. This is the legitimate path toward the 1100 target.

6. **OSK trim rework** — supersedes the mechanism shipped on 2026-09-03:
   - **session-scope configuration only.** The greeter never reads it, and
     `/etc/xdg/kwinrc` is never written.
   - **enable is eager and sticky** on any touchscreen appearance, including
     hotplug — udev-triggered, recorded by a marker under `/var/lib`.
   - **disable is lazy.**
   - user control **"On-screen keyboard: Automatic / Always / Off"** on the
     Appearance page, pointer-reachable, and **not** behind the Advanced auth
     gate.
   - **no boot-time writes to `/etc`.**
   - Ships to `:testing` on structural greeter safety. A touch-equipped seat
     joins the §10.2 **mandatory** matrix, and its verification gates `:stable`
     for this feature.

7. **STATUS.** Idle-RAM acceptance is recorded as **MET** only after the reworked
   trim ships and a fresh median-of-3 passes clause 2's gate. The 2026-09-03
   marginal result stands as correctly unrecorded.

**Why:** ADR-017 fixed *what* is measured and left *how often* undefined, so a
single run with ~50 MiB of noise decided a gate with under 4 MiB of headroom —
a coin flip in both directions. And the budget it inherited (1126) predated any
GPU-measured evidence: it was a proxy number carried forward, not a floor
anybody had observed. Setting the gate from a measured floor plus one noise
spread makes it a real line; keeping the aspiration separate keeps the ambition
honest rather than pretending the gate encodes it.

The absolute gate is deliberately slack, which is why clause 3 exists. A budget
loose enough not to be a coin flip is also loose enough to hide 60 MiB of creep,
so the sensitive detector is relative and the blocking one is absolute. They
catch different failures and neither substitutes for the other.

Clause 6 exists because the shipped trim wrote a **system-wide** KConfig default,
which the greeter's own kwin also reads. On a machine whose digitizer is detected
late — or attached after boot — that combination could suppress the on-screen
keyboard at the login screen, where the failure mode is not an awkward session
but an owner who cannot type their password. Session scope removes the greeter
from the blast radius entirely, and eager-and-sticky enable means the answer to
"is there a touchscreen" only ever has to be *yes* once.

**Consequences:**

- A product measurement costs three boots. That is acceptable because it is not a
  per-PR cost; the CI tripwire keeps its slack by construction.
- Recording all three values means a marginal build is visible as marginal, rather
  than as whichever single number happened to land.
- Clause 3 introduces the first gate that can be passed by *explaining* rather
  than by fixing. That is intentional — creep is sometimes justified — but it
  means the acknowledgement text is part of the record and should say what was
  bought, not merely that someone noticed.
- The 950 aspiration no longer gates anything. If clause 5's investigation finds
  nothing, saying so is the honest outcome; the aspiration should then be revised
  by ADR rather than left standing as decoration.
