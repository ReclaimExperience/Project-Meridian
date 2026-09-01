## WP-NN — <what this slice delivers>

Closes part of #<tracking issue>. Governing ADRs: <list>.

### Acceptance checklist (copied verbatim from the PRD — PRD 14.2 item 2)

> Paste your WP's Acceptance list here as checkboxes, unedited. This is your
> definition of done, and nobody moved it while you slept.

- [ ] ...

### Evidence

> A claim without pasted evidence is not done (PRD 14.2 item 5). Paste the
> commands you ran and their output.

```text

```

### `[VERIFY]` items touched

> For each one: the exact command, its output, and the decision it drove.
> If a `[VERIFY]` failed, say which fallback you took and why (PRD 0.2).

| Item | Command | Result | Decision |
|---|---|---|---|

### Deviations from the spec

> Honest list, or "none". A deviation recorded here is fine; a deviation
> discovered later by someone else is not.

### STATUS.md

- [ ] Updated per PRD 6.4, including Deviations and Open threads.

### Rule check (PRD 14.3)

- [ ] **R-A** Green or honest — no failing, flaky or skipped tests. Flaky = broken.
- [ ] **R-B** No hand-fixes in a VM. A clean rebuild reproduces everything here.
- [ ] **R-C** Smallest true change — no drive-by bumps, no "while I was here".
- [ ] **R-D** No plumbing leaks into user-visible strings (PRD 4.5); INV-0 holds.
- [ ] **R-E** Budgets unmoved (RAM / boot / ISO / perf). I did not edit a gate.
- [ ] **R-F** Any screenshot re-baseline is its own commit with a STATUS.md note.
- [ ] **R-G** Config > patch > fork. Any patch carries its `.md` justification.
- [ ] **R-H** Owner-gated paths (polkit, signing, packages.yml removals, ci/, ADRs)
      either untouched, or CODEOWNERS review requested.

---

### Reviewer (a different agent session — PRD 14.5)

- [ ] I ran the acceptance list **independently**, not just read it.
- [ ] Clean rebuild reproduces the result (hunting for R-B violations).
- [ ] No baseline was fudged to go green (R-F).
- [ ] STATUS.md is honest about what did not land.

**Verdict:** APPROVE / CHANGES REQUESTED / ESCALATE
