"""A small QMP client (PRD 7.4).

QEMU's Machine Protocol is the harness's only channel into a running VM before
the guest is reachable any other way: it takes screenshots, injects keyboard and
pointer events, and reports run state. Everything else in the harness is built
on this file.

Deliberately dependency-free — a JSON-lines protocol over a unix socket does not
justify a library, and the harness must run identically on the Mac dev loop and
on a CI runner.
"""

from __future__ import annotations

import json
import socket
import time
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from typing import Self


class QMPError(RuntimeError):
    """QEMU rejected a command, or the socket died mid-conversation."""


class QMP:
    """A connection to one running VM's QMP socket."""

    def __init__(self, socket_path: str | Path, connect_timeout: float = 120.0):
        self.socket_path = str(socket_path)
        self._sock: socket.socket | None = None
        self._stream = None
        self._connect(connect_timeout)

    # ---------------------------------------------------------------- setup --

    def _connect(self, timeout: float) -> None:
        """Wait for QEMU to create the socket, then negotiate capabilities.

        The socket does not exist until QEMU has started, so a plain connect
        races the VM launch. Polling here keeps that race out of every caller.
        """
        deadline = time.monotonic() + timeout
        last_error: Exception | None = None
        while time.monotonic() < deadline:
            try:
                sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
                sock.connect(self.socket_path)
                self._sock = sock
                self._stream = sock.makefile("rw", encoding="utf-8", newline="\n")
                break
            except (FileNotFoundError, ConnectionRefusedError) as exc:
                last_error = exc
                time.sleep(0.5)
        else:
            raise QMPError(
                f"{self.socket_path} never accepted a connection within {timeout:.0f}s "
                f"— the VM did not start ({last_error})"
            )

        greeting = json.loads(self._stream.readline())
        self.version = greeting.get("QMP", {}).get("version", {}).get("qemu", {})
        self.execute("qmp_capabilities")

    def close(self) -> None:
        if self._sock is not None:
            try:
                self._sock.close()
            finally:
                self._sock = None
                self._stream = None

    def __enter__(self) -> Self:
        return self

    def __exit__(self, *_exc) -> None:
        self.close()

    # ------------------------------------------------------------- protocol --

    def execute(self, command: str, **arguments):
        """Run one QMP command and return its `return` value.

        Asynchronous events are interleaved with replies on the same socket and
        are skipped here; a caller asking for a command result never wants a
        BLOCK_IO_ERROR in its place.
        """
        if self._stream is None:
            raise QMPError("QMP connection is closed")
        payload = {"execute": command}
        if arguments:
            payload["arguments"] = arguments
        self._stream.write(json.dumps(payload) + "\n")
        self._stream.flush()

        while True:
            line = self._stream.readline()
            if not line:
                raise QMPError(f"QMP socket closed while waiting for '{command}'")
            reply = json.loads(line)
            if "event" in reply:
                continue
            if "error" in reply:
                error = reply["error"]
                raise QMPError(f"{command}: {error.get('class')}: {error.get('desc')}")
            return reply.get("return")

    # ---------------------------------------------------------------- state --

    def status(self) -> str:
        """'running', 'paused', 'shutdown', ..."""
        return (self.execute("query-status") or {}).get("status", "unknown")

    def is_running(self) -> bool:
        return self.status() == "running"

    # ----------------------------------------------------------------- view --

    def screendump(self, path: str | Path) -> Path:
        """Write the current framebuffer to `path` as a PPM."""
        path = Path(path).absolute()
        path.parent.mkdir(parents=True, exist_ok=True)
        self.execute("screendump", filename=str(path))
        if not path.exists():
            raise QMPError(f"screendump reported success but wrote nothing to {path}")
        return path

    # ---------------------------------------------------------------- input --

    def key(self, *keys: str) -> None:
        """Press one key, or a chord.

        Names are QEMU qcodes ('ret', 'esc', 'ctrl', 'f2', 'a'), not characters.
        A chord is one call — `key("ctrl", "alt", "f2")` — because QEMU presses
        and releases the whole list together.
        """
        self.execute("send-key", keys=[{"type": "qcode", "data": k} for k in keys])

    def type_text(self, text: str, delay: float = 0.05) -> None:
        """Type an ASCII string one key at a time.

        Slow by construction: SDDM and Plasma drop keys delivered faster than a
        human types, and a password that loses a character fails a login test in
        a way that looks like a real defect.
        """
        for char in text:
            for qcode in _qcodes_for(char):
                self.key(*qcode)
            time.sleep(delay)

    def move_pointer(self, x: int, y: int) -> None:
        """Move the absolute pointer. Coordinates are 0..32767, not pixels."""
        self.execute(
            "input-send-event",
            events=[
                {"type": "abs", "data": {"axis": "x", "value": max(0, min(32767, x))}},
                {"type": "abs", "data": {"axis": "y", "value": max(0, min(32767, y))}},
            ],
        )

    def click(self, button: str = "left") -> None:
        self.execute(
            "input-send-event",
            events=[{"type": "btn", "data": {"down": True, "button": button}}],
        )
        time.sleep(0.15)
        self.execute(
            "input-send-event",
            events=[{"type": "btn", "data": {"down": False, "button": button}}],
        )

    def wake_display(self, click: bool = True) -> None:
        """Nudge the pointer so a greeter or lock screen reveals its form.

        Not cosmetic. SDDM's Breeze theme opens on a clock overlay and only
        shows the password field after input; screenshotting without this
        photographs a clock, which reads as a boot that never reached a greeter.
        WP-01's first screenshot was misread for exactly this reason.
        """
        for x, y in ((10000, 10000), (20000, 22000), (16384, 16384)):
            self.move_pointer(x, y)
            time.sleep(0.4)
        # `click=False` when the subject is a transient popup. The click here
        # dismissed every context menu this harness ever tried to photograph:
        # the menu opened, the wake clicked it away, and the frame captured the
        # window behind it while the suite reported "captured menu". Two guards
        # that were each correct alone, composed so that one erased the other's
        # subject.
        if click:
            self.click()
        time.sleep(1.0)


# QEMU qcodes for the characters the harness actually types (usernames,
# passwords, short commands). Anything outside this set raises rather than
# silently typing nothing.
_SHIFTED = {
    "!": "1",
    "@": "2",
    "#": "3",
    "$": "4",
    "%": "5",
    "^": "6",
    "&": "7",
    "*": "8",
    "(": "9",
    ")": "0",
    "_": "minus",
    "+": "equal",
    "{": "bracket_left",
    "}": "bracket_right",
    ":": "semicolon",
    '"': "apostrophe",
    "<": "comma",
    ">": "dot",
    "?": "slash",
    "|": "backslash",
    "~": "grave_accent",
}
_PLAIN = {
    " ": "spc",
    "-": "minus",
    "=": "equal",
    "[": "bracket_left",
    "]": "bracket_right",
    ";": "semicolon",
    "'": "apostrophe",
    ",": "comma",
    ".": "dot",
    "/": "slash",
    "\\": "backslash",
    "`": "grave_accent",
    "\n": "ret",
}


def _qcodes_for(char: str) -> list[tuple[str, ...]]:
    if char.isalpha() and char.isascii():
        return [("shift", char.lower())] if char.isupper() else [(char,)]
    if char.isdigit():
        return [(char,)]
    if char in _PLAIN:
        return [(_PLAIN[char],)]
    if char in _SHIFTED:
        return [("shift", _SHIFTED[char])]
    raise QMPError(
        f"no qcode mapping for {char!r}. Add it to _PLAIN/_SHIFTED rather than "
        f"letting the harness type nothing and fail somewhere else."
    )
