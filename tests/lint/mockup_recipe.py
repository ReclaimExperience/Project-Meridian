#!/usr/bin/env python3
"""tokens.json must match the mockup's own recipe, read from its source.

Six turns of this work package were spent measuring a colour gap that did not
exist. The reference being compared against was a JPEG crop, and that crop was a
render of a *newer* mockup than the one the tokens came from — so every delta
measured the distance between two versions, and a plane fitted to that
glow-composited image produced a confident, entirely phantom "the ramp is
rotated 94 degrees".

The rule the chase paid for: **design updates enter the pipeline as source,
never as renders.** A JPEG cannot be a source of truth. It contains no recipe,
only the result of one, and anything recovered from it by fitting is an
inference wearing a measurement's clothes.

So this reads the design canvas's own `.dc.html`, extracts the wallpaper recipe
it specifies, and asserts `tokens.json` still agrees. When the mockup is
updated, this fails and names the difference — instead of the gap being noticed
months later as "the desktop looks a bit off".
"""

from __future__ import annotations

import importlib.util
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
MOCKUP = ROOT / "docs/design/mockup/Meridian OS.dc.html"
TOKENS = ROOT / "docs/design/tokens.json"

NAMES = {"Soft violet": "softViolet", "Dusk": "dusk", "Deep teal": "deepTeal"}
# One 8-bit step of slack: the canvas quotes oklch to two significant
# figures, so its sRGB rendering can land a count either side.
CHANNEL_TOL = 1


def load_generator():
    spec = importlib.util.spec_from_file_location(
        "gt", ROOT / "shell/theme/generate-theme.py"
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def parse_wallpapers(text: str) -> dict:
    out = {}
    for name, css in re.findall(r"'([^']+)':\s*'(linear-gradient\([^']+\))'", text):
        angle = float(re.search(r"linear-gradient\(\s*([\d.]+)deg", css).group(1))
        stops = []
        for lightness, chroma, hue, pos in re.findall(
            r"oklch\(\s*([\d.]+)\s+([\d.]+)\s+([\d.]+)\s*\)(?:\s+([\d.]+)%)?", css
        ):
            stops.append(
                (
                    float(lightness),
                    float(chroma),
                    float(hue),
                    float(pos) if pos else None,
                )
            )
        if stops:
            out[name] = {"angle": angle, "stops": stops}
    return out


def parse_glows(text: str) -> list:
    glows = []
    for style in re.findall(
        r'style="(position:absolute;[^"]*radial-gradient[^"]*)"', text
    ):

        def pct(key, style=style):
            match = re.search(rf"(?:^|;){key}:(-?[\d.]+)%", style)
            return float(match.group(1)) / 100 if match else None

        width, height = pct("width"), pct("height")
        top, left, bottom, right = pct("top"), pct("left"), pct("bottom"), pct("right")
        colour = re.search(r"rgba\((\d+),\s*(\d+),\s*(\d+),\s*([\d.]+)\)", style)
        if width is None or height is None or not colour:
            continue
        # CSS `right: R` puts the element's right edge at (100% - R), so a
        # NEGATIVE R pushes it beyond the container: right:-15% means the edge
        # sits at 115%, not 85%. Getting that sign wrong moves the glow's
        # centre from (80%, 90%) to (50%, 30%) — halfway across the screen.
        x0 = left if left is not None else (1 - right) - width
        y0 = top if top is not None else (1 - bottom) - height
        glows.append(
            {
                "cx": round(x0 + width / 2, 4),
                "cy": round(y0 + height / 2, 4),
                "rx": round(width / 2, 4),
                "ry": round(height / 2, 4),
                "color": "#{:02x}{:02x}{:02x}".format(
                    *(int(colour.group(i)) for i in (1, 2, 3))
                ),
                "opacity": float(colour.group(4)),
            }
        )
    return glows


def main() -> int:
    if not MOCKUP.is_file():
        print(f"mockup-recipe: no canvas source at {MOCKUP.relative_to(ROOT)}")
        return 1
    gt = load_generator()
    text = MOCKUP.read_text(errors="replace")
    tokens = json.loads(TOKENS.read_text())
    source_walls = parse_wallpapers(text)
    source_glows = parse_glows(text)
    failures = 0

    if not source_walls:
        print("mockup-recipe: no wallpaper recipe found in the canvas source")
        return 1

    for human, key in NAMES.items():
        if human not in source_walls:
            print(f"mockup-recipe: canvas has no '{human}' wallpaper")
            failures += 1
            continue
        want, have = source_walls[human], tokens["wallpaper"][key]
        if abs(have["angle"] - want["angle"]) > 0.01:
            print(f"{key}: angle {have['angle']} != canvas {want['angle']}")
            failures += 1
        if len(have["stops"]) != len(want["stops"]):
            print(f"{key}: {len(have['stops'])} stops, canvas has {len(want['stops'])}")
            failures += 1
            continue
        for index, ((hex_value, pos), (wl, wc, wh, wpos)) in enumerate(
            zip(have["stops"], want["stops"])
        ):
            # Compare in the direction that survives the gamut: canvas oklch
            # -> sRGB hex, against the token's hex. The reverse looks tempting
            # and is wrong for any stop outside sRGB — Deep Teal's dark end,
            # oklch(0.35 0.09 240), clamps to #003f64 with red at zero, and
            # reading THAT back gives oklch(0.3533 0.0855 243.0). Comparing
            # those numbers reports a 3-degree hue drift in a token that is in
            # fact exactly what the canvas asks for.
            expected_hex = gt.oklch_to_hex(wl, wc, wh)
            got = tuple(int(hex_value.lstrip("#")[i : i + 2], 16) for i in (0, 2, 4))
            want_rgb = tuple(
                int(expected_hex.lstrip("#")[i : i + 2], 16) for i in (0, 2, 4)
            )
            if max(abs(a - b) for a, b in zip(got, want_rgb)) > CHANNEL_TOL:
                print(
                    f"{key} stop {index}: {hex_value}, but canvas "
                    f"oklch({wl} {wc} {wh}) is {expected_hex}"
                )
                failures += 1
            expected = wpos if wpos is not None else (0 if index == 0 else 100)
            if abs(pos - expected) > 0.01:
                print(f"{key} stop {index}: at {pos}%, canvas says {expected}%")
                failures += 1

        for index, want_glow in enumerate(source_glows):
            if index >= len(have.get("glows", [])):
                print(f"{key}: canvas has glow {index}, tokens do not")
                failures += 1
                continue
            have_glow = have["glows"][index]
            for field in ("cx", "cy", "rx", "ry", "opacity"):
                if abs(have_glow[field] - want_glow[field]) > 0.005:
                    print(
                        f"{key} glow {index}: {field}={have_glow[field]}, canvas "
                        f"says {want_glow[field]}"
                    )
                    failures += 1
            if have_glow["color"].lower() != want_glow["color"].lower():
                print(
                    f"{key} glow {index}: colour {have_glow['color']}, canvas "
                    f"says {want_glow['color']}"
                )
                failures += 1

    if failures:
        print(f"mockup-recipe: {failures} difference(s) from the canvas source")
        return 1
    print(
        f"mockup-recipe: {len(NAMES)} wallpaper(s) and {len(source_glows)} glow(s) "
        "match the canvas source"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
