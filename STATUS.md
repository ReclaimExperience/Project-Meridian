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
| WP-01 | Base image: builds, boots, publishes | 0 | M | medium (external base) | WP-00 | TODO |
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
