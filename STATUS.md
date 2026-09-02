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
| WP-02 | De-bloat & package curation | 0 | M | low | WP-01 | TODO |
| WP-03 | VM test harness & story framework | 0 | L | medium | WP-01 (images to test) | IN PROGRESS |
| WP-04 | Update pipeline, rollback, signing | 0 | M | medium | WP-01 | TODO |
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

0 / 22 green. No harness yet (WP-03). Every story is currently unproven.

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

## WP-03 VM test harness — IN PROGRESS 2026-09-02 (agent run 1, slice 1 of ~6)

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

**Still to deliver:** OCR text assertions, screenshot-diff with baselines and
masks, `tests/stories/` + `zt_template.py`, `perf`/`screens`/`security`/`privacy`
suites, CI `vm-test` job, `docs/testing.md`, and the acceptance items — x86_64
smoke in CI, deliberately-broken-assertion artifacts, `mtest` absent from any
pushed digest, and 10x consecutive green for the flaky-rate gate.
