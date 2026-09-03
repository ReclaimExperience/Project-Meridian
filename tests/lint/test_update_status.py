#!/usr/bin/env python3
"""The update-status contract (PRD 8.0), driven against the real publisher.

bootc is daemonless and exposes no D-Bus API, so `/run/meridian/update-status.json`
is not a convenience — it IS the interface between WP-04's update machinery and
WP-12's Settings page. WP-12 does not exist yet, which is exactly why this test
does: a contract nobody can build against until both sides are finished is not a
contract, it is a hope.

So this drives the shipped script with a stubbed `bootc` and validates what comes
out against the committed schema. Every state WP-12 has to render is produced
here, including the two that only happen on a bad day.

The atomicity check is not decoration. Settings reads this file on a timer; if it
can observe a half-written document it shows a parse error to a user who did
nothing wrong, and the bug is unreproducible by definition.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
PUBLISHER = (
    ROOT / "os" / "rootfs" / "usr" / "libexec" / "meridian" / "publish-update-status"
)
SCHEMA = ROOT / "catalog" / "schemas" / "update-status.schema.json"

BOOTC_IDLE = json.dumps(
    {
        "status": {
            "booted": {
                "image": {
                    "image": {
                        "image": "ghcr.io/reclaimexperience/project-meridian:stable"
                    },
                    "version": "1.0.0",
                    "timestamp": "2026-09-01T00:00:00Z",
                }
            },
            "staged": None,
        }
    }
)
BOOTC_STAGED = json.dumps(
    {
        "status": {
            "booted": {
                "image": {
                    "image": {
                        "image": "ghcr.io/reclaimexperience/project-meridian:stable"
                    },
                    "version": "1.0.0",
                    "timestamp": "2026-09-01T00:00:00Z",
                }
            },
            "staged": {
                "image": {
                    "image": {
                        "image": "ghcr.io/reclaimexperience/project-meridian:stable"
                    },
                    "version": "1.0.1",
                    "timestamp": "2026-09-03T00:00:00Z",
                }
            },
        }
    }
)


def run_publisher(
    tmp: Path, bootc_json: str | None, rollback: bool, state_arg: str | None = None
) -> tuple[int, str, dict | None]:
    bindir = tmp / "bin"
    bindir.mkdir(exist_ok=True)
    if bootc_json is None:
        (bindir / "bootc").unlink(missing_ok=True)
    else:
        stub = bindir / "bootc"
        stub.write_text(f"#!/bin/sh\ncat <<'JSON'\n{bootc_json}\nJSON\n")
        stub.chmod(0o755)

    out = tmp / "update-status.json"
    out.unlink(missing_ok=True)
    marker = tmp / "rollback-happened"
    if rollback:
        marker.write_text("2026-09-03T02:00:00+00:00\n")
    else:
        marker.unlink(missing_ok=True)

    source = PUBLISHER.read_text()
    source = source.replace("OUT=/run/meridian/update-status.json", f"OUT={out}")
    source = source.replace(
        "ROLLBACK_MARKER=/var/lib/meridian/rollback-happened",
        f"ROLLBACK_MARKER={marker}",
    )
    driver = tmp / "publish"
    driver.write_text(source)
    driver.chmod(0o755)

    env = dict(os.environ)
    env["PATH"] = f"{bindir}:{env['PATH']}"
    cmd = ["bash", str(driver)] + ([state_arg] if state_arg else [])
    result = subprocess.run(cmd, capture_output=True, text=True, env=env, check=False)
    document = None
    if out.exists():
        try:
            document = json.loads(out.read_text())
        except ValueError:
            document = {"__unparseable__": out.read_text()}
    return result.returncode, result.stdout + result.stderr, document


def main() -> int:
    from jsonschema import Draft202012Validator

    schema = json.loads(SCHEMA.read_text())
    Draft202012Validator.check_schema(schema)
    validator = Draft202012Validator(schema)
    failures = 0

    cases = [
        ("nothing staged", BOOTC_IDLE, False, None, "up-to-date"),
        ("an update is staged", BOOTC_STAGED, False, None, "staged"),
        ("the machine rolled itself back", BOOTC_IDLE, True, None, "rolled-back"),
        ("the check failed", BOOTC_IDLE, False, "error", "error"),
        ("bootc is absent entirely", None, False, None, "up-to-date"),
    ]

    with tempfile.TemporaryDirectory() as tmpdir:
        tmp = Path(tmpdir)
        print("every state WP-12 must render is produced, and validates")
        for name, bootc_json, rollback, state_arg, want_state in cases:
            code, output, doc = run_publisher(tmp, bootc_json, rollback, state_arg)
            if code != 0 or doc is None:
                print(f"  FAIL  {name}: exit={code}, no document")
                print("      " + output.strip().replace("\n", "\n      "))
                failures += 1
                continue
            errors = list(validator.iter_errors(doc))
            if errors:
                print(f"  FAIL  {name}: does not match the committed contract")
                for err in errors[:3]:
                    print(f"      {list(err.path)}: {err.message}")
                failures += 1
            elif doc["state"] != want_state:
                print(
                    f"  FAIL  {name}: state is {doc['state']!r}, wanted {want_state!r}"
                )
                failures += 1
            else:
                print(f"  ok    {name} -> state={doc['state']!r}")

        # A rollback must not be silently outranked by an available update: the
        # machine healing itself is the one thing the user is owed an explanation
        # for, and "staged" would hide it behind good news.
        print("\na rollback is never hidden behind an available update")
        _code, _out, doc = run_publisher(tmp, BOOTC_STAGED, True, None)
        if doc and doc["state"] == "rolled-back" and doc["rollback"]["happened"]:
            print("  ok    rolled-back outranks staged")
        else:
            print(
                f"  FAIL  state is {doc and doc['state']!r} with a rollback marker present"
            )
            failures += 1

        print("\nthe file is written atomically")
        source = PUBLISHER.read_text()
        if "mktemp" in source and "mv " in source:
            print("  ok    written to a temp file and moved into place")
        else:
            print("  FAIL  the publisher writes in place; Settings polls this file")
            print("      and can observe a half-written document, which shows a")
            print("      parse error to a user who did nothing wrong.")
            failures += 1

        print("\nit is world-readable — Settings runs as the user, not as root")
        _code, _out, _doc = run_publisher(tmp, BOOTC_IDLE, False, None)
        written = tmp / "update-status.json"
        mode = written.stat().st_mode & 0o777
        if mode & 0o044:
            print(f"  ok    mode {mode:04o}")
        else:
            print(f"  FAIL  mode {mode:04o} — the consumer cannot read it")
            failures += 1

    print()
    if failures:
        print(f"update-status: {failures} failure(s)")
        return 1
    print(
        f"update-status: {len(cases)} state(s) validate against the committed "
        "contract, atomically written and readable by the consumer"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
