#!/usr/bin/env python3
"""Every CODEOWNERS rule must actually govern something (PRD 7.5, rule R-H).

A rule that matches nothing is worse than no rule: GitHub applies no review
requirement and the file still reads like a gate. WP-01 moved
os/rootfs/usr/etc/ to os/rootfs/etc/ and left the polkit and image-signing rules
pointing into space; nobody noticed until review.

Two earlier versions of this check were themselves vacuous:

  1. It asked only whether SOME ancestor directory existed, so
     `/os/rootfs/usr/etc/polkit-1/` passed because `os/rootfs/usr/` exists.
  2. It expanded patterns with a hand-rolled regex. That regex anchored only on
     a LEADING slash, while gitignore also anchors a pattern containing an
     interior separator — so `rootfs/etc/` (a real rule with the `/os` prefix
     dropped) matched two files here and zero on GitHub. The lint reported clean
     on exactly the class of defect it exists to catch.

So matching is delegated to `git check-ignore`, which implements these semantics
for real. `git ls-files` supplies the file list; git also supplies the meaning of
the pattern. Nothing about the matching rules is reimplemented here.

CODEOWNERS is *close* to gitignore but not identical: GitHub does not support
character ranges (`[a-z]`) or negation (`!`). Those are rejected outright rather
than guessed at, because git would happily match them while GitHub would not.

This does not verify that the OWNER resolves — GitHub is the only authority on
that, and the lint workflow asks it directly via the codeowners/errors endpoint.
"""

from __future__ import annotations

import re
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
CODEOWNERS = ROOT / ".github" / "CODEOWNERS"

# A trailing comment of the form "# planned: WP-NN", and nothing looser. An
# earlier version searched the whole line, so any comment merely containing the
# phrase excused a dead rule.
PLANNED = re.compile(r"#\s*planned:\s*WP-(\d{2})\s*$")
MAX_WP = 26  # PRD section 8 defines WP-00 .. WP-26

UNSUPPORTED = {
    "[": "character ranges are not supported by GitHub CODEOWNERS",
    "]": "character ranges are not supported by GitHub CODEOWNERS",
    "!": "negation is not supported by GitHub CODEOWNERS",
}


def tracked_files() -> list[str]:
    out = subprocess.run(
        ["git", "ls-files"], cwd=ROOT, capture_output=True, text=True, check=True
    )
    return [line for line in out.stdout.split("\n") if line]


def split_rule(rule: str) -> str:
    """Return the pattern, honouring backslash-escaped spaces.

    `rule.split()[0]` truncated an escaped path at the backslash — and this repo
    already tracks a mockup file whose name contains a space.
    """
    out, i = [], 0
    while i < len(rule):
        char = rule[i]
        if char == "\\" and i + 1 < len(rule):
            out.append(rule[i : i + 2])
            i += 2
            continue
        if char.isspace():
            break
        out.append(char)
        i += 1
    return "".join(out)


def matching_files(pattern: str, files: list[str]) -> list[str]:
    """Ask git which tracked files a pattern governs. Git is the authority."""
    with tempfile.NamedTemporaryFile("w", suffix=".exclude", delete=False) as handle:
        handle.write(pattern + "\n")
        exclude = handle.name
    try:
        result = subprocess.run(
            [
                "git",
                "-c",
                f"core.excludesFile={exclude}",
                "check-ignore",
                "--no-index",
                "--stdin",
            ],
            cwd=ROOT,
            input="\n".join(files),
            capture_output=True,
            text=True,
            check=False,
        )
        # exit 0 = something matched, 1 = nothing matched, >1 = real error
        if result.returncode > 1:
            raise RuntimeError(result.stderr.strip() or "git check-ignore failed")
        return [line for line in result.stdout.split("\n") if line]
    finally:
        Path(exclude).unlink(missing_ok=True)


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
        pattern = split_rule(rule)

        bad = next((c for c in UNSUPPORTED if c in pattern), None)
        if bad:
            failures += 1
            print(f"codeowners-lint: line {lineno}: '{pattern}' — {UNSUPPORTED[bad]}.")
            print("    GitHub would ignore this rule, so the path is NOT owner-gated.")
            continue

        try:
            matches = matching_files(pattern, files)
        except RuntimeError as exc:
            failures += 1
            print(
                f"codeowners-lint: line {lineno}: '{pattern}' — git rejected it: {exc}"
            )
            continue

        if matches:
            live += 1
            continue

        marker = PLANNED.search(raw)
        if marker:
            number = int(marker.group(1))
            if number > MAX_WP:
                failures += 1
                print(
                    f"codeowners-lint: line {lineno}: marker names WP-{marker.group(1)}, "
                    f"but the PRD defines WP-00 through WP-{MAX_WP:02d}."
                )
                continue
            planned += 1
            continue

        failures += 1
        print(f"codeowners-lint: line {lineno}: '{pattern}' matches no tracked file.")
        print("    The rule governs nothing, so this path is NOT owner-gated.")
        print("    If the path simply does not exist yet, say so explicitly with a")
        print("    trailing marker naming the work package that will create it:")
        print(f"        {pattern}    @org/team   # planned: WP-NN")

    if failures:
        print(f"\ncodeowners-lint: FAILED ({failures} rule(s) govern nothing)")
        return 1

    print(
        f"codeowners-lint: clean ({live} rule(s) matching tracked files, "
        f"{planned} marked planned; matching delegated to git check-ignore)"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
