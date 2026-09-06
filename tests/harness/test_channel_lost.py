#!/usr/bin/env python3
"""A command typed at a login prompt did not run, and must not look like one.

The single most expensive harness defect of WP-05. When the machine reboots
mid-suite — which greenboot does on purpose — the login session dies and every
subsequent command is typed into `fedora login:` as a username. No sentinel can
come back, so the harness waited out its timeout and reported:

    command timed out after 60s: 'systemctl is-active graphical.target'

That reads as a slow machine. It was written up as a product finding more than
once, including a claim that graphical.target never activates — while
photographs of the same image showed a working greeter at 60 seconds.

The rule this encodes, from the handoff report: a result is evidence only if the
command demonstrably ran. So a lost session raises ChannelLost, which is a
different exception from a timeout, and the channel re-establishes itself once
rather than reporting a phantom.
"""

from __future__ import annotations

import sys
import threading
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from harness.console import ChannelLost, Console, ConsoleError

# Typing a command at `login:` makes login ask for a password.
LOST_SESSION = "\nPassword: "
LIVE_SHELL = ""  # a live shell simply says nothing until the command finishes


class FakeSocket:
    """Answers like the far end would.

    `run` clears the buffer before sending, so seeding a login prompt
    beforehand proves nothing — it gets wiped. The machine's REPLY is what
    matters, so this fake injects it on send, which is also what exposed that
    a lost session shows `Password:` rather than another `login:`.
    """

    def __init__(self, console, reply: str) -> None:
        self.sent = b""
        self._console = console
        self._reply = reply

    def sendall(self, data: bytes) -> None:
        self.sent += data
        with self._console._lock:
            self._console._buffer += self._reply


def console_replying(reply: str):
    c = object.__new__(Console)
    c._buffer = ""
    c._lock = threading.Lock()
    sock = FakeSocket(c, reply)
    c._sock = sock
    return c, sock


def main() -> int:
    failures = 0

    # 1. At a login prompt with NO remembered credentials: ChannelLost, and the
    #    message must say the command never ran.
    c, _sock = console_replying(LOST_SESSION)
    try:
        c.run("systemctl is-active graphical.target", timeout=1)
        print("FAIL: a command typed at a login prompt reported success")
        failures += 1
    except ChannelLost as exc:
        if "never ran" not in str(exc):
            print(f"FAIL: ChannelLost message does not say it never ran: {exc}")
            failures += 1
    except ConsoleError as exc:
        print(f"FAIL: raised a plain timeout instead of ChannelLost: {exc}")
        failures += 1

    # 2. A shell IS present and the command is merely slow: a plain timeout,
    #    NOT ChannelLost. The two must stay distinguishable.
    c, _sock = console_replying(LIVE_SHELL)
    try:
        c.run("sleep 999", timeout=1)
        print("FAIL: a slow command reported success")
        failures += 1
    except ChannelLost as exc:
        print(f"FAIL: a slow command on a live shell raised ChannelLost: {exc}")
        failures += 1
    except ConsoleError as exc:
        if "genuinely slow" not in str(exc):
            print(f"FAIL: timeout message does not distinguish itself: {exc}")
            failures += 1

    # 3. ChannelLost must be catchable as ConsoleError, so existing handlers
    #    keep working.
    if not issubclass(ChannelLost, ConsoleError):
        print("FAIL: ChannelLost is not a ConsoleError")
        failures += 1

    if failures:
        print(f"channel-lost: {failures} failure(s)")
        return 1
    print(
        "channel-lost: login prompt raises ChannelLost, a live-but-slow shell "
        "raises a plain timeout, and the two are distinguishable"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
