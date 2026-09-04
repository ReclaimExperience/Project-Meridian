#!/usr/bin/env python3
"""os/rootfs/etc/containers/policy.json must parse under containers-image.

It shipped with a `_comment` key. JSON has no comment syntax, so I invented one —
against a parser I had personally proved rejects unknown keys, hours earlier,
with a probe that returned `Unknown key "totallyMadeUpField"`.

The consequence was not cosmetic. `bootc install to-filesystem` reads this file,
so the DISK IMAGE BUILD failed:

    error: Installing to filesystem: Creating ostree deployment:
    invalid policy in "/etc/containers/policy.json": Unknown key "_comment"

An unusable image, from a file that is valid JSON, passes every schema check we
had, and reads perfectly well to a person.

This check is deliberately in two parts:

  1. a KEY ALLOWLIST, which runs everywhere, including the macOS dev loop where
     there is no containers-image to ask;
  2. the REAL PARSER when skopeo is available, because an allowlist is my model
     of the schema and the parser is the schema. A positive control runs first —
     a policy with a planted bogus key must be rejected — since a parser check
     that cannot fail proves nothing.
"""

from __future__ import annotations

import json
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
POLICY = ROOT / "os" / "rootfs" / "etc" / "containers" / "policy.json"

# From containers-policy.json(5). Anything outside this is rejected at parse
# time by every consumer, bootc install included.
TOP_LEVEL = {"default", "transports"}
REQUIREMENT = {
    "type",
    "keyPath",
    "keyPaths",
    "keyData",
    "keyDatas",
    "fulcio",
    "rekorPublicKeyPath",
    "rekorPublicKeyData",
    "signedIdentity",
    "keyType",
    "pkiRoots",
    "pkiIntermediates",
    "subjectEmail",
}
IDENTITY = {"type", "dockerReference", "dockerRepository", "prefix", "signedPrefix"}


def check_keys(document: dict) -> list[str]:
    problems = []
    extra = set(document) - TOP_LEVEL
    if extra:
        problems.append(f"top level has unknown key(s): {sorted(extra)}")
    for scope, requirements in (
        document.get("transports", {}).get("docker", {})
    ).items():
        for requirement in requirements:
            unknown = set(requirement) - REQUIREMENT
            if unknown:
                problems.append(f"{scope}: unknown key(s) {sorted(unknown)}")
            identity = requirement.get("signedIdentity") or {}
            unknown_identity = set(identity) - IDENTITY
            if unknown_identity:
                problems.append(f"{scope}: signedIdentity {sorted(unknown_identity)}")
    for requirement in document.get("default", []):
        unknown = set(requirement) - REQUIREMENT
        if unknown:
            problems.append(f"default: unknown key(s) {sorted(unknown)}")
    return problems


def parser_rejects(policy_path: Path) -> bool | None:
    """Ask containers-image itself. None when skopeo is unavailable."""
    if not shutil.which("skopeo"):
        return None
    result = subprocess.run(
        [
            "skopeo",
            "--policy",
            str(policy_path),
            "copy",
            "docker://quay.io/fedora/fedora:44",
            f"dir:{tempfile.mkdtemp()}/out",
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    return "invalid policy" in (result.stdout + result.stderr)


def main() -> int:
    failures = 0
    document = json.loads(POLICY.read_text())

    print("key allowlist (runs everywhere, including the macOS dev loop)")
    problems = check_keys(document)
    for problem in problems:
        print(f"  FAIL  {problem}")
        print("      containers-image rejects unknown keys outright, and")
        print("      `bootc install to-filesystem` reads this file — so an unknown")
        print("      key does not degrade anything, it makes the image unbuildable.")
    failures += len(problems)
    if not problems:
        print("  ok    every key is one containers-policy.json(5) defines")

    print("\nthe real parser (skopeo), when it is available")
    with tempfile.TemporaryDirectory() as tmp:
        # Positive control FIRST: a check that cannot fail proves nothing.
        bogus = Path(tmp) / "bogus.json"
        planted = json.loads(POLICY.read_text())
        planted["_comment"] = ["exactly the key that broke the disk image build"]
        bogus.write_text(json.dumps(planted))

        control = parser_rejects(bogus)
        if control is None:
            print("  skip  skopeo is not installed; the allowlist above stands alone")
        elif not control:
            print("  FAIL  positive control: a policy with a planted unknown key was")
            print("      ACCEPTED, so this parser is not enforcing anything and a")
            print("      pass below would mean nothing.")
            failures += 1
        else:
            print("  ok    positive control: a planted unknown key IS rejected")
            if parser_rejects(POLICY):
                print("  FAIL  containers-image rejects our shipped policy.json.")
                failures += 1
            else:
                print("  ok    containers-image accepts our shipped policy.json")

    print()
    if failures:
        print(f"policy-json: {failures} failure(s)")
        return 1
    print("policy-json: parses under containers-image's rules")
    return 0


if __name__ == "__main__":
    sys.exit(main())
