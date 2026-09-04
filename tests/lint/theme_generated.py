#!/usr/bin/env python3
"""Generated theme assets must match their generator.

The colour schemes are derived from docs/design/tokens.json, which PRD §4 calls
the human contract. A committed file that no longer matches what the generator
produces is worse than a hand-written one: it LOOKS derived, so nobody re-derives
it, and the palette drifts from the mockup one hex at a time until the screenshot
and the design are different products.

So this regenerates into a temporary tree and diffs. It never rewrites the
committed files — a lint that silently fixes what it finds teaches people the
generator is optional.
"""

from __future__ import annotations

import filecmp
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
GENERATOR = ROOT / "shell" / "theme" / "generate-color-schemes.py"
COMMITTED = ROOT / "os" / "rootfs" / "usr" / "share" / "color-schemes"


def main() -> int:
    failures = 0
    with tempfile.TemporaryDirectory() as tmp:
        out = Path(tmp) / "color-schemes"
        result = subprocess.run(
            [sys.executable, str(GENERATOR), "--out", str(out)],
            capture_output=True,
            text=True,
            check=False,
        )
        if result.returncode != 0:
            print("  FAIL  the generator itself does not run:")
            print("      " + (result.stdout + result.stderr).strip()[:400])
            return 1

        expected = sorted(p.name for p in out.glob("*.colors"))
        actual = sorted(p.name for p in COMMITTED.glob("*.colors"))
        if expected != actual:
            print(f"  FAIL  generator produces {expected}, repo has {actual}")
            return 1

        print("generated colour schemes match tokens.json")
        for name in expected:
            if filecmp.cmp(out / name, COMMITTED / name, shallow=False):
                print(f"  ok    {name}")
            else:
                print(f"  FAIL  {name} is STALE — tokens.json has moved on.")
                print("      Run `just assets` and commit the result. The palette")
                print("      drifting from the design is invisible until someone")
                print("      compares a screenshot to the mockup.")
                failures += 1

    print()
    if failures:
        print(f"theme-generated: {failures} stale file(s)")
        return 1
    print(f"theme-generated: {len(expected)} file(s) match their generator")
    return 0


if __name__ == "__main__":
    sys.exit(main())
