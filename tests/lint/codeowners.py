#!/usr/bin/env python3
"""Every CODEOWNERS rule must actually govern something (PRD 7.5, rule R-H).

A rule that matches nothing is worse than no rule: GitHub applies no review
requirement and the file still reads like a gate. WP-01 moved
os/rootfs/usr/etc/ to os/rootfs/etc/ and left the polkit and image-signing rules
pointing into space; nobody noticed until review.

The first version of this check only asked whether some ancestor directory
existed. That passed `/os/rootfs/usr/etc/polkit-1/` because `os/rootfs/usr/`
exists, and would have passed a one-character typo of any live rule. It reported
clean on the exact defect it was written for.

So: expand each pattern against the actual git index, the way GitHub does, and
require at least one match — or an explicit `# planned: WP-NN` marker. Most
owner-gated paths belong to work packages that have not started, and "not built
yet" is legitimate; what is not legitimate is being unable to tell that apart
from "moved and forgotten". The marker makes it a reviewable statement instead
of a guess.

This does not verify that the OWNER resolves — GitHub is the only authority on
that, and the lint workflow asks it directly via the codeowners/errors endpoint.
"""

from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
CODEOWNERS = ROOT / ".github" / "CODEOWNERS"

PLANNED = re.compile(r"#\s*planned:\s*WP-\d{2}")


def tracked_files() -> list[str]:
    out = subprocess.run(
        ["git", "ls-files"], cwd=ROOT, capture_output=True, text=True, check=True
    )
    return [line for line in out.stdout.split("\n") if line]


def pattern_to_regex(pattern: str) -> re.Pattern:
    """Translate a CODEOWNERS (gitignore-style) pattern into a regex.

    Anchored if it starts with '/', otherwise it may match at any depth.
    A trailing '/' means "everything under this directory".
    """
    anchored = pattern.startswith("/")
    body = pattern.lstrip("/")
    directory = body.endswith("/")
    body = body.rstrip("/")

    parts, i = [], 0
    while i < len(body):
        char = body[i]
        if body.startswith("**/", i):
            # `**/` spans ZERO or more directories, so /os/**/*.yml must match
            # os/packages.yml. Translating it as ".*/" silently required at
            # least one intermediate directory and rejected a legal pattern.
            parts.append("(?:.*/)?")
            i += 3
        elif body.startswith("**", i):
            parts.append(".*")
            i += 2
        elif char == "*":
            parts.append("[^/]*")
            i += 1
        elif char == "?":
            parts.append("[^/]")
            i += 1
        else:
            parts.append(re.escape(char))
            i += 1

    core = "".join(parts)
    # A directory rule governs everything beneath it; a file rule may also name
    # a directory, so allow an optional subtree either way.
    suffix = "/.*" if directory else "(/.*)?"
    prefix = "" if anchored else "(.*/)?"
    return re.compile(f"^{prefix}{core}{suffix}$")


def main() -> int:
    if not CODEOWNERS.exists():
        print("codeowners-lint: .github/CODEOWNERS is missing")
        return 1

    files = tracked_files()
    failures = live = planned = 0

    for lineno, raw in enumerate(CODEOWNERS.read_text().split("\n"), 1):
        rule = raw.split("#", 1)[0].strip()
        if not rule:
            continue
        pattern = rule.split()[0]

        matcher = pattern_to_regex(pattern)
        matches = [f for f in files if matcher.match(f)]

        if matches:
            live += 1
            continue

        if PLANNED.search(raw):
            planned += 1
            continue

        failures += 1
        print(f"codeowners-lint: line {lineno}: '{pattern}' matches no tracked file.")
        print("    The rule governs nothing, so this path is NOT owner-gated.")
        print("    If the path simply does not exist yet, say so explicitly:")
        print(f"        {pattern}    @org/team   # planned: WP-NN")

    if failures:
        print(f"\ncodeowners-lint: FAILED ({failures} rule(s) govern nothing)")
        return 1

    print(
        f"codeowners-lint: clean ({live} rule(s) matching tracked files, "
        f"{planned} marked planned)"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
