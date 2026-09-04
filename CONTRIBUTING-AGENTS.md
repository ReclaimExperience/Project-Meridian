# Agent operating rules — the contract

> Copied verbatim from `docs/PRD.md` §14 at WP-00. The PRD is authoritative;
> this file exists so an agent can read the contract without loading the whole PRD.

---

## Agent operating rules (the contract — copied to CONTRIBUTING-AGENTS.md at WP-00)

### 14.1 Identity & scope
You are one agent executing exactly one work package (or one clearly-named slice of an L-size WP). You do not refactor beyond your WP, "improve" other WPs' output, or edit ADRs/PRD. Curiosity goes in STATUS.md notes, not commits.

### 14.2 Session protocol
1. Read §0 → §14 → your WP → its Governing ADRs → STATUS.md → your WP's Inputs (as defined in §0.1 item 5). Nothing else initially.
2. Restate (in your PR description) your WP's acceptance list as a checklist. This is your definition of done; nobody moved it while you slept.
3. Work in branch `wp/<nn>-<slug>`. Commit early/small; message format per 6.2.
4. **Verify-then-use** every `[VERIFY]` you touch; paste evidence (command + output) into the PR.
5. Run your acceptance commands yourself before declaring done; paste outputs. A claim without pasted evidence is not done.
6. Update STATUS.md per 6.4 (including honest Deviations and Open threads). Close with the PR link in your WP's tracking issue.

### 14.3 The prime rules
- **R-A: Green or honest.** Never mark done with failing/flaky/skipped tests. Flaky = broken; fix or escalate.
- **R-B: If you fixed it by hand in a VM, you fixed nothing.** Every fix lands as repo files that produce the fix on a clean build (7.1).
- **R-C: Smallest true change.** No drive-by dependency bumps, no framework swaps, no "while I was here".
- **R-D: The user never sees your plumbing.** Strings per 4.5; no jargon leaks; INV-0 above all.
- **R-E: Budgets are laws.** RAM/boot/ISO/perf gates fail = your change shrinks or escalates; never edit the gate.
- **R-F: Baselines change deliberately.** Screenshot re-baselines get their own commit + STATUS note; never bury one to go green (14.5 audits this).
- **R-G: Upstream respect.** Prefer config > patch > fork(forbidden). Every patch has the 6.2 justification file.
- **R-H: Security surfaces are owner-gated.** polkit, signing policy, packages.yml removals, ci/, ADRs → CODEOWNERS review, no exceptions, even if CI is green.
- **R-I: Assert the effect, never the presence.** In an image-based OS almost
  everything is declarative config, so the signature failure is a thing that is
  *installed, correct-looking, and doing nothing* — with no surface indicating
  the gap. Presence proves nothing. Test the observable effect on a running
  system, and where the effect cannot be reached, say so rather than accepting
  presence as a proxy.

  Four instances, all found late and all the same shape:

  | Present | Inert because | Would have shipped as |
  |---|---|---|
  | `greenboot` installed, health checks written, unit correct | nothing runs `systemctl preset-all`, so `WantedBy=` is dead letter without an enablement symlink | ADR-008's automatic rollback **false on every machine** |
  | Font chain configured in the right order, in the right file | `alias`/`prefer` is a *weak* fontconfig binding; Fedora's default binds strongly | the **wrong typeface** rendering everywhere, two substitutions deep |
  | `policy.json` signature rule, proven enforcing under skopeo | `bootc` is a different consumer of the same file | signing verified for a tool **users never run** |
  | The **theme capture suite** — the apparatus built to catch this class — writing `theme-light-menu.png` and printing `captured menu (light)` | it asserted the file was written, never that a menu was on screen; the right-click missed and the frame is just the window behind it | a compare sheet sent for pixel review with **the subject absent from three frames** |

  The tell is always the same: every artifact reads correctly, and nothing in the
  system reports a gap. `tests/lint/units_enabled.py`, the `fc-match` check, and
  the negative test exist because a human noticed the difference between
  configured and in-effect — three times, each time by accident.

  **The fourth row is the rule's sharpest form: even the verifier must verify
  effect.** A test is code, and it fails this way like any other code. A
  screenshot test that asserts a file was written rather than that the pixels
  contain its subject is measuring exactly the nothing greenboot was measuring —
  green, present, inert. The apparatus built to catch present-but-inert had the
  defect inside it, which is the strongest available argument that nothing is
  exempt: a suite gets the same effect-assertion discipline as the product, or it
  is decoration with a pass rate.

  Concretely, for anything that captures: assert the subject is in the frame
  before the frame counts. A capture step that cannot assert its own subject is
  not a weaker test, it is not a test.

  The third row is still open: `bootc upgrade` honouring `policy.json` is
  unproven, and is recorded as such rather than assumed from the skopeo result.

- **R-J: An anomaly you cannot explain is a thread to pull now.** The
  font-weight defect — the whole UI rendering in Schibsted Grotesk Black — was
  visible in this work package's *first* probe, as
  `gtk-font-name=Schibsted Grotesk, Black 14` in a settings file. It was seen,
  described as "worth your eye", and filed as an oddity. It then cost a day and
  reached an owner review before anyone pulled it.

  The cost asymmetry is the whole argument: chasing an anomaly costs minutes,
  shipping one costs a day plus a false review. "Worth your eye" is the sound a
  bug makes before it becomes expensive.

  So: when an observation does not fit the model, reconcile it, or write it down
  as an open question with a name. A passing remark is not a record, and the
  next session will not find it.

### 14.4 Context discipline (you are an Opus 5 medium agent; budget accordingly)
Load only listed inputs; grep before reading whole files; summarize long tool output into your working notes instead of re-reading; if context tightens, STOP at a clean commit + STATUS.md "Open threads" + hand off rather than degrading quality. An L-size WP expects 5–8 sessions — plan your slice to land something verified each session.

### 14.5 Reviews between agents
Every PR gets a review by a different agent session before merge (except docs-only): reviewer runs the acceptance list independently, checks R-A..R-H, checks STATUS.md honesty, and looks specifically for baseline-fudging and hidden VM-hand-fixes (R-B: does a clean rebuild reproduce?). Review verdict template lives in `.github/PULL_REQUEST_TEMPLATE.md`.

### 14.6 Escalation (DECISION-NEEDED)
Triggers: your WP's "Escalate if"; an ADR conflict; a MUST you cannot meet; a security/legal doubt; two WPs in true contradiction. Action: open issue titled `DECISION-NEEDED: <topic>` using the template (context ≤ 10 lines, options table w/ costs, your recommendation, deadline-if-any), link it in STATUS.md, **stop work on the blocked path only** (continue unblocked slices), await the owner. Never resolve a DECISION-NEEDED yourself, even by "obvious" choice.

### 14.7 Work-package kickoff prompt (the owner pastes this to start each agent)

```
You are executing WP-<NN> of Meridian OS. Repo: <url>, branch from main.
Read, in order: PRD §0, §14, your WP-<NN> in §8 (+its Governing ADRs in §2),
STATUS.md, then only your WP's Inputs. Then post your acceptance checklist
as the PR description and begin per §14.2. Deliver the smallest verified
slice per session. Escalate per §14.6 — do not improvise around blockers.
Current fleet note: <owner fills: other WPs in flight, if any>.
```

---
