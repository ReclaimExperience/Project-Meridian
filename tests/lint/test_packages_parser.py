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
        "protect:\n  - plasma-desktop\n"
        "systemd:\n  mask:\n    - baloo_file.service\n  disable:\n    - foo.timer\n"
    ),
    "inline lists": (
        "version: 1\nadd: [a, b, c]\nremove: [x]\nprotect: [plasma-desktop]\n"
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
    # --- block form -------------------------------------------------------
    "block yaml tag": (
        "version: 1\nadd: []\nremove: []\n"
        "systemd:\n  mask:\n    - !!str foo.service\n  disable: []\n"
    ),
    "block backslash escape": 'version: 1\nadd:\n  - "haruna\\x2Dextra"\nremove: []\n',
    "block anchor on an item": "version: 1\nadd:\n  - &a haruna\nremove: []\n",
    # --- flow form: the SAME defects, delivered the other way --------------
    #
    # These exist because a previous round guarded only the block branch while
    # the shipped os/packages.yml uses the flow form on every list. The guards
    # were on the path the real file never takes, and
    # `mask: ["baloo\x5Ffile.service"]` masked a nonexistent unit, exit 0.
    # Any new rule must be proven in BOTH forms or it is not proven.
    "flow yaml tag": "version: 1\nadd: [!!str haruna]\nremove: []\n",
    "flow backslash escape": 'version: 1\nadd: ["haruna\\x2Dextra"]\nremove: []\n',
    "flow anchor": "version: 1\nadd: [&a haruna]\nremove: []\n",
    "flow mask escape": (
        "version: 1\nadd: []\nremove: []\n"
        'systemd:\n  mask: ["baloo\\x5Ffile.service"]\n  disable: []\n'
    ),
    "flow unicode escape": 'version: 1\nadd: ["harun\\u0061"]\nremove: []\n',
    "flow whitespace in element": 'version: 1\nadd: ["two words"]\nremove: []\n',
    # --- structure: an absent key is not an empty one ----------------------
    "missing add key": "version: 1\nremove: []\n",
    "typo'd keys": "version: 1\nadds:\n  - alpha\nremoves:\n  - beta\n",
    "empty file": "",
    # Fail-open cases: YAML a real reader refuses, or structure that silently
    # produced an empty list. Found in round four.
    "multiple documents": "version: 1\nadd: [alpha]\n---\nremove: []\n",
    "tab indentation": "version: 1\nadd:\n\t- alpha\nremove: []\n",
    "mapping under a list key": "version: 1\nadd:\n  sub:\n    - evil\nremove: []\n",
}

# `rpm` has to actually work now: apply-packages.sh snapshots the installed set
# before and after the removal. A stub that prints nothing makes both snapshots
# empty, so the cascade guard sees no casualties and passes vacuously — the
# exact shape of pass this suite exists to prevent. This one reads a real file.
RPM_STUB = """#!/bin/sh
case "$1" in
  -qa) cat "$RPM_DB" ;;
  -q)  grep -qx "$2" "$RPM_DB" || { echo "package $2 is not installed"; exit 1; }
       echo "$2" ;;
esac
exit 0
"""

# `dnf remove` that mutates the fake database AND applies a cascade map, because
# taking dependents with it is the behaviour under test, not an edge case.
DNF_CASCADE_STUB = """#!/bin/sh
printf '%s %s\\n' "$(basename "$0")" "$*" >> "$STUB_LOG"
case "$*" in
  *remove*)
    for pkg in "$@"; do
      case "$pkg" in -*|remove|install) continue ;; esac
      for victim in "$pkg" $(awk -v p="$pkg" '$1==p {print $2}' "$CASCADE_MAP"); do
        grep -vx "$victim" "$RPM_DB" > "$RPM_DB.new" || true
        mv "$RPM_DB.new" "$RPM_DB"
      done
    done ;;
esac
exit 0
"""

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
    rpm = bindir / "rpm"
    rpm.write_text(RPM_STUB)
    rpm.chmod(0o755)


def run_script(manifest: Path, bindir: Path, log: Path) -> tuple[int, str, str]:
    env = dict(os.environ)
    env["PATH"] = f"{bindir}:{env['PATH']}"
    env["STUB_LOG"] = str(log)

    # These cases ask one question: which packages does the script act on? The
    # rpm database just has to be consistent with a successful run, so it holds
    # the protected packages (installed, and they survive) and none of the
    # removals (already gone, so nothing lingers). Removal SEMANTICS — cascades,
    # survivors, vacuous protection — are the cascade suite's job, with a stub
    # that mutates this database for real.
    db = bindir.parent / "rpmdb-canonical"
    try:
        declared = yaml.safe_load(manifest.read_text()) or {}
        protect = declared.get("protect") or []
    except (yaml.YAMLError, AttributeError):
        protect = []
    db.write_text("".join(f"{p}\n" for p in protect))
    env["RPM_DB"] = str(db)

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

        # Ignore flags, not just the two literals: the install line carries
        # --setopt=install_weak_deps=False, and treating a flag as a package
        # name made every canonical case fail.
        def names(items):
            return [
                a
                for a in items
                if not a.startswith("-") and a not in ("install", "remove")
            ]

        if tool == "dnf" and "install" in args:
            seen["add"] += names(args)
        elif tool == "dnf" and "remove" in args:
            seen["remove"] += names(args)
        elif tool == "systemctl" and args and args[0] in ("mask", "disable"):
            seen[args[0]] += args[1:]
    return seen


def schema_valid(text: str) -> bool:
    """Does this manifest pass catalog/schemas/packages.schema.json?"""
    import json

    from jsonschema import Draft202012Validator

    schema = json.loads((ROOT / "catalog/schemas/packages.schema.json").read_text())
    try:
        data = yaml.safe_load(text)
    except yaml.YAMLError:
        return False
    return not list(Draft202012Validator(schema).iter_errors(data))


# Cascade scenarios. Each is (manifest, installed, cascade map, must_fail,
# expected substring). These are regression tests for a build that reported
# EXIT=0 while having deleted the entire desktop.
CASCADES = {
    "a removal that takes the desktop must fail the build": (
        (
            "version: 1\nadd: []\nremove: [kmenuedit]\n"
            "protect: [plasma-desktop, sddm]\nsystemd:\n  mask: []\n  disable: []\n"
        ),
        ["kmenuedit", "plasma-desktop", "sddm", "kwin"],
        "kmenuedit plasma-desktop\nkmenuedit sddm\n",
        True,
        "plasma-desktop",
    ),
    "ordinary companion subpackages are reported, not fatal": (
        (
            "version: 1\nadd: []\nremove: [firefox]\n"
            "protect: [plasma-desktop]\nsystemd:\n  mask: []\n  disable: []\n"
        ),
        ["firefox", "firefox-langpacks", "plasma-desktop"],
        "firefox firefox-langpacks\n",
        False,
        "firefox-langpacks",
    ),
    "a package that survives its own removal must fail the build": (
        (
            "version: 1\nadd: []\nremove: [plasma-welcome]\n"
            "protect: [plasma-desktop]\nsystemd:\n  mask: []\n  disable: []\n"
        ),
        ["plasma-welcome", "plasma-desktop"],
        "",  # no cascade, and the stub is told to remove nothing
        True,
        "STILL installed",
    ),
    "a protect entry that is not installed must fail the build": (
        (
            "version: 1\nadd: []\nremove: [firefox]\n"
            "protect: [plasma-desktop, sddm]\nsystemd:\n  mask: []\n  disable: []\n"
        ),
        # sddm is absent — exactly the real case: Fedora 44 replaced it with
        # plasma-login-manager, so the entry guarded nothing and read as though
        # it did.
        ["firefox", "plasma-desktop"],
        "",
        True,
        "not installed",
    ),
    "removing without a protect list must fail closed": (
        (
            "version: 1\nadd: []\nremove: [kmenuedit]\nprotect: []\n"
            "systemd:\n  mask: []\n  disable: []\n"
        ),
        ["kmenuedit", "plasma-desktop"],
        "",
        True,
        "no 'protect:' list",
    ),
}


def run_cascades(tmpdir: Path) -> int:
    """Drive the real script against a fake rpm database that cascades."""
    failures = 0
    print("\ncascade guards — a build must not delete the desktop and exit 0")
    for name, (manifest_text, installed, cmap, must_fail, expect) in CASCADES.items():
        bindir = tmpdir / "cascade-bin"
        bindir.mkdir(exist_ok=True)
        make_stubs(bindir)
        # The inert dnf stub for the "survives its own removal" case: it logs
        # and changes nothing, which is exactly what a weak-dep reinstall looks
        # like from outside.
        dnf = bindir / "dnf"
        dnf.write_text(STUB if not cmap and "STILL" in expect else DNF_CASCADE_STUB)
        dnf.chmod(0o755)

        db = tmpdir / "rpmdb"
        db.write_text("".join(f"{p}\n" for p in installed))
        cascade_map = tmpdir / "cascade"
        cascade_map.write_text(cmap)
        manifest = tmpdir / "cascade.yml"
        manifest.write_text(manifest_text)

        env = dict(os.environ)
        env["PATH"] = f"{bindir}:{env['PATH']}"
        env["STUB_LOG"] = str(tmpdir / "cascade.log")
        env["RPM_DB"] = str(db)
        env["CASCADE_MAP"] = str(cascade_map)
        result = subprocess.run(
            ["bash", str(SCRIPT), str(manifest)],
            capture_output=True,
            text=True,
            env=env,
            check=False,
        )
        output = result.stdout + result.stderr
        failed = result.returncode != 0

        if failed != must_fail:
            want = "fail" if must_fail else "succeed"
            print(f"  FAIL  {name}")
            print(f"      expected the script to {want}; it exited {result.returncode}")
            print("      " + output.strip().replace("\n", "\n      "))
            failures += 1
        elif expect not in output:
            print(f"  FAIL  {name}")
            print(f"      exited {result.returncode} as expected, but never mentioned")
            print(f"      {expect!r} — the operator cannot act on a failure they")
            print("      cannot read.")
            failures += 1
        else:
            verb = "refused" if must_fail else "allowed"
            print(f"  ok    {name}  ({verb}, naming {expect!r})")
    return failures


def main() -> int:
    failures = 0

    # A rejection case only proves something if the input is one the schema
    # would let through. Otherwise the test is asserting that the parser refuses
    # input nothing would ever hand it. Structural cases are exempt: they are
    # the ones the schema itself catches, and the point is that the build path
    # never runs the schema.
    # Cases the schema itself also rejects. They still belong in the suite —
    # the build path never runs the schema — but they are not evidence about
    # schema-valid input, so they are exempt from the check above.
    STRUCTURAL = {
        "missing add key",
        "typo'd keys",
        "empty file",
        "flow whitespace in element",
        "multiple documents",
        "tab indentation",
        "mapping under a list key",
    }
    for name, text in MUST_REJECT.items():
        if name in STRUCTURAL:
            continue
        if not schema_valid(text):
            print(f"  WEAK CASE  '{name}' does not pass packages.schema.json,")
            print("      so refusing it proves nothing about real-world input.")
            failures += 1

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

        failures += run_cascades(tmpdir)

    if failures:
        print(f"\npackages-parser: {failures} failure(s)")
        return 1
    print(
        f"\npackages-parser: {len(CANONICAL)} canonical manifests act exactly as PyYAML "
        f"reads them; {len(MUST_REJECT)} ambiguous ones are refused with no side "
        f"effects; {len(CASCADES)} cascade scenario(s) behave correctly"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
