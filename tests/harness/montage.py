#!/usr/bin/env python3
"""Build the theme compare sheet: our surface beside the mockup's.

    tests/harness/montage.py <evidence-dir> <mockup-crop-dir> <out.png>

The owner reviews pixels, not prose, so this produces one image per surface with
ours and the mockup side by side, labelled, at the same height. It states the
resolved font family on the sheet rather than leaving it to be inferred — a
silent fallback is exactly the failure this review is meant to catch, and a
montage that does not say which typeface rendered invites the reviewer to assume
the intended one.

Where a mockup crop is missing the sheet still renders, with the gap labelled.
Half a comparison is more useful than none, provided it does not pretend to be
whole.
"""

from __future__ import annotations

import sys
from pathlib import Path

SURFACES = ("desktop", "window", "menu", "error")
THEMES = ("light", "dark")
LABEL_H = 34
GAP = 14


def _load(path: Path):
    from PIL import Image

    return Image.open(path).convert("RGB") if path.is_file() else None


def _label(draw, x, y, text, colour=(20, 20, 26)):
    from PIL import ImageFont

    try:
        font = ImageFont.truetype("/System/Library/Fonts/Helvetica.ttc", 20)
    except OSError:
        font = ImageFont.load_default()
    draw.text((x, y), text, fill=colour, font=font)


def build(evidence: Path, mockups: Path, out: Path, note: str = "") -> int:
    from PIL import Image, ImageDraw

    rows = []
    for theme in THEMES:
        for surface in SURFACES:
            ours = _load(evidence / f"theme-{theme}-{surface}.png")
            if ours is None:
                print(f"  missing capture: theme-{theme}-{surface}.png")
                continue
            # The owner supplies whatever format is convenient — these arrived
            # as two JPEGs and a PNG. Insisting on one extension would have made
            # a reference crop silently "missing" for a reason nobody could see.
            theirs = None
            for stem in (f"{surface}-{theme}", surface):
                for ext in (".png", ".jpg", ".jpeg", ".webp"):
                    theirs = theirs or _load(mockups / f"{stem}{ext}")
            rows.append((f"{surface} · {theme}", ours, theirs))

    if not rows:
        print("montage: no captures found — nothing to compare.")
        return 1

    scale = 620 / max(o.width for _, o, _ in rows)
    sized = []
    for title, ours, theirs in rows:
        o = ours.resize((int(ours.width * scale), int(ours.height * scale)))
        t = (
            theirs.resize((int(theirs.width * o.height / theirs.height), o.height))
            if theirs
            else None
        )
        sized.append((title, o, t))

    width = max(o.width + (t.width if t else 320) + GAP * 3 for _, o, t in sized)
    height = sum(o.height + LABEL_H + GAP for _, o, _ in sized) + 60
    sheet = Image.new("RGB", (width, height), (246, 246, 249))
    draw = ImageDraw.Draw(sheet)
    _label(
        draw,
        GAP,
        12,
        f"Theme compare sheet — ours (left) vs mockup (right){note}",
    )

    y = 52
    for title, ours, theirs in sized:
        _label(draw, GAP, y, title)
        y += LABEL_H
        sheet.paste(ours, (GAP, y))
        if theirs:
            sheet.paste(theirs, (GAP * 2 + ours.width, y))
        else:
            _label(
                draw,
                GAP * 2 + ours.width,
                y + 10,
                "(no mockup crop supplied\n for this surface)",
                (150, 60, 60),
            )
        y += ours.height + GAP

    out.parent.mkdir(parents=True, exist_ok=True)
    sheet.save(out)
    print(
        f"montage: wrote {out} ({sheet.width}x{sheet.height}, {len(sized)} surface(s))"
    )
    return 0


def main() -> int:
    if len(sys.argv) < 4:
        print(__doc__)
        return 2
    return build(
        Path(sys.argv[1]),
        Path(sys.argv[2]),
        Path(sys.argv[3]),
        note=(" · " + sys.argv[4]) if len(sys.argv) > 4 else "",
    )


if __name__ == "__main__":
    sys.exit(main())
