#!/usr/bin/env python3
"""Vendored fonts must be the bytes someone actually reviewed.

Schibsted Grotesk is not packaged in Fedora, so it is vendored (PRD §4.1, "OFL;
bundle in image"). A binary in the tree carries no provenance of its own: nothing
in a `.ttf` says which upstream release it came from, whether it was modified, or
whether anyone looked at it. The recorded SHA-256 is what turns "a font file" into
"version 1.100, commit d485f61f, unmodified".

Two things this defends:

  * **A silent swap.** A different cut of the family — subset, patched, or simply
    newer — renders slightly differently everywhere and looks like nothing is
    wrong. Same shape as colour drift, and the same defence: compare against a
    recorded value rather than trust the file in the tree.
  * **The licence claim.** `PROVENANCE.md` states the fonts are unmodified, which
    is what keeps OFL's Reserved Font Name clause disengaged. If the bytes change,
    that sentence stops being true, and a checksum is the only thing that notices.
"""

from __future__ import annotations

import hashlib
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
FONT_DIR = ROOT / "os" / "rootfs" / "usr" / "share" / "fonts" / "schibsted-grotesk"
PROVENANCE = FONT_DIR / "PROVENANCE.md"

ROW = re.compile(r"^\|\s*`([^`]+)`\s*\|\s*`([0-9a-f]{64})`\s*\|", re.MULTILINE)


def main() -> int:
    failures = 0
    if not PROVENANCE.is_file():
        print(f"  FAIL  {PROVENANCE.relative_to(ROOT)} is missing.")
        print("      A vendored binary with no provenance record is a file nobody")
        print("      can vouch for.")
        return 1

    recorded = dict(ROW.findall(PROVENANCE.read_text()))
    if not recorded:
        print("  FAIL  PROVENANCE.md records no checksums, so it asserts nothing.")
        return 1

    print("vendored fonts match their recorded provenance")
    for name, expected in sorted(recorded.items()):
        path = FONT_DIR / name
        if not path.is_file():
            print(f"  FAIL  {name} is recorded but not present.")
            failures += 1
            continue
        actual = hashlib.sha256(path.read_bytes()).hexdigest()
        if actual != expected:
            print(f"  FAIL  {name} does not match its recorded checksum.")
            print(f"      recorded {expected}")
            print(f"      actual   {actual}")
            print("      Either the file was replaced, or it was modified — and if")
            print("      modified, PROVENANCE.md's 'unmodified' claim is now false")
            print("      and OFL's Reserved Font Name clause is engaged.")
            failures += 1
        else:
            print(f"  ok    {name}  ({path.stat().st_size:,} bytes)")

    # Every shipped binary must be accounted for, or a file could be added
    # without a checksum and inherit the record's credibility.
    shipped = {p.name for p in FONT_DIR.iterdir() if p.suffix in (".ttf", ".otf")}
    unrecorded = shipped - set(recorded)
    if unrecorded:
        print(f"  FAIL  shipped but not recorded: {sorted(unrecorded)}")
        print("      Add it to PROVENANCE.md with its source and checksum.")
        failures += 1

    if not (FONT_DIR / "OFL.txt").is_file():
        print("  FAIL  OFL.txt is not committed alongside the fonts.")
        print("      The licence requires it to travel with the font.")
        failures += 1
    else:
        print("  ok    OFL.txt ships with the fonts")

    print()
    if failures:
        print(f"font-provenance: {failures} failure(s)")
        return 1
    print(f"font-provenance: {len(recorded)} file(s) match, licence present")
    return 0


if __name__ == "__main__":
    sys.exit(main())
