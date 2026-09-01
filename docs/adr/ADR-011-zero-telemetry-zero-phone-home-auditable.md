# ADR-011 — Zero telemetry, zero phone-home, auditable

**Status:** Accepted (settled law — see PRD §0.1 item 2)
**Source:** `docs/PRD.md` §2, verbatim

---

**Decision:** Meridian ships **no** telemetry, crash reporting, analytics, unique identifiers, or "check-in" of any kind. The complete list of automatic outbound connections is: registry update checks (OS + Flatpak), fwupd metadata, NTP, geoip lookup during OOBE timezone detection (one call, no persistence, skippable), and captive-portal detection (NetworkManager default; disableable in Settings → Advanced). CI test `tests/privacy/network_audit.sh` boots an idle system for 10 minutes and fails if any other destination is contacted. KDE's optional user feedback (`kuserfeedback`) is compiled out / force-disabled via KIOSK. A "Report a problem" button in Settings → About assembles a local diagnostic zip **on the user's disk** for them to attach wherever they choose; it uploads nothing itself.
**Why:** Pillar 5 is only a differentiator if it is provable. The CI test makes it provable and keeps it true.
