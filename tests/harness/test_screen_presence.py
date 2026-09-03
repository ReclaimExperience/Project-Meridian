#!/usr/bin/env python3
"""The blank-screen guard, proven without booting anything.

Regression test for a real nightly run. Every frame it captured was pure black —
stddev 0.00000, maximum pixel value 0 — and the harness printed

    smoke: greeter screenshot smoke-greeter.png

as though a greeter had been seen, typed a password into it, and failed 420
seconds later blaming `plasmashell`, which had done nothing wrong.

The guard against that shape already existed, in `screens.py`, written after
review round 3. `screens` runs in no automated context. `smoke` gates every pull
request and had no such check. So the interesting assertion here is not that the
maths works — it is that the suites people actually run now call it.
"""

from __future__ import annotations

import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from harness import screen

ROOT = Path(__file__).resolve().parents[2]


class FakeVM:
    """Returns a canned frame for every screenshot. `arch` is read by perf."""

    arch = "x86_64"

    def __init__(self, frame: Path, work: Path) -> None:
        self._frame = frame
        self._work = work
        self.shots = 0

    def screenshot(self, name: str) -> Path:
        import shutil

        self.shots += 1
        target = self._work / f"{name}.png"
        shutil.copy(self._frame, target)
        return target


def main() -> int:
    from PIL import Image

    failures = 0
    with tempfile.TemporaryDirectory() as tmp:
        work = Path(tmp)

        black = work / "black.png"
        Image.new("RGB", (1280, 800), (0, 0, 0)).save(black)
        # Not a real desktop, but well above the blank floor, which is the
        # property under test.
        content = work / "content.png"
        img = Image.new("RGB", (1280, 800), (0, 0, 0))
        for x in range(0, 1280, 2):
            for y in range(0, 800, 2):
                img.putpixel((x, y), (255, 255, 255))
        img.save(content)

        print("a black screen must be refused, by name")
        try:
            screen.wait_for_screen(FakeVM(black, work), "the greeter", tries=3)
        except AssertionError as exc:
            message = str(exc)
            ok = "BLANK" in message and "the greeter" in message
            print(f"  {'ok  ' if ok else 'FAIL'}  refused: {message.splitlines()[0]}")
            failures += 0 if ok else 1
            if "plasmashell" in message:
                print("  FAIL  the message blames plasmashell; that was the bug")
                failures += 1
        else:
            print("  FAIL  a screen of pure black was accepted as a greeter")
            print("      This is the exact frame the nightly captured and used.")
            failures += 1

        print("\na screen with content must be accepted")
        try:
            got = screen.wait_for_screen(FakeVM(content, work), "the desktop", tries=5)
            ok = got.exists()
            print(f"  {'ok  ' if ok else 'FAIL'}  accepted {got.name}")
            failures += 0 if ok else 1
        except AssertionError as exc:
            print(f"  FAIL  a screen with real detail was rejected: {exc}")
            failures += 1

        print("\ndetail measurement")
        for path, label, expect_blank in (
            (black, "pure black", True),
            (content, "half-lit", False),
        ):
            detail = screen.frame_detail(path)
            blank = detail < screen.BLANK_STDDEV
            ok = blank == expect_blank
            print(f"  {'ok  ' if ok else 'FAIL'}  {label}: detail {detail:.5f}")
            failures += 0 if ok else 1

    # The point of the whole exercise: the suites that run must call it.
    print("\nthe suites that gate a PR must actually use the guard")
    suites = ROOT / "tests" / "harness" / "suites"
    for name in ("smoke", "perf"):
        source = (suites / f"{name}.py").read_text()
        typed = "type_text" in source
        guarded = "wait_for_screen" in source
        if typed and not guarded:
            print(f"  FAIL  {name}.py types into the screen without checking it is on")
            failures += 1
        else:
            print(f"  ok    {name}.py checks the screen is up before using it")

    print()
    if failures:
        print(f"screen-presence: {failures} failure(s)")
        return 1
    print("screen-presence: black frames are refused by name, and smoke/perf call it")
    return 0


if __name__ == "__main__":
    sys.exit(main())
