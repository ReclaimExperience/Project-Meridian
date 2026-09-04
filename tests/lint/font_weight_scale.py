#!/usr/bin/env python3
"""KDE font entries must use the weight scale their own format is parsed on.

`font=Schibsted Grotesk,14,-1,5,400,0,0,0,0,0` looks obviously right: 400 is
Normal on the CSS scale QFont::Weight uses in Qt6. But a TEN-field entry is
Qt's legacy QFont::toString() form, whose weight field is the old 0..99 scale.
400 is not Normal there — it is past the end and clamps to the heaviest weight
the family has.

It shipped that way. The whole UI rendered in Schibsted Grotesk Black, and the
tell had been sitting in `~/.config/gtk-3.0/settings.ini` the entire time, where
kde-gtk-config had faithfully translated the parsed value into
`gtk-font-name=Schibsted Grotesk, Black 14`.

Proven in the VM by writing both values and comparing frames: 400 renders black,
50 renders normal. This check exists so the next person to touch the generator
cannot reintroduce it by writing the number that looks correct.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
# Qt's legacy scale: 0..99, with 50 Normal, 63 DemiBold, 75 Bold.
MAX_LEGACY_WEIGHT = 99
FONT_KEYS = (
    "font",
    "fixed",
    "menuFont",
    "smallestReadableFont",
    "toolBarFont",
    "activeFont",
)


def main() -> int:
    failures = 0
    checked = 0
    for path in sorted(ROOT.glob("os/rootfs/**/kdeglobals")):
        for lineno, line in enumerate(path.read_text().splitlines(), 1):
            match = re.match(r"\s*(\w+)\s*=\s*(.+)$", line)
            if not match or match.group(1) not in FONT_KEYS:
                continue
            fields = [f.strip() for f in match.group(2).split(",")]
            if len(fields) != 10:
                # A 16-field entry is the modern form, where 100..900 is right.
                continue
            checked += 1
            try:
                weight = int(fields[4])
            except ValueError:
                print(f"{path.relative_to(ROOT)}:{lineno}: weight is not a number")
                failures += 1
                continue
            if weight > MAX_LEGACY_WEIGHT:
                print(
                    f"{path.relative_to(ROOT)}:{lineno}: {match.group(1)} has "
                    f"weight {weight} in a 10-field entry, whose scale is "
                    f"0..{MAX_LEGACY_WEIGHT}. Qt clamps this to the heaviest "
                    "weight the family has — the UI renders Black, not Normal."
                )
                failures += 1

    if not checked:
        print("font-weight-scale: no 10-field font entries found — check the glob")
        return 1
    if failures:
        print(f"font-weight-scale: {failures} bad entry/entries")
        return 1
    print(f"font-weight-scale: {checked} font entry/entries on the legacy scale")
    return 0


if __name__ == "__main__":
    sys.exit(main())
