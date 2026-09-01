# ADR-016 — Search is instant and local: apps, settings, places, recent files — no indexer

**Status:** Accepted (settled law — see PRD §0.1 item 2)
**Source:** `docs/PRD.md` §2, verbatim

---

**Decision:** Baloo (KDE's file content indexer) is disabled and masked. Start-menu search covers: installed apps, settings pages, sidebar places, recently used documents (KActivities), and a literal filename walk when the user presses Enter on "Search files for …" (Dolphin's non-indexed search). No background content indexing exists in 1.0.
**Why:** Baloo is historically the #1 "why is my disk/CPU busy" complaint and violates pillar 4's calm-machine promise; our personas search for apps and recent things, not full-text.
**Consequences:** No content search inside files from the Start menu (Windows parity is honestly mixed here anyway). Revisit for v2 with a strictly-idle indexer.
