# ADR-017 — The idle-RAM budget is GPU-measured; CI gates via a calibrated offset

**Status:** Accepted
**Source:** owner decision, 2026-09-03, on the evidence in issue #32

---

**Decision:**

1. **`ram.idle.product` = 1126 MiB (target 950).** This is the definition of the
   PRD §1.5 metric. Measured **GPU-rendered**. The canonical seat is the §10.2
   low-end matrix row (4 GB RAM, integrated GPU), under the 2-minute-settle
   protocol. Until that machine exists, the owner's GPU-accelerated local VM is
   the interim calibration source, and is recorded as such.

2. **`ram.idle.ci` = `ram.idle.product` + `render_offset`.** A per-PR tripwire,
   measured exactly as today — the llvmpipe VM, no GPU. `render_offset` is an
   **empirical calibration constant, not a tunable.** `tests/perf/budgets.json`
   stores the product budget and the offset with its provenance (method, build
   id, Plasma and Mesa versions, date); the gate is **computed as the sum and
   never stored as a literal**, so it cannot be hand-edited without touching the
   provenance record. Effective CI gate today: **1308 MiB** (CI-equivalent
   target 1132).

3. **Recalibration:** at every M-gate, one paired measurement — same build, both
   renderers. The offset may only ever change to a newly measured pair. Drift of
   more than 25% between gates is itself a finding to investigate (a rendering
   stack change) before the new value is adopted. A real regression lands in
   both measurements equally, so it cannot hide inside the offset.

4. **Forbidden:** removing the on-screen keyboard or `xwaylandvideobridge` to
   satisfy any RAM gate. Both are persona capabilities — touch input, and screen
   sharing in X11 apps such as Zoom and Discord.

5. **Commissioned, as a legitimate trim and separate from this gate:** start the
   on-screen keyboard **conditionally on touchscreen presence** instead of
   resident-always. 72 MiB PSS at idle on a touchless desktop is real bloat by
   our own definition. The trim counts honestly in both measurements.
   *Acceptance:* the OSK still appears on touch hardware — a touch-equipped
   laptop is added to the §10.2 matrix for this.

**Why:** the budget's derivation — a 4 GB floor minus the browser's working set —
only makes sense GPU-measured. The VM number was always a proxy, and the PRD
conflated the two. Measurement showed the gap between them is 182 MiB, which is
larger than every candidate saving combined: the product was never ~300 MiB over
budget, it was 116 MiB over a budget measured through the wrong lens.

**Consequences:**

- PRD §1.5's metric row and `tests/perf/idle_ram.sh` gain the two names, so
  "idle RAM" can no longer mean two different numbers in the same sentence.
- A CI run that is green proves only that the tripwire held. Product conformance
  is claimed **only** from a GPU-rendered measurement.
- The offset is a standing admission that CI does not measure the product. It
  earns its place by being cheap and by catching regressions early; it is not
  evidence for a release claim.
- If the rendering stack changes materially — a Mesa or Plasma major, or virgl
  behaviour — the offset is wrong until re-measured, and clause 3's drift check
  is the thing that catches it.

**Naming note.** This ADR says "maliit (OSK)". Fedora 44 / Plasma 6.7 does not
ship maliit: the on-screen keyboard is `plasma-keyboard`, backed by
`qt6-qtvirtualkeyboard`. The protection in clause 4 is implemented against the
packages that are actually installed, under `protect:` in `os/packages.yml`,
because a rule naming a package that does not exist protects nothing — the same
defect this project already hit when `sddm` sat in that list after Fedora had
replaced it with plasmalogin.
