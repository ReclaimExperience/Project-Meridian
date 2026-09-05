#!/usr/bin/env python3
"""The boot floor must disarm a brick, and must not break a real rollback.

A machine was found dead at the bootloader in this state:

    boot_counter=-1   boot_success=0   saved_entry=1

...with exactly one entry in /boot/loader/entries. Fedora's ostree grub.cfg
sets `default=1` when the counter runs out WITHOUT checking that a second entry
exists, so GRUB was pointed at a deployment that was not there.

The dangerous half of this fix is the half that could break rollback: a service
that clears boot counters is one bad condition away from disabling the
self-healing it is protecting. So the case that must NOT be touched — a counter
armed WITH a rollback target present — is tested first-class, not as an
afterthought.

No VM: the script takes its grubenv and entries directory from the
environment, so the states are constructed as files.
"""

from __future__ import annotations

import os
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "os/rootfs/usr/libexec/meridian-boot-floor"

STUB = """#!/usr/bin/env bash
f="$1"; shift
case "$1" in
  list) cat "$f" 2>/dev/null ;;
  unset) shift; for k in "$@"; do sed -i.bak "/^$k=/d" "$f"; done ;;
  set) shift; for kv in "$@"; do k="${kv%%=*}"; sed -i.bak "/^$k=/d" "$f"; \
       echo "$kv" >> "$f"; done ;;
esac
exit 0
"""

# (name, entries, starting env, must_contain, must_not_contain)
CASES = [
    (
        "the wild brick: counter spent, one deployment",
        1,
        "boot_counter=-1\nboot_success=0\nsaved_entry=1\n",
        ["saved_entry=0"],
        ["boot_counter"],
    ),
    (
        "armed counter WITH a rollback target — must be left alone",
        2,
        "boot_counter=3\nboot_success=0\nsaved_entry=1\n",
        ["boot_counter=3", "saved_entry=1"],
        [],
    ),
    (
        "entry pointer past the end of a two-entry menu",
        2,
        "boot_success=0\nsaved_entry=7\n",
        ["saved_entry=0"],
        ["saved_entry=7"],
    ),
    (
        "healthy machine, nothing to do",
        2,
        "boot_success=1\nsaved_entry=0\n",
        ["boot_success=1", "saved_entry=0"],
        [],
    ),
]


def main() -> int:
    failures = 0
    for name, entries, start, must, must_not in CASES:
        with tempfile.TemporaryDirectory() as td:
            tmp = Path(td)
            bindir, entdir = tmp / "bin", tmp / "entries"
            bindir.mkdir()
            entdir.mkdir()
            stub = bindir / "grub2-editenv"
            stub.write_text(STUB)
            stub.chmod(0o755)
            for i in range(1, entries + 1):
                (entdir / f"ostree-{i}.conf").write_text("title x\n")
            env_file = tmp / "grubenv"
            env_file.write_text(start)

            environ = dict(os.environ)
            environ["PATH"] = f"{bindir}:{environ['PATH']}"
            environ["MERIDIAN_GRUBENV"] = str(env_file)
            environ["MERIDIAN_BLS_ENTRIES"] = str(entdir)
            proc = subprocess.run(
                ["bash", str(SCRIPT)], env=environ, capture_output=True, text=True
            )
            if proc.returncode != 0:
                print(f"FAIL [{name}]: exited {proc.returncode}: {proc.stderr[:200]}")
                failures += 1
                continue
            result = env_file.read_text()
            for token in must:
                if token not in result:
                    print(f"FAIL [{name}]: expected {token!r} in:\n{result}")
                    failures += 1
            for token in must_not:
                if token in result:
                    print(f"FAIL [{name}]: {token!r} should be gone, in:\n{result}")
                    failures += 1

    if failures:
        print(f"boot-floor: {failures} failure(s)")
        return 1
    print(f"boot-floor: {len(CASES)} state(s) — brick disarmed, real rollback untouched")
    return 0


if __name__ == "__main__":
    sys.exit(main())
