#!/usr/bin/env python3
"""Console prompt matching, against real serial output.

A serial console carries the kernel's printk stream as well as getty's prompts,
and the kernel does not wait its turn. This is a real capture from a boot:

    Password: [   11.139142] clocksource: Watchdog remote CPU 1 read timed out

`password:\\s*$` does not match that. The login timed out after 30 seconds and
the failure read as an image that would not accept its own credentials — the
harness accusing the thing it was testing, which is the same shape as the black
screen that got blamed on plasmashell.

It is intermittent by nature: whether a printk lands inside the prompt line
depends on timing, so the same image logs in fine most runs. Rule R-A treats
flaky as broken, and a login that fails one run in ten is worse than one that
always fails — it teaches people to re-run.
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from harness.console import LOGIN_PROMPT, PASSWORD_PROMPT, PROMPT

# (pattern, line, should_match, why)
CASES = [
    (PASSWORD_PROMPT, "Password: ", True, "the ordinary case"),
    (PASSWORD_PROMPT, "Password:", True, "no trailing space"),
    (
        PASSWORD_PROMPT,
        "Password: [   11.139142] clocksource: Watchdog remote CPU 1 read timed out",
        True,
        "the capture that broke a real run",
    ),
    (
        PASSWORD_PROMPT,
        "Password: [    0.000001] anything at all here",
        True,
        "any printk, not just that one",
    ),
    (
        PASSWORD_PROMPT,
        "the password: was wrong, and this is prose about it",
        False,
        "prose containing 'password:' must NOT read as a prompt",
    ),
    (LOGIN_PROMPT, "fedora login: ", True, "the ordinary case"),
    (
        LOGIN_PROMPT,
        "fedora login: [   9.5] EXT4-fs (vda3): mounted filesystem",
        True,
        "printk after the login prompt",
    ),
    # PROMPT stays anchored on purpose: it is matched against output a command
    # produced, so a '#' mid-output must not read as "the shell is ready".
    (PROMPT, "user@host:~$ ", True, "shell prompt at end of line"),
    (
        PROMPT,
        "echo '# this is a comment' # and more",
        False,
        "a '#' inside command output is not a shell prompt",
    ),
]


def main() -> int:
    failures = 0
    for pattern, line, want, why in CASES:
        got = bool(pattern.search(line))
        ok = got == want
        print(f"  {'ok  ' if ok else 'FAIL'}  {why}")
        if not ok:
            print(f"      line:  {line!r}")
            print(f"      wanted {want}, got {got}")
            failures += 1

    print()
    if failures:
        print(f"console-prompts: {failures} failure(s)")
        return 1
    print(f"console-prompts: {len(CASES)} case(s) including real interleaved printk")
    return 0


if __name__ == "__main__":
    sys.exit(main())
