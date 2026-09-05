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
| 3 | GTK applications | a GTK theme plus `gtk-application-prefer-dark-theme` | `kde-gtk-config`, which writes `~/.config/gtk-{3,4}.0/` | **Wired and witnessed.** `adwaita-1-demo` ships in the base image and visibly follows light↔dark; asserted in the capture suite by luminance, not by eye. |
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

**Layer 4 being green is necessary, not sufficient** — it proves the preference
is published, not that an application honours it. So the suite runs
`adwaita-1-demo`, which ships in the base image (no download, no network), and
asserts the captured frames actually darken: mean luminance must drop by 25+
between the light and dark passes.

`adwaita-1-demo` is libadwaita, and libadwaita consumes
`org.freedesktop.appearance color-scheme` — the same mechanism Firefox uses. So
this is not scaffolding to be replaced: it is the test Firefox inherits when it
is provisioned via the ISO sideload set.

An earlier claim here — that no GTK application existed in the image at all —
was wrong. It came from checking a hand-written list of candidate names rather
than asking what actually links `libgtk`. The same shape as the `rpm -q breeze`
error (rule R-J): a negative answer to a narrow question read as a general one.

**A correction worth keeping, because it nearly became a build failure.**
`rpm -q breeze` and `rpm -q breeze-gtk` both answer "not installed", and that
was read as the packages being absent. Neither is a package *name* in Fedora 44:
the Qt widget style is `plasma-breeze`, and the GTK theme is
`breeze-gtk-gtk3` / `breeze-gtk-gtk4`. All of them were installed the whole
time. Adding the invented names to `add:` would have failed the build on a
package dnf cannot resolve. They are in `protect:` instead — the intent
(never ship a `widgetStyle` without the style) enforced against a future
de-bloat, without claiming an install that never happened.

A negative `rpm -q` answers "this NAME is not installed", which is not the same
claim as "this THING is missing" (rule R-J).

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

### Open: the Soft Violet ramp does not match the mockup

Measured, not estimated. Nine sample points across the mockup's desktop against
our generated ramp, mean ΔRGB **83**, worst **185** at bottom-right.

Two candidate explanations were implemented and then measured, and **neither
accounts for it**:

- The missing radial glows — now implemented as authored. Worth ~10 RGB at the
  corner where they are strongest, and nothing in the middle.
- sRGB versus perceptual interpolation — the stops are now densified along the
  OKLCh path. Worth **1–3 RGB**. The three Soft Violet stops sit close enough in
  hue (290°, 275°, 265°) that the two curves nearly coincide; the 100+ midpoint
  error that this fix was expected to remove is not present between *these*
  colours. The fix is still correct and stays, but it did not explain anything.

Mean ΔRGB after both: **82**. So the residual is the base ramp itself.

Fitting a plane to the mockup's clean wallpaper area gives:

| | mockup (fitted) | tokens / PRD 4.2 |
|---|---|---|
| light end | `#f2c7ff` | `#c3bfe3` |
| 55% | `#a885da` | `#6d7ac2` |
| dark end | `#5d43b3` | `#2c488e` |
| ramp angle | ~254° (light on the **right**) | 160° (light **top-left**) |
| canvas | 5208×3264, aspect **1.596** (16:10) | SVG authored 3840×2160 (16:9) |

The mockup's ramp is violet throughout and runs light-right to dark-left. Ours
is lavender-to-**navy** and runs light-top-left to dark-bottom-right — close to
perpendicular, and a different hue family. No amount of glow or interpolation
closes that.

Caveats on the fit, stated so it is not over-read: the plane fit includes the
glows, which lift both ends; a three-stop ramp is not exactly planar; and JPEG
plus the aspect-ratio difference add noise. The direction and the hue family are
unambiguous; the exact stop values are indicative.

**This is R-K's case: extraction infidelity, not an authority conflict.** The
tokens were extracted from the mockup and drifted. Awaiting the owner's
reconciliation of the specific stops before anything is built on this ground.

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

## Window corner radius

The mockup's windows are rounded at roughly 14px; Breeze's are squarer.

**KDecoration3 in Plasma 6.7 does support it.** The decoration plugin exports
`KDecoration3::Decoration::setBorderRadius(const BorderRadius &)` and
`BorderRadius(double, double, double, double)` — per-corner radii — and
`libkwin` carries a `cornerRadius` symbol. So this is a capability question
about the Breeze *decoration's* configuration surface, not a hard limit of the
compositor, and it must not be logged as a deviation until that surface has
been tried.

**Tried, and it does not reach.** Breeze's decoration KCM exposes exactly one
control here — a boolean, "Round bottom corners of windows with no borders"
(`roundedCorners`). No numeric radius. Writing `BorderRadius=14` and
`CornerRadius=14` into `kwinrc` under `[org.kde.kdecoration3]` and `[Windows]`
and reconfiguring KWin changed nothing: the rendered corner's inset profile is
identical before and after, `[6, 4, 2, 2, 1, 1, 0, 0 ...]` pixels — an
effective radius of about **6px** against the mockup's 14.

That the keys were accepted into `kwinrc` proves nothing; any key can be
written. The pixels are what was compared (R-I).

**Deviation, logged:** window corner radius is ~6px, not 14px. The engine is
not the limit — `KDecoration3::Decoration::setBorderRadius(BorderRadius)` takes
per-corner values and `KWin::BorderRadius` consumes them — but Breeze's
configuration surface does not expose it. Aurorae remains the escalation if the owner wants the exact 14px — the engine
ships (`org.kde.kwin.aurorae.so`) but `/usr/share/aurorae/themes/` does not
exist, so that route means *authoring* a decoration theme, which sits below
"config" in the WP-05 priority order and is not taken on our own initiative.

## Plasma Style `meridian`

Generated from tokens, like everything else: `surface`, `hairline`, `radius`.
It is where the panel, popup and tooltip **material** lives — the translucency,
the corner radius and the hairline that a colour scheme cannot express, because
a colour scheme has no geometry.

Ships five frames: `widgets/panel-background.svg`, `dialogs/background.svg`,
`widgets/tooltip.svg`, `widgets/background.svg`, `widgets/plasmoidheading.svg`.

**These SVGs are a contract, not pictures.** Plasma's FrameSvg slices each file
by element ID and tiles the pieces at whatever size it needs:

```text
topleft      top       topright
left        center     right
bottomleft  bottom     bottomright
```

A missing id is not an error anyone sees — Plasma falls back to the *default*
theme's element for that slice, so the frame still renders, as our corners with
Breeze's edges. Present, correct-looking, half someone else's.
`tests/lint/plasma_style.py` asserts every id, and is verified to fail when one
is renamed.

Two construction notes worth keeping:

- Each slice is drawn as its **own geometry**, not as a clipped copy of the
  whole rounded rect. Qt reports an element's bounds ignoring clip paths, so a
  clipped construction measures as the full rect and every margin lands wrong.
- `hint-*-margin` rects are separate from the frame art on purpose: content
  inset comes from those, so an 18px corner radius does not force 18px padding.

Translucency comes from the token alpha (`surface.window` is
`rgba(252,252,254,0.94)`), so the material is in the style. The **blur** behind
it is a KWin effect and belongs to WP-07/08/09 (PRD §5.12 deviation 9) — a
translucent panel over an unblurred background is the expected intermediate
state, not a defect.

## Icon theme `meridian`

PRD 4.4: Breeze as the base set with an override layer for the folder set
(tinted to accent), the core app icons and tray glyphs. `index.theme` declares
`Inherits=breeze,hicolor`, which is the whole design — we override what the eye
lands on and let Breeze answer for the thousands of icons we have not drawn.

The tile language is read from the mockup **source**, not approximated from a
render: 135° two-stop linear gradients, a rounded square at 13/46 of the tile,
a white glyph. The gradients are the mockup's own values.

**An icon theme only overrides an icon whose NAME an application asks for.**
Shipping `meridian-files.svg` overrides nothing: no desktop entry references
it, so the theme would install, apply, and change not one pixel — present,
applied, inert. So each tile is emitted under the names the shipped apps
actually use (`org.kde.dolphin`, `org.kde.gwenview`, `org.kde.haruna`,
`org.kde.kwrite`, `systemsettings`, `computer`, `user-trash`, `firefox`,
`libreoffice-startcenter`), and the accent folder under the set Dolphin's
sidebar and the desktop show (`folder`, `user-home`, `folder-documents`,
`folder-downloads`, `folder-pictures`, `folder-music`, `folder-videos`).

### Open, and deliberately not guessed

- **Which twelve?** PRD 4.4 says "the 12 core app icons". The mockup defines
  nine apps plus Computer and Trash — eleven tiles. Mail and Software have no
  shipped application to point at yet (our store is WP-13), and PRD §3.2's
  visible set includes apps the mockup never drew (Ark, Okular, KCalc,
  Spectacle, plasma-systemmonitor, print-manager). The mapping is an owner
  decision, not an extraction.
- **Tray glyphs** (1.6px stroke outline style per PRD 4.4) are not yet drawn.
- **The glyph is text.** The mockup's tiles use letters, so ours do, which
  makes the icon depend on the UI font resolving at icon-render time. That is a
  real dependency and is why the capture photographs the launcher rather than
  trusting the files to exist.
