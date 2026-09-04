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
