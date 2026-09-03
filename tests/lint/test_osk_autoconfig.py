#!/usr/bin/env python3
"""The on-screen keyboard's session-scope mechanism (ADR-018 clause 6).

The version this replaces wrote `/etc/xdg/kwinrc` — a SYSTEM-WIDE KConfig
default that the greeter's own kwin also reads. On a machine whose digitizer is
detected late, or attached after boot, that could have suppressed the keyboard at
the LOGIN SCREEN, where the failure mode is not an awkward session but an owner
who cannot type their password. It was measured for its memory saving and shipped
without that interaction being tested at all.

So the assertions here are ordered by what actually matters:

  1. **Nothing ever writes to /etc.** Structural, checked against the source, and
     the reason this mechanism is safe to ship before a touch seat exists.
  2. Enable is eager and sticky; disable is lazy. One sighting of a touchscreen
     is enough, forever — being wrong towards a keyboard nobody needs costs
     72 MiB, being wrong the other way costs someone their computer.
  3. The user's choice wins over both.
"""

from __future__ import annotations

import os
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
LIBEXEC = ROOT / "os" / "rootfs" / "usr" / "libexec" / "meridian"
SESSION = LIBEXEC / "osk-session-config"
MARK = LIBEXEC / "osk-mark-touch"
UDEV = (
    ROOT
    / "os"
    / "rootfs"
    / "usr"
    / "lib"
    / "udev"
    / "rules.d"
    / "70-meridian-touchscreen.rules"
)
USER_UNIT = (
    ROOT
    / "os"
    / "rootfs"
    / "usr"
    / "lib"
    / "systemd"
    / "user"
    / "meridian-osk-session.service"
)

OSK = "org.kde.plasma.keyboard.desktop"


def run_session(tmp: Path, mode: str | None, marker: bool) -> tuple[int, str, str]:
    """Drive the real script with a fake HOME, marker and kwriteconfig6."""
    home = tmp / "home"
    (home / ".config" / "meridian").mkdir(parents=True, exist_ok=True)
    if mode is not None:
        (home / ".config" / "meridian" / "osk.conf").write_text(mode + "\n")
    else:
        (home / ".config" / "meridian" / "osk.conf").unlink(missing_ok=True)

    marker_dir = tmp / "var" / "lib" / "meridian"
    marker_dir.mkdir(parents=True, exist_ok=True)
    marker_path = marker_dir / "touchscreen-seen"
    if marker:
        marker_path.write_text("seen=now\n")
    else:
        marker_path.unlink(missing_ok=True)

    bindir = tmp / "bin"
    bindir.mkdir(exist_ok=True)
    # A kwriteconfig6 that records what it was asked to write.
    (bindir / "kwriteconfig6").write_text(
        '#!/bin/sh\nprintf "%s\\n" "$*" >> "$KW_LOG"\nexit 0\n'
    )
    (bindir / "kwriteconfig6").chmod(0o755)
    log = tmp / "kw.log"
    log.unlink(missing_ok=True)

    source = SESSION.read_text().replace(
        "MARKER=/var/lib/meridian/touchscreen-seen", f"MARKER={marker_path}"
    )
    driver = tmp / "osk-session-config"
    driver.write_text(source)
    driver.chmod(0o755)

    env = dict(os.environ)
    env["PATH"] = f"{bindir}:{env['PATH']}"
    env["HOME"] = str(home)
    env["XDG_CONFIG_HOME"] = str(home / ".config")
    env["KW_LOG"] = str(log)
    result = subprocess.run(
        ["bash", str(driver)], capture_output=True, text=True, env=env, check=False
    )
    written = log.read_text() if log.exists() else ""
    return result.returncode, result.stdout + result.stderr, written


def keyboard_on(written: str) -> bool:
    return OSK in written


def main() -> int:
    failures = 0

    # --- 1. the structural property, which is why this can ship early -------
    print("the greeter must be structurally out of reach")
    sources = {p.name: p.read_text() for p in (SESSION, MARK)}
    sources["udev rule"] = UDEV.read_text()
    sources["user unit"] = USER_UNIT.read_text()
    for name, text in sources.items():
        # CODE only. These files talk about /etc in their comments, on purpose:
        # they explain what the superseded mechanism did and why it was unsafe.
        # Forbidding the explanation along with the behaviour would delete the
        # reason the rework exists, and the next person would rediscover it the
        # expensive way.
        code = "\n".join(
            line for line in text.splitlines() if not line.lstrip().startswith("#")
        )
        touches_etc = "/etc/" in code
        print(f"  {'FAIL' if touches_etc else 'ok  '}  {name} never writes under /etc")
        if touches_etc:
            offending = [ln for ln in code.splitlines() if "/etc/" in ln]
            for line in offending:
                print(f"      {line.strip()}")
        failures += 1 if touches_etc else 0
    unit = sources["user unit"]
    is_user_unit = "systemd/user" in str(USER_UNIT)
    print(
        f"  {'ok  ' if is_user_unit else 'FAIL'}  it is a USER unit, in the session's own scope"
    )
    failures += 0 if is_user_unit else 1
    if "WantedBy=plasma-workspace.target" not in unit:
        print("  FAIL  the unit is not wanted by any target, so it never runs")
        failures += 1
    else:
        print("  ok    the unit is actually pulled in by plasma-workspace.target")

    with tempfile.TemporaryDirectory() as tmpdir:
        tmp = Path(tmpdir)

        # --- 2. eager and sticky enable, lazy disable ----------------------
        print("\nautomatic: one touchscreen sighting is enough, forever")
        for marker, want_on, why in [
            (True, True, "a machine that has seen a touchscreen keeps the keyboard"),
            (False, False, "a machine that never has does not carry it"),
        ]:
            code, _output, written = run_session(tmp, None, marker)
            got = keyboard_on(written)
            ok = code == 0 and got == want_on
            print(f"  {'ok  ' if ok else 'FAIL'}  {why}")
            if not ok:
                print(f"      exit={code} wrote={written.strip()!r}")
                failures += 1

        # --- 3. the user's choice beats the hardware, both ways ------------
        print("\nthe user's choice wins over the hardware")
        for mode, marker, want_on, why in [
            ("always", False, True, "'Always' keeps it on a touchless desktop"),
            ("off", True, False, "'Off' turns it off even on a tablet"),
            ("automatic", True, True, "'Automatic' follows the hardware"),
        ]:
            code, _output, written = run_session(tmp, mode, marker)
            got = keyboard_on(written)
            ok = code == 0 and got == want_on
            print(f"  {'ok  ' if ok else 'FAIL'}  {why}")
            if not ok:
                print(f"      exit={code} wrote={written.strip()!r}")
                failures += 1

        # --- 4. it writes the SESSION's kwinrc, not a system one -----------
        print("\nscope")
        code, _output, written = run_session(tmp, "always", False)
        if ".config/kwinrc" not in written:
            print(f"  FAIL  it did not target the session kwinrc: {written.strip()!r}")
            failures += 1
        else:
            print("  ok    it writes the session's own kwinrc")

    print()
    if failures:
        print(f"osk-session: {failures} failure(s)")
        return 1
    print(
        "osk-session: nothing writes under /etc, enable is sticky, disable is lazy, "
        "and the user's choice wins"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
