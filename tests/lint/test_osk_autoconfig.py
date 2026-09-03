#!/usr/bin/env python3
"""The on-screen-keyboard trim, driven against real udev output shapes.

ADR-017 clause 5 asks for the OSK to start only where there is a touchscreen.
Clause 4 forbids removing it. So the script has to get the HARDWARE QUESTION
right, and the two ways of being wrong are not symmetric:

    wrong on a touchless desktop  ->  72 MiB wasted, nobody notices
    wrong on a touch-only tablet  ->  the owner cannot type their password

Which means the interesting test is not "does it disable the keyboard" — it is
"does it refuse to disable the keyboard whenever it is not certain". A run with
no udevadm, an empty device database, or a database listing no input devices at
all must leave Plasma's default alone. Absence of evidence is not evidence of
absence, and here the difference is someone locked out of their machine.

Drives the real script with a stubbed `udevadm`, against a temporary kwinrc.
"""

from __future__ import annotations

import os
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "os" / "rootfs" / "usr" / "libexec" / "meridian" / "osk-autoconfig"

TOUCH_DB = """P: /devices/pci0000:00/0000:00:14.0/usb1/1-3/1-3:1.0/0003:04F3:24A1.0001
E: ID_INPUT=1
E: ID_INPUT_TOUCHSCREEN=1
E: NAME="ELAN Touchscreen"
"""

NO_TOUCH_DB = """P: /devices/platform/i8042/serio0/input/input3
E: ID_INPUT=1
E: ID_INPUT_KEYBOARD=1
E: NAME="AT Translated Set 2 keyboard"
P: /devices/platform/i8042/serio1/input/input5
E: ID_INPUT=1
E: ID_INPUT_TOUCHPAD=1
"""

# A database with no input devices at all. Something is wrong with the query,
# not with the hardware — so this must NOT be read as "no touchscreen".
NO_INPUTS_DB = """P: /devices/pci0000:00/0000:00:1f.2
E: ID_MODEL=SSD
"""

CASES = [
    ("touchscreen present", TOUCH_DB, 0, False, "keyboard left enabled"),
    ("keyboard and touchpad only", NO_TOUCH_DB, 0, True, "keyboard disabled"),
    ("database lists no input devices", NO_INPUTS_DB, 0, False, "left alone: unsure"),
    ("udevadm fails", "", 1, False, "left alone: unsure"),
    ("udevadm returns nothing", "", 0, False, "left alone: unsure"),
]


def run_case(tmp: Path, db: str, rc: int, existing: str | None) -> tuple[int, str, str]:
    bindir = tmp / "bin"
    bindir.mkdir(exist_ok=True)
    stub = bindir / "udevadm"
    stub.write_text(f"#!/bin/sh\ncat <<'DB'\n{db}\nDB\nexit {rc}\n")
    stub.chmod(0o755)

    kwinrc = tmp / "kwinrc"
    if existing is None:
        kwinrc.unlink(missing_ok=True)
    else:
        kwinrc.write_text(existing)

    env = dict(os.environ)
    env["PATH"] = f"{bindir}:{env['PATH']}"
    # The script writes /etc/xdg/kwinrc; point it at a temp file for the test.
    source = SCRIPT.read_text().replace("KWINRC=/etc/xdg/kwinrc", f"KWINRC={kwinrc}")
    driver = tmp / "osk-autoconfig"
    driver.write_text(source)
    driver.chmod(0o755)

    result = subprocess.run(
        ["bash", str(driver)], capture_output=True, text=True, env=env, check=False
    )
    written = kwinrc.read_text() if kwinrc.exists() else ""
    return result.returncode, result.stdout + result.stderr, written


def disabled(text: str) -> bool:
    return "InputMethod=" in text and "InputMethod=org" not in text


def main() -> int:
    failures = 0
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp = Path(tmpdir)

        print("hardware detection — when may the keyboard be turned off?")
        for name, db, rc, want_disabled, why in CASES:
            code, output, written = run_case(tmp, db, rc, None)
            got = disabled(written)
            if code != 0:
                print(f"  FAIL  {name}: script exited {code}")
                print("      " + output.strip().replace("\n", "\n      "))
                failures += 1
            elif got != want_disabled:
                print(f"  FAIL  {name}: expected {why}")
                print(f"      kwinrc is now {written!r}")
                if got:
                    print("      It DISABLED the on-screen keyboard without")
                    print("      establishing there is no touchscreen. On a tablet")
                    print("      that is a machine nobody can log in to.")
                failures += 1
            else:
                print(f"  ok    {name} -> {why}")

        print("\nthe decision must be revisited, not sticky")
        # A machine that gains a touchscreen (docked 2-in-1, replaced panel) must
        # get its keyboard back, so a previous disable has to be removed again.
        code, output, written = run_case(tmp, TOUCH_DB, 0, "[Wayland]\nInputMethod=\n")
        if disabled(written):
            print(
                "  FAIL  a previously-written disable survived a touchscreen appearing"
            )
            print(f"      kwinrc is still {written!r}")
            failures += 1
        else:
            print("  ok    an earlier disable is removed when a touchscreen appears")

        print("\nuser choice is never overwritten")
        code, output, written = run_case(
            tmp,
            NO_TOUCH_DB,
            0,
            "[Wayland]\nInputMethod=org.kde.plasma.keyboard.desktop\n",
        )
        if "org.kde.plasma.keyboard.desktop" not in written:
            print("  FAIL  it removed an explicit InputMethod someone had set.")
            print("      Turning the keyboard on is a choice a person can make;")
            print("      a memory optimisation must not silently undo it.")
            failures += 1
        else:
            print("  ok    an explicitly configured keyboard is left in place")

    print()
    if failures:
        print(f"osk-autoconfig: {failures} failure(s)")
        return 1
    print(
        f"osk-autoconfig: {len(CASES)} detection case(s); disables only on proven "
        "absence, and never overrides a person's choice"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
