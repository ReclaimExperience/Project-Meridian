# ADR-004 — Applications are Flatpaks from Flathub. Full stop.

**Status:** Accepted (settled law — see PRD §0.1 item 2)
**Source:** `docs/PRD.md` §2, verbatim

---

**Decision:** All GUI applications — preinstalled and user-installed — are Flatpaks from Flathub. The image contains no user-facing package manager and Discover's PackageKit backend is not shipped. Preinstalled Flatpaks are provisioned system-wide at install time from an on-ISO sideload repo (offline-capable), then updated from Flathub. The Software store (WP-13) installs to the system installation via polkit rules that allow active local users to install/remove apps without a password (Windows parity: installing an app is not an admin ceremony; *system* changes still are).
**Why:** One app format = one sandbox story, one update mechanism, one store backend; app crashes can't break the OS; app updates are decoupled from OS updates.
**Consequences:** The rare tool with no Flatpak (e.g. some drivers' vendor utilities) is simply not offered. CLI developer tools are out of persona scope (Advanced users get `toolbox`/`distrobox` which ship hidden in the image for Jordan, undocumented in UI).
