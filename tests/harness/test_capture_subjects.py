#!/usr/bin/env python3
"""The capture suite's subject assertions must actually catch a missing subject.

R-I's fourth row, tested rather than asserted. The theme suite wrote
`theme-light-menu.png`, printed "captured menu (light)", and shipped a frame
with no menu in it — because "captured" meant "a file was written". These are
the checks that replaced that, and a check that cannot fail is the same
decoration in a new place, so each one is exercised against a frame that should
fail it.

No VM: the primitives take image files, so synthetic frames prove the logic.
"""

from __future__ import annotations

import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from harness.screen import changed_region, dominant_colours, nearest_distance

# docs/design/tokens.json, wallpaper softViolet
STOPS = [(0xC3, 0xBF, 0xE3), (0x6D, 0x7A, 0xC2), (0x2C, 0x48, 0x8E)]


def frame(tmp: Path, name: str, fill, box=None, box_fill=None):
    from PIL import Image, ImageDraw

    img = Image.new("RGB", (1280, 800), fill)
    if box:
        ImageDraw.Draw(img).rectangle(box, fill=box_fill)
    path = tmp / f"{name}.png"
    img.save(path)
    return path


def gradient(tmp: Path, name: str, stops):
    from PIL import Image

    img = Image.new("RGB", (1280, 800))
    px = img.load()
    for y in range(800):
        t = y / 799
        if t < 0.55:
            a, b, u = stops[0], stops[1], t / 0.55
        else:
            a, b, u = stops[1], stops[2], (t - 0.55) / 0.45
        col = tuple(int(a[i] + (b[i] - a[i]) * u) for i in range(3))
        for x in range(1280):
            px[x, y] = col
    path = tmp / f"{name}.png"
    img.save(path)
    return path


def main() -> int:
    failures = 0
    with tempfile.TemporaryDirectory() as td:
        tmp = Path(td)

        # --- menu assertion --------------------------------------------------
        base = frame(tmp, "base", (40, 44, 52))
        same = frame(tmp, "same", (40, 44, 52))
        menu = frame(tmp, "menu", (40, 44, 52), (500, 300, 780, 620), (250, 250, 255))
        whole = frame(tmp, "whole", (200, 30, 30))

        f_same, box_same = changed_region(base, same)
        if box_same is not None or f_same >= 0.004:
            print(f"FAIL: identical frames read as a menu ({f_same:.4%})")
            failures += 1

        f_menu, box_menu = changed_region(base, menu)
        if box_menu is None or not (0.004 <= f_menu <= 0.45):
            print(f"FAIL: a real menu rectangle was not accepted ({f_menu:.4%})")
            failures += 1
        elif box_menu != (500, 300, 780, 620):
            print(f"FAIL: menu bbox wrong: {box_menu}")
            failures += 1

        f_whole, _ = changed_region(base, whole)
        if f_whole <= 0.45:
            print(f"FAIL: a full repaint passed as a menu ({f_whole:.1%})")
            failures += 1

        # --- wallpaper assertion ---------------------------------------------
        ours = gradient(tmp, "ours", STOPS)
        near = min(nearest_distance(c, STOPS) for c in dominant_colours(ours))
        if near > 90:
            print(f"FAIL: our own gradient was not recognised (distance {near:.0f})")
            failures += 1

        # A stand-in for the base image's wallpaper: nothing like our palette.
        foreign = gradient(tmp, "foreign", [(20, 90, 30), (240, 200, 60), (250, 120, 10)])
        near_foreign = min(nearest_distance(c, STOPS) for c in dominant_colours(foreign))
        if near_foreign <= 90:
            print(f"FAIL: a foreign wallpaper passed as ours (distance {near_foreign:.0f})")
            failures += 1

    if failures:
        print(f"capture-subjects: {failures} failure(s)")
        return 1
    print(
        "capture-subjects: menu detected, no-change rejected, full repaint "
        "rejected, our gradient recognised, foreign wallpaper rejected"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
