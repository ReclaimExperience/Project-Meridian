#!/usr/bin/env python3
"""shellcheck the bash embedded in Justfile recipes (PRD 6.3).

`lint-shell` only sees tracked *.sh files, so the largest block of shell in this
repo — the recipe bodies — went unlinted. Every shell defect found in the WP-01
reviews lived there: a `find` that aborted under pipefail before reaching its own
error message, a `brew --prefix` whose failure exited 127 with no output.

Two ways this check has been fooled before, both now guarded:

  * a recipe name shape the header pattern missed (`_todo`), so its shell was
    silently dropped while the script reported "all clean";
  * a body extracted as EMPTY because the de-indent assumed four spaces, while
    `just` also accepts tabs and two spaces. Zero lines were linted and the
    recipe was reported "ok".

Hence: the indent is derived from the body rather than assumed, an empty or
truncated body is an error rather than a pass, and the number of recipes
extracted is reconciled against the number of headers found.
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
# own making that would bury real findings.
INTERP = re.compile(r"\{\{[^}]*\}\}")
PLACEHOLDER = "${JUSTVAR}"

# A recipe header sits at column 0: name, optional parameters, then ':' not '='
# (which would be an assignment). Attributes like [private] precede it.
# `[^:=]*` for the parameter list silently dropped every recipe with a default
# value (`build arch="x86_64":`) — three of the four largest shell bodies in the
# file. `[^:]*` keeps assignments out via the (?!=) lookahead instead.
HEADER = re.compile(r"^([A-Za-z_][A-Za-z0-9_-]*)([^:]*):(?!=)")


class Recipe:
    def __init__(self, name: str, start: int, body: str, shebang: bool, raw_lines: int):
        self.name = name
        self.start = start
        self.body = body
        self.shebang = shebang
        self.raw_lines = raw_lines


def parse_recipes() -> tuple[list[Recipe], int]:
    """Return (recipes, header_count). Bodies are de-indented by the indent the
    body actually uses, not an assumed one."""
    lines = JUSTFILE.read_text().split("\n")
    recipes: list[Recipe] = []
    headers = 0
    i = 0

    while i < len(lines):
        match = HEADER.match(lines[i])
        if not match:
            i += 1
            continue

        # Collect the indented block that follows.
        block, j = [], i + 1
        while j < len(lines) and (
            lines[j].startswith((" ", "\t")) or not lines[j].strip()
        ):
            block.append(lines[j])
            j += 1

        non_blank = [ln for ln in block if ln.strip()]
        if not non_blank:
            i = j if j > i else i + 1
            continue

        headers += 1
        indent = re.match(r"^[ \t]*", non_blank[0]).group(0)
        body_lines = [
            ln[len(indent) :] if ln.startswith(indent) else ln.lstrip() for ln in block
        ]
        shebang = non_blank[0].strip().startswith("#!")
        if not shebang:
            # Non-shebang recipes run line-by-line under `set shell`. Leading
            # '@' (suppress echo) and '-' (ignore failure) are just directives,
            # not shell.
            body_lines = [re.sub(r"^[@-]+", "", ln) for ln in body_lines]

        recipes.append(
            Recipe(
                match.group(1), i + 2, "\n".join(body_lines), shebang, len(non_blank)
            )
        )
        i = j

    return recipes, headers


def just_recipe_names() -> set[str] | None:
    """Ask `just` what recipes exist. Returns None if it cannot tell us."""
    try:
        out = subprocess.run(
            ["just", "--dump", "--dump-format", "json"],
            cwd=ROOT,
            capture_output=True,
            text=True,
            check=True,
        )
        import json

        return set(json.loads(out.stdout).get("recipes", {}))
    except (OSError, subprocess.CalledProcessError, ValueError):
        return None


def main() -> int:
    recipes, headers = parse_recipes()
    if not recipes:
        print("justfile-shell: no recipes found — did the Justfile format change?")
        return 1

    # Completeness, checked against `just` itself rather than against our own
    # parsing. Counting our own headers only proves the parser agrees with
    # itself: an earlier version silently dropped every recipe whose parameter
    # had a default value, and the count matched perfectly the whole time.
    declared = just_recipe_names()
    if declared is not None:
        missed = declared - {r.name for r in recipes}
        if missed:
            print(
                f"justfile-shell: `just` declares {len(declared)} recipe(s) but "
                f"{len(missed)} were not extracted, so their shell is unlinted:"
            )
            for name in sorted(missed):
                print(f"    {name}")
            print("    Fix the header pattern in this script; do not ignore the gap.")
            return 1
    elif headers != len(recipes):
        print(
            f"justfile-shell: found {headers} recipe header(s) but extracted "
            f"{len(recipes)} — some recipe's shell is going unlinted."
        )
        return 1

    failures = 0
    with tempfile.TemporaryDirectory() as tmp:
        for recipe in recipes:
            extracted = [ln for ln in recipe.body.split("\n") if ln.strip()]
            # An empty or truncated body means the de-indent went wrong and the
            # recipe is being silently skipped. That is the failure this lint
            # exists to prevent, so it must be an error, never a quiet "ok".
            if len(extracted) < recipe.raw_lines:
                print(
                    f"  FAIL  recipe '{recipe.name}' (Justfile line {recipe.start}): "
                    f"extracted {len(extracted)} of {recipe.raw_lines} body line(s)."
                )
                print(
                    "      The de-indent lost lines, so this recipe is not being linted."
                )
                failures += 1
                continue

            source = INTERP.sub(PLACEHOLDER, recipe.body)
            stub = "JUSTVAR=x\n" if INTERP.search(recipe.body) else ""
            script = Path(tmp) / f"{recipe.name}.sh"
            script.write_text(stub + source)

            result = subprocess.run(
                ["shellcheck", "--shell=bash", "--exclude=SC2148", str(script)],
                capture_output=True,
                text=True,
                check=False,
            )
            kind = "shebang" if recipe.shebang else "line-by-line"
            if result.returncode != 0:
                print(
                    f"  FAIL  recipe '{recipe.name}' ({kind}, Justfile line {recipe.start})"
                )
                for line in result.stdout.split("\n"):
                    if line.strip():
                        print(f"      {line}")
                failures += 1
            else:
                print(
                    f"  ok    recipe '{recipe.name}' ({kind}, {len(extracted)} line(s), "
                    f"Justfile line {recipe.start})"
                )

    if failures:
        print(f"\njustfile-shell: {failures} recipe(s) with findings")
        return 1
    shebangs = sum(1 for r in recipes if r.shebang)
    print(
        f"\njustfile-shell: {len(recipes)} recipe(s) clean "
        f"({shebangs} shebang, {len(recipes) - shebangs} line-by-line)"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
