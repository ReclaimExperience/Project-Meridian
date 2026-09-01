# ADR-008 — Updates are silent, staged, atomic, and self-healing

**Status:** Accepted (settled law — see PRD §0.1 item 2)
**Source:** `docs/PRD.md` §2, verbatim

---

**Decision:** OS updates: a systemd timer checks daily, downloads and **stages** the new image in the background (`bootc upgrade`), and finalizes on the next natural reboot/shutdown — no forced restarts, no "Updating… 30%" hostage screens, ever. **greenboot** health checks (graphical target reached, NetworkManager alive, session started) run on each boot; a boot that fails health checks automatically reboots into the previous deployment and flags the failure to Settings → Updates. App updates: `flatpak update --noninteractive` timer, twice daily. Firmware: fwupd refreshes metadata and *offers* firmware updates in Settings → Updates (never auto-applied). Settings → Updates is a read-mostly status page: "You're up to date", last check, history, one advanced "Apply at shutdown now" action.
**Why:** Pillar 1 + the single most-hated Windows behavior eliminated as a headline feature.
**Consequences:** Update servers are the public registry (zero infra); release discipline lives in CI gates (7.5), because every push to `stable` reaches users' next boot.
