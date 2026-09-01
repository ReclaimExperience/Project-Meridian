# ADR-013 — Targets: x86_64 (UEFI first), aarch64 for development only

**Status:** Accepted (settled law — see PRD §0.1 item 2)
**Source:** `docs/PRD.md` §2, verbatim

---

**Decision:** Ship x86_64 at Fedora's own baseline (in practice any 64-bit CPU from ~2014 onward; we add no extra micro-architecture requirement of our own). UEFI is the first-class boot path; legacy BIOS boot MUST work through the same installer (bootc installs GRUB2 for both) but gets best-effort QA. Minimums: 4 GB RAM, 40 GB disk, dual-core 2014-era CPU; recommended 8 GB/SSD. aarch64 images are built in CI and used for the Apple-Silicon local dev loop (7.2); they are not a supported end-user target in 1.0. Secure Boot: 1.0 requires it disabled — the ISO boot failure mode is detected in docs/first-boot guidance with per-vendor BIOS instructions (10.4); pursuing a signed shim is v1.x (Section 15).
