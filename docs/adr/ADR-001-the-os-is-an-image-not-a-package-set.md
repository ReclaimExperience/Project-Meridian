# ADR-001 — The OS is an image, not a package set

**Status:** Accepted (settled law — see PRD §0.1 item 2)
**Source:** `docs/PRD.md` §2, verbatim

---

**Decision:** Meridian OS is an immutable, image-based ("atomic") system built on **Fedora bootc** technology. The entire OS filesystem is defined by one OCI container build (`os/Containerfile`), versioned in Git, built in CI, and distributed through a container registry. Clients update by pulling the new image and rebooting into it; the previous deployment is retained and bootable.
**Why:** (a) It makes "it never breaks" structural: updates are atomic, rollback is built-in, users cannot wedge the OS because the OS is read-only. (b) It is the perfect substrate for agent-driven development: every change is a reviewable diff to a Containerfile or an overlaid file, reproducibly built and boot-tested in CI. (c) Distribution infrastructure is a free public registry, not custom mirrors. (d) The pattern is production-proven at consumer scale by SteamOS (image-based) and the Universal Blue family (Bazzite/Bluefin/Aurora, Fedora bootc-based).
**Rejected:** Debian/Ubuntu mutable base (older kernels, user-breakable, we'd run apt infra); Arch (rolling breakage vs. pillar 1); NixOS (declarative but its failure modes and ecosystem violate pillar 2 for our persona); building from scratch (absurd).
**Consequences:** No user-facing package manager exists (see ADR-004 for apps). `/usr` is read-only; machine-local state lives in `/etc` (3-way merged on update) and `/var`. Anything we configure must be baked as image defaults under `/usr` (e.g. `/usr/etc`, `/usr/share`) rather than post-install scripts.
