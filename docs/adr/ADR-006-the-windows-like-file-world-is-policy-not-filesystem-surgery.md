# ADR-006 — The Windows-like file world is policy, not filesystem surgery

**Status:** Accepted (settled law — see PRD §0.1 item 2)
**Source:** `docs/PRD.md` §2, verbatim

---

**Decision:** Users see exactly: `Home` (containing `Desktop`, `Documents`, `Downloads`, `Music`, `Pictures`, `Videos`), `Trash`, and mounted removable media. This is enforced by configuration: a shipped `user-places.xbel` (sidebar), Dolphin defaults (breadcrumb-only location bar, no editable URL, hidden-files off), hidden `konsole`/"Open Terminal" actions via KIOSK restrictions, GTK bookmarks for portal dialogs, and desktop icons. The real filesystem is untouched underneath — no bind-mount games, no renamed FHS directories, no kernel tricks. **Full filesystem + terminal access is an Advanced mode**: Settings → Advanced (polkit-authenticated, admin password) toggles "Show system files" and "Enable Terminal", which flip the same configuration the other way.
**Why:** Config-level abstraction is robust across updates, invisible to apps (paths stay standard so nothing breaks), reversible, and honest. Filesystem surgery breaks Flatpak portals, support articles, and future us.
**Consequences:** A determined user can still type `/` in a file dialog path field where portals allow it. That is acceptable: we are designing away *accidental* complexity, not building a prison.
