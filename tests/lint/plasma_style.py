#!/usr/bin/env python3
"""A Plasma Style's SVGs are a contract, not pictures.

Plasma's FrameSvg slices each file by ELEMENT ID and tiles the pieces at
whatever size the panel or popup happens to be:

    topleft      top       topright
    left        center     right
    bottomleft  bottom     bottomright

A missing id is not an error anyone sees. Plasma falls back to the default
theme's element for that slice, so the frame still renders — as a mix of our
corners and Breeze's edges, or the reverse. The theme reads as applied and is
half someone else's, which is R-I exactly: present, correct-looking, inert.

So the contract is asserted rather than assumed. This also checks the
`hint-*-margin` rects, because content padding comes from those and not from
how large the corner art happens to be.
"""

from __future__ import annotations

import re
import sys
import xml.etree.ElementTree as ET
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
STYLE = ROOT / "os/rootfs/usr/share/plasma/desktoptheme"

FRAME_IDS = {
    "topleft",
    "top",
    "topright",
    "left",
    "center",
    "right",
    "bottomleft",
    "bottom",
    "bottomright",
}
# KWin blurs behind the region these define. Translucency without them is
# translucency over an unblurred background: the alpha is real, the material is
# not.
MASK_IDS = {f"mask-{name}" for name in FRAME_IDS}
# Plasma rewrites this block's contents per colour scheme; elements opt in with
# class="ColorScheme-*" and fill="currentColor". A hardcoded fill renders
# exactly as authored and never follows light/dark — which is how the first cut
# of this style produced a near-white panel under a dark scheme, while
# `plasma-apply-desktoptheme` reported success.
STYLESHEET_ID = "current-color-scheme"

HINT_IDS = {
    "hint-top-margin",
    "hint-bottom-margin",
    "hint-left-margin",
    "hint-right-margin",
}


def ids_in(path: Path) -> set[str]:
    root = ET.parse(path).getroot()
    return {el.get("id") for el in root.iter() if el.get("id")}


def main() -> int:
    if not STYLE.is_dir():
        print(f"plasma-style: no style at {STYLE.relative_to(ROOT)}")
        return 1
    svgs = sorted(STYLE.rglob("*.svg"))
    if not svgs:
        print("plasma-style: the style ships no SVGs — nothing is themed")
        return 1

    failures = 0
    for svg in svgs:
        rel = svg.relative_to(ROOT)
        try:
            present = ids_in(svg)
        except ET.ParseError as exc:
            print(f"{rel}: not valid XML — {exc}")
            failures += 1
            continue
        missing = FRAME_IDS - present
        if missing:
            print(
                f"{rel}: missing frame element(s) {sorted(missing)}. "
                "Plasma will fall back to the default theme for those slices, "
                "so the frame renders as ours and Breeze's mixed together."
            )
            failures += 1
        missing_hints = HINT_IDS - present
        if missing_hints:
            print(
                f"{rel}: missing {sorted(missing_hints)} — content padding "
                "would come from the corner art's size instead of the token."
            )
            failures += 1
        missing_mask = MASK_IDS - present
        if missing_mask:
            print(
                f"{rel}: missing {sorted(missing_mask)[:3]}... — no blur mask, "
                "so the frame is translucent over an unblurred background."
            )
            failures += 1

        text = svg.read_text()
        if STYLESHEET_ID not in present:
            print(
                f'{rel}: no <style id="{STYLESHEET_ID}"> — Plasma has nothing '
                "to rewrite, so the frame keeps its authored colours and never "
                "follows the colour scheme."
            )
            failures += 1
        if "ColorScheme-" not in text or 'fill="currentColor"' not in text:
            print(
                f'{rel}: paints without class="ColorScheme-*" + '
                'fill="currentColor", so the stylesheet cannot reach it.'
            )
            failures += 1
        hardcoded = re.findall(r'fill="#[0-9a-fA-F]{6}"', text)
        if len(hardcoded) > len(MASK_IDS):
            print(
                f"{rel}: {len(hardcoded)} hardcoded fill(s); only the mask "
                "slices may be flat."
            )
            failures += 1

    for required in ("metadata.json",):
        for style_dir in {p.parent for p in STYLE.iterdir() if p.is_dir()} | set(
            STYLE.iterdir()
        ):
            if not style_dir.is_dir():
                continue
            if style_dir.parent == STYLE and not (style_dir / required).is_file():
                print(
                    f"{style_dir.relative_to(ROOT)}: no {required}, so Plasma "
                    "will not list the theme at all"
                )
                failures += 1

    if failures:
        print(f"plasma-style: {failures} problem(s)")
        return 1
    print(f"plasma-style: {len(svgs)} frame(s), all nine slices + margin hints")
    return 0


if __name__ == "__main__":
    sys.exit(main())
