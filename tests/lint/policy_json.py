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
import re
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


def parser_verdict(policy_path: Path) -> tuple[str, str]:
    """Ask containers-image itself. Returns (verdict, detail).

    verdict is "accepted", "unknown-key:<key>", "rejected", or "no-skopeo".

    The distinction matters because the local parser is NOT the one that will
    read this file. Ubuntu 24.04's skopeo is 1.13.3 and rejects `keyPaths`;
    Fedora 44 — what the IMAGE ships — is 1.22 and accepts it. A check that
    fails on a correct policy is exactly as harmful as one that passes a broken
    one, and this check did the former in CI while passing locally.
    """
    if not shutil.which("skopeo"):
        return "no-skopeo", ""
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
    output = result.stdout + result.stderr
    if "invalid policy" not in output:
        return "accepted", ""
    match = re.search(r'Unknown key \\?"([^"\\]+)', output)
    if match:
        return f"unknown-key:{match.group(1)}", output.strip()[:200]
    return "rejected", output.strip()[:200]


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

        control, _detail = parser_verdict(bogus)
        if control == "no-skopeo":
            print("  skip  skopeo is not installed; the allowlist above stands alone")
        elif not control.startswith("unknown-key:"):
            print(f"  FAIL  positive control: a planted unknown key gave {control!r},")
            print("      so this parser is not enforcing anything and a pass below")
            print("      would mean nothing.")
            failures += 1
        else:
            print("  ok    positive control: a planted unknown key IS rejected")
            verdict, detail = parser_verdict(POLICY)
            if verdict == "accepted":
                print("  ok    containers-image accepts our shipped policy.json")
            elif verdict.startswith("unknown-key:"):
                key = verdict.split(":", 1)[1]
                if key in REQUIREMENT | TOP_LEVEL | IDENTITY:
                    # Version skew, not a defect. This local parser is older than
                    # the one the image ships, and the key is valid there.
                    version = subprocess.run(
                        ["skopeo", "--version"],
                        capture_output=True,
                        text=True,
                        check=False,
                    ).stdout.strip()
                    print(f"  note  this skopeo does not know {key!r} — VERSION SKEW,")
                    print(f"      not a defect. {version}")
                    print("      The image ships containers-common 0.67.0, which")
                    print(f"      supports {key!r}; Ubuntu 24.04's skopeo 1.13.3 does")
                    print("      not. The allowlist above is the authority here.")
                    print("      Portability note: policy.json needs a consumer new")
                    print(f"      enough for {key!r}.")
                else:
                    print(f"  FAIL  containers-image rejects an unknown key {key!r},")
                    print("      and it is not one containers-policy.json(5) defines.")
                    print(f"      {detail}")
                    failures += 1
            else:
                print(f"  FAIL  containers-image rejects our policy: {detail}")
                failures += 1

    print()
    if failures:
        print(f"policy-json: {failures} failure(s)")
        return 1
    print("policy-json: parses under containers-image's rules")
    return 0


if __name__ == "__main__":
    sys.exit(main())
