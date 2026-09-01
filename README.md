# Meridian OS

> A minimal, unbreakable, image-based Linux distribution that lets a Windows
> user switch and never notice they left — no terminal, no tinkering, no bloat,
> no spyware.

Windows 10 support ended in October 2025. Hundreds of millions of working PCs
fail Windows 11's hardware requirements. This is built for the person who owns
one of them and uses a computer the way most people do: a browser, files, email,
printing, video calls, a handful of apps.

**Status: pre-alpha.** Phase 0 of 6. Not installable yet. See [STATUS.md](STATUS.md).

## The seven pillars

1. **It never breaks.** One immutable image, atomic A/B updates, automatic rollback.
2. **Nothing requires a terminal. Ever.** Enforced by 22 story tests in CI.
3. **Familiar by default.** Start button, taskbar, `Win+E`, `F2`, drives that pop up.
4. **Minimal is a feature.** ~12 preinstalled apps, idle RAM under 1.1 GiB.
5. **Private by architecture.** Zero telemetry — and a CI test that proves it.
6. **Hardware just works.** Proven by a panel the user sees *before* installing.
7. **Honest about Windows software.** Told the truth before wasting an afternoon.

## How this repository is built

Read [`docs/PRD.md`](docs/PRD.md). It is the whole product: 16 architecture
decisions, a screen-by-screen spec, and 27 work packages with machine-checkable
acceptance criteria. It is executed by agents, one work package at a time, under
the contract in [CONTRIBUTING-AGENTS.md](CONTRIBUTING-AGENTS.md).

Two rules explain most of the repo's shape:

- **If it isn't reproduced by `just <target>` from a clean checkout, it doesn't
  exist.** No artifact may depend on anyone's hand-configured VM.
- **Green or honest.** No work is marked done with failing, flaky or skipped
  tests, and no claim lands without pasted evidence.

## Quick start (development)

```bash
just            # list every target
just lint       # the full lint suite — green from day one
just test-lint  # prove the lints catch what they claim to
```

Targets that aren't implemented yet fail loudly and name the work package that
owns them. Requires `bash`, `just`, `shellcheck`, `ruff`, `python3` with
`jsonschema`; building images additionally needs `podman`, `skopeo` and `qemu`
(see PRD section 7.2).

## Layout

| Path | What lives there |
|---|---|
| `os/` | The OS: Containerfile, package lists, files overlaid into the image |
| `shell/` | Theme, look-and-feel package, the three custom plasmoids |
| `apps/` | Welcome, Software, Windows app support, Migration, Settings pages |
| `installer/` | Live ISO and the three-screen installer |
| `catalog/` | What switchers see in the store, and the Windows-app truth table |
| `tests/` | The harness and every gate: stories, perf, privacy, security, lints |
| `docs/` | PRD, ADRs, design tokens, contracts, help, QA records |

## License

Code MIT ([LICENSE](LICENSE)), docs CC-BY-SA-4.0, theme assets derived from
Breeze LGPL-2.1+. Third-party notices in [NOTICE](NOTICE). Built on Fedora, KDE
Plasma, Universal Blue, and the work of thousands.
