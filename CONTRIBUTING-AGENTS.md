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
