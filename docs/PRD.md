# Meridian OS — Product Requirements Document

**Codename:** Project Migration · **Document version:** 1.0 · **Date:** 2026-09-01
**Status:** APPROVED FOR EXECUTION
**Execution model:** This PRD is written to be executed by a fleet of Claude Opus 5 (medium reasoning) agents working in work packages. Section 0 and Section 14 are the agent contract — read them before touching anything.

> **One sentence:** Meridian OS is a minimal, unbreakable, image-based Linux distribution that lets a Windows user switch and never notice they left — no terminal, no tinkering, no bloat, no spyware.

---

## 0. How to use this document (read first, every agent, every session)

### 0.1 Reading order for an agent starting a work package

1. This Section 0, then Section 14 (Agent Operating Rules) — the contract.
2. The Architecture Decision Records in Section 2 that your work package lists under "Governing ADRs". ADRs are **settled law**: you never re-litigate them, you implement them. If an ADR appears wrong or impossible, you stop and escalate (see 14.6) — you do not decide differently on your own.
3. Your work package (WP) in Section 8, in full, including Forbidden actions and Escalation triggers.
4. `STATUS.md` at the repo root — the live state of the world. Trust it over your assumptions about what other WPs have done.
5. Only your WP's **Inputs**, defined for every WP as: the files/paths named in its own body, the Deliverables of the WPs it Depends on, the interface contracts it touches (8.0), and those WPs' STATUS.md entries. Do not free-roam the repo to "get context"; it wastes your context window and causes drift.

### 0.2 Conventions used in this document

- **MUST / MUST NOT / SHOULD / MAY** carry RFC-2119 meaning. A MUST that cannot be met is an escalation, never a silent downgrade.
- All file paths are repo-relative unless they start with `/usr`, `/etc`, `/var` (paths inside the OS image) or `~` (paths in a user session).
- `${BRAND}` means the product name. Until WP-26 (naming) completes, `${BRAND}` = "Meridian OS", brand id = `meridian`. **No agent may hardcode the brand name outside the branding module** (see 6.5); this makes the final rename a one-commit change.
- **Verify-then-use:** any external fact marked `[VERIFY]` (an image tag, a repo URL, a tool's current capability) MUST be verified at execution time before being relied on, using the exact verification command given. External ecosystems move; this document ages. When a `[VERIFY]` fails, follow the listed fallback; if there is no fallback, escalate.
- "The mockup" means the approved design reference `docs/design/mockup/Meridian OS.dc.html` (provided by the owner; its extracted tokens are Appendix A and its behavior is specified in Section 5 — the written spec, not the mockup file, is authoritative where they differ; differences are listed in 5.12).

### 0.3 The one invariant that outranks everything

**INV-0 (Zero-Terminal Invariant):** Every task a target-persona user can want to do MUST be achievable through the GUI alone. No error dialog, help text, first-run experience, or documented workflow may instruct the user to open a terminal, edit a config file, or run a command. The canonical user stories in Section 10.1 (22 at time of writing) are the enforcement checklist; every release gate runs them. Any WP that ships a user-visible flow MUST add or update the corresponding story test.

If you find yourself writing documentation that says "open a terminal", you have found a product bug. File it and fix the product, not the documentation.

---

## 1. Product vision

### 1.1 The moment

Windows 10 support ended in October 2025. Hundreds of millions of working PCs fail Windows 11's hardware requirements, and the users who own them face three options: buy a new computer, run an unsupported OS, or switch. Meanwhile Windows 11 itself is pushing ads in the Start menu, mandatory accounts, Recall-style surveillance features, and OneDrive upsells onto the users who *can* upgrade. There has never been a larger population of people who *want* off Windows — and mainstream Linux still greets them with a choice of 300 distros, a package manager, and a forum thread telling them to edit a config file.

Meridian OS is built for exactly this person. Not for gamers (Bazzite exists), not for developers (Fedora, Arch and NixOS exist), not for tinkerers (everything exists). For the person who uses a computer the way most people use a computer: a browser, files, email, printing, video calls, a handful of apps — and who wants the machine to be quiet, familiar, fast, and none of anyone else's business.

### 1.2 The seven pillars (product principles, in priority order)

1. **It never breaks.** The OS is a single immutable image with atomic A/B updates and automatic rollback. There is no package manager to misuse, no dependency hell, no half-updated state. A failed update heals itself. This is not a QA aspiration; it is an architectural property (ADR-001).
2. **Nothing requires a terminal. Ever.** (INV-0.) The terminal exists, hidden, for the 1% — behind an authenticated Advanced toggle, like Windows' own admin tools.
3. **Familiar by default.** Start button, taskbar, system tray, window controls on the right, Win+E, Ctrl+C, F2, UAC-style password prompts, drives that pop up when plugged in, `Documents`/`Downloads`/`Pictures` and nothing scarier. A Windows user's muscle memory works on day one.
4. **Minimal is a feature.** ~12 preinstalled apps. No office suite preload, no mail client preload, no games, no trials, no "McAfee moment". Idle RAM ≤ 1.1 GiB. Anything else is one click away in a curated store.
5. **Private by architecture.** Zero telemetry. No accounts required. No ads. The only network calls a fresh install makes are update checks and the things the user asks for. This is the marketing spearhead and it must be literally, auditably true (Section 12).
6. **Hardware just works.** Wi-Fi, Bluetooth, printers, webcams, USB drives, battery management, Nvidia — inherited from the best driver-complete base in the ecosystem plus our own enablement work, and proven by a hardware test panel the user sees *before* installing.
7. **Honest about Windows software.** A built-in compatibility layer runs many Windows programs, and the product tells the truth about which ones before the user wastes an afternoon. Overpromising here is how you lose a switcher forever.

### 1.3 Personas (design targets — every UX decision is tested against these three)

**Pat, 58 — "the Windows 10 refugee" (primary).** Retired teacher. HP desktop from 2017 (i5-7500, 8 GB RAM, 1 TB HDD + small SSD), fails Win11 check. Uses: Chrome, Gmail, Facebook, online banking, photos from a phone via USB cable, prints boarding passes on an HP inkjet, plays media files a nephew sends. Fears: losing photos, "breaking it", viruses, being tricked. Will never open a terminal; will call the nephew instead. Success = Pat forgets which OS this is within two weeks.

**Sam, 41 — "the small-business operator" (primary).** Runs a 6-person landscaping company from a 2019 laptop. Uses: Microsoft 365 in the browser, QuickBooks Online, WhatsApp Web, a supplier's Chrome-only ordering portal, spreadsheets, PDFs of invoices, a cheap Brother laser printer, and **one legacy Windows .exe** — a label-printing utility from a hardware vendor, last updated 2019. Success = every SaaS tool works in a first-class browser, the .exe runs under Windows App Support, invoices print, and updates never interrupt a workday.

**Jordan, 24 — "the family IT department" (secondary).** Installs Meridian for parents and grandparents. Technical enough to dual-boot, not interested in maintaining Arch for their mother. Wants: set-and-forget updates, remote-help-friendly defaults, the Advanced toggle for themselves. Jordan is also our community evangelist — the person who files good bug reports. Success = Jordan installs it on four family machines and stops getting support calls.

### 1.4 Non-goals for 1.0 (explicitly out of scope — do not build, do not scaffold "for later")

- Gaming as a focus (Steam is installable from the store; we do not tune for it, ship gamescope, or advertise it).
- ARM consumer hardware support (aarch64 is CI-supported for development on Apple Silicon only; no ARM laptop enablement work).
- Enterprise fleet features: domain join, MDM, Group Policy analogs, SSO at login.
- Touch/tablet-first UX, convertibles, phones.
- 32-bit x86, PowerPC, RISC-V.
- A from-scratch desktop shell, compositor, or toolkit (ADR-003, ADR-005).
- Our own package format, repository, or app sandbox (Flatpak/Flathub only, ADR-004).
- Email client, office suite, photo editor preinstalls — store items, not image items.
- Custom kernel patches. We ship Fedora's kernel untouched.
- A web browser of our own, a search deal, or any monetization surface inside the OS.

### 1.5 Success metrics for 1.0

| Metric | Gate | Measured by |
|---|---|---|
| Unattended-install success on the reference hardware matrix | ≥ 95% of attempts | Section 10.2 matrix runs |
| Zero-Terminal story pass rate | 22/22 stories | Section 10.1 in CI + manual |
| "Parent test": non-technical human completes the 10-task script unaided | ≥ 9/10 tasks, ≥ 4/5 testers | Moderated sessions, M5 |
| Idle RAM after login (2-min settle, 4 GB VM) | ≤ 1.1 GiB (target 950 MiB) | `tests/perf/idle_ram.sh` in CI |
| Cold boot, power-on → login screen (virtio SSD VM) | ≤ 15 s (target 10 s) | `tests/perf/boot_time.sh` in CI |
| Login → usable desktop | ≤ 5 s | same harness |
| ISO size | ≤ 3.5 GiB (target 3.0) | CI artifact check |
| Update applied + reboot survives, and a sabotaged update auto-rolls back | 100% in rollback drill | WP-04 test, rerun at every release |
| Outbound network connections at idle from fresh install | update checks only | `tests/privacy/network_audit.sh` |
| Non-loopback listening sockets after boot | none beyond the printing allowlist (mDNS UDP 5353; CUPS/ipp-usb loopback-only) | `tests/security/ports.sh` |

Note on the ISO budget: an earlier working figure of 2.8 GiB was revised to 3.5 GiB gate / 3.0 target after deciding to carry an offline Flatpak sideload set (Firefox + core apps) on the ISO so that offline installs still produce a fully working system (ADR-010). Working offline on day one is worth 500 MiB.

---

## 2. Architecture Decision Records

Each ADR is **final** unless the owner overturns it via the escalation path (14.6). Agents cite the ADR number in commit messages when a change implements it.

### ADR-001 — The OS is an image, not a package set
**Decision:** Meridian OS is an immutable, image-based ("atomic") system built on **Fedora bootc** technology. The entire OS filesystem is defined by one OCI container build (`os/Containerfile`), versioned in Git, built in CI, and distributed through a container registry. Clients update by pulling the new image and rebooting into it; the previous deployment is retained and bootable.
**Why:** (a) It makes "it never breaks" structural: updates are atomic, rollback is built-in, users cannot wedge the OS because the OS is read-only. (b) It is the perfect substrate for agent-driven development: every change is a reviewable diff to a Containerfile or an overlaid file, reproducibly built and boot-tested in CI. (c) Distribution infrastructure is a free public registry, not custom mirrors. (d) The pattern is production-proven at consumer scale by SteamOS (image-based) and the Universal Blue family (Bazzite/Bluefin/Aurora, Fedora bootc-based).
**Rejected:** Debian/Ubuntu mutable base (older kernels, user-breakable, we'd run apt infra); Arch (rolling breakage vs. pillar 1); NixOS (declarative but its failure modes and ecosystem violate pillar 2 for our persona); building from scratch (absurd).
**Consequences:** No user-facing package manager exists (see ADR-004 for apps). `/usr` is read-only; machine-local state lives in `/etc` (3-way merged on update) and `/var`. Anything we configure must be baked as image defaults under `/usr` (e.g. `/usr/etc`, `/usr/share`) rather than post-install scripts.

### ADR-002 — Base image: Universal Blue main (Fedora Kinoite lineage)
**Decision:** `os/Containerfile` starts `FROM` the Universal Blue Plasma base image — `ghcr.io/ublue-os/kinoite-main:<current-fedora>` `[VERIFY]` — which is Fedora Kinoite plus the full out-of-tree driver and codec stack (full ffmpeg, Intel/AMD media drivers, Broadcom Wi-Fi, controller drivers, fwupd enabled). An `-nvidia` variant of our image is additionally built `FROM ghcr.io/ublue-os/kinoite-nvidia:<current-fedora>` `[VERIFY]` (or by layering ublue's Nvidia driver packages if the combined image is the current ublue pattern — adopt whatever mechanism ublue currently uses for Nvidia).
**Verification (WP-01):** `skopeo inspect --raw docker://ghcr.io/ublue-os/kinoite-main:42` (adjust release number to current Fedora stable) must succeed, show a recent build date (< 30 days), and its manifest list MUST include both `amd64` and `arm64`. Inspect labels/README for the currently-recommended tag scheme. **If the base lacks arm64** (historically common for ublue main images), adopt the pre-authorized split-base without escalation: ublue for x86_64 (user-facing), Fedora Kinoite base + the hardware-enablement layer for the aarch64 dev-loop image — one Containerfile, ARG-switched base, hardware-enablement layer applied only where needed; note it in STATUS.md.
**Fallback:** If ublue has renamed or stopped publishing these images, base on Fedora's own `quay.io/fedora/fedora-kinoite:<release>` (or `quay.io/fedora-ostree-desktops/kinoite`) `[VERIFY]` and create `os/layers/hardware-enablement.inc` replicating the driver/codec additions (RPM Fusion multimedia swap of ffmpeg, `libva` drivers, `broadcom-wl` akmod, Nvidia akmods from ublue's akmods repo). This fallback is ~2 extra agent-sessions of work; prefer the ublue base.
**Why:** Ten years of community driver debugging inherited in one `FROM` line; the single highest-leverage decision for pillar 6.
**Consequences:** We track Fedora's release cadence (rebase 1–2×/year, see 7.6); we owe ublue upstream courtesy (credit, bug reports, no hotlink abuse of their CI).

### ADR-003 — Desktop: KDE Plasma 6, Wayland-only, configured and themed — never forked
**Decision:** The desktop is Plasma 6 on Wayland (Xwayland present for app compat; no X11 session installed). We achieve the Meridian look and behavior exclusively through: (a) a custom Plasma **Look-and-Feel + Plasma Style + color schemes + window decoration config**, (b) **three custom plasmoids** (Start menu, Quick Settings, workspace pager) written in QML against public Plasma APIs, (c) configuration defaults and **KDE KIOSK immutability locks**, (d) at most small, upstreamable patches carried in `os/patches/` with written justification. We MUST NOT fork Plasma, KWin, or Dolphin.
**Why:** Plasma is architecturally Windows-shaped (panel/taskbar/tray), Wayland-first with best-in-class fractional scaling (the v2 "high-definition, macOS-feel" path), themable to near-pixel fidelity, and battle-tested as a consumer product by Valve. Forking converts a 4-agent theming job into a permanent 40-agent maintenance job.
**Consequences:** ~95% mockup fidelity, not 100%; Section 5.12 lists accepted deviations. Plasma version bumps arrive with Fedora rebases and get a regression WP each cycle.

### ADR-004 — Applications are Flatpaks from Flathub. Full stop.
**Decision:** All GUI applications — preinstalled and user-installed — are Flatpaks from Flathub. The image contains no user-facing package manager and Discover's PackageKit backend is not shipped. Preinstalled Flatpaks are provisioned system-wide at install time from an on-ISO sideload repo (offline-capable), then updated from Flathub. The Software store (WP-13) installs to the system installation via polkit rules that allow active local users to install/remove apps without a password (Windows parity: installing an app is not an admin ceremony; *system* changes still are).
**Why:** One app format = one sandbox story, one update mechanism, one store backend; app crashes can't break the OS; app updates are decoupled from OS updates.
**Consequences:** The rare tool with no Flatpak (e.g. some drivers' vendor utilities) is simply not offered. CLI developer tools are out of persona scope (Advanced users get `toolbox`/`distrobox` which ship hidden in the image for Jordan, undocumented in UI).

### ADR-005 — Custom shell pieces are plasmoids; system plumbing is reused, never rewritten
**Decision:** The Start menu, Quick Settings, and pager are our QML plasmoids, but they MUST consume existing Plasma/KDE frameworks for all system state: `plasma-nm` QML plugin for networks, `plasma-pa`/PipeWire models for audio, PowerDevil D-Bus for brightness/battery, `Bluez`/Bluedevil for BT, the `org.kde.plasma.private.notifications` model for notifications, KRunner (Milou) for search. Writing a new NetworkManager client, mixer, or notification daemon is forbidden.
**Fallback:** If the custom Quick Settings plasmoid misses the M2 quality gate (7.5), ship the stock system tray + applets themed to Meridian colors, and move the custom plasmoid to v1.1. The Start menu has no fallback — it is core identity and must land.

### ADR-006 — The Windows-like file world is policy, not filesystem surgery
**Decision:** Users see exactly: `Home` (containing `Desktop`, `Documents`, `Downloads`, `Music`, `Pictures`, `Videos`), `Trash`, and mounted removable media. This is enforced by configuration: a shipped `user-places.xbel` (sidebar), Dolphin defaults (breadcrumb-only location bar, no editable URL, hidden-files off), hidden `konsole`/"Open Terminal" actions via KIOSK restrictions, GTK bookmarks for portal dialogs, and desktop icons. The real filesystem is untouched underneath — no bind-mount games, no renamed FHS directories, no kernel tricks. **Full filesystem + terminal access is an Advanced mode**: Settings → Advanced (polkit-authenticated, admin password) toggles "Show system files" and "Enable Terminal", which flip the same configuration the other way.
**Why:** Config-level abstraction is robust across updates, invisible to apps (paths stay standard so nothing breaks), reversible, and honest. Filesystem surgery breaks Flatpak portals, support articles, and future us.
**Consequences:** A determined user can still type `/` in a file dialog path field where portals allow it. That is acceptable: we are designing away *accidental* complexity, not building a prison.

### ADR-007 — Installer: Calamares, three screens, with a custom bootc deploy module
**Decision:** The ISO is a **live session** ("try before you install") with a hardware-check panel, launching **Calamares** branded to Meridian and reduced to three user screens (Language/Keyboard → Disk → You). Deployment is performed by a custom Calamares Python job module that runs `bootc install to-filesystem` from the container image embedded on the ISO, then provisions the Flatpak sideload set. Partitioning uses Calamares' mature kpmcore stack including NTFS resize for "Install alongside Windows". Optional LUKS full-disk encryption is a checkbox on the Disk screen (off by default in 1.0; TPM auto-unlock is v1.x, Section 15).
**ISO build:** Universal Blue's live-ISO tooling (`titanoboa`) `[VERIFY]`, falling back to Fedora `livemedia-creator`/lorax with a kickstart. Whichever tool, the output MUST embed the OCI image in containers-storage so installs work fully offline.
**Rejected:** Anaconda (powerful, but its UX cannot be reduced to our three screens without more effort than writing one Calamares module); Readymade (watch it — re-evaluate at WP-17 `[VERIFY]`; adopt only if it demonstrably beats the Calamares path by then).

### ADR-008 — Updates are silent, staged, atomic, and self-healing
**Decision:** OS updates: a systemd timer checks daily, downloads and **stages** the new image in the background (`bootc upgrade`), and finalizes on the next natural reboot/shutdown — no forced restarts, no "Updating… 30%" hostage screens, ever. **greenboot** health checks (graphical target reached, NetworkManager alive, session started) run on each boot; a boot that fails health checks automatically reboots into the previous deployment and flags the failure to Settings → Updates. App updates: `flatpak update --noninteractive` timer, twice daily. Firmware: fwupd refreshes metadata and *offers* firmware updates in Settings → Updates (never auto-applied). Settings → Updates is a read-mostly status page: "You're up to date", last check, history, one advanced "Apply at shutdown now" action.
**Why:** Pillar 1 + the single most-hated Windows behavior eliminated as a headline feature.
**Consequences:** Update servers are the public registry (zero infra); release discipline lives in CI gates (7.5), because every push to `stable` reaches users' next boot.

### ADR-009 — Windows App Support = umu + Proton-GE, optional, expectation-managed
**Decision:** Windows-program compatibility ships as an optional component ("Windows App Support"), not in the base image. Flow: double-clicking any `.exe` (MIME `application/vnd.microsoft.portable-executable` and `application/x-ms-dos-executable`) opens our `meridian-winapps` helper, which on first use offers a one-click install of the support layer (**umu-launcher** + current **Proton-GE**, downloaded to `/var/lib/meridian/winapps/runtime`) `[VERIFY umu-launcher is maintained; fallback: Bottles flatpak preconfigured headlessly]`. Each Windows app gets its own prefix under `~/.local/share/meridian/winapps/<slug>/`; installers are detected and resulting Start-menu shortcuts surface as real desktop entries; uninstall appears in Settings → Apps. **Before** first run of a recognized app, the helper checks the bundled compatibility list (Appendix C) and speaks plainly: green "Works well", yellow "Mostly works — known issues: …", red "Doesn't work — here's the best alternative" (e.g. Microsoft Office → M365 web / LibreOffice; AutoCAD → red, no sugarcoating). Unknown apps get an honest "Untested — trying is safe, expect rough edges."
**Why:** umu gives us Valve-grade Wine (Proton) outside Steam with pressure-vessel isolation and no game-launcher baggage; the honesty layer is pillar 7 and protects the brand from the "Linux lied to me" churn loop.
**Consequences:** Games are explicitly not the target (Steam exists in the store for that); anti-cheat titles are out of scope, and the compat list says so.

### ADR-010 — Browser: Firefox preinstalled; Chrome/Edge/Brave one click away
**Decision:** Firefox (Flathub, unmodified upstream branding) is the preinstalled default browser and lives in the ISO sideload set so offline installs have a working browser. The Welcome app's Browser page and the store's "Popular with switchers" rail offer Chrome, Edge, Brave, and Vivaldi as one-click installs; choosing one there sets it as default browser and pins it to the taskbar in place of Firefox. No search-deal modifications, no bundled extensions, no changed defaults beyond `browser.aboutwelcome` trimming via distribution policies.json (privacy-neutral).
**Why:** Firefox is the only major browser we may legally redistribute on media; Chrome's EULA requires user-initiated download. SaaS-dependent users (Sam) get Chrome in one click during onboarding.

### ADR-011 — Zero telemetry, zero phone-home, auditable
**Decision:** Meridian ships **no** telemetry, crash reporting, analytics, unique identifiers, or "check-in" of any kind. The complete list of automatic outbound connections is: registry update checks (OS + Flatpak), fwupd metadata, NTP, geoip lookup during OOBE timezone detection (one call, no persistence, skippable), and captive-portal detection (NetworkManager default; disableable in Settings → Advanced). CI test `tests/privacy/network_audit.sh` boots an idle system for 10 minutes and fails if any other destination is contacted. KDE's optional user feedback (`kuserfeedback`) is compiled out / force-disabled via KIOSK. A "Report a problem" button in Settings → About assembles a local diagnostic zip **on the user's disk** for them to attach wherever they choose; it uploads nothing itself.
**Why:** Pillar 5 is only a differentiator if it is provable. The CI test makes it provable and keeps it true.

### ADR-012 — Nvidia: one ISO, automatic post-install specialization
**Decision:** We publish a single universal ISO. The installer detects an Nvidia dGPU (PCI vendor 0x10de, Turing or newer for the proprietary/open stack; older cards stay on nouveau with a Settings notice). On Nvidia machines, the installed system boots first on nouveau/simpledrm, and a one-shot service (`meridian-gpu-specialize.service`) queues a rebase to the `-nvidia` image variant; on first network availability it stages the rebase and the Updates page shows "Graphics driver ready — takes effect after restart". Fully offline Nvidia machines keep working on the fallback stack until network exists.
**Why:** One download (no "which ISO?" support burden) beats shipping both driver stacks on one ISO (+1 GiB) or maintaining two ISOs (user confusion).
**Consequences:** Nvidia + permanently-offline is degraded (2D/basic 3D) — acceptable edge; documented.

### ADR-013 — Targets: x86_64 (UEFI first), aarch64 for development only
**Decision:** Ship x86_64 at Fedora's own baseline (in practice any 64-bit CPU from ~2014 onward; we add no extra micro-architecture requirement of our own). UEFI is the first-class boot path; legacy BIOS boot MUST work through the same installer (bootc installs GRUB2 for both) but gets best-effort QA. Minimums: 4 GB RAM, 40 GB disk, dual-core 2014-era CPU; recommended 8 GB/SSD. aarch64 images are built in CI and used for the Apple-Silicon local dev loop (7.2); they are not a supported end-user target in 1.0. Secure Boot: 1.0 requires it disabled — the ISO boot failure mode is detected in docs/first-boot guidance with per-vendor BIOS instructions (10.4); pursuing a signed shim is v1.x (Section 15).

### ADR-014 — Public monorepo, permissive where ours, GHCR distribution, signed images
**Decision:** Development happens in a public GitHub monorepo (`<org>/meridian`) from day 1. Our original code: MIT. Theme assets derived from Breeze: LGPL-2.1+ (as upstream). Config and docs: MIT/CC-BY-SA as conventional. OS images and ISOs are published to GHCR + GitHub Releases; images are cosign-signed in CI and clients enforce the signature via `/etc/containers/policy.json` (WP-04). Channels: `:stable` (default), `:testing` (weekly), version tags for every release.

### ADR-015 — Security defaults: invisible, Windows-familiar where visible
**Decision:** SELinux enforcing (inherited, never surfaced to the user); firewalld on; no non-loopback listening sockets after boot except the explicit printing/discovery allowlist — mDNS on UDP 5353 (firewalld `mdns` service) with CUPS and `ipp-usb` bound to loopback only — enforced by the CI allowlist in `tests/security/ports.sh` (CI-verified); polkit prompts styled as our "UAC" (admin password for system changes; app installs from the store exempted per ADR-004); no SSH daemon; automatic security updates via ADR-008; AutoPlay for removable media NEVER executes content — it opens a folder (explicitly safer than historical Windows autorun, and we say so in marketing); Flatpak portal-based permissions are the app-permission model surfaced in Settings → Apps.

### ADR-016 — Search is instant and local: apps, settings, places, recent files — no indexer
**Decision:** Baloo (KDE's file content indexer) is disabled and masked. Start-menu search covers: installed apps, settings pages, sidebar places, recently used documents (KActivities), and a literal filename walk when the user presses Enter on "Search files for …" (Dolphin's non-indexed search). No background content indexing exists in 1.0.
**Why:** Baloo is historically the #1 "why is my disk/CPU busy" complaint and violates pillar 4's calm-machine promise; our personas search for apps and recent things, not full-text.
**Consequences:** No content search inside files from the Start menu (Windows parity is honestly mixed here anyway). Revisit for v2 with a strictly-idle indexer.

---

## 3. System design overview

### 3.1 Layer diagram

```
┌────────────────────────────────────────────────────────────────────────┐
│  USER APPS — Flatpaks from Flathub (Firefox preinstalled; the rest     │
│  user-chosen). Sandboxed; portals for files/screens/devices. ADR-004   │
├────────────────────────────────────────────────────────────────────────┤
│  MERIDIAN EXPERIENCE LAYER (this repo's product code)                  │
│   • Look-and-Feel: theme, plasma style, colors, decoration, SDDM,      │
│     Plymouth, wallpapers, fonts, icons          (shell/theme, WP-05/06)│
│   • Plasmoids: meridian-start, meridian-quicksettings, meridian-pager  │
│     + panel layout                              (shell/*, WP-07/08/09) │
│   • Apps: Welcome (OOBE), Software store, Windows App Support,         │
│     Migration wizard, custom Settings pages     (apps/*, WP-12..14,20,21)│
│   • Policy: KIOSK locks, places, shortcuts ("Familiar"), polkit rules, │
│     hidden-FS config, automount/AutoPlay        (os/rootfs, WP-07/10/11)│
├────────────────────────────────────────────────────────────────────────┤
│  DESKTOP PLATFORM — KDE Plasma 6 (Wayland), KWin, Dolphin, SDDM,       │
│  PipeWire, NetworkManager, BlueZ, PowerDevil/tuned-ppd, CUPS, fwupd.   │
│  Configured & locked, never forked. ADR-003/005                        │
├────────────────────────────────────────────────────────────────────────┤
│  BASE IMAGE — Universal Blue kinoite-main (Fedora Kinoite + full       │
│  driver/codec stack). ADR-002                                          │
├────────────────────────────────────────────────────────────────────────┤
│  DELIVERY — bootc atomic image; GHCR registry = update server; A/B     │
│  deployments; greenboot auto-rollback; cosign-signed. ADR-001/008/014  │
└────────────────────────────────────────────────────────────────────────┘
```

### 3.2 What is in the image vs. not

**In the image (read-only /usr):** Plasma desktop + our experience layer; Dolphin, Ark, Gwenview, Haruna (media), Okular (PDF), KWrite, KCalc, Spectacle, plasma-systemmonitor, print-manager; our four apps; konsole + toolbox/distrobox (hidden, Advanced); NetworkManager/BlueZ/PipeWire/CUPS/sane-airscan/fwupd/tuned-ppd/thermald; NTFS/exFAT/MTP support; fonts (Schibsted Grotesk, Inter, Noto family incl. CJK+emoji, Liberation, Carlito, Caladea); greenboot; umu bootstrap stub. **~12 visible apps total.**

**Not in the image:** office suite, mail client, browser (Flatpak — but carried on the ISO sideload), games, Discover, Akonadi/PIM, Baloo (masked), KDE Connect (v2), development tools in PATH-visible form, any ublue branding remnants (must be scrubbed, WP-02).

**Preinstalled Flatpak set (system-wide, from ISO sideload):** `org.mozilla.firefox` only, plus the Flathub remote configured. Everything else is store-on-demand. (Media, PDF, images are native KDE apps above — no Flatpak needed.)

### 3.3 Data flow of an update (for every agent's mental model)

CI merges to `main` → image built + tested + signed → pushed `:testing` → weekly promotion gate (7.5) retags `:stable` → user timer `bootc upgrade` stages in background → user's next shutdown/boot activates → greenboot verifies → failure = automatic rollback + flag in Settings. At no point does the user see a progress bar they didn't ask for.

---

## 4. Design language specification

The complete machine-readable token set is **Appendix A** (`docs/design/tokens.json` in-repo). This section is the human contract. Fidelity target: a screenshot of the built OS beside the mockup should read as the same product at arm's length (per-surface screenshot-diff gates in 7.4).

### 4.1 Type

- **UI family:** Schibsted Grotesk (OFL; bundle in image), fallback Inter → Noto Sans. **Fixed:** JetBrains Mono (hidden terminal, KWrite).
- Scale (@1×, logical px): body 14; secondary 13.5; captions 12.5; overline labels 11 (600, letter-spacing 0.08em, uppercase); window/page titles 20 (700); hero 22 (700). Line-height ≈1.35 for text, 1.2 for titles. Antialiasing on; hinting slight; fractional-scale rendering must stay crisp at 100/125/150/200%.

### 4.2 Color

- **Light surfaces:** window `#fcfcfe` at 94% + blur; sidebar `#f5f5fa` at 60%; hairlines `rgba(0,0,0,0.06)`; hover fill `rgba(0,0,0,0.05–0.07)`; card fill `rgba(0,0,0,0.035)`.
- **Ink:** primary `#1a1a22`; secondary `#55555f`; tertiary `#7a7a86`; disabled/hint `#9a9aa6`.
- **Accents (user-selectable, default blue):** blue `#0098c0` · violet `#7f78d6` · green `#019f68` · red `#cd605a` · graphite `#4f5661`. (Authored as OKLCH 0.62/0.14/{220,285,160,25} + 0.45/0.02/260 — keep OKLCH authoritative in tokens, ship hex to Qt.) Close-button hover is always `#e5484d` white glyph.
- **Dark theme (Meridian Dark — our derivation; mockup is light-only):** base `#131318`; window `#1c1c24` at 94%; sidebar `#17171f`/60%; hairlines `rgba(255,255,255,0.07)`; ink `#ececf2`/`#b8b8c4`/`#8f8f9c`; accents same hues lightened one step (L+0.08). Both themes ship in 1.0; light is default; toggle lives in Settings → Appearance.
- **Wallpapers (3, shipped as 4K PNG + source SVG gradients):** Soft Violet `#c3bfe3 → #6d7ac2 (55%) → #2c488e` at 160°; Dusk `#ecc5a7 → #bd615b (60%) → #4b346f`; Deep Teal `#90cacd → #008192 (55%) → #003f64`. Plus both theme-neutral radial glows per mockup.

### 4.3 Shape, depth, materials

- Radii: windows & taskbar 14; Start/Quick panels 18; cards & rows 12; buttons/inputs 8–10; pills 999.
- Shadows: windows `0 24px 70px rgba(20,15,60,0.35)`; floating panels `0 30px 80px rgba(20,15,60,0.40)`; taskbar `0 10px 30px rgba(20,15,60,0.30)`; cards `0 1px 4px rgba(0,0,0,0.06)`.
- Material: panel & popups translucent (blur 30–36px, saturate ~1.4, ~1px inner light border `rgba(255,255,255,0.5)`); windows near-opaque translucent. KWin blur effect enabled for these surface classes only — never full transparency of app content.
- Motion: popups fade-up 14px / 180ms ease-out; toggles 200ms; window open/close use Plasma's stock scale+fade at 150–200ms. Nothing bounces. `prefers-reduced-motion` honored (Plasma animation-speed accessibility setting).

### 4.4 Iconography & brand

- System icons: Breeze as base set, with a Meridian override layer for: folder set (tinted to accent), the 12 core app icons (rounded-square, gradient fills per mockup's tile language), tray glyphs (1.6px stroke outline style per mockup SVGs). Full custom icon set is v2; 1.0 overrides only what the eye lands on.
- Logo: ring-in-rounded-square, gradient `#00abd3 → #2a5fb7` (mockup's Start button mark). Ship SVG masters + raster sizes in `shell/theme/branding/`. All brand assets referenced ONLY via the branding module (6.5).

### 4.5 Voice & writing rules (all UI strings, all agents)

Plain, short, warm, zero jargon. Never: "mount", "partition" (installer says "disk"), "repository", "flatpak", "daemon", "prefix", "rebase". Sentence case everywhere including buttons and titles. Contractions welcome. Errors say what happened + the one next step, e.g. "Couldn't reach Wi-Fi network 'Home-5G'. Move closer or check the password." Every dialog's primary action is a verb ("Install", "Copy files", "Not now" — never "OK/Cancel" pairs where avoidable). The word "Linux" appears in About and marketing, not in daily UI chrome.

---

## 5. UX specification (screen by screen)

Authoritative behavior spec. Mockup deviations: 5.12. Every numbered requirement here maps to a WP acceptance test.

### 5.1 Desktop & taskbar

- Floating taskbar: 52px tall, 12px margins from screen edges, radius 14, translucent+blur. Left→right: **Start** (logo mark + word "Start"), hairline divider, **workspace pager** (3 numbered squares; active = white chip w/ shadow), divider, **pinned/running apps** (40px hit-targets, 28px tiles, 14×3px accent underline on running), spacer, **Quick Settings cluster** (network glyph + battery glyph + unread-dot; one hit target opening Quick Settings), **clock** (two-line: time over short date).
- Defaults pinned: Files, Firefox ("Web"), Software, Settings. Single monitor: taskbar on primary only; additional monitors get none in 1.0.
- Desktop: icons top-left column, 86px cells: **Home**, **Software**, **Trash** (Trash shows filled/empty states). Right-click desktop menu (curated): New folder · New text file · Paste · Change wallpaper · Display settings. Nothing else in 1.0.
- Windows: buttons right (min/max/close, 27px, subtle rounded squares; close hover `#e5484d`); double-click titlebar maximizes; drag-to-top edge maximizes, side edges tile 50%, quarter-tiling in corners (KWin defaults tuned); Alt-drag anywhere moves (bonus, undocumented).

### 5.2 Start menu (plasmoid `meridian-start`)

- Opens from Start button or **single Meta press** (must not fire on Meta+X combos). 560px wide panel above taskbar-left, radius 18, fade-up.
- Layout per mockup: search field top (placeholder "Search apps, files and settings", focused on open — typing immediately searches via KRunner scopes per ADR-016); left = "Pinned" 3×3 app grid (page dots if >9; right-click → Unpin / Uninstall); right column = "Places" (Home, Documents, Downloads, Pictures, Trash — opens Files) + persistent **"Coming from Windows?"** card (opens Software's switcher guide); footer = avatar + first name, spacer, power glyph → menu: Sleep · Restart · Shut down · Lock · Log out (+ "Restart to apply updates" contextual item per ADR-008).
- All-apps: "All apps" link above grid → alphabetical scroll list w/ letter index. Search results grouped: Apps · Settings · Files (recents) · Places. Enter launches the top hit.
- Default pins: Files, Web (Firefox), Software, Settings, Photos→Gwenview, Media→Haruna, Documents→Okular, Notes→KWrite, Calculator. When Welcome installs a different browser it replaces the Web pin.

### 5.3 Quick Settings (plasmoid `meridian-quicksettings`)

- 350px panel above taskbar-right per mockup: 2×2 toggle tiles (Wi-Fi w/ SSID subtitle → expands to network list inline incl. password entry via plasma-nm QML; Bluetooth w/ device count → expands to pairing list; Do not disturb; Night light), Brightness + Volume sliders (per-device flyout on volume long-press), Notifications section (Clear all; grouped cards; "All caught up" empty state), footer "Battery 84% · 5 h 20 m" + Settings link.
- The taskbar cluster mirrors state (VPN glyph when active, mic-in-use dot, battery %). Media playback: an MPRIS "now playing" row appears above toggles when active (matches Windows 11 behavior switchers expect).
- OSDs: volume/brightness keys show minimal pill OSD top-center (Plasma OSD themed).

### 5.4 Files (Dolphin, configured)

- Chrome per mockup: toolbar = back/forward, centered breadcrumb chip ("Home / Documents"; click segment to jump; **no editable path field** in default mode), search icon (filename search of current tree), view toggle (grid/list), overflow menu (New folder, Select all, Show hidden files, Sort, Empty Trash contextually).
- Sidebar "Places": Home, Desktop, Documents, Downloads, Music, Pictures, Videos, Trash; "Devices" group appears only when removable media present (each with eject glyph). Footer: disk-free bar for Home's volume ("182 GB free"). Sidebar is not user-editable in default mode (KIOSK) to keep support articles true.
- Behaviors: **single-click selects, double-click opens** (Windows parity — override Plasma default); F2 rename inline; Delete → Trash w/ undo toast (Ctrl+Z works); Shift+Delete permanent w/ confirm; Ctrl+Shift+N new folder; typing jumps to match; drag-drop between windows; zip: right-click → "Compress to ZIP" / double-click zip opens Ark preview with visible "Extract" button (Windows parity); "Open with" submenu curated.
- Context menu (file): Open · Open with · Cut/Copy/Paste · Rename · Compress/Extract · Move to Trash · Properties. Absolutely no "Open terminal here", "Root actions", "Activities" entries (KIOSK-hidden).
- Network/remote locations: hidden entirely in default mode (v1 scope cut; SMB browsing is v1.x, Section 15).

### 5.5 Removable media & AutoPlay

- Insert USB storage → auto-mount (udisks2/kded automounter) → toast notification "USB drive connected" with actions **Open folder** (default; Enter opens) and Eject; device appears in Files sidebar + a taskbar-adjacent eject is available via Quick Settings devices row. Phones (MTP/PTP) mount the same way via kio-mtp ("Pat plugs in her phone" is story ZT-06). NTFS/exFAT/FAT32 drives mount read-write silently. **Never** execute or offer to execute anything from media (ADR-015). Eject flushes and confirms "Safe to remove".

### 5.6 Settings (curated System Settings)

- Visible sidebar (exactly, in order): **Wi-Fi & Network · Bluetooth · Displays · Sound · Power & Battery · Appearance · Printers · Apps · Users · Date & Time · Updates · Advanced · About**. Every other KCM is KIOSK-hidden (not uninstalled — Advanced re-exposure possible later). Window chrome per mockup (centered title, sidebar w/ colored glyph tiles).
- **Appearance:** wallpaper picker (3 + user image), accent (5 swatches), Light/Dark, **"Familiar mode"** toggle ("Windows-style shortcuts and window behavior", ON default — OFF switches shortcut scheme to stock Plasma and restores Plasma single-click open; the toggle exists to make the promise legible, and for converts going native).
- **Updates (custom KCM, WP-12):** status headline, last-check time, "What's new" history list (image changelog + app updates), firmware offers, Advanced row: "Apply pending update at next shutdown" indicator. No manual "check now" anxiety button on the main surface (it lives behind the history view).
- **Apps (custom KCM):** installed list (Flatpaks + Windows apps w/ badge), per-app: uninstall, permissions (portal toggles in plain language), "runs at login" if applicable, default-app assignments (browser, mail-to, PDF, images, video, music).
- **Advanced (custom KCM, polkit-gated — the "super user option"):** authenticating unlocks the page for the session; toggles: **Show system files in Files** (adds Computer/Root places, enables editable path, shows hidden-file toggle prominence), **Enable Terminal** (unhides Konsole in Start/search), **Developer mode** (unhides toolbox/distrobox docs page), captive-portal check off, and "Reset all Meridian defaults". Each toggle explains itself in one sentence. State persists per-machine (`/etc/meridian/advanced.conf`).
- **About:** device name (editable), "Meridian OS 1.0 'name'", hardware summary, storage, "Report a problem" (ADR-011 local zip), licenses, credits ("Built on Fedora, KDE Plasma, and the work of thousands — see Credits").

### 5.7 Software (custom store app, WP-13)

- Window per mockup: hero banner ("Switching from Windows?" → guide view), **"Popular with switchers"** grid of cards: icon tile, name, one-line "Replaces X" subtitle, Install pill → progress ring → "Open". Sections below: Essentials · Browsers · Work · Creative · Media · Utilities (catalog-driven, Appendix B). Search field queries Flathub (AppStream); results show verified-publisher badge; unverified apps show a calm caution note.
- The switcher guide view: two-column "On Windows you used → Here you use" mapped list (catalog `replaces` data), each row installable inline.
- Updates tab: "Apps update themselves in the background" + history (read-only; reinforces ADR-008). Installed tab mirrors Settings → Apps uninstall.
- Non-goals: ratings/reviews (v2), Flathub account features, paid apps. Backend: system-installation via `libflatpak`/CLI + polkit rule (ADR-004); operations resumable and cancel-safe; store never blocks on metadata refresh (cached AppStream, refreshed by timer).
- **Fallback gate (ADR-005 pattern):** if store quality gate fails at M2 (7.5), ship Discover (Flathub-only, themed) and keep the curated grid inside Welcome; the custom store moves to v1.1. Decision recorded in STATUS.md by the M2 review.

### 5.8 Welcome (OOBE app, WP-14; runs full-screen on first login, relaunchable from Start)

Pages, in order, each skippable: 1) **Hello** (three-point promise per mockup modal); 2) **Connect** (Wi-Fi list via plasma-nm QML; skipped if wired/online); 3) **Browser** (Firefox preselected "Ready"; Chrome/Edge/Brave/Vivaldi tiles — selecting installs in background with progress chip and swaps default+pin); 4) **Windows apps** ("Do you have Windows programs you need?" → one-click enable of Windows App Support, or "Skip — you can add it anytime"); 5) **Your files** (if an NTFS Windows partition with `/Users` is detected → launches Migration wizard inline, 5.10; else offers "Copy from a USB drive" tip); 6) **Look** (wallpaper + accent + Light/Dark quick pick); 7) **Tour** (60-second overlay pointing at Start, Files places, Quick Settings, Software — dismiss anytime). Finish fires confetti-free, calm "You're all set."

### 5.9 Windows App Support (WP-20)

- First `.exe` double-click → consent card: what it is, what it can/can't run, one-click install (downloads runtime; ~15s on broadband). Thereafter: known installer → guided install into per-app container, then "Added to Start menu: <App>"; known app binary → compat verdict (ADR-009 traffic light + source-of-truth: Appendix C list bundled in image, refreshed via OS updates) then run; unknown → honest "Untested" + run. Per-app: Start menu entry w/ Windows-app badge, pin-able, uninstall via Settings → Apps (removes container). Files default-open stays native (e.g. a .pdf never silently opens a Windows viewer).
- Explicit red-list messaging for: Microsoft Office desktop (→ M365 web / LibreOffice), Adobe CC (→ web/alternatives), anti-cheat games (→ "not supported"), printers'/scanners' driver suites (→ "not needed — plug it in"). This candor is a product feature, not a disclaimer.

### 5.10 Migration wizard (WP-21)

- Entry: Welcome page 5, or Software guide, or plugging in a drive containing `/Users`. Steps: pick source (detected Windows partition ro-mounted / external drive) → pick person (`C:\Users\<name>` enumerated w/ sizes) → pick what (Desktop, Documents, Pictures, Music, Videos, Downloads — checkboxes w/ sizes, OneDrive-folder warning if cloud-placeholder files detected) → space check → copy with progress/pause/resume (KIO), collision policy "keep both" → report ("2,314 files copied · 3 skipped (already there)"). Never writes to the Windows partition. Browser bookmarks: if Chrome/Edge profile found, exports bookmarks HTML to Documents with a pointer in the report (full profile import is v1.x).

### 5.11 Installer & live experience (WP-16/17)

- **Live boot** (from USB): lands on full Meridian desktop with a centered **"Try or Install"** card: left "Look around first" (dismisses to live desktop w/ persistent Install icon on desktop+taskbar), right "Install Meridian". Card footer = **hardware check row**: Wi-Fi ✓/✗ (click to connect), Sound ✓ (plays chime on click), Display ✓ (resolution), Battery ✓ (% or "desktop"), Keyboard layout guessed. Failures show plain guidance ("Wi-Fi needs a driver we couldn't load — installing over ethernet will fetch it"). This panel is the anti-"will it work?" answer and a marketing screenshot.
- **Installer (Calamares, 3 screens):** 1) Language + keyboard (timezone auto via one geoip call if online, editable); 2) **Disk**: cards — "Erase this disk and install" (disk picker w/ human names "500 GB SSD — has Windows on it"), "Install alongside Windows" (shown only when Windows detected; one slider splits space, NTFS resized safely w/ chkdsk-dirty guard + "back up first" nudge), "Advanced" (small link → full Calamares partitioner, LUKS checkbox lives here AND as a simple "Encrypt this computer (ask a password at power-on)" checkbox on the main cards); 3) **You**: name → suggested short username + hostname ("pats-desktop"), password ×2 (strength meter, no composition rules), "Log in automatically" checkbox (off). Then a single summary screen with the one scary sentence in plain words ("This will erase everything on 'the 500 GB SSD'.") → Install (slideshow = 5 calm slides of pillar features) → "Restart now". Target: power-on of USB → restart in under 15 minutes on an SSD, ≤ 8 clicks total.
- Dual-boot: GRUB menu hidden when Meridian is alone; when Windows detected, 3-second boot menu "Meridian OS / Windows" (os-prober), RTC set to localtime-compat to prevent the classic clock-skew bug (WP-19), and Windows partition appears in Files ONLY in Advanced mode (default: hidden to prevent accidental C:\ damage; Migration wizard accesses it read-only regardless).

### 5.12 Accepted deviations from the mockup (logged; owner-approved via this PRD)

1. Sidebar/places adds **Desktop** and **Videos** (brief requires; mockup omitted for brevity).
2. Desktop icons: mockup's separate **Computer** icon dropped (duplicate of Home; the "This PC" mental model is served by the Devices sidebar group + About). 3 icons ship.
3. **Dark theme added** (mockup is light-only; tokens derived per 4.2).
4. Mockup's pinned Mail/Photos/Music/Notes/Office tiles map to store items or native apps (3.2); no PIM preinstalls.
5. Mockup "Search" glyph in Files toolbar left position → merged into standard toolbar cluster.
6. Store "Popular with switchers" Spotify subtitle "Music streaming" retained but Spotify sits in catalog, not preinstalled.
7. Quick Settings gains an MPRIS now-playing row (switcher expectation; mockup silent on it).
8. Workspaces: exactly 3 fixed numbered spaces in 1.0 (no add/remove UI; power users get KWin shortcuts; revisit v1.x).

---

## 6. Repository & engineering conventions

### 6.1 Monorepo layout (`github.com/<org>/meridian`, public, ADR-014)

```
meridian/
├── os/
│   ├── Containerfile              # THE OS. FROM ublue kinoite-main → layers below
│   ├── packages.yml               # single source of truth: rpm add/remove lists
│   ├── rootfs/                    # copied into image verbatim (keep tree = image tree)
│   │   ├── usr/etc/…              # image defaults for /etc (xdg, dolphinrc, kiosk, polkit…)
│   │   ├── usr/lib/systemd/…      # timers/units: updates, gpu-specialize, flatpak-provision
│   │   ├── usr/share/meridian/    # branding.json, catalog/, compat/, flatpak-sideload manifest
│   │   └── usr/share/…            # wallpapers, fonts, icons, look-and-feel install targets
│   ├── patches/                   # carried patches; each MUST have a .md justification
│   └── scripts/build/*.sh         # image build helper scripts (called from Containerfile)
├── shell/
│   ├── theme/                     # plasma style SVGs, color schemes, decoration cfg, cursors
│   │   ├── branding/              # logo SVG masters, raster exports
│   │   ├── sddm-meridian/        # login theme
│   │   └── plymouth-meridian/    # boot splash
│   ├── look-and-feel/org.meridian.desktop/   # LnF package incl. layout.js defaults
│   └── plasmoids/
│       ├── org.meridian.start/
│       ├── org.meridian.quicksettings/
│       └── org.meridian.pager/
├── apps/
│   ├── welcome/                   # Kirigami OOBE (C++ shell + QML)
│   ├── software/                  # store (C++/QML + libflatpak backend)
│   ├── winapps/                   # Windows App Support helper + CLI
│   ├── migration/                 # migration wizard
│   └── settings-kcms/             # Updates, Apps, Advanced KCMs
├── installer/
│   ├── calamares/                 # settings.conf, branding/, modules/bootcinstall/
│   └── iso/                       # titanoboa (or lorax) configs, sideload manifest
├── catalog/                       # catalog.json + compat.json sources (Appendices B/C) + schemas
├── tests/                         # harness (7.4), stories/, perf/, privacy/, security/, baselines/
├── ci/                            # GitHub Actions workflows (referenced by .github/workflows)
├── docs/
│   ├── adr/                       # ADRs as files (seeded from §2; template included)
│   ├── design/                    # tokens.json, mockup/ (owner-provided), baseline renders
│   └── help/                      # user help articles (GUI-only wording, INV-0)
├── STATUS.md                      # live world state (format: 6.4)
├── CONTRIBUTING-AGENTS.md         # copy of §14 (WP-00 creates)
├── Justfile                       # every dev entrypoint: just build/vm-run/vm-test/iso/…
└── LICENSE, NOTICE                # MIT + third-party notices
```

### 6.2 Change rules

- Trunk-based: short-lived branches `wp/<nn>-<slug>`, PR to `main`, CI must be green, squash-merge with message `WP-NN: <what> (ADR-xxx)`. No direct pushes to `main`.
- Every rpm add/remove goes through `os/packages.yml` (Containerfile consumes it). A package appearing anywhere else fails CI lint.
- Every file overlaid into the image lives in `os/rootfs/` mirroring its final path. No `RUN echo > /etc/...` inline writes in the Containerfile (greppability = auditability).
- Carried patches: `os/patches/NNN-component-purpose.patch` + sibling `.md` stating upstream status (submitted? link?) and removal condition. CI fails a patch without its .md.
- Generated artifacts (icons rasters, wallpapers PNG) are built by `just assets` from SVG sources; both source and output are committed (reproducibility + no build-time font/renderer drift).

### 6.3 Quality bars (linted in CI)

`shellcheck` on all shell; `qmllint` on all QML; `ruff` on Python; JSON schemas validate `catalog/*.json`, `branding.json`, `tokens.json`; reuse/licensing headers; markdown lint on docs; the string-lint (`tests/lint/strings.sh`) greps built UI strings for forbidden jargon (4.5 list) and forbidden phrases ("open a terminal", "run the command" — INV-0 enforcement in help/docs too).

### 6.4 STATUS.md — the shared memory between agents

One section per WP, ≤ 10 lines each, appended at WP completion (and updated on partial stops):

```
## WP-07 Plasma layout & lockdown — DONE 2026-09-14 (agent run 3)
Delivered: LnF package org.meridian.desktop; kiosk baseline; familiar shortcuts scheme.
Verified: just vm-test stories/ZT-01,02,14 green on x86_64+aarch64; screenshots baselined.
Deviations: pager folded into panel layout (was planned separate) — no API change.
Notes for later WPs: layout.js is the only place panels are defined; kiosk keys in
  usr/etc/xdg/kdeglobals — extend, don't duplicate.
Open threads: meta-single-press needs re-check after Plasma 6.x bump (issue #41).
```

Agents MUST read STATUS.md before starting and MUST NOT contradict a DONE entry without escalation.

### 6.5 Branding indirection (rename-proofing, per 0.2)

`os/rootfs/usr/share/meridian/branding.json` = single source: product name, short name, brand id, version string, URLs, support email. Everything user-visible reads it (QML apps at runtime; static assets via `just assets` templating; os-release generated from it at image build). CI check: `tests/lint/branding.sh` greps the repo for the literal product name outside `branding.json`, `docs/`, and this PRD — any hit fails. The WP-26 rename must be achievable in one PR touching ~3 files + asset regen.

---

## 7. Build, test & release infrastructure

### 7.1 The golden rule

**If it isn't reproduced by `just <target>` from a clean checkout, it doesn't exist.** No artifact may depend on an agent's (or the owner's) hand-configured VM. The Justfile is the complete vocabulary: `just build [arch]`, `just vm-image`, `just vm-run`, `just vm-test [suite]`, `just iso`, `just assets`, `just lint`, `just perf`.

### 7.2 Local development on the owner's Mac (Apple Silicon M5)

- Toolchain: Homebrew → `podman`, `just`, `skopeo`, `qemu` (+ UTM app optional for a GUI console). `podman machine init --cpus 6 --memory 8192 --disk-size 80 && podman machine start` gives the Linux build env; `just build` produces the **aarch64** image natively (fast); `just vm-image` runs bootc-image-builder (privileged podman) → `build/meridian-aarch64.qcow2`; `just vm-run` boots it under qemu-system-aarch64 with HVF acceleration — this is the second-scale iteration loop for all UI/UX work.
- x86_64 locally: `just build x86_64` cross-builds under emulation (slow; allowed for spot checks). The authoritative x86_64 loop is CI (7.3). ISO testing on the Mac: `just vm-run-iso` boots the x86_64 ISO under TCG emulation — functional, slow; used for installer eyeball checks only.
- Nothing in the repo may require macOS specifics; all `just` targets run identically on a Linux workstation.

### 7.3 CI (GitHub Actions; all workflows in `ci/`, thin shims in `.github/workflows/`)

| Job | Runner | Trigger | Does |
|---|---|---|---|
| lint | ubuntu-latest | every PR | 6.3 suite, fast-fail |
| build-x86_64 | ubuntu-latest | every PR | image build → `podman save` artifact; PR images pushed to `ghcr.io/<org>/meridian:pr-NNN` |
| build-aarch64 | ubuntu-24.04-arm `[VERIFY free arm64 runners for public repos]` | every PR | same for aarch64 (fallback: qemu cross-build, nightly only) |
| vm-test | ubuntu-latest (KVM available `[VERIFY /dev/kvm on hosted runners]`) | every PR | boots PR image qcow2, runs `tests/` suites: smoke, stories, screenshot-diff, perf gates, security/privacy audits |
| iso | ubuntu-latest | main nightly + tags | `just iso` → artifact + checksummed release upload |
| installer-e2e | ubuntu-latest (KVM) | main nightly + tags | boots ISO in QEMU, VNC-scripted 3-screen install (erase-disk path), reboots into installed disk, runs smoke + OOBE test |
| rollback-drill | ubuntu-latest (KVM) | main nightly + tags | WP-04's sabotaged-update auto-rollback test |
| promote | — | manual/weekly | retags tested `:testing` digest → `:stable` after gate 7.5 |
| sign | in build/promote | pushes | cosign sign; SBOM (syft) attached |

### 7.4 The VM test harness (`tests/harness/` — WP-03; the enabler of agent self-verification)

- Python + QEMU/QMP. Capabilities: boot image/ISO headless (KVM or TCG or HVF auto-detected); wait-for-state via QMP screendump + OCR (tesseract) and pixel probes; input injection via QMP `input-send-event` (keyboard scancodes, absolute pointer) with a VNC (`vncdotool`) fallback; serial-console log capture; guest exec channel for assertions once booted. **Test-access rule:** no published image (`:testing` or `:stable`) ever contains test credentials; the harness injects a transient `mtest` login at boot time via kernel cmdline + systemd credentials (or bakes it only into local/`pr-NNN` CI artifacts that are never promoted). `:testing` digests therefore stay clean and are promotable to `:stable` by pure retag (7.3).
- Assertion styles: `assert_screen("sddm-login", timeout=60)` (reference PNG + RMSE ≤ threshold, masks for clock/battery regions); `assert_text("You're all set")` (OCR); `guest.run("free -m")` parsing for perf gates.
- Baselines in `tests/baselines/<screen>/<arch>.png`, regenerated deliberately via `just baseline <screen>` and reviewed as image diffs in PRs. Antialiasing tolerance: RMSE threshold 0.03, per-screen overridable; never raise a threshold to make a test pass without a STATUS.md note.
- Every Zero-Terminal story (10.1) is a `tests/stories/zt_NN_*.py` script in this harness. Screenshot artifacts upload on failure.

### 7.5 Quality gates

- **PR gate:** lint + build + vm-test(smoke, changed-area stories, screenshot-diff, RAM/boot budgets) green. No human review requirement between agents, BUT any PR touching `docs/adr/`, `packages.yml` removals, polkit rules, or `ci/` requires the owner's approval (CODEOWNERS enforced).
- **M-gates (milestone reviews, Section 9):** full story suite + perf + privacy/security audits + the milestone's specific exit criteria, run on both arches; results pasted into STATUS.md by the closing agent.
- **Promote-to-stable gate (weekly):** nightly suites green 2 consecutive days; rollback drill green; no open P1 issues; test-user stripped verification; image diff (package/size delta) reviewed.

### 7.6 Cadence & maintenance model

Fedora rebase: ~1 month after each Fedora GA, as a dedicated WP (bump base tag on a branch, full suite, fix fallout, 1 week in `:testing`). Plasma point releases arrive via the base image weekly rebuild (nightly CI catches regressions). Security: base image rebuilds pull Fedora security updates automatically; our nightly → `:testing`; promote gate keeps `:stable` at most ~1 week behind — CVE embargo exceptions promoted manually same-day.

---

## 8. Work packages

### 8.0 Cross-WP interface contracts (authoritative; WP-00 copies to `docs/contracts/interfaces.md`; consumers and providers both test against the fixtures in `tests/fixtures/contracts/`)

- **`org.meridian.shell.Pins` (D-Bus, session; provider WP-08 — and it drives BOTH pin surfaces, writing the panel launcher list in WP-07's containment config as well as the Start grid):** `ListPins() → as` (desktop-file ids, start-grid order), `Pin(s id)`, `Unpin(s id)`, `ReplacePin(s oldId, s newId)` (used by Welcome's browser swap — replaces in Start grid AND taskbar launchers), signal `PinsChanged(as)`.
- **`org.meridian.Software` (D-Bus, session; provider WP-13):** `OpenApp(s flatpakRef)`, `Install(s flatpakRef) → o` (job), `Uninstall(s flatpakRef) → o`, job objects emit `Progress(u)`/`Done(b, s)`; Discover-fallback mode MUST still provide this name with `OpenApp`/`Uninstall` minimum.
- **`org.meridian.WinApps` (D-Bus, session; provider WP-20; consumers WP-12 Apps page + WP-14 page 4 build against the fixture NOW):** `IsRuntimeInstalled() → b`, `InstallRuntime() → o` (job as above), `ListApps() → a(sss)` (slug, name, iconPath), `Uninstall(s slug) → o`, signal `AppsChanged()`. Until WP-20 lands, WP-14 ships page 4 feature-flag-hidden; **WP-20's deliverables include flipping the flag and extending ZT-17** with the enable-support path.
- **Update status file (provider WP-04; consumer WP-12):** `/run/meridian/update-status.json` — `{ "state": "up-to-date|staged|rolled-back|error", "booted": {image, version, date}, "staged": {...}|null, "rollback": {happened: bool, date}|null, "lastCheck": iso8601, "flatpakHistory": [...], "firmwareOffers": [...] }`.
- **`/etc/meridian/advanced.conf` (provider WP-12; consumers WP-10/08):** ini, keys `show_system_files`, `enable_terminal`, `developer_mode`, `captive_portal` (bool each).
- **`branding.json`, `tokens.json`, `catalog.json`, `compat.json`:** schemas in `catalog/schemas/` are the contract; providers WP-00/15.

**Template fields:** Phase · Depends (hard order) · Parallel-safe with · Risk · Size (S ≈ 1 agent session, M ≈ 2–4, L ≈ 5–8) · Governing ADRs · Objective · Deliverables (exact paths) · Steps · Acceptance (commands/checks that MUST pass) · Forbidden · Escalate if.
Execution sequencing and parallelization map: 8.7. Every WP ends by updating STATUS.md (6.4) and, where it shipped UX, adding/updating its Zero-Terminal story tests.

### Phase 0 — Foundation (M0)

---

#### WP-00 — Repository bootstrap & conventions
Phase 0 · Depends: none · Parallel-safe: alone (everything depends on it) · Risk: low · Size: S · ADRs: 014, all (seeding)
**Objective:** A clean public monorepo where every later WP has rails to run on.
**Deliverables:** Full tree per 6.1 (empty dirs get `.gitkeep` + `README.md` stating owner WP); `docs/adr/ADR-001..016.md` (verbatim from §2, one file each, + `ADR-000-template.md`); `STATUS.md` seeded with header + WP index table (status column: TODO); `CONTRIBUTING-AGENTS.md` (§14 verbatim); `Justfile` with stub targets that fail loudly with "implemented in WP-NN"; `os/rootfs/usr/share/meridian/branding.json` (+ JSON schema in `catalog/schemas/`); `docs/design/tokens.json` (Appendix A verbatim); lint workflow (6.3 subset that can run day 1: shellcheck, ruff, markdown, branding-lint, schema validation, and `tests/lint/strings.sh` — the jargon/INV-0 string lint, seeded with the 4.5 forbidden list so it exists before the first UI string does); `LICENSE` (MIT), `NOTICE` stub; CODEOWNERS per 7.5; PR + DECISION-NEEDED issue templates (14.6).
**Steps:** scaffold → seed ADRs/tokens/branding → wire lint CI → open tracking issues WP-01..26 with links into this PRD → tag `v0.0.0-bootstrap`.
**Acceptance:** fresh clone: `just lint` green in CI on a trivial PR; `tests/lint/branding.sh` catches a planted violation (prove by test); all 16 ADR files render; STATUS.md index lists 27 WPs.
**Forbidden:** any OS/build logic; choosing names (use `${BRAND}` defaults).
**Escalate if:** org/repo permissions or GHCR publishing unavailable.

---

#### WP-01 — Base image: builds, boots, publishes
Phase 0 · Depends: WP-00 · Parallel-safe: WP-03 (interface: image tag names) · Risk: medium (external base) · Size: M · ADRs: 001, 002, 013, 014
**Objective:** `just build` produces a bootable Meridian-labeled image on both arches; CI publishes it.
**Deliverables:** `os/Containerfile` (FROM per ADR-002; installs nothing yet beyond branding os-release + image labels); `os/packages.yml` (empty add/remove, schema-validated); `Justfile` real targets: `build`, `vm-image` (bootc-image-builder → qcow2), `vm-run` (qemu wrapper: KVM/HVF/TCG autodetect, virtio, 4 GB); `ci/` build workflows (7.3 build rows) pushing `ghcr.io/<org>/meridian:{testing,pr-NNN}` x86_64+aarch64; base-image verification script `os/scripts/build/verify-base.sh` implementing ADR-002 `[VERIFY]` + its fallback decision output.
**Steps:** run verify-base and record result in STATUS.md → minimal Containerfile → local aarch64 build+boot on the Mac loop (7.2) → CI matrix → registry push + cosign scaffold (full signing enforced in WP-04).
**Acceptance:** `verify-base.sh` output committed; `just build && just vm-image && just vm-run` reaches SDDM greeter on aarch64 locally and x86_64 in CI (manual screenshot attached to PR — harness arrives in WP-03); `skopeo inspect` of pushed image shows our labels (name/version/PRD ref); both-arch CI green.
**Forbidden:** package additions/removals (WP-02's); theming.
**Escalate if:** ADR-002 fallback also fails, or bootc-image-builder cannot produce a bootable qcow2 on the Mac podman path (blocks the whole dev loop).

---

#### WP-02 — De-bloat & package curation
Phase 0 · Depends: WP-01 · Parallel-safe: WP-03, 04 · Risk: low · Size: M · ADRs: 003, 004, 016; §3.2
**Objective:** The image contains exactly the 3.2 manifest — nothing else that draws pixels or burns RAM.
**Deliverables:** `os/packages.yml` populated: remove (Discover + PackageKit stack, Akonadi/PIM, Baloo (or masked if dep-locked — record which), KDE games/extras, plasma-welcome, konversation/kmail-anything, ublue-branded extras `[list at execution from rpm -qa diff]`); add (haruna, print-manager, sane-airscan backends, fonts per 4.1/3.2, toolbox/distrobox, tuned-ppd, thermald, greenboot); systemd preset file disabling/masking: baloo, kwallet-pam prompts for our flow, anything phoning home found by audit; `tests/perf/idle_ram.sh` + `boot_time.sh` (first real perf tests, callable standalone pre-WP-03).
**Steps:** boot base → inventory (`rpm -qa`, `systemctl list-units`, `flatpak list`) committed to `docs/inventory-before.txt` → iterate removals in packages.yml (bootc build cycle) → verify nothing user-visible broke (apps menu audit vs 3.2 list) → record after-inventory + RAM delta.
**Acceptance:** idle RAM ≤ 1.1 GiB gate passes on x86_64 KVM 4 GB VM (report number in STATUS.md; target 950 MiB — if > gate, escalate, don't hide); app launcher shows only 3.2's visible set (screenshot); `systemctl --failed` empty; no `.desktop` entries from removed stacks; `docs/inventory-after.txt` committed.
**Forbidden:** removing anything ADR-002's driver stack provides (drivers/codecs stay even if "unused" in VM); removing konsole (hidden ≠ removed, ADR-006).
**Escalate if:** a 3.2 removal is dependency-locked into Plasma (document, propose substitute, wait).

---

#### WP-03 — VM test harness & story framework
Phase 0 · Depends: WP-01 (images to test) · Parallel-safe: WP-02, 04 · Risk: medium · Size: L · ADRs: none new (implements 7.4)
**Objective:** The self-verification machine every later WP's acceptance runs on.
**Deliverables:** `tests/harness/` per 7.4 (boot, QMP screendump+OCR, input injection, guest-exec via `mtest` user baked only into testing/PR images by Containerfile build-arg, serial logging); `just vm-test [suite]`; suites: `smoke` (boots to SDDM, login succeeds, plasmashell alive, `systemctl --failed` empty), `perf` (wraps WP-02 scripts w/ gates), `screens` (screenshot-diff w/ baseline+mask machinery per 7.4), `tests/security/ports.sh` (socket scan vs. the ADR-015 allowlist), and `tests/privacy/network_audit.sh` (10-minute idle capture; fails on any destination outside ADR-011's permitted set: OS/Flatpak registry checks, fwupd metadata, NTP, OOBE geoip, captive-portal probe — allowlist file is the ADR's testable form); `tests/stories/` framework + `zt_template.py`; CI `vm-test` job wired for PRs (7.3); failure artifacts (screenshots, serial log) uploaded; `docs/testing.md` (how to write a story test, how to re-baseline).
**Steps:** boot/QMP core → screendump+OCR asserts → input injection (QMP first; vncdotool fallback; prove both with SDDM login) → guest-exec channel → suites → CI wiring → docs.
**Acceptance:** `just vm-test smoke` green locally (aarch64) and in CI (x86_64); deliberately-broken assertion produces useful artifacts; `mtest` absent from any pushed image (scripted check on the pushed digest: no such user, no credential unit) while harness-injected access works on the same digest locally; flaky-rate: smoke suite 10× consecutive green in CI (record run link).
**Forbidden:** tests that depend on wall-clock timing without waits; network-dependent assertions in smoke.
**Escalate if:** hosted-runner KVM unavailable (fallback plan: TCG with 3× timeouts — implement, note perf caveat, continue).

---

#### WP-04 — Update pipeline, rollback, signing
Phase 0 · Depends: WP-01 · Parallel-safe: WP-02, 03 · Risk: medium · Size: M · ADRs: 008, 014
**Objective:** ADR-008 mechanically true, provable by drill.
**Deliverables:** `os/rootfs/usr/lib/systemd/system/`: `meridian-os-update.{service,timer}` (daily, randomized, metered-connection-aware `bootc upgrade` stage-only), flatpak-update timer (2×/day), all Wants-ed into a `meridian-maintenance.target`; status publisher: each run (and each boot) writes `bootc status --json` + rollback marker to world-readable `/run/meridian/update-status.json` — the read path for WP-12's Updates page (contract 8.0); greenboot config + our checks in `usr/lib/greenboot/check/required.d/` (graphical.target reached ≤ 90 s, sddm active, NetworkManager startable) `[VERIFY greenboot+bootc integration current mechanism; fallback: bootc's native rollback + our boot-counter unit replicating greenboot semantics]`; cosign signing in CI + `usr/etc/containers/policy.json` enforcing our key for our registry scope; `ci/` rollback-drill workflow: build sabotage image (unit that breaks graphical target), stage as update in a VM, reboot, assert auto-return to previous deployment + marker file for Settings; `docs/updates.md` (channel/promote runbook per 7.5/7.6).
**Acceptance:** rollback drill green in CI (the flagship test — link in STATUS.md); staged-update flow observed: timer fires in test-clocked VM, `bootc status` shows staged, reboot activates; unsigned/wrong-key image REFUSED by policy (negative test); no update activity produces user-visible UI (that arrives with WP-12's page).
**Forbidden:** auto-reboot logic; update UI (WP-12); shortening the drill by faking the failure detection.
**Escalate if:** signature enforcement breaks offline-ISO install path (coordinate with WP-17 — policy must allow the embedded image by digest).

### Phase 1 — Identity (M1)

---

#### WP-05 — Theme core
Phase 1 · Depends: WP-02, 03 · Parallel-safe: WP-06, and with 07 by contract (theme names fixed here) · Risk: medium · Size: L · ADRs: 003; §4, Appendix A
**Objective:** Plasma wearing Meridian: colors, style, decoration, fonts, wallpapers, icon overrides — both themes.
**Deliverables:** `shell/theme/`: color schemes `MeridianLight.colors`/`MeridianDark.colors` (from tokens); Plasma Style `meridian` (panel/popup SVGs w/ translucency+radius per 4.3); window decoration: Breeze configured (buttons right, our colors; verify Breeze close-hover renders `#e5484d` — if Breeze can't hit spec, decision per 8-line rule in Forbidden) `[VERIFY current Plasma decoration theming surface — Aurorae status changed across Plasma 6.x]`; icon override theme `meridian` (inherits Breeze; overrides per 4.4 — folder set, 12 app icons, tray glyphs; SVG sources + `just assets`); fonts packaged + fontconfig defaults; wallpapers (SVG sources → 4K PNGs, `just assets`); kdeglobals defaults (fonts, single-click=false, animation speed); `docs/design/theming.md` (what lives where, how to preview: `just vm-run --theme-dirty` hot-reload note).
**Steps:** color schemes → plasma style → decoration verify+config → icons → fonts/wallpapers → bake defaults into `os/rootfs/usr/etc/` → baseline screenshots (SDDM excluded, that's WP-06): desktop, a themed window (KWrite), context menu, both themes.
**Acceptance:** `just vm-test screens --suite theme` green with new baselines on both arches; side-by-side compare sheet (harness montage) attached to PR vs mockup crops for: window chrome, taskbar area colors (pre-layout), menu material; RAM delta from theme ≤ 30 MiB; light↔dark switch leaves no unthemed surface in the 3.2 app set (scripted walk + screenshots).
**Forbidden:** forking Breeze source wholesale (config + assets + ≤ small patch w/ justification only); shipping any raster without SVG source.
**Escalate if:** decoration cannot meet 4.3 radius/button spec via any supported mechanism (owner decides fidelity trade).

---

#### WP-06 — Boot & login: Plymouth, SDDM, silence
Phase 1 · Depends: WP-05 (brand assets) · Parallel-safe: WP-07+ · Risk: low · Size: S · ADRs: 003; §4
**Objective:** Power button → calm brand → login, no text soup.
**Deliverables:** `shell/theme/plymouth-meridian/` (logo on `#131318`, indeterminate soft spinner; matching firmware-logo handoff where BGRT allows); kernel args baked via bootc (`quiet loglevel=3 rd.udev.log_level=3 plymouth.ignore-serial-consoles` — exact set tuned in-WP); `shell/theme/sddm-meridian/` QML theme per mockup language (centered avatar, name, password field, accent focus ring; session/layout pickers hidden by default; power actions bottom-right); autologin config path for installer's checkbox (consumed by WP-17); boot-time budget kept.
**Acceptance:** boot screencast (harness frame captures) shows zero text frames UEFI→SDDM on clean boot; `boot_time.sh` still ≤ gate; SDDM baseline screenshot both themes; wrong-password shows gentle shake+message (story ZT-19 seed); autologin path proven in a test image.
**Forbidden:** custom greeters beyond SDDM theming; boot animations > 1 s loops.
**Escalate if:** silent boot leaks vendor/firmware text we can't suppress (document per-hardware in 10.2 notes instead).

---

#### WP-07 — Panel layout, KIOSK lockdown, Familiar shortcuts (+pager)
Phase 1 · Depends: WP-05 · Parallel-safe: WP-08, 09 (contract: containment names + plasmoid IDs reserved) · Risk: medium · Size: M · ADRs: 003, 005, 006, 016; §5.1, Appendix D
**Objective:** The Meridian shell frame: floating panel with stock placeholders, locked-down Plasma, Windows muscle-memory active.
**Deliverables:** `shell/look-and-feel/org.meridian.desktop/` (LnF: defaults + `layouts/org.meridian.desktop-layout.js` building the 5.1 panel — floating, 52px, order per spec — using stock kickoff/tray as placeholders until WP-08/09 swap in by plasmoid id); `org.meridian.pager` minimal plasmoid (3 fixed numbered chips per 5.1; ~150 lines QML); KIOSK baseline in `os/rootfs/usr/etc/xdg/` (immutable panel `[$i]` groups; action restrictions: `shell_access=false`, editable desktop off, widget-add off, run_command krunner scope per ADR-016) + `docs/kiosk.md` (every key + why); Familiar shortcut scheme shipped as kglobalshortcuts defaults + kwinrc (full Appendix D map incl. Meta-single-press, Meta+E/D/L/I/P/V, Win+arrows tiling, Ctrl+Shift+Esc, PrtScn family, Alt+F4); "Familiar mode" backing store (the config pair the WP-12 toggle flips; scheme files for both modes).
**Acceptance:** stories ZT-01 (start opens via Meta), ZT-14 (shortcut sampler: harness sends each Appendix-D chord, asserts effect) green; panel screenshot-diff vs mockup crop (placeholder plasmoids masked); user cannot: remove panel, add widgets, drag desktop icons into chaos (scripted attempts fail silently per KIOSK); pager switches 3 spaces w/ windows retained (scripted).
**Forbidden:** implementing start/quicksettings here (placeholders only); any shortcut that shadows app-standard Ctrl combos.
**Escalate if:** Meta-single-press unreliable on current Plasma (known-shifting area) — implement best mechanism, file upstream issue, note in STATUS.

---

#### WP-08 — Start menu plasmoid (`org.meridian.start`)
Phase 1 · Depends: WP-07 · Parallel-safe: WP-09, 10 · Risk: medium-high (core identity) · Size: L · ADRs: 005, 016; §5.2
**Objective:** The mockup's Start menu, functioning, fast.
**Deliverables:** `shell/plasmoids/org.meridian.start/` QML+minimal C++ plugin if needed: layout per 5.2 (560px, search, pinned 3×3 grid w/ drag-reorder + right-click Unpin/Uninstall hooks (uninstall calls Software via DBus — stub interface now, WP-13 implements), All-apps view, Places column, switcher card, footer w/ power menu incl. contextual restart-to-update line reading WP-04's marker); search via KRunner/Milou models restricted to ADR-016 scopes with grouped results; pinned-state storage (plasmoid config, default set per 5.2, DBus API for WP-14's browser-pin swap: `org.meridian.shell.Pins`); open/close animation per 4.3; keyboard-complete navigation (arrows/enter/esc/type-to-search).
**Acceptance:** stories ZT-01 (open→type "fire"→Enter launches Firefox ≤ 400 ms open-to-list), ZT-02 (pin/unpin persists reboot), ZT-16 (power menu: lock via harness, assert SDDM lock screen); screenshot-diff vs mockup (grid, places, card, footer) both themes; cold-open ≤ 150 ms after login settle (perf probe); all-apps list shows exactly visible-app set (3.2 audit reused); zero QML console errors in journal during suite.
**Forbidden:** new system services; web/search-engine integration; recents beyond KActivities data.
**Escalate if:** Milou/KRunner QML API insufficient for grouped scopes (fallback: direct KRunner DBus queries — allowed, note it).

---

#### WP-09 — Quick Settings plasmoid (`org.meridian.quicksettings`)
Phase 1 · Depends: WP-07 · Parallel-safe: WP-08, 10 · Risk: high (most integration surface) · Size: L · ADRs: 005 (incl. its fallback); §5.3
**Objective:** One calm panel replacing the tray zoo.
**Deliverables:** `shell/plasmoids/org.meridian.quicksettings/`: taskbar cluster (network/battery/dot + clock stays separate per layout) and popup per 5.3 — toggles wired to plasma-nm QML (Wi-Fi list+connect+password inline), Bluedevil (list/pair/connect), DND (notification inhibition), Night light (KWin colors DBus); sliders: brightness (PowerDevil DBus, absent→hidden on desktops), volume (plasma-pa model, per-device flyout); MPRIS row; notifications model (grouped, clear-all, actions passthrough); battery footer w/ time estimate; devices row (mounted removables w/ eject — udisks via Solid) feeding WP-11; hidden-but-present StatusNotifier host for third-party tray icons (collapsed "…" overflow — apps like Steam need it; curated placement).
**Acceptance:** stories ZT-03 (join WPA2 from popup, wrong-then-right password path), ZT-04 (pair BT audio device — QEMU emulated or loopback-scripted; plus manual matrix note), ZT-05 (volume slider + mute via keys w/ OSD), notification receive/clear scripted; screenshot-diff vs mockup; popup open ≤ 120 ms; **fallback checkpoint:** if by its 6th session this WP hasn't passed ZT-03/05, STOP and execute ADR-005 fallback (themed stock tray), file the plasmoid as v1.1 branch, record in STATUS.md — the milestone must not slip on this.
**Forbidden:** reimplementing NM/BlueZ/PipeWire clients (ADR-005); breaking third-party tray SNI contract.
**Escalate if:** fallback itself can't meet stories (unlikely; would indicate deeper image problem).

### Phase 2 — Core switcher UX (M2)

---

#### WP-10 — Files experience
Phase 2 · Depends: WP-05 (theme), WP-07 (kiosk base) · Parallel-safe: WP-08, 09, 11, 12 · Risk: low-medium · Size: M · ADRs: 006; §5.4
**Objective:** Dolphin becomes the mockup's Files: six folders, Trash, calm chrome, Windows habits honored.
**Deliverables:** `os/rootfs/usr/etc/` defaults: `dolphinrc` (toolbar per 5.4, breadcrumb non-editable, double-click open, grid default w/ sensible list columns, no split view button, remember-per-folder off), curated `dolphin` toolbar/menu XML (kxmlgui override), skeleton `user-places.xbel` (Places per 5.4 order + hidden-by-default extras; Devices group emerges via Solid automatically), GTK bookmarks skel (portal dialog parity), KIOSK keys hiding: open-terminal, root-actions, activities, places-editing; xdg-user-dirs enforced (`Desktop Documents Downloads Music Pictures Videos` — created + translated names off-by-default, see WP-24); Trash policy (size cap 10% of volume, purge prompt at cap); "Compress to ZIP"/Extract service-menu curation (Ark); Properties dialog audit (plain-language sizes/permissions tab simplified via kiosk where possible); disk-free footer (Dolphin's Space Info on); type-ahead jump verified; default file associations map (`os/rootfs/usr/etc/xdg/mimeapps.list`: browser per ADR-010, media→Haruna, images→Gwenview, pdf→Okular, txt→KWrite, zip→Ark…).
**Acceptance:** stories ZT-07 (copy file USB→Documents via drag), ZT-08 (rename F2, delete→Trash, restore from Trash, empty Trash), ZT-09 (zip roundtrip: compress two files, double-click open, extract) green; screenshot-diff Files window vs mockup both themes; path field NOT editable by any click surface in default mode; `/` unreachable via UI in default mode (scripted probe: no Root place, no URL entry, portal dialogs open at Home scope); after WP-12's Advanced toggle: Computer/Root place appears + editable path works (joint test with WP-12); mimeapps audit: every 3.2 filetype opens the intended app (scripted `xdg-mime` sweep).
**Forbidden:** patching Dolphin source (config/kxmlgui/kiosk only — if a 5.4 item is impossible without patch, minimal patch via 6.2 rules with justification); touching real FS layout (ADR-006).
**Escalate if:** breadcrumb-only mode has no supported config path (then patch route per above, noting upstream PR).

---

#### WP-11 — Removable media, phones, AutoPlay
Phase 2 · Depends: WP-09 (devices row), WP-10 (sidebar) · Parallel-safe: WP-12, 13 · Risk: low · Size: S · ADRs: 015; §5.5
**Objective:** Plug it in → it shows up → open → eject safely. Like Windows, minus autorun malware.
**Deliverables:** kded automounter defaults on (all removables, on attach+login); device-notifier config: single toast per 5.5 w/ Open-folder default action; udisks defaults confirmed for ntfs3 rw (`ntfs3` preferred, `ntfs-3g` fallback present), exfat, vfat (flush-friendly mount opts for pull-without-eject tolerance); kio-mtp/kamera present + tested path for Android (MTP) and iPhone (`ifuse`/libimobiledevice photos-only — verify feasibility `[VERIFY]`; if Apple pairing flakes, story marks iPhone "best effort", note in 10.2); eject flow: sidebar + Quick Settings + notification, with sync-flush and "Safe to remove" confirmation; polkit: mounting removables passwordless for active user, internal partitions stay gated (Advanced).
**Acceptance:** story ZT-06 scripted with QEMU `usb-storage` hotplug (attach → toast ≤ 3 s → Open lands in root of drive → copy both directions → eject → clean detach in journal); NTFS-formatted stick roundtrip; MTP smoke via `mtp-detect` harness stub + manual matrix entry; negative: autorun.inf present → nothing executes, no prompt mentions it.
**Forbidden:** auto-opening full-screen anything; indexing media on attach.
**Escalate if:** ntfs3 write instability appears in current kernel (flip default to ntfs-3g in one commit — decision pre-authorized here).

---

#### WP-12 — Settings curation + custom KCMs
Phase 2 · Depends: WP-05, 07; WP-04 (updates data) · Parallel-safe: WP-10, 11, 13 · Risk: medium · Size: L · ADRs: 006, 008, 011; §5.6
**Objective:** Settings a switcher can read: 13 pages, 4 of them ours.
**Deliverables:** systemsettings sidebar allowlist per 5.6 (KIOSK-hide all else; keep hidden KCM binaries — Advanced may re-expose later versions); ordering + icon tiles per mockup (custom sidebar styling within systemsettings theming limits — screenshot gate decides adequacy); custom KCMs in `apps/settings-kcms/`: **Updates** (bootc is daemonless with no D-Bus API — WP-04's update service therefore publishes `bootc status --json` output plus rollback markers to `/run/meridian/update-status.json`, world-readable, refreshed by the timer and on boot; this KCM reads that file plus flatpak history + fwupd offers; headline states; history list; apply-at-shutdown indicator; failure surface for WP-04 rollback marker: "Last update was undone automatically — you're on the previous version. We'd love the report." → About's report tool), **Apps** (Flatpak list w/ uninstall+portal permissions in plain language; Windows-apps section built against the `org.meridian.WinApps` contract fixture (8.0); defaults picker per 5.6), **Advanced** (polkit action `org.meridian.settings.advanced` auth_admin; toggles per 5.6 writing `/etc/meridian/advanced.conf` + applying live: places/terminal/dev-mode/captive-portal; "Reset Meridian defaults" = wipe user-level overrides of our config domains w/ confirm), **About** (branding.json-driven; device rename; report-a-problem zip: journal tail, hw inventory, versions — saved to Documents, path shown, nothing uploaded (ADR-011)); Appearance page: confirm stock KCM covers 5.6 needs (wallpaper/accent/light-dark) + add **Familiar mode** toggle (flips WP-07's scheme pair + Dolphin click mode live) — extend via our KCM if stock can't host the toggle sanely.
**Acceptance:** stories ZT-10 (change wallpaper+accent, survives reboot), ZT-11 (Updates page states: up-to-date / staged / rolled-back — harness drives all three via WP-04 hooks), ZT-12 (Advanced auth → system files visible in Files → toggle back), ZT-13 (add second user from Users page, log into it — profile gets full Meridian defaults: this test guards our skel/defaults architecture); sidebar shows exactly the 13 (screenshot + scripted KCM enumeration); jargon lint on all our KCM strings; every page keyboard-navigable.
**Forbidden:** forking systemsettings shell; any setting that writes outside user config + `/etc/meridian/`; telemetry-ish "diagnostics upload" convenience.
**Escalate if:** stock Appearance KCM can't be trimmed to spec (then our replacement page — small, but owner should know scope grew).

---

#### WP-13 — Software store (`apps/software/`)
Phase 2 · Depends: WP-05; WP-15 (catalog schema — can start against schema draft) · Parallel-safe: WP-10, 11, 12, 14 · Risk: high (has sanctioned fallback) · Size: L · ADRs: 004, 005-pattern, 010; §5.7
**Objective:** The mockup's Software window: curated switcher catalog + full Flathub search, one-click everything.
**Deliverables:** Kirigami/QML app + C++ backend on libflatpak: system-installation ops (install/uninstall/cancel/resume, progress), passwordless app management via a polkit **rules.d grant on flatpak's existing actions** (`org.freedesktop.Flatpak.app-install`/`app-remove` etc., allowed for active local users; **no custom privileged daemon and no new polkit action** — flatpak's system helper does the privileged work) w/ written security rationale in `docs/security-notes.md` (scope: Flathub remote only, no remote-adding); AppStream cache consumption (timer-refreshed, store never blocks); UI per 5.7: hero→guide view ("On Windows → Here" from catalog `replaces`), curated rails, search w/ verified badge + calm unverified note, app pages (screenshots, size, permissions preview), Installed/Updates read-mostly tabs; DBus service `org.meridian.Software` (open-to-app, uninstall — consumed by Start right-click & Settings→Apps); post-install: "Open" + auto Start-menu availability; default-browser/pin handoff hooks for Welcome (ADR-010).
**Acceptance:** stories ZT-15 (search "spotify" → install → appears in Start → open; uninstall from store), ZT-20 (guide view: install LibreOffice from "Replaces Microsoft Office" row) — both against real Flathub in CI (network job, retry-tolerant, nightly-only variant offline-mocked); screenshot-diff vs mockup (hero, rails, cards) both themes; cancel mid-download leaves no partial wreckage (`flatpak repair` clean); cold-open ≤ 1.5 s to interactive with warm AppStream cache; **fallback checkpoint at M2 review:** quality gate = the two stories + diff + a 10-minute owner drive; failing → execute 5.7 fallback (themed Discover) in a dedicated S-size recovery session, custom store → v1.1 branch, STATUS.md records the call.
**Forbidden:** adding remotes/repos UI; ratings scraping; "featured" content not from our catalog; any nag surface.
**Escalate if:** Flathub AppStream/API changes break search fundamentals (short-term: curated-catalog-only mode behind the same UI).

---

#### WP-14 — Welcome / OOBE (`apps/welcome/`)
Phase 2 · Depends: WP-08 (pins DBus), WP-09 (nm QML precedent), WP-13 (installs), stubs acceptable w/ contract tests · Parallel-safe: WP-10..13 late-phase · Risk: medium · Size: M · ADRs: 010, 011; §5.8
**Objective:** First login → connected, browsered, oriented — under 3 minutes, all skippable.
**Deliverables:** full-screen Kirigami flow per 5.8 (7 pages), autostart on first login of each user (marker in user config; "Welcome" stays in Start); Wi-Fi page reusing plasma-nm QML (shared component w/ WP-09 — extract to `shell/qml-common/` if needed); Browser page driving WP-13 backend (background install w/ progress chip; on select: default-browser set via portal/mimeapps + `org.meridian.shell.Pins.ReplacePin` — which swaps BOTH the Start-grid and taskbar pins per contract 8.0; Firefox remains installed — user can remove in store; copy explains that in one line); Windows-apps page (built against the 8.0 `org.meridian.WinApps` fixture; feature-flag-hidden until WP-20 flips it per contract); Files page (detection hook from WP-21, same flagging); Look page (mini Appearance: 3 wallpapers, 5 accents, L/D); Tour overlay (anchored coach marks on live shell, 4 stops, esc anytime); geoip timezone single-call w/ explicit "Detected: Chicago — change?" line (ADR-011 listed call).
**Acceptance:** story ZT-17 (fresh user first login → complete flow with browser=Chrome path in nightly network job → lands on desktop with Chrome default+pinned, Welcome never auto-shows again); skip-everything path ≤ 20 s to desktop; every page keyboard/escape clean; offline: Browser page shows Firefox-ready + "others need internet — find them later in Software" (no dead buttons); screenshot-diffs for Hello and Tour stops.
**Forbidden:** account creation (installer's job), EULAs, newsletter/registration, "tips" notifications post-completion.
**Escalate if:** portal default-browser setting flaky under Plasma (fallback: mimeapps.list write + xdg-settings, documented).

---

#### WP-15 — Curated catalog & compatibility data
Phase 2 · Depends: WP-00 (schemas home) · Parallel-safe: everything (pure data; unblocks 13/20 early — schedule FIRST in phase) · Risk: low · Size: M · ADRs: 004, 009; Appendices B, C
**Objective:** The editorial soul: what switchers see in the store and the truth about Windows apps.
**Deliverables:** `catalog/catalog.json` (schema + seed per Appendix B: ≥ 40 entries across 5.7's sections, each: flatpak ref (verified to exist on Flathub at commit time via `catalog/scripts/verify_refs.py` — CI job re-verifies weekly), name, replaces, one-liner (voice per 4.5), section, switcher-rank); `catalog/compat.json` (schema + seed per Appendix C: ≥ 50 Windows apps with status green/yellow/red/untested, evidence note, alternative pointer (catalog cross-ref), matcher fields (exe names, product-name substrings)); both shipped into image at `/usr/share/meridian/{catalog,compat}/` (update channel = OS updates, by design); editorial guide `catalog/EDITORIAL.md` (inclusion bar: works via Flathub, actively maintained, no dark patterns; ranking rationale; red-status wording templates per ADR-009).
**Acceptance:** schemas validate; `verify_refs.py` green (all refs installable); compat seed covers Appendix C's mandatory list incl. the honest reds (MS Office desktop, Adobe CC, anti-cheat titles); every red has an alternative or explicit "no good alternative — consider dual-boot" (the honest worst case); jargon lint on all strings; WP-13/20 consume without code changes (contract fixtures in `tests/fixtures/`).
**Forbidden:** paid placement of any kind; entries untested against Flathub; compat verdicts without an evidence note (even "ProtonDB gold, 2026-08" suffices — dated).
**Escalate if:** none foreseeable; this is editorial labor.

### Phase 3 — Getting it onto machines (M3)

---

#### WP-16 — Live ISO & hardware check
Phase 3 · Depends: WP-02 (image contents), WP-03 (harness) · Parallel-safe: WP-17 (contract: ISO layout), 18, 19 · Risk: medium-high (external tooling) · Size: L · ADRs: 007, 013
**Objective:** One bootable USB that sells the product before installing it.
**Deliverables:** `installer/iso/` build via titanoboa `[VERIFY: repo active, supports our bootc image]` — fallback: lorax/`livemedia-creator` kickstart path (decision + evidence in STATUS.md); ISO contents: squashfs live system of the full image, **embedded OCI image in containers-storage for offline install**, Flatpak sideload repo (Firefox + runtimes; manifest `installer/iso/sideload.yml`), memtest + media-check boot entry; live session: autologin `live` user, Welcome suppressed, **"Try or Install" card** per 5.11 (part of `apps/welcome/` codebase, live-mode flag) w/ hardware check row (Wi-Fi via NM state, sound chime via PipeWire probe, display res, battery via UPower, layout guess) + plain-language failure guidance strings; Install icons (desktop+taskbar) launching WP-17; `just iso` + CI iso job (7.3) w/ checksums; boot support: UEFI (primary) + BIOS (best-effort, ADR-013) from the same ISO; USB-writing doc `docs/help/make-a-usb.md` (Fedora Media Writer / Rufus / Etcher — GUI-only instructions, INV-0).
**Acceptance:** CI: ISO boots UEFI (OVMF) and BIOS (SeaBIOS) in harness → live desktop ≤ 90 s; hardware row states render (network yes/no simulated both ways, sound probe asserts sink activity); ISO ≤ 3.5 GiB gate; offline VM (no netdev): live desktop fully functional, Firefox launches from sideload; media-check entry passes on good ISO / fails on corrupted byte (scripted).
**Forbidden:** shipping the installer as the boot target (live-first is the product decision); netinstall-only paths.
**Escalate if:** both titanoboa and lorax paths can't embed OCI+sideload within size gate (owner decides: size gate vs offline capability).

---

#### WP-17 — Installer: Calamares, three screens, bootc deploy
Phase 3 · Depends: WP-16 (boots from its live env), WP-04 (policy/signing interplay) · Parallel-safe: WP-18, 19 · Risk: **highest in project** · Size: L · ADRs: 007, 013, 015
**Objective:** Pat installs Meridian alone, in under 15 minutes, without learning what a partition is.
**Deliverables:** `installer/calamares/`: `settings.conf` sequencing (welcome-less: our 3 screens per 5.11 + summary + exec + finished), branding component (QML slideshow: 5 pillar slides per 5.11, Meridian chrome), config for locale/keyboard screen (geoip optional), partition screen config (erase-disk w/ human disk names; alongside-Windows w/ NTFS resize + `ntfsfix`-dirty guard + backup nudge; advanced link to full partitioner; LUKS checkbox both surfaces; swap: zram-only default, no disk swap partition (hibernate non-goal per 15); filesystem: btrfs with Fedora's standard subvolume layout (`root`, `home` — snapshots enable v1.x backup feature)); users screen config (per 5.11: derived username/hostname, strength meter config, autologin checkbox wiring WP-06 path); **`modules/bootcinstall/`** (Python job: `bootc install to-filesystem` from ISO's embedded store onto the target mounts w/ `--source-imgref` local, correct ESP/BIOS-grub handling via bootc, kernel args from WP-06, signing-policy install per WP-04 allowing embedded-digest, error surfaces in plain language); post-install module: Flatpak sideload provision (system remote+installs from ISO payload), firstboot flags for WP-14/18, machine-id reset, live-user cleanup; unattended profile for CI (`installer/calamares/unattended-ci.conf` driving the erase-disk path headlessly for the e2e job — config-file based, not UI scripting, where Calamares permits; else harness VNC script per 7.3).
**Acceptance:** CI installer-e2e (7.3): ISO boot → scripted 3-screen erase-install → reboot from disk → smoke + ZT-17 OOBE chain green, UEFI and BIOS variants; alongside-Windows e2e: fixture disk image w/ small NTFS Windows-like layout → resize → dual entries in boot menu → **Windows still boots** (fixture asserts NTFS mounts clean + bootmgr chainload reaches its stub); LUKS path: install w/ encryption → passphrase unlock boot → smoke; failure UX: yanked target disk mid-copy → plain-language error + safe abort (no half-bootloader); click-count audit ≤ 8 on happy path (harness counts); install duration ≤ 15 min in KVM-on-SSD budget.
**Forbidden:** exposing Calamares' stock module soup (netinstall, packagechooser…); any screen beyond 5.11's; writing to detected Windows partitions except the sanctioned resize.
**Escalate if:** `bootc install to-filesystem` hits a blocker with Calamares' mount layout (fallback ladder pre-authorized: (1) `to-disk` mode with Calamares limited to disk-choice + LUKS, losing custom layouts in Advanced; (2) Readymade evaluation per ADR-007; escalate before falling past (1)).

---

#### WP-18 — Nvidia specialization
Phase 3 · Depends: WP-01 (variant build), WP-17 (firstboot flag), WP-12 (Updates surface) · Parallel-safe: WP-16, 19 · Risk: medium · Size: M · ADRs: 012
**Objective:** ADR-012's single-ISO promise: Nvidia machines specialize themselves.
**Deliverables:** `-nvidia` image variant in CI matrix (build rows ×2; `os/Containerfile` ARG-switched base per ADR-002); `meridian-gpu-specialize.service` (oneshot: PCI probe 0x10de + generation gate per ADR-012 → write intent flag) + companion network-triggered stage unit (`bootc switch --apply=staged` equivalent to variant tag `[VERIFY exact bootc rebase verb]`); Updates-page state line via WP-12 hook ("Graphics driver ready — takes effect after restart"); pre-Turing detection → Settings notice string ("This graphics card uses the built-in driver; games and video acceleration are limited.") + docs; interaction guard w/ WP-04 (specialize wins queue priority over same-day OS update; single reboot applies both).
**Acceptance:** harness VM w/ fake Nvidia PCI id (qemu `-device` vendor spoof or injected sysfs fixture — implement whichever is honest, document) walks: install → flag → simulated network → staged variant → reboot → `bootc status` shows nvidia image booted; non-Nvidia VM: service exits 0-noop ≤ 50 ms, no flag; offline Nvidia: system fully usable on fallback, Updates page explains pending driver; real-hardware entry added to 10.2 matrix (GTX 16xx + RTX 30xx rows) for M4 manual pass.
**Forbidden:** shipping both driver stacks in one image; kernel-arg hacks per-machine outside bootc-managed args.
**Escalate if:** ublue's nvidia variant mechanism shifts under us mid-phase (pin previous tag, note, continue; structural change → owner).

---

#### WP-19 — Dual-boot polish
Phase 3 · Depends: WP-17 · Parallel-safe: WP-16, 18 · Risk: low · Size: S · ADRs: 007, 013
**Objective:** Coexisting with Windows without the classic paper cuts.
**Deliverables:** GRUB config policy: menu hidden+0s when Meridian alone; os-prober-driven "Windows" entry (title exactly "Windows", not "Windows Boot Manager (on /dev/…)") + 3 s menu when present; `timedatectl set-local-rtc 1` applied by installer only-when-Windows-detected (the clock-skew fix); `meridian-boot-reconcile.service` (oneshot, each boot, ≤ 200 ms budget): if the recorded Windows partition no longer exists → regenerate boot entries (os-prober rerun) and reset RTC to UTC — no user action, no docs needed (INV-0); Windows partition hidden from Files default mode (WP-10 places policy — assert), visible read-write in Advanced w/ warning row; hibernated-Windows guard: NTFS mount refuses+explains when hiberfil dirty ("Windows is hibernated — restart Windows fully first") in Migration wizard + Advanced mount paths; boot-menu theme (minimal: brand mark + two entries, GRUB theme in `shell/theme/`).
**Acceptance:** WP-17's alongside e2e extended: menu shows 2 entries themed, timeout 3 s, RTC flag set; solo-install shows no menu flash; fixture-hibernated NTFS → correct refusal strings in both surfaces; removing Windows partition (fixture) → next boot: reconcile service regenerates entries, menu auto-hides, RTC back to UTC (asserted in harness).
**Forbidden:** auto-mounting Windows partition rw anywhere in default mode; touching Windows bootloader entries beyond chainload.
**Escalate if:** none expected.

### Phase 4 — The Windows bridge (M4)

---

#### WP-20 — Windows App Support (`apps/winapps/`)
Phase 4 · Depends: WP-15 (compat data), WP-12 (Apps page), WP-13 (store presence optional) · Parallel-safe: WP-21, 22, 23 · Risk: high (external ecosystem) · Size: L · ADRs: 009; §5.9
**Objective:** Sam's label-printer .exe runs; nobody gets lied to.
**Deliverables:** `meridian-winapps` (Qt helper + `winapps` CLI for tests): MIME registration per ADR-009 (both exe types + .msi); first-use consent card + runtime bootstrap (umu-launcher + Proton-GE current → `/var/lib/meridian/winapps/runtime`, checksummed, resumable download, ~"15 s on broadband" claim validated `[VERIFY umu-launcher release channel + Proton-GE latest]`, fallback per ADR-009: preconfigured Bottles flatpak driven headlessly — same UX contract); per-app containers `~/.local/share/meridian/winapps/<slug>/` (prefix + metadata.json); installer-detection heuristics (filename/PE product markers: setup/install/msi → run installer flow; watch prefix Start-Menu dir → surface created shortcuts as desktop entries w/ Windows-badge icon per 4.4); compat gate UI per ADR-009 traffic light (matcher: exe name + PE VersionInfo product string vs compat.json; unknown → honest untested card); runner env (umu with per-app GAMEID default, dxvk/vkd3d via Proton, Wayland-native where Proton allows, windowed-first defaults); registry DBus `org.meridian.WinApps` implementing the 8.0 contract exactly (fixture test green); **flip WP-14's page-4 feature flag + extend ZT-17** per contract; uninstall = remove container + entries; docs `docs/help/windows-apps.md` (expectations page, GUI-only).
**Acceptance:** story ZT-18: harness installs a known-green FOSS Windows app (pin exact: e.g. Notepad++ installer .exe fixture, checksummed in `tests/fixtures/`) → shortcut appears in Start → launches → window on Wayland → uninstall via Settings clean; red-flow: fixture matching "Microsoft Office" product → red card w/ M365/LibreOffice pointers, no run-anyway buried (run-anyway exists but secondary per 5.9); offline: .exe double-click w/o runtime → clear "needs internet once" card; runtime download resumable (kill+resume test); no terminal windows ever flash (Wayland assert on surfaces).
**Forbidden:** claiming game support anywhere in UI; auto-associating documents (pdf/doc/etc.) to Windows apps (ADR 5.9); running anything from removable media without the same consent card (blocked by default + explicit enable per-drive is v1.x — for 1.0: exe on removable media prompts to copy to Documents first, closing the USB-autorun-style hole).
**Escalate if:** umu abandoned/incompatible at execution → execute Bottles fallback (pre-authorized), STATUS.md records; if even Bottles can't meet ZT-18 → owner call on shipping Windows-app support in 1.0 vs 1.1 (milestone gate decision).

---

#### WP-21 — Migration wizard (`apps/migration/`)
Phase 4 · Depends: WP-10 (Files conventions), WP-14 (entry point), WP-19 (NTFS guards) · Parallel-safe: WP-20, 22, 23 · Risk: medium · Size: M · ADRs: —; §5.10
**Objective:** Pat's 20 years of photos arrive safely; the old Windows disk is never harmed.
**Deliverables:** Kirigami wizard per 5.10: source scan (blkid NTFS + `/Users` presence; external drives incl. "old laptop via USB adapter" case), ro-mount via udisks (never rw — enforced mount opts + WP-19 hibernation guard), user enumeration w/ du-style sizing (async, cancellable), folder checkbox tree w/ sizes + OneDrive-placeholder detection (reparse-point flags → warning "these files live in Microsoft's cloud — sign into onedrive.com to get them" + excluded-by-default), destination = matching xdg dirs, space preflight, KIO-based copy queue (progress, pause/resume, per-file error skip-log, collision → "keep both" suffixing), final report per 5.10 (+ saved as `Documents/Migration report.txt`); bookmarks extraction (Chrome/Edge `Bookmarks` JSON → `Documents/Windows bookmarks.html` standard format + report pointer); relaunchable from Start ("Bring my files").
**Acceptance:** story ZT-21: fixture NTFS image (two users, nested folders, long paths, unicode names, a OneDrive-placeholder marker, 10k-file dir) → wizard full path → counts match fixture manifest exactly, placeholders excluded w/ warning shown, source hash-verified untouched (before/after image checksum), report content asserted; interrupted-copy resume test (kill mid-copy → relaunch → resume completes, no dupes); low-space path shows plain refusal before copying; hibernated fixture → WP-19 message.
**Forbidden:** writing one byte to source; migrating AppData/Program Files (out of scope, no toggle); background "sync" ambitions.
**Escalate if:** KIO throughput pathological on huge trees (fallback: rsync-style internal copier behind same UI — pre-authorized).

### Phase 5 — Hardening & release (M5)

---

#### WP-22 — Printing & scanning
Phase 5 · Depends: WP-12 (Printers page visible) · Parallel-safe: WP-20, 21, 23, 24 · Risk: low-medium · Size: S · ADRs: 015
**Objective:** "Plug in printer → print" — driverless-first, the way modern printers actually work.
**Deliverables:** CUPS + `ipp-usb` + Avahi service-discovery defaults on (driverless IPP Everywhere as the only advertised path); print-manager KCM confirmed in Settings→Printers (add flow: auto-discovered list w/ human names; manual-IP entry for stubborn office gear); default job options sane (A4/Letter by locale, duplex default off); sane-airscan for scanning + a scan flow decision: ship `skanpage` `[VERIFY current KDE scan app fit]` visible only when scanner detected (Solid-triggered .desktop conditional — else always-visible in All apps, small); test-page flow prints branded page; queue toasts ("Printing 'Boarding pass' — 2 pages"); legacy non-IPP printers explicitly out of scope for guided UX — Printers page links help doc explaining the 2015 cutoff kindly + Advanced escape hatch mentions nothing (no driver-hunt UI, pillar 4).
**Acceptance:** CI: `cups-pdf` virtual printer e2e (add via discovery mock → print test page from Okular via harness → PDF artifact byte-sane); story ZT-22 scripted against cups-pdf; ipp-usb unit active-on-plug (udev fixture); manual matrix (10.2): ≥ 3 real printers incl. one HP inkjet + one Brother laser at M5; jargon lint on Printers strings.
**Forbidden:** bundling vendor driver blobs (hplip-gui and friends stay out); "download driver" flows.
**Escalate if:** print-manager KCM UX unsalvageable for Pat (screenshot evidence → owner decides mini-KCM scope).

---

#### WP-23 — Power, battery & thermals
Phase 5 · Depends: WP-09 (battery surfaces), WP-12 (Power page) · Parallel-safe: WP-20..22, 24 · Risk: low · Size: S · ADRs: 015
**Objective:** Laptop behavior that matches lid-and-battery instincts from Windows.
**Deliverables:** tuned-ppd (power-profiles API) w/ profiles wired to Quick Settings battery flyout + Power page (Balanced default; Performance on AC-desktop default); PowerDevil defaults: lid close = sleep (s2idle), 15-min display off / 20-min sleep on battery, never-sleep on AC-desktop, low-battery warnings at 20/10/5% w/ our toast styling, critical action hibernate-off→shutdown-safe (no-hibernate per ADR-013 zram decision — verify messaging says "shutting down soon" honestly); thermald active on Intel; battery health/charge-limit rows on Power page where sysfs supports (Lenovo/Framework/ASUS conservation endpoints — feature-detect, hide otherwise); wake-on-lid + instant-resume audit in matrix; "Sleep" naming everywhere (never "suspend").
**Acceptance:** harness (VM-limited): profile switch reflected in `tuned-adm active` via UI path; idle timers fire (clock-accelerated) → display off event logged; low-battery fixture (UPower mock) → correct toast ladder; matrix at M5: 3 laptops sleep/resume 10-cycle clean, battery estimate sane vs 2-min discharge sample; RAM/boot budgets unmoved.
**Forbidden:** TLP or other stacked power daemons; hibernate resurrection.
**Escalate if:** s2idle broken on a matrix laptop (document per-device, deep-sleep quirks are v1.x enablement backlog).

---

#### WP-24 — Accessibility & internationalization
Phase 5 · Depends: feature-complete UI (post 13/14/12) · Parallel-safe: WP-22, 23, 25 · Risk: medium · Size: M · ADRs: —
**Objective:** Meridian is usable by more of the family than the mockup's ideal user.
**Deliverables:** a11y pass on all custom surfaces (start, quicksettings, welcome, store, wizards, KCMs): full keyboard paths (already story-gated), Accessible names/roles on every interactive QML item (Qt Accessibility), visible focus rings per token spec, contrast audit both themes (WCAG AA on text surfaces; fix tokens where failing — tokens.json patch w/ owner ping if brand colors shift), Plasma's screen reader (Orca) smoke on login+start+files ("does it speak, is it navigable" bar, not full certification — recorded honestly in docs), magnifier/large-text sanity at 125/150/200% (screenshot suite × scale factors — layout breakage fails); i18n: all our QML/C++ strings through KI18n from birth (retrofit-audit here + lint that bans raw literals in UI properties `tests/lint/i18n.sh`), translation infrastructure (Weblate-ready POT export in CI `[VERIFY hosted-Weblate free tier for FOSS]`), 1.0 shipped locales: en, es, fr, de, pt-BR (machine-draft + human-review flag where community review absent — marked "beta translation" in Settings honestly), keyboard-layout coverage inherited (installer screen already picks); RTL smoke (ar) on start+files layout mirroring — defects filed, fix-or-document.
**Acceptance:** contrast report artifact ≥ AA on both themes; scale-factor screens green at 4 factors; Orca smoke checklist committed w/ results; `i18n.sh` lint green (zero raw strings); `LANG=es_ES` boot → start menu/store/settings speak Spanish (screenshot suite locale variant); pseudo-locale (xx-double-length) run shows no clipped layouts on the 6 core surfaces.
**Forbidden:** shipping a locale > 20% untranslated as non-beta; contrast fixes via per-surface hacks instead of tokens.
**Escalate if:** brand accent fails AA on light theme chips (likely for blue-on-white small text — proposed compliant darkened variant included in report for owner sign-off).

---

#### WP-25 — Beta program, hardware matrix, release engineering
Phase 5 · Depends: M3 complete (installable) · Parallel-safe: WP-22..24 (runs alongside as the umbrella) · Risk: low (labor) · Size: M · ADRs: 008, 014
**Objective:** 1.0 earns its number on real machines and real strangers.
**Deliverables:** `docs/qa/hardware-matrix.md` per 10.2 (row template + result log; owner recruits hardware, Jordan-types recruited via public repo); beta channel mechanics (`:testing` opt-in toggle in Advanced + Updates-page badge "You're helping test"); issue intake: templates (bug w/ auto-report-zip attach instructions, hardware report), triage labels, P1 definition (data loss, boot failure, update failure, security); release checklist `docs/qa/release-checklist.md` (Section 9.3 verbatim + sign-off table); download page (GitHub Pages in `docs/site/`: one page, one button, checksum + Ventoy/Fedora-Media-Writer GUI instructions, hardware minimums, honest FAQ incl. Secure Boot disable guidance per-vendor per 10.4); versioning + release automation (tag → iso build → checksums → GH Release w/ generated notes from STATUS/changelog discipline); post-1.0 update drill on a beta cohort (stable promote observed landing on ≥ 5 external machines via voluntary beta-thread confirmations — ADR-011 means we cannot and do not measure it ourselves).
**Acceptance:** two full release-checklist dry runs executed (RC1, RC2) w/ all gates green + signed-off table; matrix ≥ the 10.2 mandatory rows filled, zero P1s open; download page live w/ working artifacts; a stranger-test (someone outside the project) takes USB→installed→OOBE unaided w/ notes filed.
**Forbidden:** analytics on the download page beyond host-native totals; release with red matrix rows waived silently (owner may waive explicitly in writing per row).
**Escalate if:** beta recruitment stalls < 6 external machines (owner decides: delay vs narrowed 1.0 hardware claims).

---

#### WP-26 — Naming & brand finalization
Phase 5 · Depends: none technically (owner-driven; MUST complete before RC1) · Parallel-safe: all · Risk: low · Size: S · ADRs: 014; §6.5; Appendix E
**Objective:** The real name, cleanly applied.
**Deliverables:** Candidate dossier per Appendix E process (5 names incl. "Meridian OS" as candidate #1: for each — trademark search evidence (USPTO/EUIPO TESS-level lookups documented), domain/handle availability, distro-namespace collision check (DistroWatch + GitHub search), linguistic checks in shipped locales, wordmark sketch in the 4.4 language); owner selection → single rename PR flipping `branding.json` + asset regen (`just assets`) + os-release + docs sweep, proving the 6.5 invariant; wordmark/logo final SVG masters; boilerplate (one-line, boilerplate paragraph, README hero) in brand voice.
**Acceptance:** rename PR touches ≤ 5 files + generated assets (CI branding-lint proves zero stragglers); all screenshot baselines regenerated in same PR (name appears in About/SDDM/installer slides only — token-driven); dossier committed.
**Forbidden:** names requiring "Linux" in them; anything within edit-distance embarrassment of existing distros (checked in dossier).
**Escalate if:** candidate #1 trademark-blocked and owner unavailable → hold at codename, do not self-select.

### 8.7 Sequencing & parallelization map

```
Phase 0: WP-00 → WP-01 → {WP-02 ∥ WP-03 ∥ WP-04}                  (3 lanes after 01)
Phase 1: WP-05 → {WP-06 ∥ WP-07} → {WP-08 ∥ WP-09}                (theme first, then shell lanes)
Phase 2: WP-15 FIRST (unblocks data) ∥ then {WP-10 ∥ WP-12 ∥ WP-13} → WP-11 → WP-14 (integrates)
Phase 3: WP-16 → WP-17 → {WP-18 ∥ WP-19}   (16/17 overlap after ISO layout contract fixed)
Phase 4: {WP-20 ∥ WP-21}
Phase 5: {WP-22 ∥ WP-23 ∥ WP-24} under WP-25 umbrella; WP-26 anytime before RC1
Recommended fleet: 3–4 concurrent agents max; more causes STATUS.md contention and
integration drift. One agent per WP; never two agents inside one WP simultaneously.
```

---

## 9. Milestones & release criteria

### 9.1 Milestone gates (each = full 7.5 M-gate run + listed exit criteria + owner demo)

- **M0 "It boots and heals"** (Phase 0): image builds both arches; boots to stock desktop in harness; RAM/boot budgets baselined; rollback drill green; harness runs in CI on PRs. *Demo: sabotaged update healing itself on video.*
- **M1 "It's Meridian"** (Phase 1): themed boot→login→desktop; Start + Quick Settings (or sanctioned fallback) live; Familiar shortcuts; screenshot suite vs mockup approved by owner. *Demo: mockup beside VM, arm's-length test.*
- **M2 "A switcher can live here"** (Phase 2): all Phase-2 stories green; Settings curated; store installing real apps; OOBE complete; INV-0 suite (available stories) 100%. *Demo: fresh-login-to-productive in 3 minutes.*
- **M3 "It ships on metal"** (Phase 3): ISO + 3-screen installer; erase/alongside/LUKS paths green in CI; first real-hardware installs (≥ 2 machines); Nvidia specialization proven; dual-boot clean. *Demo: USB → installed laptop, timed.*
- **M4 "The bridge holds"** (Phase 4): ZT-18/21 green; compat honesty flows demoed; migration fixture perfect-copy proof. *Demo: Sam scenario end-to-end (SaaS + one .exe + print).*
- **M5 / 1.0 gate:** Section 9.3 checklist, entire.

### 9.2 Suggested agent-effort budget (for fleet planning, not deadlines)

Phase 0 ≈ 11 sessions · Phase 1 ≈ 17 · Phase 2 ≈ 22 · Phase 3 ≈ 16 · Phase 4 ≈ 10 · Phase 5 ≈ 12 → **~88 Opus-5-medium sessions** end to end, ±40%. Re-estimate at each M-gate in STATUS.md.

### 9.3 The 1.0 release checklist (every line checked, evidence-linked, signed)

1. All 27 WPs DONE in STATUS.md (or owner-waived in writing with v1.1 issue links).
2. Zero-Terminal suite 22/22 on x86_64 stable ISO→install→use path.
3. All Section 1.5 metric gates green, numbers recorded.
4. Hardware matrix mandatory rows all green (10.2), zero open P1s, P2s triaged with owners.
5. Rollback drill + update-landing drill on beta cohort confirmed.
6. Privacy audit (`network_audit.sh`) + manual Wireshark session reviewed and published as a repo doc (the receipts behind pillar 5).
7. Security review: ports scan clean against the allowlist, polkit rules audit signed, SELinux enforcing, signature enforcement verified, no test credentials in any published digest, dependency CVE scan clean or waived.
8. Parent test ≥ 9/10 tasks ≥ 4/5 testers, notes filed.
9. Docs complete: help center articles for every 10.1 story (GUI-only wording lint green), FAQ, Secure Boot guide.
10. WP-26 name applied everywhere; screenshots/site/README coherent; LICENSE/NOTICE accurate.
11. Release artifacts: signed images `:stable`+version tag, ISO + SHA256SUMS on the download page, release notes in brand voice.
12. Owner's final demo sign-off recorded in STATUS.md.

---

## 10. QA program

### 10.1 The Zero-Terminal stories (INV-0 enforcement; each is a harness script + help article)

| ID | Story (the user can…) | Primary WP |
|---|---|---|
| ZT-01 | Open Start with the Windows key, find and launch an app by typing | 07/08 |
| ZT-02 | Pin/unpin an app; pins survive reboot | 08 |
| ZT-03 | Join a Wi-Fi network, including recovering from a wrong password | 09 |
| ZT-04 | Pair Bluetooth headphones and hear sound switch to them | 09 |
| ZT-05 | Change volume/brightness by keys and slider, with OSD feedback | 09 |
| ZT-06 | Plug in a USB drive or phone, open it, and eject it safely | 11 |
| ZT-07 | Copy files between USB and Documents by drag and drop | 10/11 |
| ZT-08 | Rename (F2), delete to Trash, restore, and empty Trash | 10 |
| ZT-09 | Zip two files and extract a received zip | 10 |
| ZT-10 | Change wallpaper, accent color, and light/dark; keep after reboot | 12 |
| ZT-11 | See update status, incl. staged and rolled-back states, in plain words | 04/12 |
| ZT-12 | Unlock Advanced with a password; see system files; lock it again | 12/10 |
| ZT-13 | Add a family member's account; their first login gets full Meridian defaults | 12 |
| ZT-14 | Use the Windows shortcut set (Appendix D sampler) successfully | 07 |
| ZT-15 | Search the store, install an app, open it, uninstall it | 13 |
| ZT-16 | Lock, sleep, restart, shut down from the Start power menu | 08 |
| ZT-17 | Complete first-boot setup incl. choosing Chrome as default browser | 14 |
| ZT-18 | Run a Windows program from an .exe, then remove it from Settings | 20 |
| ZT-19 | Recover from a mistyped login password without panic | 06 |
| ZT-20 | Find "what replaces Excel" in the store guide and install it | 13/15 |
| ZT-21 | Bring Documents and Pictures over from a Windows disk | 21 |
| ZT-22 | Add a discovered printer and print a test page | 22 |

(The gate is ALL 22 stories green; any story added later joins the gate automatically.)

### 10.2 Hardware matrix (mandatory rows for 1.0; template in `docs/qa/`)

| Class | Reference target | Why |
|---|---|---|
| Win10-refugee desktop | Dell OptiPlex 3050 / HP 2016–2017 i5, HDD+SSD | Pat's machine; BIOS+UEFI variants |
| Win10-refugee laptop | ThinkPad T480 or similar 8th-gen | The canonical switcher laptop |
| Modern mainstream laptop | 2022+ Ryzen or 12th-gen Intel, Wi-Fi 6 | Sam's class; s2idle + brightness + webcam |
| Low-end constraint | 4 GB RAM Celeron/Pentium laptop, eMMC | Floor honesty (ADR-013) |
| Nvidia desktop | GTX 16xx AND RTX 30xx+ | ADR-012 both driver generations |
| Trouble-hardware seat | One Broadcom-Wi-Fi Mac or similar | Driver-stack proof |
| VMs | UTM/aarch64 (dev loop), QEMU-KVM x86_64 (CI), plus one VirtualBox+VMware smoke | Where users will "try it first" |

Per-row protocol: live-boot hardware panel → install (path per row) → ZT sampler (01,03,05,06,16,22) → sleep/resume ×10 (laptops) → update+rollback drill → result + quirks logged.

### 10.3 Parent test script (M5, moderated, 5 testers ≥ 45 y/o non-technical)

Boot installed machine → 10 tasks: connect Wi-Fi; open the internet and find a news site; make a folder "Recipes" in Documents and put a text file in it; plug in this USB stick and copy the photos folder to Pictures; change the wallpaper; install "Spotify"; play the sample video file; print this page (cups-pdf allowed); find how much battery is left; turn it off. Success = no facilitator intervention, no terminal sighting, tester-reported confidence ≥ 4/5.

### 10.4 Known-limits documentation (shipped honestly in FAQ)

Secure Boot must be disabled in 1.0 (per-vendor GUI guide; shim planned v1.x); fingerprint readers not supported 1.0; HDR not surfaced; iPhone = photos-only best-effort; legacy (pre-2015 non-IPP) printers unsupported by design; MS Office desktop and Adobe CC do not run — alternatives guided (ADR-009).

---

## 11. Risk register

| # | Risk | L×I | Mitigation (in-plan) | Fallback (pre-authorized) |
|---|---|---|---|---|
| R1 | Calamares×bootc install module hits integration wall | M×H | WP-17 is the highest-scrutiny WP; module is thin over `bootc install` | Fallback ladder in WP-17 Escalate; Readymade re-eval |
| R2 | Custom Quick Settings misses quality bar | M×M | ADR-005 reuse rule; WP-09 6-session checkpoint | Themed stock tray ships 1.0; plasmoid → v1.1 |
| R3 | Custom store misses quality bar | M×M | libflatpak-only scope; M2 gate | Themed Discover + curated grid in Welcome |
| R4 | ublue base images renamed/discontinued | L×H | ADR-002 verify + weekly ref-check CI | Fedora Kinoite base + our hardware-enablement layer |
| R5 | Plasma 6.x bump breaks plasmoids/theme | M×M | Nightly CI against base rebuilds; rebase-WP per cycle (7.6) | Pin previous base tag while fixing (bootc makes this one line) |
| R6 | Secure-Boot-on machines can't boot ISO → support burden | H×M | Detection impossible pre-boot; docs/FAQ per-vendor + marketing honesty (10.4) | v1.x shim WP (15); never claim SB support until real |
| R7 | umu/Proton-GE ecosystem shift | M×M | ADR-009 verify at WP-20 | Bottles-headless same-UX fallback |
| R8 | NTFS resize corrupts a beta tester's Windows | L×VH | dirty-bit guard, chkdsk gate, backup nudge, e2e fixture proof (WP-17) | Alongside-mode hides if guard trips; erase/second-disk paths unaffected |
| R9 | RAM/ISO budgets fail late | L×M | Budgets are PR gates from Phase 0, not release-time surprises | Owner-visible budget renegotiation (1.5 note precedent) |
| R10 | Codec/patent posture of ublue full-ffmpeg | L×M | Same posture as major community distros; document in 13 | Swap to constrained ffmpeg build; store offers full via Flathub (user-initiated) |
| R11 | Agent drift: two agents contradict, STATUS.md rots | M×M | §14 contract, one-agent-per-WP, CODEOWNERS on load-bearing paths | M-gate reconciliation session re-baselines STATUS.md |
| R12 | Naming candidate trademark-blocked | M×L | 5-candidate dossier, codename decoupling (6.5) | Ship RC under next candidate; rename is 1 PR by design |

## 12. Security & privacy posture (summary; enforced via ADR-011/015 tests)

Attack surface: no non-loopback listening sockets beyond the audited printing allowlist (mDNS 5353; CUPS/ipp-usb on loopback); firewalld default-deny inbound (mdns service excepted); browser is the only routine network-facing app (Flatpak-sandboxed); polkit boundary = our UAC with three custom actions total (settings.advanced, winapps runtime install, plus the Flatpak rules.d grant of F12 below — each documented in `docs/security-notes.md` with scope rationale); SELinux enforcing untouched; signed OS images with enforced policy; Flathub-only remote; USB media never auto-executes (5.5/WP-20 copy-first rule for exes); update integrity = registry TLS + cosign + bootc rollback safety net. Privacy: ADR-011's complete-connections list is a *tested contract*, and the 9.3(6) published audit is part of the release definition. Threat honesty: physical access and a hostile local admin are out of 1.0 scope beyond LUKS opt-in; we say so in the FAQ rather than implying more.

## 13. Licensing & legal (execution notes for agents)

Ours: MIT (code), CC-BY-SA-4.0 (docs), OFL fonts bundled with their notices in NOTICE. Upstream-derived theme assets: LGPL-2.1+ (Breeze lineage) — keep headers. Firefox: redistribute unmodified official Flatpak (trademark-compliant; our policies.json stays within distribution-policy allowances — no search/default tampering). Chrome/Edge/Vivaldi: never redistributed; store/Welcome initiate vendor-hosted downloads w/ user click = EULA acceptance flow (Flathub's extra-data mechanism handles this — we add nothing). Proton-GE/umu: fetched at user opt-in, licenses displayed in consent card (all FOSS). Codecs: inherited posture from base (R10). "Windows" is a Microsoft trademark: nominative use only — "runs many Windows programs", never logos, never "compatible with Windows®" claims; same nominative discipline for app names in compat lists. GRUB/os-prober chainloading is standard practice. No GPL-incompatible static linking in our C++ (Qt/KF6 = LGPL, fine dynamically). NOTICE file maintained by CI dependency scan (WP-00 stub, WP-25 completes).

## 14. Agent operating rules (the contract — copied to CONTRIBUTING-AGENTS.md at WP-00)

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

## 15. Post-1.0 roadmap (v1.x → v2 "Horizon" — recorded so 1.0 agents build nothing toward it prematurely)

**v1.x candidates (order by demand):** Secure Boot shim (R6); TPM auto-unlock LUKS (Windows-BitLocker-feel encryption default); SMB/network places in Files; fingerprint login; browser-profile full import in Migration; per-drive exe trust for removable media; KDE Connect phone integration; Backups app (btrfs snapshots of @home + external drive, Time-Machine-simple); custom store v2 (if fallback shipped); community translations expansion; VirtualBox guest polish.
**v2 "Horizon" (the owner's "high-definition, macOS-feel" brief — the mockup already leans there; v2 completes it):** full custom icon set; motion/materials pass (springy-calm animation language, richer translucency depth); refined HD wallpaper collection; polished sound theme; Overview trackpad gestures; global search elevation (strictly-idle indexer revisits ADR-016); Settings visual v2; hardware partner/OEM preload mode (Calamares OEM phase + first-boot rename); ARM laptop evaluation.

---

## Appendix A — Design tokens (`docs/design/tokens.json`, seeded at WP-00)

```json
{
  "$schema": "./schemas/tokens.schema.json",
  "meta": { "source": "Meridian OS.dc.html mockup", "authoritative_space": "oklch", "version": 1 },
  "font": {
    "ui": ["Schibsted Grotesk", "Inter", "Noto Sans"],
    "mono": ["JetBrains Mono"],
    "size": { "body": 14, "secondary": 13.5, "caption": 12.5, "overline": 11, "title": 20, "hero": 22 },
    "weight": { "regular": 400, "medium": 500, "semibold": 600, "bold": 700 },
    "overline": { "letterSpacing": "0.08em", "transform": "uppercase", "weight": 600 }
  },
  "color": {
    "light": {
      "ink":      { "primary": "#1a1a22", "secondary": "#55555f", "tertiary": "#7a7a86", "hint": "#9a9aa6" },
      "surface":  { "window": "rgba(252,252,254,0.94)", "sidebar": "rgba(245,245,250,0.60)",
                    "card": "rgba(0,0,0,0.035)", "hover": "rgba(0,0,0,0.05)", "hoverStrong": "rgba(0,0,0,0.07)",
                    "hairline": "rgba(0,0,0,0.06)", "chipSoft": "#d6f0f9" },
      "onAccent": "#ffffff"
    },
    "dark": {
      "ink":      { "primary": "#ececf2", "secondary": "#b8b8c4", "tertiary": "#8f8f9c", "hint": "#6f6f7c" },
      "surface":  { "base": "#131318", "window": "rgba(28,28,36,0.94)", "sidebar": "rgba(23,23,31,0.60)",
                    "card": "rgba(255,255,255,0.045)", "hover": "rgba(255,255,255,0.06)", "hoverStrong": "rgba(255,255,255,0.09)",
                    "hairline": "rgba(255,255,255,0.07)", "chipSoft": "#0e3a4a" },
      "onAccent": "#ffffff"
    },
    "accent": {
      "blue":     { "oklch": "oklch(0.62 0.14 220)", "hex": "#0098c0", "hoverHex": "#0079a0", "darkHex": "#2fb3d9" },
      "violet":   { "oklch": "oklch(0.62 0.14 285)", "hex": "#7f78d6", "darkHex": "#9a93ea" },
      "green":    { "oklch": "oklch(0.62 0.14 160)", "hex": "#019f68", "darkHex": "#2dbb84" },
      "red":      { "oklch": "oklch(0.62 0.14 25)",  "hex": "#cd605a", "darkHex": "#e57e77" },
      "graphite": { "oklch": "oklch(0.45 0.02 260)", "hex": "#4f5661", "darkHex": "#8b93a1" },
      "default": "blue"
    },
    "system": { "closeHover": "#e5484d", "closeHoverInk": "#ffffff" },
    "logoGradient": ["#00abd3", "#2a5fb7"],
    "heroGradient": ["#4c6ebd", "#17a9cb"]
  },
  "wallpaper": {
    "softViolet": { "angle": 160, "stops": [["#c3bfe3", 0], ["#6d7ac2", 55], ["#2c488e", 100]] },
    "dusk":       { "angle": 160, "stops": [["#ecc5a7", 0], ["#bd615b", 60], ["#4b346f", 100]] },
    "deepTeal":   { "angle": 160, "stops": [["#90cacd", 0], ["#008192", 55], ["#003f64", 100]] },
    "default": "softViolet"
  },
  "radius": { "window": 14, "panel": 14, "popup": 18, "card": 12, "control": 10, "field": 8, "pill": 999 },
  "elevation": {
    "window": "0 24px 70px rgba(20,15,60,0.35)",
    "popup":  "0 30px 80px rgba(20,15,60,0.40)",
    "bar":    "0 10px 30px rgba(20,15,60,0.30)",
    "card":   "0 1px 4px rgba(0,0,0,0.06)",
    "innerLight": "inset 0 0 0 1px rgba(255,255,255,0.5)"
  },
  "material": { "blur": 30, "blurPopup": 36, "saturate": 1.4 },
  "layout": { "taskbarHeight": 52, "taskbarMargin": 12, "startWidth": 560, "quickWidth": 350,
              "windowControl": 27, "taskIcon": 28, "taskHit": 40, "desktopCell": 86, "sidebarWidth": 185 },
  "motion": { "popup": { "duration": 180, "easing": "ease-out", "travel": 14 },
              "toggle": { "duration": 200 }, "window": { "duration": 175 },
              "reducedMotionHonored": true }
}
```

## Appendix B — Curated catalog seed (structure + the mandatory 24; WP-15 extends to ≥ 40)

Schema per entry: `{ id, name, flatpakRef, section, replaces, blurb, switcherRank, verified }`.
Mandatory seed — **Switcher rail:** LibreOffice (Replaces Microsoft Office), Thunderbird (Replaces Outlook), GIMP (Replaces Photoshop), Inkscape (Replaces Illustrator), VLC (Plays every media file), Spotify, Zoom, Discord, WhatsApp-web-wrapper *only if verified official-quality — else omit, no sketchy wrappers (EDITORIAL.md bar)*, Bitwarden, Signal, Steam (games — the one place we point gamers). **Browsers:** Chrome, Edge, Brave, Vivaldi, Firefox. **Work:** OnlyOffice (Closest to Word/Excel look), Obsidian, Slack, Todoist. **Creative:** Krita (Replaces Photoshop for drawing), Audacity, Kdenlive (Replaces Movie Maker, and then some), Darktable (Replaces Lightroom). **Utilities:** qBittorrent, Flatseal *(Advanced-flagged: hidden unless Advanced mode)*. Every `flatpakRef` verified per WP-15; blurbs ≤ 8 words, voice per 4.5.

## Appendix C — Windows-app compatibility list (schema + seed rows; WP-15 extends to ≥ 50)

Schema: `{ match: {exeNames[], productContains[]}, name, status: green|yellow|red|untested, note, alternativeCatalogId?, evidence: {source, date} }`.
Mandatory seeds — **Red (honesty anchors):** Microsoft Office desktop → M365 web/LibreOffice/OnlyOffice; Adobe Photoshop/CC → GIMP/Krita/Photopea-web; AutoCAD → red, "consider keeping Windows for this" (the honest worst case); iTunes → red, "your iPhone photos still import (best effort)"; anti-cheat multiplayer games → red blanket rule + Steam pointer. **Green targets (validate at WP-15/20 with evidence):** Notepad++, 7-Zip (note: built-in zip already), IrfanView, Paint.NET-class editors (verify), common label/receipt printer utilities *(Sam's category — pick 2 real ones and actually test them)*, older LOB .NET WinForms apps pattern-entry. **Yellow:** QuickBooks Desktop (→ QuickBooks Online), older MS Office 2010/2013 (installs; activation/stability caveats). Verdicts require dated evidence (ADR-009).

## Appendix D — "Familiar" shortcut map (WP-07 ships as default scheme)

| Chord | Action | Notes |
|---|---|---|
| Meta (single press) | Open/close Start | Must not fire on Meta-chords |
| Meta+E | Files | |
| Meta+D | Show desktop (toggle) | |
| Meta+L | Lock | |
| Meta+I | Settings | |
| Meta+P | Display/projection switcher | |
| Meta+V | Clipboard history popup | Klipper, themed |
| Meta+. | Emoji picker | |
| Meta+Arrows | Snap left/right/maximize/restore; quarters via sequences | KWin tiling |
| Meta+Tab | Overview (Task View analog) | |
| Alt+Tab / Alt+Shift+Tab | Window switcher, MRU | Thumbnail switcher themed |
| Alt+F4 | Close window | |
| Ctrl+Shift+Esc | System Monitor | |
| PrtScn | Full screenshot → clipboard + Pictures/Screenshots | Spectacle silent mode |
| Meta+Shift+S | Region snip → clipboard + toast | The Win11 habit |
| Ctrl+C/X/V/Z/Y/A/S/P/F | Universal edit/find/print set | App-standard, audited in ZT-14 |
| Ctrl+Shift+N | New folder (Files/desktop) | |
| F2 / Delete / Shift+Delete | Rename / Trash / permanent (confirm) | |
| F5 | Refresh (Files, browsers) | |
| Meta+Plus/Minus | Magnifier zoom | A11y (WP-24) |
| Meta+1..9 | Launch/focus pinned taskbar app N | Power-user freebie |

"Familiar mode" OFF restores stock Plasma scheme (12's toggle); both schemes ship as named kglobalshortcuts presets.

## Appendix E — Naming dossier process (WP-26)

Five candidates; seed list (owner may replace freely): **Meridian OS** (#1, from the design file), **Harbor OS** (safe arrival metaphor), **Northstar OS**, **Solstice OS**, **Clearline OS**. Per candidate: ①identical/confusable trademark search in computer-software classes (US+EU, documented screenshots/links); ②domains (.com/.org preferred, `get<name>.com` acceptable) + GitHub org + social handles; ③collision scan: DistroWatch names, GitHub >1k-star projects, major SaaS; ④pronunciation/meaning check in en/es/fr/de/pt (no unfortunate readings); ⑤wordmark sketch in brand language (4.4) to prove it sets. Output: one-page-per-name dossier + comparison table + recommendation. Owner picks; rename per WP-26 acceptance. *(This is diligence, not legal advice; a trademark attorney's opinion before major marketing spend is the owner's call and noted as such in the dossier.)*

---

*End of PRD. STATUS.md is the living document from here; this PRD changes only by owner-approved PR touching `docs/` with a version bump in the header.*
