#!/usr/bin/env python3
"""Proves the restricted YAML parser in apply-packages.sh matches real PyYAML.

apply-packages.sh cannot use PyYAML: it runs inside the image build, where
pulling in a YAML library to read twenty lines would be silly. It instead parses
the deliberately tiny subset packages.yml is allowed to use.

That trade is only safe while the restricted parser agrees with a real one. If
it ever silently disagrees, a package would be quietly skipped or removed —
which nobody would notice until it reached hardware. This test is what keeps
that trade honest.
"""

from __future__ import annotations

import re
import subprocess
import sys
import tempfile
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "os" / "scripts" / "build" / "apply-packages.sh"

KEYS = ["add", "remove", "systemd.mask", "systemd.disable"]

CASES = {
    "empty lists": "version: 1\nadd: []\nremove: []\nsystemd:\n  mask: []\n  disable: []\n",
    "block lists": (
        "version: 1\nadd:\n  - haruna\n  - thermald\nremove:\n  - kmail\n"
        "systemd:\n  mask:\n    - baloo_file.service\n  disable:\n    - foo.timer\n"
    ),
    "inline lists": "version: 1\nadd: [a, b, c]\nremove: [x]\nsystemd:\n  mask: [m.service]\n  disable: []\n",
    "comments": (
        "version: 1\n# leading comment\nadd:\n  - haruna   # trailing comment\n"
        "remove: []\nsystemd:\n  mask: []\n  disable: []\n"
    ),
    "quoted scalars": (
        "version: 1\nadd:\n  - 'single'\n  - \"double\"\nremove: []\n"
        "systemd:\n  mask: []\n  disable: []\n"
    ),
    "the real manifest": (ROOT / "os" / "packages.yml").read_text(),
}


def extract_parser() -> str:
    """Pull the embedded python heredoc out of apply-packages.sh."""
    text = SCRIPT.read_text()
    match = re.search(r"<<'PY'\n(.*?)\nPY\n", text, re.DOTALL)
    if not match:
        raise AssertionError("could not find the embedded parser in apply-packages.sh")
    return match.group(1)


def lookup(data: dict, dotted: str) -> list:
    node = data
    for part in dotted.split("."):
        node = node.get(part) if isinstance(node, dict) else None
    return node or []


def main() -> int:
    parser_src = extract_parser()
    failures = 0

    with tempfile.TemporaryDirectory() as tmp:
        parser = Path(tmp) / "parser.py"
        parser.write_text(parser_src)
        case_file = Path(tmp) / "case.yml"

        for name, text in CASES.items():
            case_file.write_text(text)
            truth = yaml.safe_load(text)
            for key in KEYS:
                expected = lookup(truth, key)
                result = subprocess.run(
                    [sys.executable, str(parser), str(case_file), key],
                    capture_output=True,
                    text=True,
                    check=True,
                )
                got = [line for line in result.stdout.split("\n") if line]
                if got != expected:
                    print(f"  MISMATCH  {name} / {key}")
                    print(f"      pyyaml:     {expected}")
                    print(f"      restricted: {got}")
                    failures += 1
            if not failures:
                print(f"  ok  {name}")

    if failures:
        print(f"\npackages-parser: {failures} disagreement(s) with PyYAML")
        return 1
    print(f"\npackages-parser: agrees with PyYAML across {len(CASES)} cases")
    return 0


if __name__ == "__main__":
    sys.exit(main())
