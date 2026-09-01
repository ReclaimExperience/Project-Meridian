# ADR-009 — Windows App Support = umu + Proton-GE, optional, expectation-managed

**Status:** Accepted (settled law — see PRD §0.1 item 2)
**Source:** `docs/PRD.md` §2, verbatim

---

**Decision:** Windows-program compatibility ships as an optional component ("Windows App Support"), not in the base image. Flow: double-clicking any `.exe` (MIME `application/vnd.microsoft.portable-executable` and `application/x-ms-dos-executable`) opens our `meridian-winapps` helper, which on first use offers a one-click install of the support layer (**umu-launcher** + current **Proton-GE**, downloaded to `/var/lib/meridian/winapps/runtime`) `[VERIFY umu-launcher is maintained; fallback: Bottles flatpak preconfigured headlessly]`. Each Windows app gets its own prefix under `~/.local/share/meridian/winapps/<slug>/`; installers are detected and resulting Start-menu shortcuts surface as real desktop entries; uninstall appears in Settings → Apps. **Before** first run of a recognized app, the helper checks the bundled compatibility list (Appendix C) and speaks plainly: green "Works well", yellow "Mostly works — known issues: …", red "Doesn't work — here's the best alternative" (e.g. Microsoft Office → M365 web / LibreOffice; AutoCAD → red, no sugarcoating). Unknown apps get an honest "Untested — trying is safe, expect rough edges."
**Why:** umu gives us Valve-grade Wine (Proton) outside Steam with pressure-vessel isolation and no game-launcher baggage; the honesty layer is pillar 7 and protects the brand from the "Linux lied to me" churn loop.
**Consequences:** Games are explicitly not the target (Steam exists in the store for that); anti-cheat titles are out of scope, and the compat list says so.
