# STATUS.md — the live state of the world

This file is the shared memory between agents (PRD 6.4). **Read it before you
start; trust it over your assumptions about what other work packages have done.**

Rules that keep it trustworthy:

- One section per WP, <= 10 lines, appended at completion (updated on partial stops).
- An agent MUST NOT contradict a `DONE` entry without escalating (PRD 14.6).
- Deviations and open threads are recorded honestly. A tidy STATUS.md that hides
  a deviation is worse than no STATUS.md (rule R-A).
- Re-estimate the remaining effort budget at each M-gate (PRD 9.2).

## Work package index

Status: `TODO` | `IN PROGRESS` | `BLOCKED` | `DONE` | `WAIVED`

| WP | Title | Phase | Size | Risk | Depends | Status |
|---|---|---|---|---|---|---|
| WP-00 | Repository bootstrap & conventions | 0 | S | low | none | DONE |
| WP-01 | Base image: builds, boots, publishes | 0 | M | medium (external base) | WP-00 | DONE |
| WP-02 | De-bloat & package curation | 0 | M | low | WP-01 | DONE |
| WP-03 | VM test harness & story framework | 0 | L | medium | WP-01 (images to test) | DONE |
| WP-04 | Update pipeline, rollback, signing | 0 | M | medium | WP-01 | DONE |
| WP-05 | Theme core | 1 | L | medium | WP-02, 03 | TODO |
| WP-06 | Boot & login: Plymouth, SDDM, silence | 1 | S | low | WP-05 (brand assets) | TODO |
| WP-07 | Panel layout, KIOSK lockdown, Familiar shortcuts (+pager) | 1 | M | medium | WP-05 | TODO |
| WP-08 | Start menu plasmoid (`org.meridian.start`) | 1 | L | medium-high (core identity) | WP-07 | TODO |
| WP-09 | Quick Settings plasmoid (`org.meridian.quicksettings`) | 1 | L | high (most integration surface) | WP-07 | TODO |
| WP-10 | Files experience | 2 | M | low-medium | WP-05 (theme), WP-07 (kiosk base) | TODO |
| WP-11 | Removable media, phones, AutoPlay | 2 | S | low | WP-09 (devices row), WP-10 (sidebar) | TODO |
| WP-12 | Settings curation + custom KCMs | 2 | L | medium | WP-05, 07; WP-04 (updates data) | TODO |
| WP-13 | Software store (`apps/software/`) | 2 | L | high (has sanctioned fallback) | WP-05; WP-15 (catalog schema — can start against schema draft) | TODO |
| WP-14 | Welcome / OOBE (`apps/welcome/`) | 2 | M | medium | WP-08 (pins DBus), WP-09 (nm QML precedent), WP-13 (installs), stubs acceptable w/ contract tests | TODO |
| WP-15 | Curated catalog & compatibility data | 2 | M | low | WP-00 (schemas home) | TODO |
| WP-16 | Live ISO & hardware check | 3 | L | medium-high (external tooling) | WP-02 (image contents), WP-03 (harness) | TODO |
| WP-17 | Installer: Calamares, three screens, bootc deploy | 3 | L | **highest in project** | WP-16 (boots from its live env), WP-04 (policy/signing interplay) | TODO |
| WP-18 | Nvidia specialization | 3 | M | medium | WP-01 (variant build), WP-17 (firstboot flag), WP-12 (Updates surface) | TODO |
| WP-19 | Dual-boot polish | 3 | S | low | WP-17 | TODO |
| WP-20 | Windows App Support (`apps/winapps/`) | 4 | L | high (external ecosystem) | WP-15 (compat data), WP-12 (Apps page), WP-13 (store presence optional) | TODO |
| WP-21 | Migration wizard (`apps/migration/`) | 4 | M | medium | WP-10 (Files conventions), WP-14 (entry point), WP-19 (NTFS guards) | TODO |
| WP-22 | Printing & scanning | 5 | S | low-medium | WP-12 (Printers page visible) | TODO |
| WP-23 | Power, battery & thermals | 5 | S | low | WP-09 (battery surfaces), WP-12 (Power page) | TODO |
| WP-24 | Accessibility & internationalization | 5 | M | medium | feature-complete UI (post 13/14/12) | TODO |
| WP-25 | Beta program, hardware matrix, release engineering | 5 | M | low (labor) | M3 complete (installable) | TODO |
| WP-26 | Naming & brand finalization | 5 | S | low | none technically (owner-driven; MUST complete before RC1) | TODO |

## Milestone gates (PRD 9.1)

| Gate | Meaning | Status |
|---|---|---|
| M0 | It boots and heals | NOT STARTED |
| M1 | It's the product | NOT STARTED |
| M2 | A switcher can live here | NOT STARTED |
| M3 | It ships on metal | NOT STARTED |
| M4 | The bridge holds | NOT STARTED |
| M5 | 1.0 release checklist (PRD 9.3) | NOT STARTED |

## Zero-Terminal story coverage (PRD 10.1 — the INV-0 gate)

0 / 23 green. The harness exists (WP-03); no story is implemented yet, so every
one is unproven. ZT-23 (on-screen keyboard, pointer-only) was added by ADR-019 §7.

---

## WP-00 Repository bootstrap & conventions — DONE 2026-09-01 (agent run 1)

**Delivered:** PRD 6.1 tree; ADR-001..016 + template; tokens.json + schema;
branding.json + schema; Justfile (lint real, rest fail loudly naming their WP);
lint suite (shellcheck, ruff, schemas, branding, strings, markdown); CI lint
workflow; CODEOWNERS; PR/DECISION templates; docs/contracts/interfaces.md
(PRD 8.0 copy); LICENSE/NOTICE; tracking-issue bootstrap script.

**Verified:** `just lint` green; `just test-lint` green — both lints prove
themselves by planting a violation and asserting the catch (acceptance item 2).
27 WPs indexed.

**Deviations:**

1. branding-lint exclusion set is `branding.json`, `docs/`, `STATUS.md`,
   `CONTRIBUTING-AGENTS.md`, `README.md`, and the lint itself. PRD 6.5 names
   only the first two; the rest is prose that WP-26's sanctioned docs sweep
   covers.
2. branding-lint is case-sensitive and polices the product NAME only, not the
   lowercase brand *id*. The PRD itself bakes `meridian` into paths and D-Bus
   names (6.1, 8.0), so the id is not a one-PR rename and pretending otherwise
   would be dishonest.
3. tokens schema lives at `docs/design/schemas/`, not `catalog/schemas/`,
   because Appendix A's verbatim `$schema` value is `./schemas/tokens.schema.json`.
4. markdownlint skips the PRD, ADRs and CONTRIBUTING-AGENTS.md — verbatim
   owner-owned text we are forbidden to edit (99 of 167 findings were in the
   PRD). Rule MD060 (table pipe padding) is off as pure cosmetics.

**Notes for later WPs:** `just lint` is the PR gate from now on — register your
data contract in the `PAIRS` list in `tests/lint/schemas.py` when you ship one.
Any `just` recipe with a shebang MUST carry `set -euo pipefail`; without it a
failing command still passes. Target bash 3.2 (the Mac dev loop): no `mapfile`,
no `${x^^}`.

**Open threads:**

- `branding.json.supportEmail` is `null`; the owner must provision one before WP-25.
- `gh` is not authenticated on the dev machine, so the 26 tracking issues are
  scripted but not created: run `python3 ci/bootstrap-issues.py` after
  `gh auth login`. It is idempotent.
- CODEOWNERS references `@ReclaimExperience/owners`, which does not exist yet.
  Until that team exists **and** branch protection has "Require review from Code
  Owners" enabled, rule R-H is unenforced and CODEOWNERS is decorative.
- The repo is not publicly visible via the GitHub API. ADR-014 requires a public
  monorepo from day 1.
- Acceptance item 1 ("`just lint` green in CI on a trivial PR") is verified
  locally only until the first PR runs.

## Pre-flight — ADR-002 base image verification

Informational; WP-01 owns the committed `verify-base.sh`. Run ahead of WP-01
because the outcome shapes all of Phase 0. Evidence gathered against the live
GHCR and Quay APIs on 2026-09-01:

| Image | Result |
|---|---|
| `ghcr.io/ublue-os/kinoite-main:44` | EXISTS, `44.20260901.1`, built 2026-09-01T03:45Z (same day), `ostree.bootable=true`, Fedora 44, kernel 7.1.10 — **amd64 only, no arm64** |
| `ghcr.io/ublue-os/kinoite-nvidia:44` | EXISTS, `44.20260901.1`, built 2026-09-01T03:47Z, amd64 |
| `quay.io/fedora/fedora-kinoite:44` | EXISTS, multi-arch **arm64 + amd64** |

**Consequence:** the base lacks arm64 — exactly the case ADR-002 anticipates.
Its pre-authorized split-base applies and **no escalation is required**:

- x86_64 (user-facing): `ghcr.io/ublue-os/kinoite-main:44`
- aarch64 (dev loop only, ADR-013): `quay.io/fedora/fedora-kinoite:44` plus the
  hardware-enablement layer — one Containerfile, ARG-switched base.

**Open thread for WP-01/WP-18:** `kinoite-nvidia` does not follow
`kinoite-main`'s tag scheme. Its recent tags are `latest` plus a legacy
`stable-*` family last touched in 2023, though `:44` does resolve. Pin
deliberately and record which scheme is authoritative.

## WP-01 Base image: builds, boots, publishes — DONE 2026-09-02 (agent run 1)

**Delivered:** `os/Containerfile` (ARG-switched split base, branding-templated labels);
`os/packages.yml` + schema + `apply-packages.sh`; `gen-os-release.sh`;
`os/scripts/build/verify-base.sh` + committed output + `os/base-images.env`;
`os/rootfs/usr/lib/bootc/install/10-meridian.toml`; `os/.containerignore`; real
`just build` / `vm-image` / `vm-run` / `verify-base`; `ci/build.sh` +
`.github/workflows/build.yml` (both arches).

**Verified locally (aarch64, Apple Silicon, HVF):** `just build` → `just vm-image`
→ `just vm-run` boots to a **graphical session**: 213 units OK, **zero** systemd
unit failures, `bootc container lint` 13 passed, qcow2 3.6 GB, labels correct on
the built image. Screenshot: `docs/qa/evidence/wp-01-first-boot-aarch64.png`; its
footer reads "Powered by Meridian OS", proving branding.json → os-release → UI
end to end.

**Correction (found in review):** that screenshot is Plasma's `plasma-welcome`
initial-setup screen, **not** an SDDM login greeter — there is no user list and no
password field, because the qcow2 has no user account. The acceptance item says
"reaches SDDM greeter", so it is **NOT MET**. What is proven is that the graphical
target comes up and a session starts. The greeter itself needs a user account and
is re-checked after WP-02 removes `plasma-welcome` (PRD 3.2).

**Acceptance — all four items met:**

| # | Criterion | Evidence |
|---|---|---|
| 1 | `verify-base.sh` output committed | `os/scripts/build/verify-base.latest.txt`; decision `split-base`, machine-readable in `os/base-images.env` |
| 2 | build → vm-image → vm-run reaches the SDDM greeter, aarch64 locally and x86_64 in CI | `docs/qa/evidence/wp-01-sddm-greeter-{aarch64,x86_64}.png` — user listed, password field, power actions. 216 units OK locally, 248 in CI, **zero** unit failures on both |
| 3 | `skopeo inspect` of the **pushed** image shows our labels | verified anonymously (no credentials) against `pr-28-x86_64` and `pr-28-aarch64`; base.name correctly differs per arch |
| 4 | both-arch CI green | `lint`, `build-x86_64`, `build-aarch64` all green |

**What it took to reach the greeter (two blockers, only the first obvious):** the
disk image had no user account, so SDDM had nobody to offer — and an account
alone is not enough, because Plasma ships its own OOBE as `plasma-setup.service`
with `Before=display-manager.service`, which preempts SDDM entirely until
`/etc/plasma-setup-done` exists. The original screenshot was not a boot failure;
it was a wizard standing in front of the greeter. Both are disk-image-only
customizations, so the published container image is untouched and PRD 7.4's
no-test-credentials rule holds.

**FOR WP-02 AND WP-14:** the shipped image still carries `plasma-setup` and
`plasma-welcome`. Left alone, a real user meets Plasma's OOBE *before* ours
(PRD 5.8) — two wizards, ours second. Suppressing Plasma's belongs to package
curation and to our own Welcome.

**`[VERIFY]` answered for WP-03 (PRD 7.3):** `/dev/kvm` **is present and usable**
on `ubuntu-latest`, shipped as `crw-rw---- root:kvm` and usable after
`sudo chmod 666 /dev/kvm`. WP-03 can plan on KVM rather than the 3×-timeout TCG
fallback — worth knowing before designing every later suite around the slow path.
Free `ubuntu-24.04-arm` runners also work, so the qemu cross-build fallback is
unused.

**Deviations:**

1. `os/rootfs/usr/etc/` → `os/rootfs/etc/`. `bootc container lint` rejects
   `/usr/etc` in a container image outright, so the PRD 6.1 path cannot build.
   `ostree container commit` still turns `/etc` into the default `/etc`, so
   ADR-001 is satisfied; only the source path changes. **WP-07, WP-10 and WP-12
   must write image defaults to `os/rootfs/etc/`.** Verified the bases are clean,
   so this was ours.
2. Added `os/rootfs/usr/lib/bootc/install/10-meridian.toml` declaring
   `root-fs-type = "btrfs"`. Both bases ship an empty `/usr/lib/bootc/install/`,
   and bootc-image-builder fails with "missing required info: DefaultRootFs"
   without it. btrfs is not a new decision — PRD WP-17 already specifies it.
   WP-17 still owns the full partitioning story.
3. `os/.containerignore` keeps `README.md` and `.gitkeep` out of the image. Repo
   bookkeeping under `os/rootfs/` was shipping inside the OS.
4. The Mac dev loop needs a **rootful** podman machine; bootc-image-builder
   refuses to run rootless. `just vm-image` now says so with the exact commands.
   Rootful storage is separate, so switching costs one rebuild.

**Notes for later WPs:**

- os-release is machine-read by stricter parsers than the spec. No comment lines
  (bootc-image-builder aborts on the first one), double quotes not single, and
  `VERSION_ID` at most `major.minor` — osbuild builds a distro name from
  ID + VERSION_ID and rejects two dots. All three were build failures, not theory.
- In a Justfile, `{{` escapes as `{{{{` but `}}` is not special, so a Go template
  needs `{{{{ .Field }}` — writing `}}}}` emits four braces. Cost two debug cycles.
- Do not pipe a build into `tail`: the pipeline exit code hides the failure.

**Open threads:**

- ublue `kinoite-nvidia` tag scheme still unresolved for WP-18 (see pre-flight note).
- WP-02 should note the base ships `plasma-welcome`; it is what the first-boot
  screenshot shows, and PRD 3.2 lists it for removal.

## Review response — WP-00 / WP-01 (independent agent, PRD 14.5)

An independent reviewer returned **CHANGES REQUESTED** with 2 blockers and 4
majors. All blockers and the named minimum set are fixed; the findings are
recorded here because several are traps a later WP could re-enter.

| ID | Finding | Fix |
|---|---|---|
| B-1 | The restricted YAML parser silently disagreed with PyYAML on **7 schema-valid inputs** — multi-line flow sequences, quoted keys, anchors/aliases, duplicate keys (parser returned the *union*, PyYAML keeps the last), odd indentation, space before colon, flow mappings. A wrong package list would have reached `dnf` with a green build. | Parser made strict. **First attempt did not fix the blocker — see N-1 below.** Now genuinely fixed and proven against the shipped script. |
| B-2 | The `usr/etc` → `etc` move orphaned two CODEOWNERS rules — **polkit and the image signing policy**, the two most security-sensitive surfaces — so R-H would have silently stopped gating them. | Paths repointed. **The lint written to catch this did not catch it — see N-2 below.** Now rewritten and proven against the original stale rules. |
| M-3 | `ci/build.sh` regenerated `os/base-images.env` on every CI run. A transient registry error makes `verify-base.sh` emit `DECISION=fedora-fallback` **and exit 0**, so CI could have built the user-facing x86_64 image on a base with no driver stack and pushed it to `:testing`. Green build, wrong OS. | CI is compare-only: it fails if the live decision differs from the committed record. `arches_of()` retries before concluding an image is missing. `just verify-base` writes atomically so a failure no longer truncates its own evidence. |
| M-4 | "Boots to the SDDM greeter" overclaimed what the screenshot shows. | Corrected above; the acceptance item is marked NOT MET. |
| M-5 | `just vm-run` had two silent aborts (`find` under `pipefail` made its own error branch unreachable; `brew --prefix` failure exited 127 with no output on any non-Homebrew machine) and passed **no UEFI firmware for x86_64** despite ADR-013. | Firmware is resolved across macOS/Fedora/Debian paths with a clear error listing what it looked for; both aborts fixed and reproduced as fixed. |
| M-6 | ~200 lines of shell inside Justfile recipes were never linted — where every shell defect so far has lived. | `tests/lint/justfile_shell.py` extracts each recipe body and shellchecks it. 7 recipes, all clean. |
| F-7 | `gen-os-release.sh` escaped `\` and `"` but not `$` or backtick; os-release is *sourced* by root-run scripts. | Both escaped; newlines rejected outright. |
| F-9 | The strings lint covered exactly one file; `branding.json`'s name and tagline — the most user-visible strings shipping today — were unlinted. | branding.json added to scope (5 → 7 strings). |
| F-10 | `EXCLUDE_RE` was not end-anchored, so `README.md.probe` inherited `README.md`'s exemption. | Anchored — and the first attempt over-anchored and silently unexcluded the whole `docs/` tree, so the self-test now asserts **both** directions. |
| F-12 | The build workflow invoked `ci/build.sh` twice per job (two full builds, two chances for the base decision to drift) and passed the token via `-p`, visible in `/proc`. | One invocation; `--password-stdin`. |
| F-14 | `bootstrap-issues.py` reported 27 parsed where 26 are created. | Message states both numbers. |

**Deferred, with owner visibility:** F-8 (`local -n` in `apply-packages.sh` needs
bash 4.3, so the script cannot be exercised on the Mac's bash 3.2 — it only ever
runs inside the Fedora container); F-13 (`just test-lint` writes to the git index);
F-14's note that `.gitkeep` exclusion means `catalog/`/`compat/` directories will
not exist in the image, which WP-13/WP-15 must create rather than assume.

## Second review round — my own fixes were defective

The re-verification review returned **CHANGES REQUESTED** again. Two of the
blocker "fixes" did not fix their blockers. Recorded in full because the pattern
matters more than the individual bugs: **a fix is not a fix until it is proven
against the shipped artifact.**

| ID | What was actually wrong | Fix, and how it is now proven |
|---|---|---|
| N-1 (blocker) | The parser was made strict; the **call site threw its exit status away**. `mapfile_compat` read it through `< <(cmd)`, which does not propagate status, so every strict rejection printed an error and became an empty list — exit 0. This was **worse than the original bug**: one ambiguous line emptied all four lists, so packages were silently not installed, removals not performed, masks not applied, build green. A missing `python3` did the same. | Reads now use a plain assignment (which *does* carry status) and abort the build. `python3` presence is checked explicitly. Proven by reintroducing the exact bug and watching the test go red. |
| N-2 (major) | The new `codeowners.sh` walked *up* until it found any existing ancestor, so it reported "clean" on the exact rules B-2 was about. | **First attempt caught one shape only — see round three below.** |
| N-3 (major) | YAML tags and backslash escapes were accepted and mis-decoded, exit 0. | **First attempt fixed only the block branch — see round three below. The shipped manifest uses the flow form.** |
| N-4 (medium) | Merging the Build and Push steps dropped the fork-PR guard while still always passing `--push`, so a fork PR would build and then fail on a push it had no credentials for. ADR-014 makes fork PRs a real path. | Push is conditional; fork PRs build and say why they skip the push. |
| N-5 (minor) | The Justfile shell lint's header regex skipped `_`-prefixed recipes, so `_todo`'s body was unlinted while the lint said "clean". | Regex widened, plus a completeness check that fails when the shebang count exceeds the extracted-recipe count. Proven by narrowing the regex and watching it fire. |
| N-6 (minor) | The parser test extracted the heredoc and tested it **standalone** — a code path the shipped script never took. This is what hid N-1 for a whole round. | Rewritten to drive the real `apply-packages.sh` with `dnf`/`systemctl` stubs that record their arguments, comparing actual actions against PyYAML, and asserting rejected manifests produce **no side effects at all**. |
| N-7 (nit) | `mv` from `mktemp` left the committed evidence file mode 0600. | `chmod 644`. |

**The lesson, for every later WP:** three of my edits in this round silently
no-opped because a string replace did not match reformatted source, and the
"fixed" claim survived until something re-read the file. Verify that an edit
landed, and verify a fix against the artifact that ships — not against an
extracted copy of it.

## Repository governance — ARMED 2026-09-01

All three preconditions for rule R-H are satisfied and independently verified:

- The repo is **public** (ADR-014), which also made branch protection available
  on the free plan.
- `main` requires `lint`, `build-x86_64` and `build-aarch64` to pass, plus one
  code-owner approval, with stale reviews dismissed, linear history enforced,
  and force pushes and deletions blocked. Admins may bypass, deliberately:
  GitHub forbids self-approval, so full enforcement would deadlock a solo
  owner's own PRs.
- The `@ReclaimExperience/owners` team has write access, so every CODEOWNERS
  rule resolves. `gh api 'repos/{owner}/{repo}/codeowners/errors'` returns
  `{"errors":[]}` on `main`, `wp/00-repo-bootstrap` and `wp/01-base-image`.

The third is the fragile one and it fails **silently**: GitHub applies no review
requirement at all for an unresolvable owner, and the file still reads like a
gate. The lint workflow therefore asks GitHub directly on every run and fails
the build if any rule stops resolving.

Note for later agents: an earlier version of this section said the opposite
("still unarmed... R-H is a convention, not a gate"). It was left stale when
the arming landed inside a commit whose message was about something else. If
STATUS.md and the repository ever disagree again, the repository is the truth —
and the stale entry is itself a defect worth fixing immediately.

## Third review round — the same mistake, one layer down

Third consecutive **CHANGES REQUESTED**. The pattern repeated exactly: each fix
was verified against *a* path rather than *the* path.

| ID | What was still wrong | Fix, and how it is proven now |
|---|---|---|
| N-3 (blocker) | The tag/escape guards went on the **block-sequence** branch. A value can also arrive via a **flow sequence**, and the shipped `os/packages.yml` uses the flow form on all four lists — so the guards sat on the branch the real file never takes. `mask: ["baloo\x5Ffile.service"]` ran `systemctl mask baloo\x5Ffile.service`, which succeeds against a nonexistent unit: **Baloo silently not masked (ADR-016), exit 0, green build.** 25 silent divergences found. | Validation moved into one `validate_scalar()` that **both** routes call. The parser file now carries a warning that a rule added to one branch is not added. `MUST_REJECT` gained a flow variant of every defect; the suite went 9 → 19 cases. Confirmed against the shipped script in a container: exit 2. |
| N-2 (major) | The rewritten `codeowners.sh` caught the one historical shape and essentially nothing else — a typo of a live rule, a renamed subdirectory, or a file that will never exist all passed, and it false-positived on legal globs. | Rewritten to expand each pattern against the real git index the way GitHub does, requiring ≥1 match or a `# planned: WP-NN` marker. All five shapes the reviewer listed as missed are now caught; four globs accepted, a glob matching nothing still caught. It immediately failed 3 live rules the previous version called clean — those are now honestly marked planned. |
| N-5 (major) | The completeness check never checked the body was **non-empty**. Tab- and 2-space-indented recipes extracted as empty and were reported `ok`; non-shebang recipes were not linted at all. | Indent is derived from the body; an empty or truncated body is an error. Completeness is now checked against `just --dump --dump-format json` — `just`'s own answer — instead of against our parser agreeing with itself. **That immediately exposed a fresh regression of the same class: the header pattern excluded `=`, so `build`, `vm-image`, `vm-run` and `vm-test` were silently unlinted.** Coverage went 8 → 23 recipes. All six shapes in the reviewer's break matrix are caught. |
| NEW-1 (major) | The script never checked that `version`, `add` and `remove` were **present**. A typo (`adds:`) or a truncated file exited 0 having done nothing. The build path never runs the schema, so nothing else would catch it. | Required keys are enforced, unknown keys rejected, in the parser itself. |
| NEW-2 (minor) | The lint workflow installed `jsonschema` but not `PyYAML`, which two lint scripts import — working only because the hosted image happens to ship it. | Installed explicitly. |
| NEW-3 (minor) | The version-pin check only **warned**, so a laptop on a different shellcheck still got a green `just lint` — the exact drift the pins exist to stop. | `lint-toolchain` now fails, with `MERIDIAN_ALLOW_TOOL_DRIFT=1` as a documented, explicit escape hatch. |
| NEW-4 (minor) | `#` was stripped regardless of quoting, and `---` was a hard failure. | Comment stripping is quote-aware; document markers are ignored. |

**The standing lesson, restated because three rounds did not teach it:** ask which
code path the *real input* takes before declaring a fix proven. Round one fixed
the parser and not the call site; round two fixed the block branch and not the
flow branch; round three found the header pattern silently dropping the four
largest recipes. In each case the test agreed with the fix because the test
exercised the same wrong path. **Completeness checks must be answered by an
external authority** — `just --dump` for recipes, `git ls-files` for CODEOWNERS
patterns, PyYAML for manifests, GitHub for owner resolution — never by our own
parser agreeing with itself.

## Fourth review round — no blocker; the recurrence had moved into the lints

The parser held. 4,300 differential cases across four corpora, both bash
versions, one runtime route, both value routes converging on `validate_scalar()`:
**no schema-valid input makes the script exit 0 while acting on a package set
differing from PyYAML.** That is the first clean negative in four rounds on the
component that can actually break a user's machine.

The recurrence was in the two lints, and in the same shape as always — an
authority adopted for part of the question and hand-rolled for the rest.

| ID | What was wrong | Fix |
|---|---|---|
| M2 (major) | `codeowners.py` adopted `git ls-files` as the authority for the **file list** but hand-rolled the **pattern semantics**, where the whole question lives. It anchored only on a *leading* slash; gitignore also anchors a pattern with an *interior* separator. So `rootfs/etc/` — a live privilege-boundary rule with the `/os` prefix dropped — matched two files here and **zero on GitHub**. A false negative in the lint's core purpose. | Matching is delegated to `git check-ignore`. Constructs GitHub does not support (`[a-z]` ranges, `!` negation) are rejected outright rather than guessed at, since git matches them and GitHub does not. Verified against the reviewer's disagreement table. |
| M1 (major) | `justfile_shell.py`'s fallback for a missing `just` compared `headers` to `len(recipes)` — incremented on adjacent lines, so it **could never fire**. With `just` off PATH the completeness check silently vanished and a recipe containing `rm -rf $UNSET/*` passed. | A missing or failing `just` is now an error. The tautological counter and an unreachable truncated-body check are deleted rather than left looking like safety nets. |
| m5 | The `# planned:` marker was matched anywhere in the line, so any comment containing the phrase excused a dead rule. | Anchored to a trailing comment; the WP number must be within WP-00..WP-26. |
| m2 | `rule.split()[0]` truncated an escaped path at the backslash, and this repo tracks a mockup file with a space in its name. | Pattern splitting honours backslash escapes. |
| m3 | Skipping `---`/`...` silently merged a multi-document stream into one key space; PyYAML refuses such a file outright. Tabs were likewise accepted where PyYAML errors. | Both rejected. Confirmed PyYAML raises `ComposerError` and `ScannerError` on the same inputs. |
| m4 | A mapping nested under a list key was structurally accepted and silently yielded an empty list. | Rejected. |
| m6 | This file said "**Still unarmed** — R-H is a convention, not a gate" while `.github/CODEOWNERS` said ARMED and CI was already checking owner resolution. The arming landed inside a commit whose message was about parser fixes, and the shared memory was left asserting the opposite. | Governance section rewritten to match reality, with a note that the repository is the truth when the two disagree. While fixing it I duplicated two sections; `markdownlint` MD024 caught that immediately, which is the gate working. |

`MUST_REJECT` is now 22 cases; `justfile-shell` covers 23 recipes; `codeowners`
delegates matching to git.

**Where the pattern actually lives, after four rounds:** every recurrence has
been the same shape — an external authority adopted for *part* of a question and
hand-rolled for the rest. Round 2: parser strict, call site hand-rolled. Round 3:
block branch guarded, flow branch not. Round 4: git for the file list, hand-rolled
regex for the pattern semantics. Before claiming a check is authoritative, name
the authority and confirm it answers the **whole** question, not the part that
was convenient to delegate.

## x86_64 image built and inspected locally — 2026-09-01

Both halves of the ADR-002 split base now exist side by side and agree everywhere
except the base itself, which is the intent:

| | aarch64 (dev loop) | x86_64 (user-facing) |
|---|---|---|
| base | `quay.io/fedora/fedora-kinoite:44` | `ghcr.io/ublue-os/kinoite-main:44` |
| image size | 7.41 GB | **9.14 GB** |
| `bootc container lint` | 13 passed | 13 passed |
| `/usr/etc` | absent | absent |
| repo bookkeeping shipped | 0 files | 0 files |
| `root-fs-type` | btrfs | btrfs |
| os-release NAME / ID / VERSION_ID | `Meridian OS` / `meridian` / `1.0` | identical |

The ~1.7 GB difference is ublue's driver and codec stack — the thing ADR-002
selects that base for — so the split is doing what it was chosen to do.

**Known limitation for WP-03 and WP-16:** a disk image (and therefore an ISO)
can only be built for the host's own architecture on this machine. Plan the
x86_64 harness and ISO work around CI runners, not the Mac dev loop.

**Note on GHCR:** the packages are private even though the repo is public, and a
`repo`-scoped token cannot read them. This x86_64 image had to be rebuilt locally
under emulation despite CI having already built and pushed exactly it. Making the
package public would let later WPs pull CI artifacts instead of re-emulating
them.

## WP-01 closed — 2026-09-02

Acceptance is complete; the table in the WP-01 entry lists the evidence for each
item. Two things that were open are now closed rather than waived: the SDDM
greeter (both arches) and the x86_64 boot.

`ci/boot-screenshot.sh` + `ci/qmp-screenshot.py` are a **WP-01 stopgap** — a
one-off photograph, no assertions, no baselines, no story scripts. **WP-03 should
delete both** when the real harness (PRD 7.4) lands, not grow them; two
half-harnesses is worse than one.

Getting the x86_64 boot working in CI took five attempts, each producing a
finding worth keeping:

1. the boot step ran before the image was built;
2. `/dev/kvm` is `root:kvm` and needs `chmod` before it is usable;
3. bootc-image-builder refuses rootless podman, so the image must be handed to
   root's store — whose graphroot is on the runner's 14 GB root disk;
4. relocating that graphroot via `storage.conf` broke the nested podman
   (`database static dir ... does not match`), so the bytes move by **bind
   mount** while the canonical path stays;
5. `FW=$(find ... | head -1)` under `set -o pipefail` aborted the script
   silently when a search root was missing — **the same defect already fixed
   once in the Justfile's `vm-run`, reintroduced in a new file.** shellcheck
   does not flag it.

Finding 5 is the one to remember: the fix was applied where it was found, not to
the pattern. Any `$(cmd | cmd)` under `pipefail` is a silent-abort candidate.

Open, and deliberately not WP-01's to close:

- `just vm-image` cannot cross-build a disk image (nested podman under
  emulation). WP-03 and WP-16 must plan x86_64 disk/ISO work around CI runners.
- No installable ISO exists yet — that is WP-16. Bare-metal testing on real
  hardware begins there and at WP-17/WP-25, not here.

## WP-03 VM test harness — DONE 2026-09-02 (agent run 1)

**Delivered so far:** `tests/harness/` — `qmp.py` (screenshots, key/pointer
injection, run state), `console.py` (bidirectional serial console = the
guest-exec channel), `vm.py` (boots a disk image, firmware/accelerator
selection, evidence collection), `run.py` (suite runner), `suites/smoke.py`;
real `just vm-test [suite] [arch]`; credential handoff from `just vm-image` via
`build/dev-credentials.json` (gitignored).

**Verified:** `just vm-test smoke` **PASSES in 25 s** on aarch64/HVF. All seven
assertions: console login, `display-manager` active, greeter drawn, **GUI login
through SDDM**, `plasmashell` running, `systemctl --failed` empty, os-release is
ours. 206 units OK, 0 failed units. Evidence written on success as well as
failure — a suite whose artifacts appear only on failure gives you nothing to
compare a regression against.

**Guest-exec choice:** the serial console, not SSH (ADR-015 ships no sshd) and
not a guest agent (nothing should exist in the image purely to be tested). The
throwaway account lives only in the local disk image, so the container image we
publish stays clean — stricter than PRD 7.4's "bake into pr-NNN artifacts".

**Four findings, each of which had already produced a wrong test:**

1. **systemd never narrates the display manager to serial.** 71 unit lines reach
   the console; the graphical stage is not among them, because plymouth's
   console handoff swallows it. Ask systemd directly; do not scrape the boot log
   for a unit description that will never appear.
2. **A console login is not a desktop login.** `plasmashell` starts only when a
   session begins through SDDM. The first smoke suite asserted plasmashell after
   a serial login and would have failed on a perfectly good image.
3. **Shell OSC 3008 session markers read as failed units.** The ANSI stripper
   handled BEL-terminated OSC but not ST-terminated, so a prompt marker survived
   into the `systemctl --failed` parse and looked exactly like a failure.
4. **The image's hostname is `fedora`, not `meridian`.** `os-release` sets
   `DEFAULT_HOSTNAME=meridian`, but the base ships an `/etc/hostname` that wins.
   **For WP-02/WP-17:** a user's machine would introduce itself as "fedora" on
   the network and in the shell prompt.

**Slice 2 — the two audits that make ADR-011 and ADR-015 provable:**

- `tests/security/ports.sh` + `suites/security.py`: reads every bound socket in
  the running image and fails on any non-loopback listener not in
  `tests/security/allowed-ports.txt` (owner-gated). **It found a real violation
  on its first run** — see below.
- `tests/privacy/network_audit.sh` + `suites/privacy.py`: captures every packet
  from **outside** the guest via qemu `filter-dump`, so the image under audit is
  the image that ships — the guest needs no tcpdump, no capabilities, and no
  awareness it is watched. **PASSES**: on a settled idle system the only public
  destinations are `fedoraproject.org:80` (connectivity check) and
  `2.fedora.pool.ntp.org:123` (time), each printed with the ADR-011 clause that
  permits it. Default window is the full 10 minutes; `MERIDIAN_IDLE_SECONDS`
  shortens it while iterating, but the gate is 600 s — a daily check-in would be
  invisible to a two-minute sample, and a daily check-in is the thing this
  exists to catch.
- `tests/harness/pcap.py`: dependency-free pcap + DNS reader. The audit that
  proves "zero telemetry" should not rest on a parser nobody reads.
  `tests/harness/test_pcap.py` proves it against synthetic captures with known
  contents, including that a garbage file raises rather than reading as clean —
  a parser that silently returns nothing would make the whole audit vacuous.

**ADR-015 violation found, reported to WP-02 (issue #2):** the image listens on
**tcp+udp/5355 on all interfaces, IPv4 and IPv6** — LLMNR, on by default in
`systemd-resolved`. ADR-015 permits exactly one non-loopback listener (mDNS 5353,
for driverless printing). Not fixed here: WP-01/WP-03 must not change image
policy, and the allowlist is owner-gated precisely so widening it cannot be a
convenient way to go green. LLMNR is also a known credential-relay vector on
untrusted networks, so this is a pillar-5 defect, not a tidiness one.

**Design note for later suites:** the privacy audit checks BOTH what the system
asked DNS for AND where packets actually went, attributing every public
destination back to a name via DNS answers. Checking only queried names would
miss a hard-coded address — which is precisely what a check-in looks like.

**Slice 3 — screenshot-diff and the stories framework:**

- `tests/harness/screendiff.py`: RMSE comparison against committed baselines
  with per-screen masks and thresholds. Nothing in it writes a baseline — only
  `just baseline <screen>` does, and it prints a reminder to commit the result
  on its own with a STATUS note (rule R-F). A failure writes a three-panel sheet
  (baseline | actual | amplified difference) because "RMSE 0.0666 exceeds
  0.0300" says a screen changed, not what changed.
- `suites/screens.py` + baselines for `sddm-login` and `desktop` on aarch64.
  **Passes**: RMSE 0.0038 and 0.0000 on a fresh boot where the clock had moved,
  which is the point of the masks.
- **Failure path proven**, not assumed: tinting a baseline's taskbar produced
  `RMSE 0.0666 exceeds 0.0300` and a diff sheet showing the changed strip in
  magenta against black. That is WP-03's "deliberately-broken assertion produces
  useful artifacts" acceptance item, demonstrated.
- `tests/stories/` + `zt_template.py` + `suites/stories.py`: discovers every
  `zt_*.py`, runs it, reports coverage against the 22 (currently 0/22 — each
  story lands with the WP that ships its flow). The template's central rule: the
  harness console **observes**, it never performs the user's step. Doing the
  task in a shell and asserting it worked proves the shell works.

**Masks are documented in the baseline config, not buried in code.** Each
`tests/baselines/<screen>/config.json` says what is masked and why, so a
reviewer can see that the greeter's clock is excluded and the password field is
not.

**Slice 4 — CI wiring, and the WP-01 stopgap deleted:**

- `ci/boot-screenshot.sh` and `ci/qmp-screenshot.py` are **gone**, as promised
  when they were written. `ci/vm-test.sh` replaces them and keeps the three
  things they had learned: granting `/dev/kvm`, handing the image to root's
  store (bootc-image-builder refuses rootless), and chowning the output back.
- PR gate runs `smoke` on x86_64. Deliberately just that one:
  `screens` needs x86_64 baselines that must be created in their own commit
  (R-F) and do not exist; `security` currently fails on two real ADR-015 defects
  WP-02 owns; `privacy` needs a 10-minute window. Those run nightly instead.
- `ci/check-no-test-user.sh` proves the **pushed** image has no `mtest` account,
  home, credential unit or `authorized_keys` — WP-03's acceptance item, checked
  against the ref that was actually published rather than a local build.
- `.github/workflows/nightly.yml`: `smoke privacy security`, with a
  `workflow_dispatch` `repeat` input — `repeat: 10` is the flaky-rate gate.

**Second ADR-015 violation found, reported to WP-02 (issue #2): `sshd` ships.**
`openssh-server` is installed (disabled, so the socket audit did not catch it).
ADR-015 says "no SSH daemon" and section 12 states the attack surface as "browser
is the only routine network-facing app", which is untrue while it is present. The
assertion lives in the **security suite**, not in the test-credential check, so an
ADR-015 violation fails the ADR-015 gate and not an unrelated one.

**The nightly `security` suite is EXPECTED RED until WP-02 lands** — LLMNR on
5355 and sshd. Recorded here so a red nightly is a known countdown rather than
background noise: the day it goes green is the day that axis of WP-02 is done.

**Acceptance — 3 of 4 met, the fourth blocked on merge:**

| # | Criterion | Status |
|---|---|---|
| 1 | `just vm-test smoke` green locally (aarch64) **and in CI (x86_64)** | **MET, re-verified after the round-1 fixes.** Local: PASSED in 26 s, HVF. CI: PASSED in 50 s under **KVM**, 249 units OK, 0 failed units, full GUI login through SDDM — that run exercised the rewritten `Console.run` and the new negative pre-check |
| 2 | deliberately-broken assertion produces useful artifacts | **MET.** A tinted baseline produced `RMSE 0.0666 exceeds 0.0300` plus a three-panel diff sheet |
| 3 | `mtest` absent from any pushed image, while harness access works on the same digest locally | **MET, re-verified after the round-1 fixes.** The hardened `ci/check-no-test-user.sh` (sentinel + exit-status) passed against the **pushed** ref in the same CI run; the same digest logs in locally, because the account exists only in the local disk image. **Caveat:** on PRs the check runs against the `pr-NNN` tag, which PRD 7.4 permits to carry test credentials — only the push-to-`main` path validates `:testing` |
| 4 | flaky-rate: smoke 10x consecutive green **in CI** | **MET.** First nightly run after merge: `flaky-rate: 0 failure(s) across 10 consecutive pass(es)` on x86_64 under KVM (run 33599815486). 10/10 green locally too, every pass 25 s ±1 s |

`docs/testing.md` covers running suites, writing a story, re-baselining, and the
two failure modes that have already cost time (systemd does not narrate the
display manager to serial; a console login is not a desktop login).

**Open threads — genuinely outstanding, not delivered:**

- **OCR text assertions** (`assert_text`, tesseract) — PRD 7.4 names them; not
  written. Screens are compared by pixels only, so a suite cannot yet assert
  "the greeter says *You're all set*".
- **vncdotool input fallback** — WP-03's Steps say "QMP first; vncdotool
  fallback; prove both with SDDM login". Only the QMP path exists. If QMP input
  ever fails on a host, there is no second path.
- **`perf` suite** — genuinely blocked: it wraps WP-02's `idle_ram.sh` and
  `boot_time.sh`, which do not exist yet.
- **x86_64 screenshot baselines** — must be produced on an x86_64 runner and
  committed deliberately (R-F), so `screens` runs on aarch64 only for now.
- **Flaky-rate gate in CI** — 10/10 green locally; `workflow_dispatch` cannot
  target a feature branch, so it runs once `nightly.yml` is on `main`.

## WP-03 review round 1 — two suites could pass while their property was false

An independent reviewer returned **CHANGES REQUESTED** with 2 blockers and 11
majors. The harness *core* survived hard attacks — socket parsing, DNS
decompression, RMSE maths, hostile pcap input, and failure propagation in
`ci/vm-test.sh` were all confirmed sound, and a hard-coded destination with no
DNS behind it **is** caught. The holes were all in the **outermost checks that
decide pass/fail**, which is the worst place for them: a harness that cannot
fail converts an unverified claim into a green check.

| ID | What was wrong | Fix |
|---|---|---|
| BL-1 | The **privacy audit passed on an empty capture.** qemu writes the 24-byte pcap header on open, so an unattached filter-dump yields a valid empty file — and the audit printed "ADR-011 holds". The one place it is structurally blind had no self-check. | Positive control: the capture must contain DHCP or DNS, or the suite fails as *not observing* rather than passing as *nothing happened*. |
| BL-2 | **`check-no-test-user.sh` reported clean when the container failed to start.** Any podman/OCI failure gave empty output, read as "nothing found". This is acceptance item 3, which STATUS recorded as MET on a check that could not fail. | A sentinel is emitted first and required in the output; podman's exit status is captured. Proven both ways: clean image → 0, broken podman → 1. |
| MJ-1 | **`"inactive".endswith("active")` is `True`.** The "display-manager is active" assertion passed while it was inactive — in smoke, screens, *and* the story template, so every future story would have inherited it. | Exact match on the last line. |
| MJ-2 | `Console.run` split on the echoed command tail and fell back to the **whole buffer** when a printk interleaved — so `pgrep -a plasmashell` could match its own echoed command and report a session that did not exist. | Paired sentinels, assembled by the shell at runtime so the echoed line never contains the expanded marker. A missing opening sentinel is an error, never a fallback. |
| MJ-3 | Nothing distinguished "our typed password logged in" from "a session already existed". | Negative pre-check asserts plasmashell is absent *before* the GUI login. |
| MJ-4 | `pcap.read` returned a **2-tuple** on short input while its signature and callers expect 3 — leftover from a half-applied edit. | Raises with a reason; empty is never confused with quiet. |
| MJ-5 | **Every evidence JSON recorded `units_ok: 0, failed_units: []`** — `Console.run` clears the buffer, and `serial_text()` preferred it over the log. A no-failures record that could not record a failure. | Reads the log file. Now reports 207. |
| MJ-6 | The screens "wait for the shell to paint" polled `... \|\| echo settled`, so the predicate was true on the first poll and never waited. | Waits on the panel process count. |
| MJ-7 | **Masks were an uncapped bypass** — mask the whole image and any two screens match — and `/tests/harness/`, `/tests/baselines/` were **not in CODEOWNERS**, so an agent could not widen `allowed-ports.txt` without review but *could* weaken `is_local()` or delete an assertion. | 25% mask cap; masked fraction printed on every pass; CODEOWNERS extended to the harness, baselines and stories. |
| MJ-8 | The socket assertion aborted the suite, so **the sshd assertion had never executed**. | Both collected, asserted once. |
| MJ-9 | The "Still to deliver" block was a slice-1 leftover contradicting the acceptance table 8 lines above, burying what is genuinely open. | Replaced with real open threads (above). |
| MJ-10 | The reported privacy PASS was measured over ~120 s, not the 600 s gate, and STATUS did not say so. | The suite now records measured vs gate duration and **says so in its own output** when short. |
| MJ-11 | `find_disk` ignored `--arch`. | Prefers a matching path; refuses ambiguity. |

Minors fixed: `${SUDO[@]}` unbound under `set -u` on bash 3.2 (the documented
Mac path), a `--story` flag the template documented but that never existed, and
the allowlist's domain-suffix matching now warns that a broad suffix grants the
whole zone.

**The lesson, and it is the same one as WP-01's four rounds:** the core was
attacked hard and held; the defects were all one layer out, in the code that
decides whether to report success. **Check the outermost layer first — it is the
one that turns everything else into a claim.**

## WP-03 review round 2 — both blockers held; the class moved one layer out again

Second independent review. **Both round-1 blockers verified fixed under attack**
(10 synthetic captures against the real `privacy.run`; 8 stub-podman cases plus
real `probe-clean`/`probe-dirty` images built for `check-no-test-user.sh`), and
`Console.run`'s new sentinel protocol survived seven attacks including the exact
self-match it was written to prevent. But **MJ-6 was NOT fixed**, and five new
defects sat in the same outermost-layer class.

| ID | What was wrong | Fix |
|---|---|---|
| NEW-1 (major) | **`PYTHONOPTIMIZE=1` made every suite pass vacuously.** Every verdict is a bare `assert`, so one inherited environment variable turned the machinery every later WP's acceptance rests on into a rubber stamp. Demonstrated: a suite whose body is `assert False` exited **0** under `-O`. | The runner refuses to start with assertions disabled. |
| NEW-2 (major) | **MJ-6 was not fixed.** The replacement predicate (`pgrep -c plasmashell >= 1`) is true in exactly the states the wait above it already required, so it returned on the first poll — the second wait in a row that looked like a wait and was not. STATUS claimed it fixed. | Waits until two consecutive screenshots are identical — something that genuinely starts false. Observed: *"settled after 3 frame(s)"*, and both screens now compare at RMSE 0.0000. |
| NEW-3 (major) | The credential probe **missed `sysusers.d`** — the idiomatic way to declare a user on a bootc image, where `/etc/passwd` is regenerated on first boot. A planted `probe-sysusers` image reported clean. | Also greps `sysusers.d`, `shadow`, `sudoers.d`. |
| NEW-4 (major) | The nightly ran `security` — documented as expected-red — in the **same job** as `smoke` and `privacy`, so a real regression in either was invisible inside a permanently red job, and **PRD 7.5's promote-to-stable gate ("nightly green 2 consecutive days") was unsatisfiable by construction.** | Split into a gating **step** for `smoke`+`privacy` and a `continue-on-error` ADR-015 **step** (one job, not two — the round-2 wording said "job"). **Half-applied:** the dispatch default still shipped `security` into the gating step. See round 3, R3-3. **Promote-to-stable remains blocked until WP-02** — that is now stated in the job output rather than implied. |
| NEW-5 (major) | **Neither blocker fix had a regression test**, so both could be silently reopened. | `test_suite_guards.py` added — but its **BL-2 case tested the wrong branch** and was itself a vacuous pass. See round 3, R3-1. |
| NEW-6..NEW-14 | `--repeat 0` ran nothing and exited 0; the `is-active` predicate crashed on empty output and was defeated by a trailing printk; `SystemExit` escaped the runner and exited 0; a story failing at *import* aborted every later story; `from typing import Self` needs 3.11 while the PRD 7.2 Mac path has 3.9; masks were capped but the **threshold was not**; the merged ADR-015 assert mislabelled the sshd finding; stale docstrings. | All fixed. |

**Two things the owner should know.** PRD 7.5's promote-to-stable gate cannot be
met until WP-02 removes LLMNR and sshd — not a harness problem, but now
explicit. And on pull requests the credential check validates the `pr-NNN` tag,
which PRD 7.4 explicitly permits to carry test credentials; only the push-to-
`main` path checks `:testing`.

**The pattern, third occurrence:** round 1 found vacuous passes inside the
suites, round 2 found them in the layer around the suites — the runner's exit
paths, the CI job structure, and the interpreter mode. Each round the core held
and the outermost layer did not. **When reviewing a gate, start at the outside.**

## WP-03 review round 3 — the gate's own composition

Third review. The suites and the runner held under everything thrown at them —
the reviewer attacked the `PYTHONOPTIMIZE` guard six ways, the mask/threshold
ceilings seven ways, `--repeat` validation, the sentinel console protocol and
the BL-1 positive control, and broke none of them. What broke was the machinery
that decides **whether the checks run at all**, plus the round-2 regression test
written to stop a blocker being reopened.

| ID | What was wrong | Fix |
|---|---|---|
| R3-1 (blocker) | **The BL-2 regression test did not exercise the BL-2 fix.** Its stub `podman` failed at *every* subcommand, so the script short-circuited at "could not obtain the image" and never reached the sentinel logic that IS the fix. Deleting the fix left the guard green — a regression test that was itself a vacuous pass. | The stub now succeeds at `image exists`/`pull` and fails only at `run`, plus a no-sentinel case, a planted-finding case, and a clean case. **Verified by reopening BL-2: the guard goes red.** |
| R3-2 (blocker) | **Nothing noticed a check that exists but is never executed.** `just lint`/`test-lint` enumerate their sub-checks by hand. Two brand-new always-failing checks were committed and all three gates reported success without running either. The outermost vacuous pass: not a check that passes wrongly, but one nothing calls. | `tests/lint/wired.py` fails if any `tests/lint/*` or `tests/harness/test_*` is not invoked by a recipe (following one hop through `.sh` wrappers), if any `ci/*.sh` is not invoked by a workflow, or if a required check name is not produced. Proven both ways. |
| R3-3 (major) | The nightly's **dispatch default still carried `security`** into the gating step — and the flaky-rate gate is *run from that form*, so WP-03's own acceptance item was unsatisfiable. NEW-4's shape, one layer out. | Default is `smoke privacy`; `security` in the gating list is now a hard error; inputs pass via `env:` so a quote cannot break out of the script. |
| R3-4 (major) | The credential probe **grepped for a hard-coded `mtest`** unlinked from the Justfile that creates the account, and **skipped aarch64 entirely** — so `build-aarch64` was a required check that pushed an image with no assertion against it. | The account name is read from the Justfile; the check runs on both arches. |
| R3-5 (major) | **`screens` and `stories` ran in no automated context.** The screendiff apparatus — the largest body of code in this WP — had zero coverage, and `stories` returned green having run nothing, so "a story that exists and does not pass is a failure" was unproven. | `test_screendiff_stories.py` exercises both without a VM: real difference, identical, missing baseline, full-image mask, threshold ceiling, **and a deliberately failing story making the suite fail.** |
| R3-6 (minor→major later) | `_settle_screen` had **no positive control** — a frozen or black screen "settled" on frame two, the BL-1 shape moved into a wait. It also wrote a three-panel diff sheet on every non-settled poll. | Now requires the settled frame to carry real detail (stddev ≥ 0.02; a real desktop measures 0.125, black 0.000), and compares directly so no spurious diff sheets are written. **First attempt was wrong** — requiring an observed *change* failed a correctly-finished desktop, which is static by the time this runs. |
| R3-7 | Dead `wait_for_serial`: no callers, **returned `False`** on timeout where every other wait raises, and a docstring calling it "the harness's only sanctioned way to wait" — MJ-6 pre-installed for a later WP. | Deleted, with a note saying why. |
| R3-8 | **27 inline shell blocks in the workflows were linted by nothing** — the same argument that justified linting the Justfile recipes. The tell was a live `# shellcheck disable=SC2086` written by an author who believed the file was linted. | `tests/lint/workflow_shell.py`; 17 blocks clean, and proven to catch a planted `rm -rf $UNQUOTED/*`. |
| R3-9, R3-10 | Round-2 edit residue (a comment duplicated within itself) and two STATUS overclaims (NEW-5's BL-2 coverage; NEW-4 described as a separate "job" when it is a step). | Fixed; the round-2 table above now says what is actually true. |

**Known and stated, not fixed here:** `screens` cannot run in CI because only
aarch64 baselines exist and CI is x86_64; x86_64 baselines must be produced on
an x86_64 runner and committed deliberately (R-F). `stories` runs nowhere
automatically until stories exist. Both now have no-VM guards instead.

**The pattern, third confirmation.** Round 1: vacuous passes inside the suites.
Round 2: in the layer around them. Round 3: in the composition of the gate —
whether a check is named in a hand-maintained list, whether a step sits inside a
job whose name is typed into a settings page. Each round the core held and the
outermost layer did not. `tests/lint/wired.py` exists because that layer had
nothing watching it at all; it is the first check in this repo whose subject is
*the other checks*.

---

## WP-02 De-bloat & package curation — IN PROGRESS (agent run 1)

**Delivered:** `os/packages.yml` populated — 13 adds, 23 removes, `baloo_file.service`
masked (ADR-016's sanctioned dep-locked alternative, recorded as the WP asks);
`apply-packages.sh` cascade/survival/protection guards; the two inventory-after
files; `tests/perf/idle_ram.sh`, `boot_time.sh` and `budgets.json` plus the
`perf` harness suite; `security` and `perf` promoted into the PR gate.

**Numbers:** rpms 2045 → 2037; desktop entries 192 → 179; **launcher-visible 34 → 17**.
The rpm total barely moves because the removals are leaf apps and the 2,000
underneath are ADR-002's driver/codec/font stack. 17 is not yet 3.2's ~12.

**The defect this WP exists to have caught:** removing `kmenuedit` removed
`plasma-desktop` and `plasma-workspace` and the build exited **0**. `dnf remove`
takes dependents with it, and verifying that the *listed* packages are gone does
not notice the unlisted casualties. `packages.yml` now declares `protect:` and a
removal that takes any of it fails the build. It then caught `PackageKit-Qt6`
(86 packages incl. dolphin) — which `rpm -q --whatrequires` had reported as
required by nothing, because Plasma depends on the **SONAME**, not the name.

**Also found:** `protect:` listed `sddm`, which Fedora 44 does not install at all
(plasmalogin replaced it), so the login screen was unguarded behind an entry that
read like protection. Protect entries must now exist or the build fails.

**ADR-015 (issue #2) closed:** LLMNR off (`resolved.conf.d`), `openssh-server`
removed. The nightly's expected-red advisory job is deleted, not kept alongside —
a failure with a green place to land is not a failure. PRD 7.5's promote-to-stable
gate is unblocked on this axis.

**Fonts:** Liberation/Carlito/Caladea added — metric-compatible, so Windows
`.docx` keeps its line breaks. Verified by `fc-match`, not by rpm presence alone.
Schibsted Grotesk is unpackaged in Fedora; **WP-05 must bundle it**.

**NOT done — WP-02 is not DONE until these land:**

- **ADR-017 adopted (2026-09-03): the idle-RAM budget is GPU-measured; CI gates
  via a calibrated offset.** This is the **second evidence-driven budget
  amendment** — the ISO budget (2.8 → 3.5 GiB gate, for ADR-010's offline sideload
  set) was the first. `ram.idle.product` = 1126 MiB (target 950), GPU-rendered on
  the 10.2 low-end row, and the only number a release claim may cite.
  `ram.idle.ci` = product + `render_offset` (182 MiB), the llvmpipe tripwire CI
  can actually run — **computed, never stored**, so the CI gate cannot move
  without editing the offset's provenance record. Recalibrate at every M-gate
  from one paired measurement; >25% drift is a finding, not an update.
  Removing the OSK or `xwaylandvideobridge` for RAM is forbidden, and both are now
  in `protect:` rather than in prose. Commissioned separately: the OSK starts only
  where a touchscreen exists.
- **ADR-018 adopted (2026-09-03): protocol, two-tier gating, budget re-set, OSK
  rework.** Third evidence-driven budget amendment (ISO first, ADR-017 second).
  The product metric is now the **median of 3 full boots**, all three recorded —
  one run with ~50 MiB of noise was deciding a gate with under 4 MiB of headroom.
  `ram.idle.product` re-set to **1200 MiB** (target 1100) from the measured
  post-trim floor plus one noise-spread; **950 is reclassified as an aspiration
  that gates nothing**, contingent on the clause 5 investigation. Offset 186.5
  adopted with provenance, so `ram.idle.ci` = **1386.5**, still computed and never
  stored. A **relative ratchet** on summed userspace PSS (baseline 576, +25 MiB)
  is now the creep detector, because a gate slack enough not to be a coin flip is
  slack enough to hide steady growth.
- **ADR-021 verified on a real CI-equivalent run: `EXIT=0`.** steady 917.1 (inside
  the 963.2 CI target), shmem 45.4, **PSS 753.9 — −1.4 against the 755.3 baseline**
  where it read +179.3 before. boot 8.1 s. The run that failed now passes for the
  right reason.
- **Caveat recorded for the M-gate re-pairing (ADR-020 §3 / ADR-021 §4): llvmpipe
  is far less reproducible BETWEEN run-sets than GPU is.** Same image, two sets:
  llvmpipe steady medians 948.1 vs 917.1 (**31.0 MiB apart**, within-set spreads
  10.9 and 5.7); GPU medians 762.6 vs 759.9 (**2.7 MiB apart**). So the 188.2
  offset carries roughly ±31 MiB of between-set uncertainty, and a re-pairing that
  moves by that much is **not** evidence of a rendering-stack change. Not a problem
  today — the CI gate has 71.1 MiB of headroom over the measured 917.1 — but a
  future pair should be read with this in mind rather than as a precise constant.
- **ADR-021 (2026-09-03): the PSS ratchet is CI-denominated.** ADR-018 §3 seeded
  it at 576, which was **GPU-measured**, while the ratchet runs on CI's llvmpipe —
  where a healthy build reads **755.3**, so it fired at **+179 on every PR**. Same
  one-renderer-baseline / other-renderer-measurement error ADR-017 fixed for idle
  RAM, one instrument over, and it would have blocked every merge.
  Interim seed is now 755.3 (llvmpipe, paired with GPU 574.0, provenance
  recorded), retiring into a rolling median of 10 CI nightlies. **No offset** —
  deliberately asymmetric with `steady`, whose CI gate stays a computed sum
  forever because its canonical value is the GPU number; the ratchet's canonical
  value *is* the CI history, so it translates once and then stops. GPU PSS is
  informational and never cross-compared.
- **IDLE-RAM ACCEPTANCE: MET (2026-09-03, ADR-020 §2).** Fresh median-of-3 on a
  new build, GPU-rendered, under ADR-020's instruments:

  | instrument | measured | gate | verdict |
  |---|---|---|---|
  | `steady` | **759.9** MiB (763.8 / 757.4 / 759.9, spread **6.4**) | 800 (target 775) | inside the **target** |
  | `shmem` at rest | worst **118.0** MiB (55.2 / 54.0 / 118.0) | 250 ceiling | within |
  | userspace PSS ratchet | 574.0 MiB, **−2.0** vs baseline | +25 | quiet |

  All three of clause 2's conditions met, so ADR-018 clause 7 closes. **40.1 MiB
  of headroom against 6.4 MiB of noise** — decisive in both directions, which is
  the property 1126, 1200 and the committed denomination all lacked. `boot` 8.3 s,
  inside target; `baloo_file` absent; OSK absent.
  Informational only: `MemTotal − MemAvailable` medians 1208.6 (spread 14.9) and
  gates nothing.
- **Evidence for ADR-020 §4's queued question.** The ~118 MiB shmem figure
  recurred — but in **run 3** this time, where it was **run 1** before. So it is
  **not** first-boot behaviour: shmem at rest is **bimodal** (~54 or ~118),
  independent of run position. Two observations is not a characterisation, but it
  rules out the simplest explanation and the 250 MiB ceiling comfortably covers
  both modes.
- **ADR-019 §0 trigger FAILED (2026-09-03). Nothing adopted; escalated per the
  clause.** (Superseded by ADR-020, which split the instruments.) committed spread **59.2 MiB > 25 MiB threshold**, so the cache account
  I proposed is **wrong** — cache does vary (50.9) but is not where the metric's
  variance lives. The failure is single-source: **Shmem** moves 117.8/55.3/53.4
  (spread 64.4) while AnonPages holds ±9.3, SUnreclaim ±0.4, KernelStack ±0.1,
  PageTables ±0.3. Committed's spread *is* Shmem's spread.
  This is **not** "something real breathing ±75 MiB": process memory is stable and
  nothing is leaking. Shmem on Wayland is largely `wl_shm` graphics buffers —
  genuinely committed (unreclaimable without swap) but a transient pool sized by
  what was on screen at sampling. `committed − Shmem` has a spread of **9.3 MiB**,
  well inside the threshold; that observation is recorded for the owner and
  **deliberately not acted on**, because "the statistic fails its own trigger but
  would pass if we drop the failing term" needs a decision, not an agent.
  Open: run 1's 117.8 MiB was one outlier, not a spread — first-boot behaviour, an
  unsettled buffer pool, or bimodality needs more samples (S-size).
  ADR-018's current gate is unaffected and comfortably met this time: median
  1144.3 vs 1200, headroom 55.7 MiB — after 0.8 MiB last time, which is its own
  argument against treating one median-of-3 as a verdict.
- **Superseded by the above — first ADR-018 median-of-3 (2026-09-03, post-rework): 1126.1 / 1199.2 / 1201.5,
  median 1199.2 against the 1200 gate.** Passes by **0.8 MiB**, with one run over
  the gate and a spread of **75.4 MiB** — wider than the 51.7 MiB spread the
  gate's headroom was derived from. **Acceptance is NOT recorded as MET**: clause
  7's letter is satisfied, but a 0.8 MiB margin on a metric with 75 MiB of noise
  is not evidence of conformance, and claiming it would be the "green or honest"
  failure (R-A) in its most tempting form. Referred back to the owner.
  The three runs were **structurally identical** — same processes, plasmashell
  348 MiB PSS in each, OSK absent in all three, summed userspace PSS varying by
  1.7 MiB. What moved was `user.slice`'s charged memory, i.e. page cache that
  `MemAvailable` declines to call reclaimable. **The absolute metric is noisy and
  the relative one is stable — the reverse of clause 3's assumption**, which is
  now instrumented (anon/cached/slab/pagetables recorded per run) so the next
  measurement settles it rather than arguing it. Likely a clause 4 floor-vs-gate
  review item.
- **The OSK rework is verified working and kept the saving.** OSK absent across
  all three boots; userspace PSS 574.4 vs the 576 baseline (−1.6, ratchet allows
  +25). So session scope removed the greeter risk without costing the trim.
- **The OSK trim was reworked because the shipped one was unsafe.** It wrote
  `/etc/xdg/kwinrc`, a system-wide default the greeter's own kwin also reads, so a
  late-detected digitizer could have suppressed the keyboard at the **login
  screen** — an owner unable to type their password. The rework is session-scope
  only (nothing writes to `/etc`, structurally asserted in test), enable is eager
  and sticky on any touchscreen sighting including hotplug via udev marker,
  disable is lazy, and Automatic/Always/Off is the user's to set.
  **Ships to `:testing` on that structural safety; `:stable` for this feature is
  gated on the now-mandatory touch seat in 10.2.**
- **Superseded: ADR-017's result — the trim works; the gate was MARGINAL,
  not met.** `plasma-keyboard` no longer runs on a touchless machine: GPU idle
  RAM fell 1242.0 → mean 1139.9 MiB, llvmpipe ~1424 → 1326.4. But three GPU runs
  on the same image gave **1123.1 / 1122.4 / 1174.1** — two pass, one fails, with
  a spread of 51.7 MiB against under 4 MiB of headroom. R-A treats flaky as
  broken, so **idle-RAM acceptance is NOT recorded as met.**
  The variance is not the desktop: the failing run's user-visible PSS was *lower*
  than a passing run's (573.8 vs 577.7). It is system/kernel memory plus
  `MemAvailable`'s own heuristics. **This is a protocol gap** — ADR-017 specifies
  the settle but not a repeat count, so one noisy run decides a gate near the
  line. Proposed to the owner (issue #32): median of 3 for the product metric.
  Not implemented; changing how a gate decides is not an agent's call.
  The render offset survived the trim — 186.5 measured vs 182 recorded, +2.5%,
  well inside clause 3's 25%. Deliberately **not** updated: adjusting a
  calibration constant while reporting a marginal failure is indistinguishable
  from tuning the gate to pass.
- **Earlier finding, now superseded: over by 116 MiB, not ~300.** Measured both ways on
  the same image: **1242 MiB with a GPU** (`MERIDIAN_VM_GL=1`, virgl) vs ~1424 MiB
  mean with software rendering. The 182 MiB difference is llvmpipe's tile buffers,
  which no machine with a working GPU driver allocates — 155 MiB of it inside
  plasmashell alone. Escalated as issue #32 with the full evidence; the budget has
  NOT been edited (R-E). The remaining 116 MiB cannot be found without giving up
  a capability: the only candidates big enough are the on-screen keyboard
  (72 MiB PSS) and Wayland→X11 screen sharing for Zoom/Discord (29 MiB), and both
  together still miss. The open question is whether PRD 2's budget means idle RAM
  on Pat's machine or in our test VM — they differ by 182 MiB and share a name.
- **Two leads that looked obvious and were wrong**, both closed by measurement:
  the enabled-but-pointless system services (`sssd`, `systemd-homed`, `mdmonitor`,
  mandb…) do not appear in the top 20 at all; and `plasma-keyboard`, second by RSS
  at 256 MiB, freed **−5.6 MiB** when killed and respawned immediately, because
  that RSS is shared Qt pages. **RSS is not a savings list** — the perf suite now
  reports PSS alongside it so the next person does not repeat this.
- **Baloo was running despite ADR-016 and is now genuinely off.** Masking
  `baloo_file.service` was cosmetic: the XDG autostart entry starts it regardless,
  gated on a key that defaults to true when unset. `/etc/xdg/baloofilerc` fixes it,
  the perf suite fails if it is running, and the fix is **verified** on a rebuild.
- **Boot time passes; earlier failures were cold host cache.** Same image: 16.9 s
  cold, **7.8 s** warm — inside the 10 s target. Worth knowing before a 14 s
  reading is treated as a regression.
- Idle-RAM run-to-run variance is ~±25 MiB, larger than the 28 MiB Baloo saved.
- **OLD, superseded:** idle RAM 1448.2 MiB / over by 322 MiB.
- **CI is producing no workflow runs at all.** Since 21:39 on 2026-09-02, four
  pushes and a deliberate empty commit created zero runs — not cancelled, never
  created. Actions reports enabled, no concurrency guard, no path filters;
  diagnosing further needs `admin:org`. With the build host also unable to make
  a disk image (bootc-image-builder needs rootful podman, sudo is
  password-gated), **no VM measurement of any kind can be taken right now.**
- Launcher screenshot for the 3.2 visible-set acceptance.
- `systemctl --failed` empty is asserted by `smoke`, not yet confirmed on this image.

**Open thread for WP-07:** the remaining 5 launcher entries above 3.2's ~12 are
`konsole`, `kmenuedit`, three `fcitx5` entries and a duplicate System Settings.
All are dependency-locked into Plasma, so they must be **hidden** via KIOSK, not
removed (ADR-006's konsole precedent). Removing `kmenuedit` is what deleted the
desktop.

**Open thread for WP-04:** `ublue-os-update-services` is still installed and
overrides `rpm-ostreed` and flatpak update timers. That collides with ADR-008's
bootc+greenboot path. Left alone deliberately — WP-04 owns the update pipeline
and should decide, rather than WP-02 changing update behaviour as a side effect
of de-bloating.

## WP-04 DONE — 2026-09-04

Every acceptance item met. **Phase 0 is complete: WP-00 through WP-04 are all DONE.**

| Acceptance (PRD WP-04) | Result |
|---|---|
| rollback drill green in CI — the flagship | **PASS**, on real hardware; nightly job wired |
| staged-update flow observed | **PASS** — `bootc switch` staged, reboot activated it |
| unsigned/wrong-key image REFUSED (negative test) | **PASS** — signed accepted, unsigned refused |
| no update activity produces user-visible UI | holds — the status file is read-only data for WP-12 |

**Carried forward, recorded rather than closed quietly:**

- **`bootc upgrade` honouring `policy.json` is UNPROVEN.** The negative test
  proves *skopeo* enforces it; bootc is a different consumer. Last piece of
  ADR-022's VERIFY. Gates the first `:stable`.
- **`keyPaths` ANY-vs-ALL is unproven** — matters only for ADR-023's rotation
  overlap, nothing today.
- **The recovery key does not exist**, so the fleet trusts one key and is not
  recoverable. Gates the first `:stable` by design; custodying it earlier would be
  the wrong instinct (ADR-023 §5).
- **The permissive `default` in `policy.json` is unresolved.** ADR-022 called it a
  `:testing`-only state to tighten once the negative test passed. It has passed.
  My recommendation is to KEEP it: the scoped rule already enforces "our images
  must be signed" — which is what `bootc upgrade` pulls — while `default: reject`
  would add nothing to update integrity and would break `toolbox`/`distrobox`,
  which ADR-004 and PRD 3.2 ship deliberately for Advanced users. **Owner
  decision, unchanged pending an answer.**
- `keyPaths` needs containers-image ≥ ~1.14. Ubuntu 24.04's skopeo 1.13.3 rejects
  it; the image's 0.67.0 accepts it. Portability note in `docs/updates.md`.

---

## WP-04 — rollback drill GREEN (2026-09-04)

**The flagship passes.** ADR-008's self-healing promise is mechanically true and
proven, not asserted:

```text
before      sha256:7fa949b6…   original
            staged a sabotage image that breaks graphical.target
poll 1-4    sha256:88bd7ca6…   the machine ran the BAD deployment
poll 5      sha256:7fa949b6…   returned to the original on its own
marker      /var/lib/meridian/rollback-happened @ 2026-09-04T01:29:54Z
```

**PRD WP-04's `[VERIFY greenboot+bootc integration]` is RESOLVED: greenboot does
drive bootc's rollback.** The pre-authorized boot-counter fallback is not needed.

Nothing was faked. The sabotage breaks `graphical.target` — what
`10-meridian-desktop.sh` actually checks — so the real detection path ran, and the
marker was written by greenboot's own `red.d` hook rather than planted.

**Signing is proven too** (2026-09-03): the negative test is green — signed
accepted, unsigned refused, policy demonstrably live. ADR-022's hard gate on the
first `:stable` is satisfied. cosign writes `sha256-<hex>.sig`, so the tag-naming
incompatibility I feared was a false alarm from my local harness.

**Five scaffolding defects cost a cycle each** getting here, all mine rather than
the product's: cosign reading a different auth store than skopeo; the negative
test using the runner's `registries.d` instead of the image's; a `_comment` key in
`policy.json` that made the image **unbuildable** (against a strict-parser rule I
had proved myself hours earlier); `bootc status` without `sudo`; and a sudo
password prompt that HUNG a serial console for 120 s and read as bootc being
broken. None produced a false pass — each surfaced as a loud, specific failure —
but the pattern was assuming the environment instead of checking it.

**Two product defects found on the way, both silent:**

- **greenboot was installed and inert.** Nothing in this build runs
  `systemctl preset-all`, so `WantedBy=` is dead letter and greenboot had no
  enablement symlink. Automatic rollback would have been false on every machine
  while every artifact looked correct. `tests/lint/units_enabled.py` now guards it.
- **greenboot's own DNS health check would roll back offline machines.** It
  resolves `/etc/ostree/remotes.d`, which IS populated, so a laptop with no Wi-Fi
  fails and after three boots loses a good update. Disabled, for the same reason
  our own check asks whether NetworkManager can *start* rather than whether it is
  *connected*.

---

## WP-04 in progress — update mechanism and signing (2026-09-03)

**Delivered (PR 1):** `meridian-os-update.{service,timer}` (daily, randomized,
metered-aware, **stage only — never reboots**, ADR-008), flatpak timer,
`meridian-maintenance.target`; greenboot health checks + rollback marker; the
PRD 8.0 status contract as a committed JSON Schema with a contract test driving
the real publisher through all five states; cosign signing behind the `release`
environment's required reviewers; the negative test; `docs/updates.md`.

**PRD deviations, recorded not worked around:** the greenboot check asks about
`display-manager.service`, not `sddm` — Fedora 44 ships plasmalogin, so checking
`sddm` would roll back every good update forever. `policy.json` lives in `/etc`,
not `/usr/etc`, which `bootc container lint` rejects (WP-01 hit this too).

**ADR-022 (keyless signing): VERIFY says the client cannot express it.**
`fulcio` supports only `oidcIssuer`, `subjectEmail`, `caPath`, `caData`; GitHub
Actions OIDC carries the workflow identity in a URI SAN with no email SAN. The
pre-authorized key-pair fallback is in force. `ci/verify-signing-policy.sh` re-asks
this on every build — if an identity field ever appears, **retire the key**.

**ADR-023 (recoverable trust anchor):** `policy.json` trusts a key *set* via
`keyPaths`. Its stated fallback — parallel policy requirements — **would not work**:
requirements in a scope are ANDed (verified), so two side by side demand *both*
signatures and break every rotation. The recovery key is **not generated**; it
gates the first `:stable` and is deliberately not custodied earlier.

**Found while verifying: we were shipping only half the client side.** A correctly
signed image is REJECTED until `registries.d` sets `use-sigstore-attachments`.
Without it the policy rejects every image on every machine at once, and it would
present as "signing is broken" rather than a missing config. Now shipped.

**UNPROVEN, and all gate the first `:stable`:**

- whether `bootc upgrade` honours `policy.json` at all (needs a booted machine);
- whether `keyPaths` means ANY or ALL — if ALL, ADR-023's rotation overlap does
  not exist;
- **the live one:** cosign v3.1.3 writes `sha256-<hex>`, containers-image looks for
  `sha256-<hex>.sig`. If that reproduces in CI, images we sign will not verify on
  the machines receiving them. The negative test is what surfaces it.

**Nothing is signed yet.** The `sign` job has never run — it lands with this PR.

---

## WP-03 closed — 2026-09-02

All four acceptance items met. The last needed the merge itself:
`workflow_dispatch` cannot target a feature branch, so the flaky-rate gate could
only run once `nightly.yml` was on `main`. First run: **0 failures across 10
consecutive passes** on x86_64 under KVM.

**The nightly split works as designed.** Its first real run shows the gating step
green and the ADR-015 step advisory-red with a warning — and the **sshd violation
is now visible**, which it never was before: MJ-8's fix (collect both violations,
assert once) means the second finding is no longer hidden behind the first.

**Three review rounds, ~30 findings, one durable lesson.** Each round found the
same defect class one layer further out: vacuous passes inside the suites, then
in the layer around them, then in the composition of the gate itself. The answer
to "can this check fail?" kept living outside the file being reviewed.
`tests/lint/wired.py` is the response — the first check here whose subject is the
other checks. It does not close the class (it verifies a check is *invoked*, not
that its environment can run it — a gap that surfaced immediately when the lint
job lacked Pillow), but it moves the boundary out one more step.

**Open, stated, and owned:**

- `security` is RED on two real ADR-015 violations — **WP-02's to fix** (issue #2).
  **PRD 7.5's promote-to-stable gate cannot be satisfied until it is green**, so
  no image can legitimately reach `:stable` before WP-02 lands.
  **→ CLOSED by WP-02 (2026-09-03): both fixed, `security` green, issue #2 done.**
- `screens` cannot run in CI: only aarch64 baselines exist. x86_64 baselines must
  be generated on an x86_64 runner and committed deliberately (R-F) — best done
  with WP-05, when every baseline changes anyway.
- `stories` is 0 of 23; each lands with the WP that ships its flow.
  (22 when this was written; ZT-23 was added later by ADR-019 §7.)
- Not delivered, recorded rather than hidden: OCR text assertions, the vncdotool
  input fallback, and the `perf` suite (blocked on WP-02's scripts).
  **→ `perf` DELIVERED by WP-02 (2026-09-03); OCR and vncdotool remain open.**
