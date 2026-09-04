# Theming (WP-05)

How the look is produced, and — more usefully — where it stops.

Everything visual is generated from `docs/design/tokens.json` by
`shell/theme/generate-theme.py` (`just assets`). Nothing under
`os/rootfs/usr/share/color-schemes`, `.../wallpapers` or the fontconfig chain is
edited by hand; a lint fails the build if a generated file drifts from its
source.

## The dark-theme contract

**Dark is not one setting. It is four layers, and they must flip together.**

A desktop where three of the four follow is worse than one where none do,
because the odd surface reads as broken rather than as light. The layer that
decides whether dark theme is believable is the one furthest from what we set:
the browser, where most of a person's day happens.

| # | Layer | Follows | Set by | Status |
|---|---|---|---|---|
| 1 | Plasma chrome — panel, titlebars, dialogs, system UI | the Plasma colour scheme | `plasma-apply-colorscheme MeridianLight/Dark` | **Wired and proven.** Titlebars and panel flip in the capture pairs. |
| 2 | KDE editor views — Kate, KWrite, Konsole | their own KSyntaxHighlighting colour theme, *not* the Plasma scheme | not yet set | **NOT wired.** Observed: a white editor on a dark desktop. |
| 3 | GTK applications | a GTK theme plus `gtk-application-prefer-dark-theme` | `kde-gtk-config`, which writes `~/.config/gtk-{3,4}.0/` | **Partly wired, unproven.** `prefer-dark-theme=true` is written; `breeze-gtk` is **not installed**, and no GTK app exists in the image to show the result. |
| 4 | Flatpaks and portal-aware apps | the XDG portal preference `org.freedesktop.appearance color-scheme` | `xdg-desktop-portal-kde`, derived from the active Plasma scheme | **Wired and asserted** — the capture suite reads it over D-Bus each pass and fails if it disagrees with the theme (1 = dark, 2 = light). |

Layer 4 is asserted *before any GTK app exists to display it*, deliberately. A
preference that quietly stops flipping is invisible until a browser is installed
and looks wrong, which is the shape of failure this project keeps finding late
(rule R-I). Asserting it now means the plumbing is known-good on the day
Firefox arrives rather than debugged then.

### Why the browser is the deciding frame, and why it is not in this image

Firefox is a **Flatpak** by ADR-004/ADR-010 and is explicitly removed from the
RPM set (`os/packages.yml`), so it cannot appear in a capture of the base image.
It reaches a machine through the ISO sideload set. Until then, layer 3 has no
witness in the image at all: there is currently **no GTK application of any
kind** installed, so "GTK apps follow the theme" is a claim with nothing to
demonstrate it.

Two consequences, both owed:

- `breeze-gtk` should be added to `os/packages.yml`, or layer 3 has a preference
  set and no theme to apply.
- A GTK frame belongs in the compare sheet as soon as any GTK app is present.
  Layer 4 being green is necessary, not sufficient — it proves the preference is
  published, not that an application honours it.

## Wallpaper

Three gradients are generated as SVG (never raster — WP-05 Forbidden):
`softViolet`, `dusk`, `deepTeal`. The capture suite sets one with
`plasma-apply-wallpaperimage` — Plasma's own tool, so it exercises the path a
person takes — and then asserts the gradient's **stop colours are on screen**.

That assertion exists because all three shipped for the length of WP-05 without
ever being rendered: nothing set a wallpaper, so every desktop frame showed the
base image's default while being reviewed as ours. Present, correct, and inert.

**Undecided:** which gradient pairs with which theme. In KDE the wallpaper is a
desktop setting independent of the colour scheme, so the suite uses one for both
themes rather than inventing a pairing the owner has not made.

## Fonts

`Schibsted Grotesk` (UI) and `JetBrains Mono` (monospace), bound **strongly** in
the fontconfig chain. `alias`/`prefer` is a weak binding and lost to Fedora's
own strong binding, so the chain was configured and inert for two commits. The
capture suite reads `fc-match` inside the running session and prints the result
onto the compare sheet, so a silent fallback cannot be approved by inference.

## Scope boundary

Desktop icons are **WP-07**, not WP-05. They come from the Folder View
containment in the look-and-feel `layout.js`. Zero icons on a WP-05 desktop
frame is correct; judge this work package on the substrate, not on what later
packages place upon it. The same boundary applies to the panel's gestalt, and to
window translucency and blur, which live in WP-07/08/09 (PRD §5.12 deviation 9).
