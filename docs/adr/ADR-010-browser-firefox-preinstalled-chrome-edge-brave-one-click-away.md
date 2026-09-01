# ADR-010 — Browser: Firefox preinstalled; Chrome/Edge/Brave one click away

**Status:** Accepted (settled law — see PRD §0.1 item 2)
**Source:** `docs/PRD.md` §2, verbatim

---

**Decision:** Firefox (Flathub, unmodified upstream branding) is the preinstalled default browser and lives in the ISO sideload set so offline installs have a working browser. The Welcome app's Browser page and the store's "Popular with switchers" rail offer Chrome, Edge, Brave, and Vivaldi as one-click installs; choosing one there sets it as default browser and pins it to the taskbar in place of Firefox. No search-deal modifications, no bundled extensions, no changed defaults beyond `browser.aboutwelcome` trimming via distribution policies.json (privacy-neutral).
**Why:** Firefox is the only major browser we may legally redistribute on media; Chrome's EULA requires user-initiated download. SaaS-dependent users (Sam) get Chrome in one click during onboarding.
