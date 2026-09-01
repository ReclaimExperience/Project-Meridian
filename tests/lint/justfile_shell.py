#!/usr/bin/env python3
"""shellcheck the bash embedded in Justfile recipes (PRD 6.3).

`lint-shell` only sees tracked *.sh files, so the largest block of shell in this
repo — the recipe bodies — was never linted. Every shell defect found in the
WP-01 review lived there: a `find` that aborts under pipefail before reaching its
own friendly error, a `brew --prefix` whose failure exits with no message at all.

This extracts each shebang recipe body, de-indents it, neutralises just's `{{ }}`
interpolations (shellcheck cannot know their values), and runs shellcheck over
the result. Line numbers in findings are relative to the recipe, and the recipe's
starting line in the Justfile is printed alongside.
"""

from __future__ import annotations

import re
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
JUSTFILE = ROOT / "Justfile"

# just interpolations become a shell VARIABLE reference, not a literal:
# `{{ arch }}` -> `${JUSTVAR}`. Substituting a literal made shellcheck report
# every `case "{{ arch }}" in` as SC2194 "this word is constant" — noise of our
# own making that would bury the real findings.
INTERP = re.compile(r"\{\{[^}]*\}\}")
PLACEHOLDER = "${JUSTVAR}"


def recipes() -> list[tuple[str, int, str]]:
    """Return (recipe_name, first_body_line, body) for each shebang recipe."""
    lines = JUSTFILE.read_text().split("\n")
    found, i = [], 0
    while i < len(lines):
        # A recipe header sits at column 0 and ends in ':' or has parameters.
        header = re.match(r"^([a-z_][a-z0-9_-]*)(?: [^:]*)?:(?!=)", lines[i])
        if header and i + 1 < len(lines) and lines[i + 1].strip().startswith("#!"):
            name, start = header.group(1), i + 2
            body, j = [], i + 1
            while j < len(lines) and (
                lines[j].startswith("    ") or not lines[j].strip()
            ):
                body.append(lines[j][4:] if lines[j].startswith("    ") else "")
                j += 1
            found.append((name, start, "\n".join(body)))
            i = j
            continue
        i += 1
    return found


def main() -> int:
    if not (found := recipes()):
        print(
            "justfile-shell: no shebang recipes found — did the Justfile format change?"
        )
        return 1

    # Completeness check: every shebang in the Justfile must belong to a recipe
    # we actually extracted. Without this, a header the regex fails to match
    # silently drops that recipe's shell from the lint — which is exactly how
    # `_todo` went unlinted while this script reported "all clean".
    shebangs = sum(
        1 for line in JUSTFILE.read_text().split("\n") if line.strip().startswith("#!")
    )
    if shebangs != len(found):
        print(
            f"justfile-shell: the Justfile has {shebangs} shebang line(s) but only "
            f"{len(found)} recipe(s) were extracted — some recipe's shell is going "
            f"unlinted.\n"
            f"    Extracted: {[name for name, _, _ in found]}\n"
            f"    Fix the header pattern in this script; do not ignore the gap."
        )
        return 1

    failures = 0
    with tempfile.TemporaryDirectory() as tmp:
        for name, start, body in found:
            script = Path(tmp) / f"{name}.sh"
            # Only declare the placeholder when the recipe actually interpolates,
            # otherwise shellcheck reports it as an unused variable.
            stub = "JUSTVAR=x\n" if INTERP.search(body) else ""
            script.write_text(stub + INTERP.sub(PLACEHOLDER, body))
            result = subprocess.run(
                ["shellcheck", "--shell=bash", "--exclude=SC2148", str(script)],
                capture_output=True,
                text=True,
                check=False,
            )
            if result.returncode != 0:
                print(f"  FAIL  recipe '{name}' (Justfile line {start})")
                for line in result.stdout.split("\n"):
                    if line.strip():
                        print(f"      {line}")
                failures += 1
            else:
                print(f"  ok    recipe '{name}' (Justfile line {start})")

    if failures:
        print(f"\njustfile-shell: {failures} recipe(s) with findings")
        return 1
    print(f"\njustfile-shell: {len(found)} recipe(s) clean")
    return 0


if __name__ == "__main__":
    sys.exit(main())
