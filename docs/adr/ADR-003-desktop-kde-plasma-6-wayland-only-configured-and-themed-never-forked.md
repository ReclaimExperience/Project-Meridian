# ADR-003 — Desktop: KDE Plasma 6, Wayland-only, configured and themed — never forked

**Status:** Accepted (settled law — see PRD §0.1 item 2)
**Source:** `docs/PRD.md` §2, verbatim

---

**Decision:** The desktop is Plasma 6 on Wayland (Xwayland present for app compat; no X11 session installed). We achieve the Meridian look and behavior exclusively through: (a) a custom Plasma **Look-and-Feel + Plasma Style + color schemes + window decoration config**, (b) **three custom plasmoids** (Start menu, Quick Settings, workspace pager) written in QML against public Plasma APIs, (c) configuration defaults and **KDE KIOSK immutability locks**, (d) at most small, upstreamable patches carried in `os/patches/` with written justification. We MUST NOT fork Plasma, KWin, or Dolphin.
**Why:** Plasma is architecturally Windows-shaped (panel/taskbar/tray), Wayland-first with best-in-class fractional scaling (the v2 "high-definition, macOS-feel" path), themable to near-pixel fidelity, and battle-tested as a consumer product by Valve. Forking converts a 4-agent theming job into a permanent 40-agent maintenance job.
**Consequences:** ~95% mockup fidelity, not 100%; Section 5.12 lists accepted deviations. Plasma version bumps arrive with Fedora rebases and get a regression WP each cycle.
