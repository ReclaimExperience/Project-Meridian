# Cross-WP interface contracts

Copied verbatim from `docs/PRD.md` section 8.0 at WP-00, per that section's own
instruction. **The PRD is authoritative**; if this file ever disagrees with it,
the PRD wins and this copy is the bug.

Why these exist: a consumer WP must be able to start before its provider WP has
landed. Both sides build against the fixtures in `tests/fixtures/contracts/`, so
"WP-14 page 4 is written against WP-20's D-Bus name" is a testable statement
rather than a hope.

Adding or changing a contract is a PRD change (owner-approved), not an agent
change. If your WP needs a contract that is not here, escalate per PRD 14.6.

---

## 8.0 Cross-WP interface contracts (authoritative; WP-00 copies to `docs/contracts/interfaces.md`; consumers and providers both test against the fixtures in `tests/fixtures/contracts/`)

- **`org.meridian.shell.Pins` (D-Bus, session; provider WP-08 — and it drives BOTH pin surfaces, writing the panel launcher list in WP-07's containment config as well as the Start grid):** `ListPins() → as` (desktop-file ids, start-grid order), `Pin(s id)`, `Unpin(s id)`, `ReplacePin(s oldId, s newId)` (used by Welcome's browser swap — replaces in Start grid AND taskbar launchers), signal `PinsChanged(as)`.
- **`org.meridian.Software` (D-Bus, session; provider WP-13):** `OpenApp(s flatpakRef)`, `Install(s flatpakRef) → o` (job), `Uninstall(s flatpakRef) → o`, job objects emit `Progress(u)`/`Done(b, s)`; Discover-fallback mode MUST still provide this name with `OpenApp`/`Uninstall` minimum.
- **`org.meridian.WinApps` (D-Bus, session; provider WP-20; consumers WP-12 Apps page + WP-14 page 4 build against the fixture NOW):** `IsRuntimeInstalled() → b`, `InstallRuntime() → o` (job as above), `ListApps() → a(sss)` (slug, name, iconPath), `Uninstall(s slug) → o`, signal `AppsChanged()`. Until WP-20 lands, WP-14 ships page 4 feature-flag-hidden; **WP-20's deliverables include flipping the flag and extending ZT-17** with the enable-support path.
- **Update status file (provider WP-04; consumer WP-12):** `/run/meridian/update-status.json` — `{ "state": "up-to-date|staged|rolled-back|error", "booted": {image, version, date}, "staged": {...}|null, "rollback": {happened: bool, date}|null, "lastCheck": iso8601, "flatpakHistory": [...], "firmwareOffers": [...] }`.
- **`/etc/meridian/advanced.conf` (provider WP-12; consumers WP-10/08):** ini, keys `show_system_files`, `enable_terminal`, `developer_mode`, `captive_portal` (bool each).
- **`branding.json`, `tokens.json`, `catalog.json`, `compat.json`:** schemas in `catalog/schemas/` are the contract; providers WP-00/15.

**Template fields:** Phase · Depends (hard order) · Parallel-safe with · Risk · Size (S ≈ 1 agent session, M ≈ 2–4, L ≈ 5–8) · Governing ADRs · Objective · Deliverables (exact paths) · Steps · Acceptance (commands/checks that MUST pass) · Forbidden · Escalate if.
Execution sequencing and parallelization map: 8.7. Every WP ends by updating STATUS.md (6.4) and, where it shipped UX, adding/updating its Zero-Terminal story tests.
