#!/usr/bin/env python3
"""The harness must not type into the firmware.

A real 10-minute failure, from build/evidence/serial-x86_64.log:

    BdsDxe: starting Boot0001 "UEFI Misc Device"
    GRUB version 2.12
      Press enter to boot the selected OS ...  <product> 1.0.0-dev (ostree:0)
    BdsDxe: starting Boot0000 "UiApp"
    This is the option one adjusts to change the language for the current system
    ... the same line, hundreds of times ...

`login()` nudged the console with a newline every ten seconds from the moment
the harness attached. Until Linux starts a getty, the reader on the other end
is UEFI and then GRUB, where a keystroke is a menu selection. The nudges landed
in the firmware's setup application and cycled its language menu for 600s, and
the run then blamed the image: "no login prompt — is a serial getty running?"
A getty was never the problem; the machine had not booted.

Rule R-I, applied to the harness itself: assert what the console *is* before
typing at it, rather than assuming a getty is listening.
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from harness.console import Console, ConsoleError

FIRMWARE = (
    'BdsDxe: starting Boot0000 "UiApp" from Fv(7CB8BDC9)\n'
    "This is the option one adjusts to change the language for the current system"
)
GRUB_ONLY = (
    'BdsDxe: starting Boot0001 "UEFI Misc Device"\n'
    "GRUB version 2.12\n"
    "  Press enter to boot the selected OS, `e' to edit the commands"
)
BOOTED = "[   4.11] systemd[1]: Reached target Multi-User System.\nmeridian login: "


class FakeSocket:
    """Records everything written, so 'sent nothing' is checkable."""

    def __init__(self) -> None:
        self.sent = b""

    def sendall(self, data: bytes) -> None:
        self.sent += data


def console_showing(text: str) -> tuple[Console, FakeSocket]:
    """A Console wired to a fake socket, with `text` already on screen."""
    c = object.__new__(Console)
    sock = FakeSocket()
    c._sock = sock
    c._buffer = text
    import threading

    c._lock = threading.Lock()
    return c, sock


def main() -> int:
    failures = 0

    # 1. The firmware menu is refused, and refused *before* anything is typed.
    c, sock = console_showing(FIRMWARE)
    try:
        c.login("mtest", "pw", timeout=5)
        print("FAIL: login proceeded while the VM sat in the UEFI setup app")
        failures += 1
    except ConsoleError as e:
        if "UEFI setup application" not in str(e):
            print(f"FAIL: refused, but the message does not name the cause: {e}")
            failures += 1
    if sock.sent:
        print(f"FAIL: typed {sock.sent!r} into the firmware menu")
        failures += 1

    # 2. GRUB's countdown is not userspace either: still nothing typed.
    c, sock = console_showing(GRUB_ONLY)
    try:
        c.login("mtest", "pw", timeout=2)
    except ConsoleError:
        pass
    if sock.sent:
        print(f"FAIL: typed {sock.sent!r} during GRUB's menu — that selects an entry")
        failures += 1

    # 3. Once userspace is talking, the nudge is allowed through.
    c, sock = console_showing(BOOTED)
    try:
        c.login("mtest", "pw", timeout=2)
    except ConsoleError:
        pass
    if not sock.sent:
        print("FAIL: sent nothing even though a login prompt was on screen")
        failures += 1

    if failures:
        print(f"console-firmware: {failures} failure(s)")
        return 1
    print("console-firmware: firmware refused, GRUB silent, getty nudged")
    return 0


if __name__ == "__main__":
    sys.exit(main())
