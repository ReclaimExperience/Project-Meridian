#!/usr/bin/env python3
"""Regression tests for the two vacuous-pass blockers (WP-03 review round 1).

Both blockers were "the suite reports green while its property is false". They
were fixed and verified by hand — but a one-time manual check is not a guard,
and nothing in the repo could have caught either being reopened. These are that
guard, and they need no VM.

  BL-1  the privacy audit passed on an EMPTY capture
  BL-2  the credential check reported clean when the probe never ran

Also covers NEW-1, the worst of the two rounds: every suite states its verdict
with `assert`, so running under -O would have turned the whole harness into a
rubber stamp.
"""

from __future__ import annotations

import struct
import subprocess
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

ROOT = Path(__file__).resolve().parents[2]


def pcap_bytes(frames: list[bytes]) -> bytes:
    out = [struct.pack("<IHHiIII", 0xA1B2C3D4, 2, 4, 0, 0, 65535, 1)]
    for frame in frames:
        out.append(struct.pack("<IIII", 0, 0, len(frame), len(frame)) + frame)
    return b"".join(out)


class FakeConsole:
    def login(self, *_a, **_k):
        return None

    def wait_until(self, *_a, **_k):
        return "running"

    def run(self, *_a, **_k):
        return 0, ""


class FakeVM:
    """Just enough VM for a suite that only reads the capture."""

    def __init__(self, capture_file: Path):
        self.capture = True
        self.capture_file = capture_file
        self.evidence = capture_file.parent
        self.arch = "test"
        self.console = FakeConsole()

    def write_report(self, *_a, **_k):
        return None


def check(name: str, condition: bool, detail: str = "") -> int:
    print(
        f"  {'ok  ' if condition else 'FAIL'}  {name}"
        + (f": {detail}" if detail else "")
    )
    return 0 if condition else 1


def main() -> int:
    import os

    os.environ["MERIDIAN_IDLE_SECONDS"] = "0"
    from harness.suites import privacy

    failures = 0
    with tempfile.TemporaryDirectory() as tmp:
        capture = Path(tmp) / "c.pcap"

        # BL-1: an empty capture must FAIL, not read as a quiet system.
        capture.write_bytes(pcap_bytes([]))
        try:
            privacy.run(FakeVM(capture), {"user": "u", "password": "p"})
            failures += check(
                "BL-1 empty capture is refused",
                False,
                "the audit PASSED while observing nothing",
            )
        except AssertionError as exc:
            failures += check(
                "BL-1 empty capture is refused", "no DHCP or DNS" in str(exc)
            )

        # ...and a missing capture likewise.
        capture.unlink()
        try:
            privacy.run(FakeVM(capture), {"user": "u", "password": "p"})
            failures += check(
                "BL-1 missing capture is refused", False, "the audit PASSED"
            )
        except AssertionError:
            failures += check("BL-1 missing capture is refused", True)

    # BL-2: the credential check must not report clean when the probe never ran.
    #
    # The stub must let `image exists` and `pull` SUCCEED and fail only at `run`.
    # An earlier version of this test stubbed podman to fail at every
    # subcommand, so the script short-circuited at "could not obtain the image"
    # and never reached the sentinel logic that IS the fix — a regression test
    # that was itself a vacuous pass, green on a repo where the blocker had been
    # fully reopened.
    stubs = {
        "run fails silently (the original BL-2 shape)": 'case "$1" in image) exit 0;; run) exit 125;; *) exit 0;; esac',
        "run succeeds but emits nothing (no sentinel)": 'case "$1" in image) exit 0;; run) exit 0;; *) exit 0;; esac',
        "run emits a planted finding": 'case "$1" in image) exit 0;; '
        'run) echo __probe_ran__; echo "mtest in passwd: mtest:x:1001:"; exit 0;; '
        "*) exit 0;; esac",
    }
    for name, body in stubs.items():
        with tempfile.TemporaryDirectory() as tmp:
            bindir = Path(tmp) / "bin"
            bindir.mkdir()
            stub = bindir / "podman"
            stub.write_text(f"#!/bin/sh\n{body}\n")
            stub.chmod(0o755)
            env = dict(os.environ, PATH=f"{bindir}:{os.environ['PATH']}")
            result = subprocess.run(
                ["bash", str(ROOT / "ci/check-no-test-user.sh"), "example/image"],
                capture_output=True,
                text=True,
                env=env,
                check=False,
            )
            failures += check(
                f"BL-2 {name}",
                result.returncode != 0,
                f"exited {result.returncode}: {result.stdout.strip().splitlines()[-1:]}",
            )

    # ...and it must still PASS on a genuinely clean probe, or it is just a
    # check that always fails, which proves nothing either.
    with tempfile.TemporaryDirectory() as tmp:
        bindir = Path(tmp) / "bin"
        bindir.mkdir()
        stub = bindir / "podman"
        stub.write_text(
            '#!/bin/sh\ncase "$1" in image) exit 0;; '
            "run) echo __probe_ran__; exit 0;; *) exit 0;; esac\n"
        )
        stub.chmod(0o755)
        env = dict(os.environ, PATH=f"{bindir}:{os.environ['PATH']}")
        result = subprocess.run(
            ["bash", str(ROOT / "ci/check-no-test-user.sh"), "example/image"],
            capture_output=True,
            text=True,
            env=env,
            check=False,
        )
        failures += check(
            "BL-2 clean probe still passes",
            result.returncode == 0,
            f"exited {result.returncode}",
        )

    # NEW-1: assertions disabled must be refused, not silently honoured.
    result = subprocess.run(
        [sys.executable, "-O", str(ROOT / "tests/harness/run.py"), "smoke"],
        capture_output=True,
        text=True,
        check=False,
    )
    failures += check(
        "NEW-1 refuses to run with assertions disabled",
        result.returncode != 0
        and "assertions disabled" in result.stdout + result.stderr,
        f"exited {result.returncode}",
    )

    if failures:
        print(
            f"\nsuite-guards: {failures} failure(s) — a suite can pass while its property is false"
        )
        return 1
    print("\nsuite-guards: neither blocker can be silently reopened")
    return 0


if __name__ == "__main__":
    sys.exit(main())
