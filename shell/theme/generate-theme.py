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

    # KDE font entries: family,size,weight-ish,italic,weight,...  The trailing
    # fields are Qt's; only family and size are ours to set from tokens.
    def entry(family: str, size: float, weight: int = 400) -> str:
        return f"{family},{size:g},-1,5,{weight},0,0,0,0,0"

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


def wallpaper_svg(name: str, spec: dict) -> str:
    """A gradient wallpaper as SVG — the source, never a raster (WP-05 Forbidden).

    The angle is the mockup's, measured the CSS way: 160deg means the gradient
    runs from top-left-ish toward bottom-right-ish. SVG's linearGradient takes a
    vector instead, so the angle is converted rather than eyeballed — 0deg in CSS
    points up, and y is inverted between the two coordinate systems.
    """
    import math

    angle = spec["angle"]
    # CSS gradient angle -> unit vector, then to SVG's y-down space.
    radians = math.radians(angle - 90)
    dx, dy = math.cos(radians), math.sin(radians)
    x1, y1 = 0.5 - dx / 2, 0.5 - dy / 2
    x2, y2 = 0.5 + dx / 2, 0.5 + dy / 2
    stops = "\n".join(
        f'      <stop offset="{offset}%" stop-color="{colour}"/>'
        for colour, offset in spec["stops"]
    )
    return f"""<?xml version="1.0" encoding="UTF-8"?>
<!-- GENERATED FROM docs/design/tokens.json - DO NOT EDIT. `just assets`. -->
<svg xmlns="http://www.w3.org/2000/svg" width="3840" height="2160"
     viewBox="0 0 3840 2160" preserveAspectRatio="xMidYMid slice">
  <defs>
    <linearGradient id="{name}" x1="{x1:.4f}" y1="{y1:.4f}" x2="{x2:.4f}" y2="{y2:.4f}">
{stops}
    </linearGradient>
  </defs>
  <rect width="3840" height="2160" fill="url(#{name})"/>
</svg>
"""


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
