#!/usr/bin/env python3
"""Prove os/scripts/build/apply-packages.sh handles packages.yml correctly.

This test drives the REAL script, with `dnf` and `systemctl` replaced by stubs
that record their arguments. It then compares what the script would actually
have installed, removed and masked against what PyYAML says the manifest means.

It used to test the parser heredoc in isolation, extracted out of the script.
That was worthless in the way that matters: the parser was made strict and
correct, while the call site threw its exit status away (`< <(cmd)` does not
propagate status), so every strict rejection became four empty lists and a green
build. The isolated test passed throughout. A test that does not exercise the
shipped artifact proves nothing about the shipped artifact.

Two properties are asserted:

  1. For manifests in the canonical form, the packages the script acts on are
     exactly the ones PyYAML reads.
  2. For manifests the parser cannot read unambiguously, the script EXITS
     NON-ZERO. Silently proceeding with a partial list is the failure mode that
     would remove a driver from someone's machine.
"""

from __future__ import annotations

import os
import subprocess
import sys
import tempfile
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "os" / "scripts" / "build" / "apply-packages.sh"

# Manifests in the canonical form: the script must act on exactly PyYAML's lists.
CANONICAL = {
    "empty lists": "version: 1\nadd: []\nremove: []\nsystemd:\n  mask: []\n  disable: []\n",
    "block lists": (
        "version: 1\nadd:\n  - haruna\n  - thermald\nremove:\n  - kmail\n"
        "systemd:\n  mask:\n    - baloo_file.service\n  disable:\n    - foo.timer\n"
    ),
    "inline lists": (
        "version: 1\nadd: [a, b, c]\nremove: [x]\n"
        "systemd:\n  mask: [m.service]\n  disable: []\n"
    ),
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

# Valid YAML that also passes packages.schema.json, but that the parser cannot
# read unambiguously. Each must make the SCRIPT exit non-zero. Every entry here
# was found by an independent reviewer, not by imagination.
MUST_REJECT = {
    "multi-line flow sequence": "version: 1\nadd: [\n  haruna,\n  thermald\n]\nremove: []\n",
    "quoted key": 'version: 1\n"add":\n  - haruna\nremove: []\n',
    "anchor and alias": "version: 1\nadd: &pkgs\n  - haruna\nremove: *pkgs\n",
    "duplicate key": "version: 1\nadd:\n  - haruna\nadd:\n  - thermald\nremove: []\n",
    "odd indentation": (
        "version: 1\nadd: []\nremove: []\nsystemd:\n mask:\n   - baloo.service\n"
    ),
    "space before colon": "version: 1\nadd : [haruna]\nremove: []\n",
    "flow mapping": (
        "version: 1\nadd: []\nremove: []\nsystemd: {mask: [a.service], disable: []}\n"
    ),
    "yaml tag": (
        "version: 1\nadd: []\nremove: []\n"
        "systemd:\n  mask:\n    - !!str foo.service\n  disable: []\n"
    ),
    "backslash escape": 'version: 1\nadd:\n  - "haruna\\x2Dextra"\nremove: []\n',
}

STUB = """#!/bin/sh
# Records the call instead of touching a real system.
printf '%s %s\\n' "$(basename "$0")" "$*" >> "$STUB_LOG"
exit 0
"""


def make_stubs(bindir: Path) -> None:
    """dnf and systemctl stubs that log their arguments."""
    for name in ("dnf", "systemctl"):
        stub = bindir / name
        stub.write_text(STUB)
        stub.chmod(0o755)


def run_script(manifest: Path, bindir: Path, log: Path) -> tuple[int, str, str]:
    env = dict(os.environ)
    env["PATH"] = f"{bindir}:{env['PATH']}"
    env["STUB_LOG"] = str(log)
    if log.exists():
        log.unlink()
    result = subprocess.run(
        ["bash", str(SCRIPT), str(manifest)],
        capture_output=True,
        text=True,
        env=env,
        check=False,
    )
    actions = log.read_text() if log.exists() else ""
    return result.returncode, result.stdout + result.stderr, actions


def expected_actions(text: str) -> dict[str, list[str]]:
    data = yaml.safe_load(text) or {}
    systemd = data.get("systemd") or {}
    return {
        "add": data.get("add") or [],
        "remove": data.get("remove") or [],
        "mask": systemd.get("mask") or [],
        "disable": systemd.get("disable") or [],
    }


def observed_actions(actions: str) -> dict[str, list[str]]:
    seen: dict[str, list[str]] = {"add": [], "remove": [], "mask": [], "disable": []}
    for line in actions.split("\n"):
        parts = line.split()
        if not parts:
            continue
        tool, args = parts[0], parts[1:]
        if tool == "dnf" and "install" in args:
            seen["add"] += [a for a in args if a not in ("-y", "install")]
        elif tool == "dnf" and "remove" in args:
            seen["remove"] += [a for a in args if a not in ("-y", "remove")]
        elif tool == "systemctl" and args and args[0] in ("mask", "disable"):
            seen[args[0]] += args[1:]
    return seen


def main() -> int:
    failures = 0

    with tempfile.TemporaryDirectory() as tmp:
        tmpdir = Path(tmp)
        bindir = tmpdir / "bin"
        bindir.mkdir()
        make_stubs(bindir)
        log = tmpdir / "actions.log"
        manifest = tmpdir / "packages.yml"

        print("canonical manifests — the script must act on exactly PyYAML's lists")
        for name, text in CANONICAL.items():
            manifest.write_text(text)
            code, output, actions = run_script(manifest, bindir, log)
            if code != 0:
                print(f"  FAIL  {name}: script exited {code}")
                print("      " + output.strip().replace("\n", "\n      "))
                failures += 1
                continue
            want, got = expected_actions(text), observed_actions(actions)
            if want != got:
                print(f"  FAIL  {name}: acted on the wrong packages")
                for key in want:
                    if want[key] != got[key]:
                        print(f"      {key}: pyyaml={want[key]} script={got[key]}")
                failures += 1
            else:
                total = sum(len(v) for v in want.values())
                print(f"  ok    {name}  ({total} action(s) matched)")

        print("\nambiguous manifests — the script must refuse, not proceed partially")
        for name, text in MUST_REJECT.items():
            manifest.write_text(text)
            code, output, actions = run_script(manifest, bindir, log)
            if code == 0:
                print(
                    f"  FAIL  {name}: script exited 0 and acted on {observed_actions(actions)}"
                )
                print(
                    "      Refusing loudly is required; proceeding with a partial list is not."
                )
                failures += 1
            elif actions.strip():
                print(
                    f"  FAIL  {name}: exited {code} but had already acted: {actions.strip()!r}"
                )
                failures += 1
            else:
                reason = next(
                    (ln.split(": ", 2)[-1] for ln in output.split("\n") if ": " in ln),
                    "",
                )
                print(f"  reject  {name}  ({reason.strip()})")

    if failures:
        print(f"\npackages-parser: {failures} failure(s)")
        return 1
    print(
        f"\npackages-parser: {len(CANONICAL)} canonical manifests act exactly as PyYAML "
        f"reads them; {len(MUST_REJECT)} ambiguous ones are refused with no side effects"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
