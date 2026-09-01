# ADR-015 — Security defaults: invisible, Windows-familiar where visible

**Status:** Accepted (settled law — see PRD §0.1 item 2)
**Source:** `docs/PRD.md` §2, verbatim

---

**Decision:** SELinux enforcing (inherited, never surfaced to the user); firewalld on; no non-loopback listening sockets after boot except the explicit printing/discovery allowlist — mDNS on UDP 5353 (firewalld `mdns` service) with CUPS and `ipp-usb` bound to loopback only — enforced by the CI allowlist in `tests/security/ports.sh` (CI-verified); polkit prompts styled as our "UAC" (admin password for system changes; app installs from the store exempted per ADR-004); no SSH daemon; automatic security updates via ADR-008; AutoPlay for removable media NEVER executes content — it opens a folder (explicitly safer than historical Windows autorun, and we say so in marketing); Flatpak portal-based permissions are the app-permission model surfaced in Settings → Apps.
