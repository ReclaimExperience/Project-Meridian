# ADR-005 — Custom shell pieces are plasmoids; system plumbing is reused, never rewritten

**Status:** Accepted (settled law — see PRD §0.1 item 2)
**Source:** `docs/PRD.md` §2, verbatim

---

**Decision:** The Start menu, Quick Settings, and pager are our QML plasmoids, but they MUST consume existing Plasma/KDE frameworks for all system state: `plasma-nm` QML plugin for networks, `plasma-pa`/PipeWire models for audio, PowerDevil D-Bus for brightness/battery, `Bluez`/Bluedevil for BT, the `org.kde.plasma.private.notifications` model for notifications, KRunner (Milou) for search. Writing a new NetworkManager client, mixer, or notification daemon is forbidden.
**Fallback:** If the custom Quick Settings plasmoid misses the M2 quality gate (7.5), ship the stock system tray + applets themed to Meridian colors, and move the custom plasmoid to v1.1. The Start menu has no fallback — it is core identity and must land.
