# ADR-014 — Public monorepo, permissive where ours, GHCR distribution, signed images

**Status:** Accepted (settled law — see PRD §0.1 item 2)
**Source:** `docs/PRD.md` §2, verbatim

---

**Decision:** Development happens in a public GitHub monorepo (`<org>/meridian`) from day 1. Our original code: MIT. Theme assets derived from Breeze: LGPL-2.1+ (as upstream). Config and docs: MIT/CC-BY-SA as conventional. OS images and ISOs are published to GHCR + GitHub Releases; images are cosign-signed in CI and clients enforce the signature via `/etc/containers/policy.json` (WP-04). Channels: `:stable` (default), `:testing` (weekly), version tags for every release.
