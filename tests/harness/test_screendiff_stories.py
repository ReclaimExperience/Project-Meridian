#!/usr/bin/env python3
"""No-VM guards for the two suites that never run in CI (WP-03 review round 3).

`screens` cannot run in CI — only aarch64 baselines are committed and CI is
x86_64 — and `stories` currently discovers zero stories and returns green having
run nothing. So the largest body of code in this WP, the screendiff apparatus,
had no automated coverage at all, and the claim "a story that exists and does
not pass is a failure" was unproven.

These exercise both without booting anything.
"""

from __future__ import annotations

import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from harness import screendiff
from harness.suites import stories

ROOT = Path(__file__).resolve().parents[2]


def check(name: str, ok: bool, detail: str = "") -> int:
    print(f"  {'ok  ' if ok else 'FAIL'}  {name}" + (f": {detail}" if detail else ""))
    return 0 if ok else 1


def main() -> int:
    from PIL import Image

    failures = 0
    with tempfile.TemporaryDirectory() as tmp:
        work = Path(tmp)
        black = work / "a.png"
        white = work / "b.png"
        Image.new("RGB", (64, 64), (0, 0, 0)).save(black)
        Image.new("RGB", (64, 64), (255, 255, 255)).save(white)

        # A genuine difference must be reported as one.
        result = screendiff.compare("t", white, black, screendiff.ScreenConfig(), work)
        failures += check(
            "screendiff reports a real difference",
            not result.passed and result.rmse > 0.9,
            f"rmse={result.rmse:.3f}",
        )

        # Identical screens must pass.
        result = screendiff.compare("t", black, black, screendiff.ScreenConfig(), work)
        failures += check("screendiff accepts identical screens", result.passed)

        # A missing baseline must fail, never silently seed one.
        result = screendiff.compare(
            "t", black, work / "nope.png", screendiff.ScreenConfig(), work
        )
        failures += check("screendiff refuses a missing baseline", not result.passed)

        # The two bypasses: a full-image mask and a raised threshold.
        result = screendiff.compare(
            "t", white, black, screendiff.ScreenConfig(masks=[[0, 0, 64, 64]]), work
        )
        failures += check("screendiff rejects a full-image mask", not result.passed)
        result = screendiff.compare(
            "t", white, black, screendiff.ScreenConfig(threshold=1.0), work
        )
        failures += check(
            "screendiff rejects a threshold above the ceiling", not result.passed
        )

        # stories: a story that FAILS must make the suite fail. Without this the
        # suite's green-on-zero-stories behaviour proves nothing.
        story = ROOT / "tests" / "stories" / "zt_99_selftest_probe.py"
        story.write_text(
            "STORY = 'ZT-99 — probe'\nOWNER_WP = 'WP-03'\n"
            "def run(vm, credentials):\n    raise AssertionError('deliberate')\n"
        )
        try:
            stories.run(None, {})
            failures += check("stories fails when a story fails", False, "it PASSED")
        except AssertionError as exc:
            failures += check(
                "stories fails when a story fails", "deliberate" in str(exc)
            )
        finally:
            story.unlink(missing_ok=True)

        # ...and with none present it must say so rather than imply coverage.
        try:
            stories.run(None, {})
            failures += check("stories is green with none implemented", True)
        except AssertionError as exc:
            failures += check("stories is green with none implemented", False, str(exc))

    if failures:
        print(f"\nscreendiff/stories: {failures} failure(s)")
        return 1
    print("\nscreendiff/stories: both suites behave correctly without a VM")
    return 0


if __name__ == "__main__":
    sys.exit(main())
