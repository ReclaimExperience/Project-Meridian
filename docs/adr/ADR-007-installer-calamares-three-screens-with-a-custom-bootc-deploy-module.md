# ADR-007 — Installer: Calamares, three screens, with a custom bootc deploy module

**Status:** Accepted (settled law — see PRD §0.1 item 2)
**Source:** `docs/PRD.md` §2, verbatim

---

**Decision:** The ISO is a **live session** ("try before you install") with a hardware-check panel, launching **Calamares** branded to Meridian and reduced to three user screens (Language/Keyboard → Disk → You). Deployment is performed by a custom Calamares Python job module that runs `bootc install to-filesystem` from the container image embedded on the ISO, then provisions the Flatpak sideload set. Partitioning uses Calamares' mature kpmcore stack including NTFS resize for "Install alongside Windows". Optional LUKS full-disk encryption is a checkbox on the Disk screen (off by default in 1.0; TPM auto-unlock is v1.x, Section 15).
**ISO build:** Universal Blue's live-ISO tooling (`titanoboa`) `[VERIFY]`, falling back to Fedora `livemedia-creator`/lorax with a kickstart. Whichever tool, the output MUST embed the OCI image in containers-storage so installs work fully offline.
**Rejected:** Anaconda (powerful, but its UX cannot be reduced to our three screens without more effort than writing one Calamares module); Readymade (watch it — re-evaluate at WP-17 `[VERIFY]`; adopt only if it demonstrably beats the Calamares path by then).
