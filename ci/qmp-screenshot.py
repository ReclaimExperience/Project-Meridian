#!/usr/bin/env python3
"""Wait for a booted VM to settle, reveal the greeter, and photograph it.

WP-01 STOPGAP, paired with ci/boot-screenshot.sh. WP-03 owns the real harness
(PRD 7.4) and should delete both when it lands.

The pointer wiggle is not decoration: SDDM's Breeze greeter opens on a clock
overlay and only reveals the login form on input. Screenshotting without it
photographs a clock and looks like a boot that never reached a greeter — which
is exactly how WP-01's first screenshot was misread.
"""

from __future__ import annotations

import json
import socket
import sys
import time


def connect(path: str, timeout: int = 120) -> socket.socket:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        try:
            sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
            sock.connect(path)
            return sock
        except (FileNotFoundError, ConnectionRefusedError):
            time.sleep(1)
    raise SystemExit(f"qmp: {path} never appeared; the VM did not start")


def main() -> int:
    sock_path, out, settle = sys.argv[1], sys.argv[2], int(sys.argv[3])
    sock = connect(sock_path)
    stream = sock.makefile("rw", encoding="utf-8", newline="\n")
    stream.readline()  # greeting

    def cmd(name: str, **args):
        stream.write(
            json.dumps({"execute": name, **({"arguments": args} if args else {})})
            + "\n"
        )
        stream.flush()
        while True:
            reply = json.loads(stream.readline())
            if "event" not in reply:
                return reply

    cmd("qmp_capabilities")
    print(f"qmp: connected; letting the desktop settle for {settle}s")
    time.sleep(settle)

    def move(x: int, y: int) -> None:
        cmd(
            "input-send-event",
            events=[
                {"type": "abs", "data": {"axis": "x", "value": x}},
                {"type": "abs", "data": {"axis": "y", "value": y}},
            ],
        )

    for x, y in ((10000, 10000), (20000, 22000), (32768, 32768)):
        move(x, y)
        time.sleep(0.6)
    cmd(
        "input-send-event",
        events=[{"type": "btn", "data": {"down": True, "button": "left"}}],
    )
    time.sleep(0.15)
    cmd(
        "input-send-event",
        events=[{"type": "btn", "data": {"down": False, "button": "left"}}],
    )
    time.sleep(4)

    result = cmd("screendump", filename=out)
    if "error" in result:
        raise SystemExit(f"qmp: screendump failed: {result['error']}")
    status = cmd("query-status").get("return", {})
    print(f"qmp: screendump written; vm status={status.get('status')}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
