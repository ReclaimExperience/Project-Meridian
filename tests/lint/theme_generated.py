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
GENERATOR = ROOT / "shell" / "theme" / "generate-theme.py"
ROOTFS = ROOT / "os" / "rootfs"
# Every path the generator writes. Listed rather than globbed: a generated file
# that stops being generated should fail here, not quietly stop being checked.
GENERATED = (
    "usr/share/color-schemes/MeridianLight.colors",
    "usr/share/color-schemes/MeridianDark.colors",
    "etc/xdg/kdeglobals",
    "etc/fonts/conf.d/60-meridian-families.conf",
)


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

        print("generated theme files match tokens.json")
        for relative in GENERATED:
            # The generator mirrors --out for the non-colour files by string
            # substitution, so reconstruct the same way.
            produced = Path(
                str(out / relative.split("/")[-1])
                if relative.startswith("usr/share/color-schemes")
                else str(out).replace(
                    "usr/share/color-schemes", relative.rsplit("/", 1)[0]
                )
                + "/"
                + relative.rsplit("/", 1)[1]
            )
            committed = ROOTFS / relative
            if not committed.exists():
                print(
                    f"  FAIL  {relative} is not committed, but the generator writes it."
                )
                failures += 1
            elif not produced.exists():
                print(f"  FAIL  the generator no longer writes {relative}, but it is")
                print("      committed — so nothing checks it any more.")
                failures += 1
            elif filecmp.cmp(produced, committed, shallow=False):
                print(f"  ok    {relative}")
            else:
                print(f"  FAIL  {relative} is STALE — tokens.json has moved on.")
                print("      Run `just assets` and commit the result. The palette")
                print("      drifting from the design is invisible until someone")
                print("      compares a screenshot to the mockup.")
                failures += 1

    print()
    if failures:
        print(f"theme-generated: {failures} stale file(s)")
        return 1
    print(f"theme-generated: {len(GENERATED)} file(s) match their generator")
    return 0


if __name__ == "__main__":
    sys.exit(main())
