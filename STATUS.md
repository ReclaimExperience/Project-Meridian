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
| WP-01 | Base image: builds, boots, publishes | 0 | M | medium (external base) | WP-00 | IN PROGRESS |
| WP-02 | De-bloat & package curation | 0 | M | low | WP-01 | TODO |
| WP-03 | VM test harness & story framework | 0 | L | medium | WP-01 (images to test) | TODO |
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

## WP-01 Base image: builds, boots, publishes — IN PROGRESS 2026-09-01 (agent run 1)

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

**NOT yet verified — this WP is not done:**

- **SDDM login greeter** — see the correction above. A graphical session starts;
  the greeter has not been shown.
- `just vm-run x86_64` has never been executed. Until this review it also passed
  no UEFI firmware and would have booted SeaBIOS against a UEFI qcow2; firmware
  resolution is now shared by both arches but the x86_64 boot remains unverified.

**Now proven (2026-09-01, after `gh auth login`):**

- Both arches build, push and verify their labels in CI. `skopeo inspect` of the
  **pushed** x86_64 image reports `base.name=ghcr.io/ublue-os/kinoite-main:44`,
  confirming the ADR-002 split base is real on both sides, not just on paper.
- Free `ubuntu-24.04-arm` runners are available to this repo, resolving the
  PRD 7.3 `[VERIFY]`. Record the fallback (qemu cross-build, nightly only) as
  unused.
- x86_64 first failed with "no space left on device": hosted runners have ~14 GB
  on `/` and the ublue base does not fit. `ci/prepare-runner.sh` moves the
  container store to `/mnt`. aarch64 had passed only because the Fedora Kinoite
  dev base is smaller — luck, not headroom — so it runs for both arches.
- Lint tool versions are pinned in `ci/tool-versions.env`. CI was installing
  Ubuntu's shellcheck 0.9.0 while the dev machine had 0.11.0, so `just lint` was
  green locally and red in CI on the same commit — a direct violation of PRD 7.1.

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

## Repository governance — armed 2026-09-01, one step outstanding

The repo is now **public** (ADR-014 satisfied), which also made branch protection
available on the free plan. `main` now requires `lint`, `build-x86_64` and
`build-aarch64` to pass, plus one code-owner approval, with stale reviews
dismissed, linear history enforced, and force pushes and deletions blocked.
Admins may bypass, deliberately: GitHub forbids self-approval, so full
enforcement would deadlock a solo owner's own PRs.

**Still unarmed:** the `@ReclaimExperience/owners` team has no write access to
this repo, so all 13 CODEOWNERS rules fail to resolve. GitHub's
`codeowners/errors` endpoint reports every one as "Unknown owner". **Rule R-H is
therefore still a convention, not a gate** — the review requirement is live, but
no owner can satisfy it, so merges rely on the admin bypass. Granting the team
needs org-admin rights; the commands are in `.github/CODEOWNERS`.

**Follow-up for a later WP:** add the `codeowners/errors` query to CI so an
unresolvable owner fails the build. Deliberately not added now — it would fail
today and block the very PRs that carry the fix, and a check wired to be
non-blocking "for now" is how gates rot.

Secret scan after going public: no credentials, tokens, keys or PII in tracked
content or in any deleted file across the whole history. Commit author emails
are visible, which is normal for a public repo.

## Third review round — the same mistake, one layer down

Third consecutive **CHANGES REQUESTED**. The pattern repeated exactly: each fix
was verified against *a* path rather than *the* path.

| ID | What was still wrong | Fix, and how it is proven now |
|---|---|---|
| N-3 (blocker) | The tag/escape guards went on the **block-sequence** branch. A value can also arrive via a **flow sequence**, and the shipped `os/packages.yml` uses the flow form on all four lists — so the guards sat on the branch the real file never takes. `mask: ["baloo\x5Ffile.service"]` ran `systemctl mask baloo\x5Ffile.service`, which succeeds against a nonexistent unit: **Baloo silently not masked (ADR-016), exit 0, green build.** 25 silent divergences found. | Validation moved into one `validate_scalar()` that **both** routes call. The parser file now carries a warning that a rule added to one branch is not added. `MUST_REJECT` gained a flow variant of every defect; the suite went 9 → 19 cases. Confirmed against the shipped script in a container: exit 2. |
| N-2 (major) | The rewritten `codeowners.sh` caught the one historical shape and essentially nothing else — a typo of a live rule, a renamed subdirectory, or a file that will never exist all passed, and it false-positived on legal globs. | Rewritten to expand each pattern against the real git index the way GitHub does, requiring ≥1 match or a `# planned: WP-NN` marker. All five shapes the reviewer listed as missed are now caught; four globs accepted, a glob matching nothing still caught. It immediately failed 3 live rules the previous version called clean — those are now honestly marked planned. |
| N-5 (major) | The completeness check compared shebang count to extracted-recipe count and never checked the body was **non-empty**. Tab- and 2-space-indented recipes extracted as empty and were reported `ok`; non-shebang recipes were not linted at all. | Indent is derived from the body; an empty or truncated body is an error. Completeness is now checked against `just --dump --dump-format json` — `just`'s own answer — instead of against our parser agreeing with itself. **That immediately exposed a fresh regression of the same class: the header pattern excluded `=`, so `build`, `vm-image`, `vm-run` and `vm-test` were silently unlinted.** Coverage went 8 → 23 recipes. All six shapes in the reviewer's break matrix are caught. |
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
