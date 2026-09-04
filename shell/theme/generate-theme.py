#!/usr/bin/env python3
"""Generate the theme's token-derived files from docs/design/tokens.json.

Colour schemes (PRD §4.2), kdeglobals defaults and the fontconfig family chain
(§4.1) — everything whose values come from tokens. ADR-003.

The schemes are GENERATED, never hand-edited. tokens.json is the contract — PRD
§4 calls it "the human contract" with Appendix A machine-readable — and a
hand-maintained copy of a palette diverges from it silently, one hex at a time,
until the mockup and the product are different products.

`tests/lint/theme_generated.py` regenerates and diffs, so a stale committed file
fails CI rather than shipping.

## Two things about the translation that are not obvious

**Alpha is composited away.** Tokens describe surfaces as `rgba(...)` because the
mockup layers them over a blurred background. KDE colour schemes are opaque RGB
triples: the translucency in §4.3 is produced by the Plasma Style and the blur
effect, not here. So each `rgba` is flattened over the background it actually sits
on — white for light, `surface.base` for dark — which is what the eye sees when
the blur resolves.

**oklch is authoritative, hex is the fallback.** `meta.authoritative_space` is
oklch, and the accents carry both. We emit the hex because that is what KDE
parses; the oklch is what a designer edits. If they ever disagree, oklch wins and
the hex is the stale one.
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
TOKENS = ROOT / "docs" / "design" / "tokens.json"
# The product name comes from branding.json, never a literal. A rebrand is meant
# to be one file (WP-26), and a hardcoded product name in a generated asset is
# the kind that survives a rename because nobody thinks to grep the theme.
BRANDING = ROOT / "os" / "rootfs" / "usr" / "share" / "meridian" / "branding.json"
# Generated straight into the image's rootfs, which is the only tree the
# Containerfile copies (`COPY rootfs/ /`). The alternative — generate under
# shell/theme/ and copy at build time — would put two copies of the same artifact
# in the repo and give them a chance to disagree. The GENERATOR lives in
# shell/theme/ as PRD 6.1 intends; its output lives where KDE will read it.
ROOTFS = ROOT / "os" / "rootfs"
OUT = ROOTFS / "usr" / "share" / "color-schemes"

RGBA = re.compile(
    r"rgba?\(\s*([\d.]+)\s*,\s*([\d.]+)\s*,\s*([\d.]+)\s*(?:,\s*([\d.]+)\s*)?\)"
)


def parse(value: str) -> tuple[float, float, float, float]:
    """#rrggbb or rgba(r,g,b,a) -> (r, g, b, alpha)."""
    value = value.strip()
    if value.startswith("#"):
        v = value.lstrip("#")
        return (int(v[0:2], 16), int(v[2:4], 16), int(v[4:6], 16), 1.0)
    match = RGBA.match(value)
    if not match:
        raise ValueError(f"cannot parse colour {value!r}")
    r, g, b, a = match.groups()
    return (float(r), float(g), float(b), float(a) if a is not None else 1.0)


def flatten(value: str, over: tuple[float, float, float]) -> str:
    """Composite a possibly-translucent colour over an opaque background.

    KDE colour schemes have no alpha channel. Dropping it instead of compositing
    would render every translucent surface at full strength — a light theme's
    3.5%-black card becoming solid black — so the alpha is resolved against the
    surface it actually sits on.
    """
    r, g, b, a = parse(value)
    out = tuple(round(c * a + base * (1 - a)) for c, base in zip((r, g, b), over))
    return ",".join(str(max(0, min(255, c))) for c in out)


def scheme(tokens: dict, theme: str, brand: str) -> str:
    colour = tokens["color"]
    side = colour[theme]
    ink = side["ink"]
    surface = side["surface"]
    accent_name = colour["accent"]["default"]
    accent = colour["accent"][accent_name]
    accent_hex = accent["darkHex"] if theme == "dark" else accent["hex"]

    # What translucent surfaces resolve against.
    base = parse(surface["base"])[:3] if "base" in surface else (255.0, 255.0, 255.0)

    def f(value: str) -> str:
        return flatten(value, base)

    window = f(surface["window"])
    view = f(surface["base"]) if "base" in surface else "255,255,255"
    card = f(surface["card"])
    hover = f(surface["hover"])
    hairline = f(surface["hairline"])
    # ink.secondary has no KDE role: schemes carry Normal/Inactive/Active, and
    # inactive text is tertiary. Secondary is a QML-level token (WP-07 onward).
    primary, tertiary, hint = f(ink["primary"]), f(ink["tertiary"]), f(ink["hint"])
    on_accent = f(side["onAccent"])
    accent_rgb = f(accent_hex)
    close_hover = f(colour["system"]["closeHover"])
    name = f"{brand}{theme.capitalize()}"

    def block(title: str, background: str, foreground: str) -> str:
        return "\n".join(
            [
                f"[Colors:{title}]",
                f"BackgroundNormal={background}",
                f"BackgroundAlternate={card}",
                f"ForegroundNormal={foreground}",
                f"ForegroundInactive={tertiary}",
                f"ForegroundActive={accent_rgb}",
                f"ForegroundLink={accent_rgb}",
                f"ForegroundVisited={accent_rgb}",
                f"ForegroundNegative={close_hover}",
                f"ForegroundNeutral={tertiary}",
                f"ForegroundPositive={f(colour['accent']['green']['darkHex' if theme == 'dark' else 'hex'])}",
                f"DecorationFocus={accent_rgb}",
                f"DecorationHover={accent_rgb}",
                "",
            ]
        )

    return "\n".join(
        [
            "# GENERATED FROM docs/design/tokens.json — DO NOT EDIT.",
            "# Regenerate with `just assets`; tests/lint/theme_generated.py fails on drift.",
            f"# Theme: {theme}. Accent: {accent_name} ({accent_hex}).",
            "# Translucency lives in the Plasma Style and the blur effect (PRD 4.3);",
            "# these values are the composited result, because KDE schemes are opaque.",
            "",
            "[General]",
            f"ColorScheme={name}",
            f"Name={name}",
            "shadeSortColumn=true",
            "",
            block("Window", window, primary),
            block("View", view, primary),
            block("Button", card, primary),
            block("Selection", accent_rgb, on_accent),
            block("Tooltip", window, primary),
            block("Complementary", view, primary),
            block("Header", window, primary),
            "[WM]",
            f"activeBackground={window}",
            f"activeForeground={primary}",
            f"inactiveBackground={window}",
            f"inactiveForeground={hint}",
            f"activeBlend={accent_rgb}",
            f"inactiveBlend={hairline}",
            "",
            "[ColorEffects:Inactive]",
            "ChangeSelectionColor=true",
            "Color=112,111,110",
            "ColorAmount=0.025",
            "ColorEffect=2",
            "ContrastAmount=0.1",
            "ContrastEffect=2",
            "Enable=false",
            "IntensityAmount=0",
            "IntensityEffect=0",
            "",
            "[ColorEffects:Disabled]",
            f"Color={hover}",
            "ColorAmount=0",
            "ColorEffect=0",
            "ContrastAmount=0.65",
            "ContrastEffect=1",
            "IntensityAmount=0.1",
            "IntensityEffect=2",
            "",
        ]
    )


def kdeglobals(tokens: dict, brand: str) -> str:
    """Session defaults that come from tokens (PRD §4.1, §4.6).

    The font stack is the token list verbatim, so fontconfig and Qt agree on the
    order. `single-click = false` is a switcher decision, not a taste one: double
    click is what Windows taught these users, and PRD §4.6 fixes it.
    """
    font = tokens["font"]
    ui = font["ui"][0]
    mono = font["mono"][0]
    body = font["size"]["body"]

    # KDE font entries are QFont::toString(). The TEN-field form is Qt's legacy
    # serialisation, and its weight field is the old 0..99 scale — NOT the CSS
    # 100..900 scale that QFont::Weight uses in Qt6. Writing 400 there does not
    # mean Normal; it is far past 99 and clamps to the heaviest weight
    # available.
    #
    # It shipped that way and rendered the entire UI in Schibsted Grotesk Black.
    # Proven in the VM by writing both values and comparing frames: 400 -> black,
    # 50 -> normal. kde-gtk-config had been reporting it all along, translating
    # the parsed value into `gtk-font-name=Schibsted Grotesk, Black 14`.
    QT5_WEIGHT = {400: 50, 500: 57, 600: 63, 700: 75}

    def entry(family: str, size: float, weight: int = 400) -> str:
        legacy = QT5_WEIGHT[weight]
        return f"{family},{size:g},-1,5,{legacy},0,0,0,0,0"

    return "\n".join(
        [
            "# GENERATED FROM docs/design/tokens.json — DO NOT EDIT.",
            "# Regenerate with `just assets`.",
            "",
            "[General]",
            f"ColorScheme={brand}Light",
            f"font={entry(ui, body)}",
            f"fixed={entry(mono, body - 1)}",
            f"menuFont={entry(ui, body)}",
            f"smallestReadableFont={entry(ui, font['size']['overline'])}",
            f"toolBarFont={entry(ui, font['size']['caption'])}",
            "widgetStyle=Breeze",
            "",
            "[KDE]",
            # Double-click, because that is what Windows taught them (PRD 4.6).
            "SingleClick=false",
            "AnimationDurationFactor=0.5",
            "",
            "[Icons]",
            "Theme=breeze",
            "",
            "[WM]",
            f"activeFont={entry(ui, font['size']['secondary'], 600)}",
            "",
        ]
    )


def fontconfig(tokens: dict) -> str:
    """The family chain, in the token order (PRD §4.1).

    Uses `match`/`edit` with **binding="strong"**, not `alias`/`prefer`. That is
    not a style choice — the alias form was tried first and lost: `sans-serif`
    still resolved to Noto Sans even with our file sorting last in conf.d,
    because alias/prefer produces a WEAK binding and Fedora's default-font
    configuration binds strongly. Ordering was never the problem, so renaming the
    file to `99-` did nothing.

    With the strong form, `sans-serif` resolves to Inter today and will resolve to
    Schibsted Grotesk the moment it is bundled — the chain falls through in token
    order rather than silently landing on whatever fontconfig would have picked.
    """
    families = "\n".join(f"      <string>{f}</string>" for f in tokens["font"]["ui"])
    mono = "\n".join(f"      <string>{f}</string>" for f in tokens["font"]["mono"])
    return f"""<?xml version="1.0"?>
<!DOCTYPE fontconfig SYSTEM "urn:fontconfig:fonts.dtd">
<!-- GENERATED FROM docs/design/tokens.json - DO NOT EDIT. `just assets`. -->
<fontconfig>
  <match target="pattern">
    <test qual="any" name="family"><string>sans-serif</string></test>
    <edit name="family" mode="prepend" binding="strong">
{families}
    </edit>
  </match>
  <match target="pattern">
    <test qual="any" name="family"><string>monospace</string></test>
    <edit name="family" mode="prepend" binding="strong">
{mono}
    </edit>
  </match>
</fontconfig>
"""


WALL_W, WALL_H = 3840, 2160

# --------------------------------------------------------------- oklch ------
#
# The mockup's gradients are authored in CSS as
# `linear-gradient(160deg, oklch(...), oklch(...) 55%, oklch(...))`, which
# interpolates PERCEPTUALLY: the ramp keeps its lightness and chroma through
# the midpoint. An SVG `linearGradient` interpolates its stops in sRGB, which
# between a light violet and a dark blue dips darker and muddier in the middle
# — the same endpoints, a visibly different ramp, and enough to throw 100+ RGB
# at the midpoint on its own.
#
# So the stops are densified: the oklch path is sampled into intermediate sRGB
# stops close enough together that sRGB interpolation between neighbours is
# indistinguishable from the perceptual curve.


def _srgb_to_linear(c: float) -> float:
    return c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4


def _linear_to_srgb(c: float) -> float:
    return 12.92 * c if c <= 0.0031308 else 1.055 * (c ** (1 / 2.4)) - 0.055


def hex_to_oklch(value: str) -> tuple[float, float, float]:
    import math

    r, g, b = (int(value.lstrip("#")[i : i + 2], 16) / 255 for i in (0, 2, 4))
    r, g, b = _srgb_to_linear(r), _srgb_to_linear(g), _srgb_to_linear(b)
    lms = (
        0.4122214708 * r + 0.5363325363 * g + 0.0514459929 * b,
        0.2119034982 * r + 0.6806995451 * g + 0.1073969566 * b,
        0.0883024619 * r + 0.2817188376 * g + 0.6299787005 * b,
    )
    l_, m_, s_ = (v ** (1 / 3) if v > 0 else -((-v) ** (1 / 3)) for v in lms)
    lightness = 0.2104542553 * l_ + 0.7936177850 * m_ - 0.0040720468 * s_
    a_ = 1.9779984951 * l_ - 2.4285922050 * m_ + 0.4505937099 * s_
    b_ = 0.0259040371 * l_ + 0.7827717662 * m_ - 0.8086757660 * s_
    return lightness, math.hypot(a_, b_), math.degrees(math.atan2(b_, a_)) % 360


def oklch_to_hex(lightness: float, chroma: float, hue: float) -> str:
    import math

    a_ = chroma * math.cos(math.radians(hue))
    b_ = chroma * math.sin(math.radians(hue))
    l_ = lightness + 0.3963377774 * a_ + 0.2158037573 * b_
    m_ = lightness - 0.1055613458 * a_ - 0.0638541728 * b_
    s_ = lightness - 0.0894841775 * a_ - 1.2914855480 * b_
    lo, mo, so = l_**3, m_**3, s_**3
    rgb = (
        4.0767416621 * lo - 3.3077115913 * mo + 0.2309699292 * so,
        -1.2684380046 * lo + 2.6097574011 * mo - 0.3413193965 * so,
        -0.0041960863 * lo - 0.7034186147 * mo + 1.7076147010 * so,
    )
    out = []
    for channel in rgb:
        srgb = _linear_to_srgb(max(0.0, min(1.0, channel)))
        out.append(max(0, min(255, round(srgb * 255))))
    return "#{:02x}{:02x}{:02x}".format(*out)


def densify(stops: list, per_segment: int = 8) -> list:
    """Sample the oklch path between token stops into intermediate sRGB stops."""
    out: list = []
    for index in range(len(stops) - 1):
        (c0, o0), (c1, o1) = stops[index], stops[index + 1]
        l0, ch0, h0 = hex_to_oklch(c0)
        l1, ch1, h1 = hex_to_oklch(c1)
        # Shortest way round the hue circle, so a ramp never takes the long path
        # through unrelated hues.
        delta = ((h1 - h0 + 180) % 360) - 180
        for step in range(per_segment + 1):
            if index and step == 0:
                continue  # the shared stop is already emitted
            t = step / per_segment
            out.append(
                (
                    oklch_to_hex(
                        l0 + (l1 - l0) * t, ch0 + (ch1 - ch0) * t, h0 + delta * t
                    ),
                    o0 + (o1 - o0) * t,
                )
            )
    return out


def wallpaper_svg(name: str, spec: dict) -> str:
    """A gradient wallpaper as SVG — the source, never a raster (WP-05 Forbidden).

    The angle is the mockup's, measured the CSS way: 160deg means the gradient
    runs from top-left-ish toward bottom-right-ish. SVG has no angle, so the
    CSS gradient LINE is constructed instead — and it is not simply a unit
    vector rotated by the angle.

    CSS defines the gradient line through the box centre, with length
    `|W sin t| + |H cos t|`, chosen so the ramp's ends land exactly on the
    corners perpendicular to it. Expressing that as an objectBoundingBox vector
    silently changes the angle, because those units are stretched by the box:
    the same numbers on a 16:9 canvas describe a steeper ramp than CSS draws.
    Measured against the mockup's own recipe, that alone was worth a mean of 16
    RGB — small, systematic, and entirely avoidable. So the gradient is emitted
    in user space, at the size the asset actually is.

    Optional `glows` are radial overlays on top of that gradient. The mockup's
    desktop is not a bare linear gradient, and the difference is not subtle:
    without the glows the wallpaper renders flatter and cooler than the design,
    which is exactly how the first review read it. The base stops were already
    token-correct; the depth was the missing part.
    """
    import math

    theta = math.radians(spec["angle"])
    # CSS: 0deg points up and angles run clockwise; SVG's y grows downward.
    ux, uy = math.sin(theta), -math.cos(theta)
    length = abs(WALL_W * math.sin(theta)) + abs(WALL_H * math.cos(theta))
    cx, cy = WALL_W / 2, WALL_H / 2
    x1, y1 = cx - ux * length / 2, cy - uy * length / 2
    x2, y2 = cx + ux * length / 2, cy + uy * length / 2
    stops = "\n".join(
        f'      <stop offset="{offset:g}%" stop-color="{colour}"/>'
        for colour, offset in densify(list(spec["stops"]))
    )
    # The glows are ELLIPSES: the CSS sizes each glow's box independently in
    # x and y, and `closest-side` makes the gradient reach transparent at that
    # box's edges. SVG's radialGradient is circular, so the circle is drawn at
    # the horizontal radius and scaled vertically about its own centre.
    glow_defs, glow_rects = "", ""
    for index, glow in enumerate(spec.get("glows", [])):
        cx, cy = glow["cx"] * WALL_W, glow["cy"] * WALL_H
        rx, ry = glow["rx"] * WALL_W, glow["ry"] * WALL_H
        k = ry / rx
        glow_defs += (
            f'\n    <radialGradient id="{name}-glow{index}" '
            f'gradientUnits="userSpaceOnUse" '
            f'cx="{cx:g}" cy="{cy:g}" r="{rx:g}" '
            f'gradientTransform="translate(0 {cy * (1 - k):g}) scale(1 {k:g})">\n'
            f'      <stop offset="0%" stop-color="{glow["color"]}" '
            f'stop-opacity="{glow["opacity"]:g}"/>\n'
            f'      <stop offset="100%" stop-color="{glow["color"]}" '
            f'stop-opacity="0"/>\n'
            f"    </radialGradient>"
        )
        glow_rects += (
            f'\n  <rect width="{WALL_W}" height="{WALL_H}" '
            f'fill="url(#{name}-glow{index})"/>'
        )

    return f"""<?xml version="1.0" encoding="UTF-8"?>
<!-- GENERATED FROM docs/design/tokens.json - DO NOT EDIT. `just assets`. -->
<svg xmlns="http://www.w3.org/2000/svg" width="3840" height="2160"
     viewBox="0 0 3840 2160" preserveAspectRatio="xMidYMid slice">
  <defs>
    <linearGradient id="{name}" gradientUnits="userSpaceOnUse"
                    x1="{x1:.2f}" y1="{y1:.2f}" x2="{x2:.2f}" y2="{y2:.2f}">
{stops}
    </linearGradient>{glow_defs}
  </defs>
  <rect width="3840" height="2160" fill="url(#{name})"/>{glow_rects}
</svg>
"""


# ---------------------------------------------------------- plasma style ----
#
# A Plasma Style is where the panel, popups and tooltips get their material —
# the translucency, the corner radius and the hairline that a colour scheme
# cannot express, because a colour scheme has no geometry.
#
# These SVGs are NOT pictures. Plasma's FrameSvg slices each file by ELEMENT ID
# and tiles the result at any size, so the file is a contract:
#
#   topleft     top      topright
#   left       center    right
#   bottomleft bottom    bottomright
#
# Miss an id and Plasma silently falls back to Breeze's element for that slice,
# which is the present-but-inert failure again — a theme that looks applied and
# is half someone else's. tests/lint/plasma_style.py asserts every id exists.
#
# `hint-*-margin` rects are separate from the frame graphics on purpose: they
# set the CONTENT inset independently of how big the corner art is, so an 18px
# radius does not force an 18px padding.

FRAME_TILE = 8  # width/height of the tiling edge and centre cells


def _rgba(value: str) -> tuple[str, float]:
    """Return (#rrggbb, alpha) for a hex or rgba() token."""
    value = value.strip()
    if value.startswith("rgba"):
        parts = [p.strip() for p in value[value.index("(") + 1 : -1].split(",")]
        r, g, b = (int(float(x)) for x in parts[:3])
        return f"#{r:02x}{g:02x}{b:02x}", float(parts[3])
    return value, 1.0


def frame_svg(radius: int, fill: str, hairline: str, margin: int) -> str:
    """One FrameSvg: nine slices of a rounded rect, plus content-margin hints.

    Each slice is drawn as its own geometry rather than a clipped copy of the
    whole shape. Qt reports an element's bounds ignoring clip paths, so a
    clipped construction measures as the full rect and every margin comes out
    wrong — the frame renders, just not where the theme says it does.
    """
    fill_hex, fill_alpha = _rgba(fill)
    line_hex, line_alpha = _rgba(hairline)
    r, t = radius, FRAME_TILE
    total_w = total_h = 2 * r + t

    def corner(name: str, x: int, y: int, sweep: str, path: str) -> str:
        return (
            f'  <g id="{name}">\n'
            f'    <path d="{path}" fill="{fill_hex}" fill-opacity="{fill_alpha:g}"/>\n'
            f'    <path d="{sweep}" fill="none" stroke="{line_hex}" '
            f'stroke-opacity="{line_alpha:g}" stroke-width="1"/>\n'
            f"  </g>"
        )

    def edge(name: str, w: int, h: int, line: tuple | None) -> str:
        """One tiling edge (or the centre): fill, plus the hairline if any."""
        out = (
            f'  <g id="{name}">\n'
            f'    <rect x="0" y="0" width="{w}" height="{h}" '
            f'fill="{fill_hex}" fill-opacity="{fill_alpha:g}"/>\n'
        )
        if line:
            lx, ly, lw, lh = line
            out += (
                f'    <rect x="{lx}" y="{ly}" width="{lw}" height="{lh}" '
                f'fill="{line_hex}" fill-opacity="{line_alpha:g}"/>\n'
            )
        return out + "  </g>"

    parts = [
        # --- corners: a filled quarter-disc, with the arc stroked -----------
        corner(
            "topleft",
            0,
            0,
            f"M0.5,{r} A{r - 0.5},{r - 0.5} 0 0 1 {r},0.5",
            f"M0,{r} A{r},{r} 0 0 1 {r},0 L{r},{r} Z",
        ),
        corner(
            "topright",
            0,
            0,
            f"M0.5,0.5 A{r - 0.5},{r - 0.5} 0 0 1 {r - 0.5},{r}",
            f"M0,0 A{r},{r} 0 0 1 {r},{r} L0,{r} Z",
        ),
        corner(
            "bottomleft",
            0,
            0,
            f"M0.5,0 A{r - 0.5},{r - 0.5} 0 0 0 {r},{r - 0.5}",
            f"M0,0 A{r},{r} 0 0 0 {r},{r} L{r},0 Z",
        ),
        corner(
            "bottomright",
            0,
            0,
            f"M0,{r - 0.5} A{r - 0.5},{r - 0.5} 0 0 0 {r - 0.5},0",
            f"M0,{r} A{r},{r} 0 0 0 {r},0 L0,0 Z",
        ),
        # --- edges: a tile wide/tall, border line on the outer side ---------
        edge("top", t, r, (0, 0, t, 1)),
        edge("bottom", t, r, (0, r - 1, t, 1)),
        edge("left", r, t, (0, 0, 1, t)),
        edge("right", r, t, (r - 1, 0, 1, t)),
        edge("center", t, t, None),
    ]
    hints = "\n".join(
        f'  <rect id="hint-{side}-margin" x="0" y="0" width="{margin}" '
        f'height="{margin}" fill="none"/>'
        for side in ("top", "bottom", "left", "right")
    )
    body = "\n".join(parts)
    return (
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        "<!-- GENERATED FROM docs/design/tokens.json - DO NOT EDIT. `just assets`. -->\n"
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{total_w}" '
        f'height="{total_h}" viewBox="0 0 {total_w} {total_h}">\n'
        f"{body}\n{hints}\n</svg>\n"
    )


def plasma_style(tokens: dict, brand: str) -> dict:
    """Every file of the `meridian` Plasma Style, keyed by relative path."""
    light = tokens["color"]["light"]["surface"]
    radius = tokens["radius"]
    # Plasma Styles are authored against ONE palette; the colour scheme is what
    # follows light/dark. The light surface is the base here because Plasma
    # tints these graphics by the active scheme when the theme declares it.
    surface, hairline = light["window"], light["hairline"]
    return {
        "metadata.json": json.dumps(
            {
                "KPlugin": {
                    "Id": brand.lower(),
                    "Name": brand,
                    "Description": (
                        f"{brand}'s panel, popup and tooltip material. "
                        "Generated from docs/design/tokens.json."
                    ),
                    "License": "GPL-2.0-or-later",
                    "Version": tokens["meta"]["version"],
                },
                "X-Plasma-API": "5.0",
            },
            indent=2,
        )
        + "\n",
        "widgets/panel-background.svg": frame_svg(
            radius["panel"], surface, hairline, 4
        ),
        "dialogs/background.svg": frame_svg(radius["popup"], surface, hairline, 8),
        "widgets/tooltip.svg": frame_svg(radius["popup"], surface, hairline, 6),
        "widgets/background.svg": frame_svg(radius["card"], surface, hairline, 6),
        "widgets/plasmoidheading.svg": frame_svg(
            radius["card"], light["sidebar"], hairline, 4
        ),
    }


def main(argv: list[str] | None = None) -> int:
    # --out lets the staleness lint regenerate into a scratch tree and diff,
    # driving THIS file rather than a rewritten copy of it. A check that tests a
    # mutated copy is testing something the repo does not ship.
    argv = sys.argv[1:] if argv is None else argv
    out = Path(argv[argv.index("--out") + 1]) if "--out" in argv else OUT
    tokens = json.loads(TOKENS.read_text())
    brand = json.loads(BRANDING.read_text())["shortName"]
    out.mkdir(parents=True, exist_ok=True)
    for theme in ("light", "dark"):
        path = out / f"{brand}{theme.capitalize()}.colors"
        path.write_text(scheme(tokens, theme, brand))
        try:
            shown = path.relative_to(ROOT)
        except ValueError:
            shown = path
        print(f"  wrote {shown}")

    # Session defaults and the font chain live outside the color-schemes dir, so
    # they follow --out only when it is the real rootfs; the staleness lint
    # compares the whole set.
    extra = {
        Path(str(out).replace("usr/share/color-schemes", "etc/xdg"))
        / "kdeglobals": kdeglobals(tokens, brand),
        Path(str(out).replace("usr/share/color-schemes", "etc/fonts/conf.d"))
        / "60-meridian-families.conf": fontconfig(tokens),
    }
    # Wallpapers: SVG sources only. WP-05 forbids shipping a raster without its
    # SVG source, and a gradient rasterises identically at any size, so the SVG
    # IS the asset — Plasma renders it directly.
    wallpapers = tokens["wallpaper"]
    wall_root = Path(
        str(out).replace("usr/share/color-schemes", "usr/share/wallpapers")
    )
    for name, spec in wallpapers.items():
        if not isinstance(spec, dict):
            continue
        extra[wall_root / f"{name}.svg"] = wallpaper_svg(name, spec)

    style_root = Path(
        str(out).replace(
            "usr/share/color-schemes", f"usr/share/plasma/desktoptheme/{brand.lower()}"
        )
    )
    for rel, content in plasma_style(tokens, brand).items():
        extra[style_root / rel] = content

    for path, content in extra.items():
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content)
        try:
            shown = path.relative_to(ROOT)
        except ValueError:
            shown = path
        print(f"  wrote {shown}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
