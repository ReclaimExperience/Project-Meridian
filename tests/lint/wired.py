#!/usr/bin/env python3
"""Every check that exists must actually be executed by something.

The outermost form of a vacuous pass: not a check that passes wrongly, but a
check that never runs at all. `just lint` and `just test-lint` enumerate their
sub-checks by hand, and the CI workflows name `ci/*.sh` by hand, so a guard can
be written, committed, linted for style — and silently never invoked.

Demonstrated during review: two brand-new, always-failing checks were committed
under `tests/lint/` and `tests/harness/`, and `just lint`, `just test-lint` and
`ci/lint.sh` all reported success without running either.

This closes that at both levels:

  1. every check script under tests/ must be named by some Justfile recipe;
  2. every ci/*.sh must be invoked by some workflow, and the workflow jobs that
     matter must be in the committed required-checks list.

Level 2 matters because a step can be deleted from inside a job while the job
name — the thing branch protection actually requires — keeps reporting green.
"""

from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
JUSTFILE = ROOT / "Justfile"
WORKFLOWS = ROOT / ".github" / "workflows"

# Scripts under tests/ that are checks, and must therefore be invoked.
CHECK_GLOBS = (
    "tests/lint/*.py",
    "tests/lint/*.sh",
    "tests/harness/test_*.py",
    "tests/perf/*.sh",
)

# Support code that is imported rather than invoked. Anything added here is a
# claim that the file is not a check; keep it short and justified.
NOT_A_CHECK = {
    "tests/lint/strings-allow.txt",
}

# ci/*.sh that must be reachable from a workflow, with the job whose name branch
# protection requires. A step can be deleted from inside a job while the job
# keeps reporting green, so the pairing is what matters, not mere presence.
CI_SCRIPTS = {
    "ci/lint.sh": "lint",
    "ci/build.sh": "build",
    "ci/vm-test.sh": "build",
    "ci/check-no-test-user.sh": "build",
    "ci/prepare-runner.sh": "build",
    "ci/verify-signing-policy.sh": "build",
    "ci/sign-image.sh": "sign",
    "ci/negative-test-signing.sh": "sign",
}

# Job names branch protection requires on `main`. Kept here so a rename shows up
# in review as a change to this list.
REQUIRED_CHECKS = ("lint", "build-x86_64", "build-aarch64")


def tracked(pattern: str) -> list[str]:
    out = subprocess.run(
        ["git", "ls-files", pattern],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=True,
    )
    return [line for line in out.stdout.split("\n") if line]


def _invoked(path: str, justfile: str) -> bool:
    """Is this script run, directly or through one wrapper?

    `strings.py` and `codeowners.py` are invoked by their `.sh` wrappers rather
    than named in a recipe. That is one hop, not an exemption — so follow
    exactly one hop, through wrappers that are themselves named directly.

    Deliberately NOT recursive: a mutual-recursion version of this blew the
    stack, and because the crash was inside a `grep` pipeline the failure looked
    like a clean run. A check whose own failure mode is silence is the thing
    this file exists to prevent.
    """
    name = Path(path).name
    if name in justfile or path in justfile:
        return True
    for wrapper in tracked("tests/lint/*.sh") + tracked("ci/*.sh"):
        wrapper_name = Path(wrapper).name
        directly_named = wrapper_name in justfile or wrapper in justfile
        if not directly_named:
            continue
        if name in (ROOT / wrapper).read_text():
            return True
    return False


def main() -> int:
    failures = 0
    justfile = JUSTFILE.read_text()
    workflow_text = "\n".join(p.read_text() for p in sorted(WORKFLOWS.glob("*.yml")))

    # --- 1. every check script is invoked by a recipe -----------------------
    checked = 0
    for glob in CHECK_GLOBS:
        for path in tracked(glob):
            if path in NOT_A_CHECK:
                continue
            checked += 1
            if _invoked(path, justfile):
                continue
            failures += 1
            print(f"wired-lint: {path} is never run by any Justfile recipe.")
            print("    It is committed and style-linted, and it checks nothing,")
            print("    because nothing calls it. Add it to `lint` or `test-lint`.")

    # --- 2. every ci script is invoked by a workflow ------------------------
    for script, job in CI_SCRIPTS.items():
        if script not in workflow_text:
            failures += 1
            print(f"wired-lint: {script} is not invoked by any workflow.")
            print("    A gate that CI never runs is a gate in name only.")
            continue
        if job not in workflow_text:
            failures += 1
            print(f"wired-lint: {script} runs, but job {job!r} is not defined.")

    # --- 3. the required checks still exist ---------------------------------
    # A rename fails safe on GitHub (the required check never reports, so the
    # merge blocks), but it fails CONFUSINGLY. Name it here instead.
    job_names = set(re.findall(r"^\s*name:\s*(\S+)\s*$", workflow_text, re.MULTILINE))
    matrix_names = set(
        re.findall(r"name:\s*(\S+)-\$\{\{\s*matrix\.arch", workflow_text)
    )
    for required in REQUIRED_CHECKS:
        base = required.rsplit("-", 1)[0]
        if required in job_names or base in matrix_names or required in workflow_text:
            continue
        failures += 1
        print(f"wired-lint: branch protection requires the check {required!r},")
        print("    but no workflow produces a job with that name. Either the job")
        print("    was renamed or the protection list is stale; both mean the")
        print("    gate is not what it says it is.")

    if failures:
        print(f"\nwired-lint: {failures} check(s) exist but are not wired in")
        return 1
    print(
        f"wired-lint: clean ({checked} check script(s) invoked, "
        f"{len(CI_SCRIPTS)} ci script(s) reachable, "
        f"{len(REQUIRED_CHECKS)} required check(s) produced)"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
