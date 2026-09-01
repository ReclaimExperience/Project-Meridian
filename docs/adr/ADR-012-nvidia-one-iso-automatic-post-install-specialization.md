# ADR-012 — Nvidia: one ISO, automatic post-install specialization

**Status:** Accepted (settled law — see PRD §0.1 item 2)
**Source:** `docs/PRD.md` §2, verbatim

---

**Decision:** We publish a single universal ISO. The installer detects an Nvidia dGPU (PCI vendor 0x10de, Turing or newer for the proprietary/open stack; older cards stay on nouveau with a Settings notice). On Nvidia machines, the installed system boots first on nouveau/simpledrm, and a one-shot service (`meridian-gpu-specialize.service`) queues a rebase to the `-nvidia` image variant; on first network availability it stages the rebase and the Updates page shows "Graphics driver ready — takes effect after restart". Fully offline Nvidia machines keep working on the fallback stack until network exists.
**Why:** One download (no "which ISO?" support burden) beats shipping both driver stacks on one ISO (+1 GiB) or maintaining two ISOs (user confusion).
**Consequences:** Nvidia + permanently-offline is degraded (2D/basic 3D) — acceptable edge; documented.
