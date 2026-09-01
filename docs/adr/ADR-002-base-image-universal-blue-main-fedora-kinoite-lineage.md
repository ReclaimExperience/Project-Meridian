# ADR-002 — Base image: Universal Blue main (Fedora Kinoite lineage)

**Status:** Accepted (settled law — see PRD §0.1 item 2)
**Source:** `docs/PRD.md` §2, verbatim

---

**Decision:** `os/Containerfile` starts `FROM` the Universal Blue Plasma base image — `ghcr.io/ublue-os/kinoite-main:<current-fedora>` `[VERIFY]` — which is Fedora Kinoite plus the full out-of-tree driver and codec stack (full ffmpeg, Intel/AMD media drivers, Broadcom Wi-Fi, controller drivers, fwupd enabled). An `-nvidia` variant of our image is additionally built `FROM ghcr.io/ublue-os/kinoite-nvidia:<current-fedora>` `[VERIFY]` (or by layering ublue's Nvidia driver packages if the combined image is the current ublue pattern — adopt whatever mechanism ublue currently uses for Nvidia).
**Verification (WP-01):** `skopeo inspect --raw docker://ghcr.io/ublue-os/kinoite-main:42` (adjust release number to current Fedora stable) must succeed, show a recent build date (< 30 days), and its manifest list MUST include both `amd64` and `arm64`. Inspect labels/README for the currently-recommended tag scheme. **If the base lacks arm64** (historically common for ublue main images), adopt the pre-authorized split-base without escalation: ublue for x86_64 (user-facing), Fedora Kinoite base + the hardware-enablement layer for the aarch64 dev-loop image — one Containerfile, ARG-switched base, hardware-enablement layer applied only where needed; note it in STATUS.md.
**Fallback:** If ublue has renamed or stopped publishing these images, base on Fedora's own `quay.io/fedora/fedora-kinoite:<release>` (or `quay.io/fedora-ostree-desktops/kinoite`) `[VERIFY]` and create `os/layers/hardware-enablement.inc` replicating the driver/codec additions (RPM Fusion multimedia swap of ffmpeg, `libva` drivers, `broadcom-wl` akmod, Nvidia akmods from ublue's akmods repo). This fallback is ~2 extra agent-sessions of work; prefer the ublue base.
**Why:** Ten years of community driver debugging inherited in one `FROM` line; the single highest-leverage decision for pillar 6.
**Consequences:** We track Fedora's release cadence (rebase 1–2×/year, see 7.6); we owe ublue upstream courtesy (credit, bug reports, no hotlink abuse of their CI).
