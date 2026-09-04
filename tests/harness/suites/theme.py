"""Theme capture (WP-05): the surfaces a colour review actually needs.

Produces one frame per surface per theme, for the montage that goes to the owner.
It is a CAPTURE suite, not a comparison one — `screens` compares against
baselines, and there are no baselines until these frames are approved. Approval
is what creates them (rule R-F).

What it captures, and why each earns a frame:

  * **desktop** — wallpaper, and the only place the gradient is visible at size.
  * **window** — a themed app window (KWrite): titlebar, chrome, text on surface.
    The three-step ink hierarchy is legible here and nowhere else.
  * **menu** — a context menu: the material, hairline and radius system on a
    popup, which is the surface closest to what WP-07 will later blur.
  * **error** — an error dialog. This one is a specific check, not decoration:
    close-hover reaches Breeze through the scheme's `ForegroundNegative`, and
    that role is ALSO KDE's error-text colour. Both are now #e5484d. Almost
    certainly fine — both are danger-red — but "almost certainly" is not a thing
    to leave unlooked-at, so the review gets a frame of an actual error state.

Both themes, because the dark scheme must read as a designed set rather than a
naive inversion, and that judgement needs the pair side by side.
"""

from __future__ import annotations

import re
import time

from harness.screen import wait_for_screen
from harness.vm import VM

SETTLE = 4

# Commands sent over the serial console run in a login shell with no session
# environment, so anything that talks to the compositor fails with
# "could not connect to display". Rather than guessing WAYLAND_DISPLAY and
# XDG_RUNTIME_DIR, take them from the session that is actually running: read
# plasmashell's own environ. A guess would work until the session numbering
# changed and then fail in a way that looks like the theme being broken.
# Commands sent over the serial console run in a login shell with no session
# environment, so anything talking to the compositor fails with "could not
# connect to display". The env is captured ONCE, to a file, and sourced before
# each GUI command.
#
# The first version re-ran a `tr | grep | xargs -d` pipeline before every
# command. It worked in the light pass and HUNG for 90s in the dark one, which
# is the worst kind of helper: fragile in a way that presents as the thing it is
# helping being broken. Capturing once means one place to verify, and it is
# verified rather than assumed.
SESSION_ENV_FILE = "/tmp/meridian-session-env"
SESSION_ENV = f". {SESSION_ENV_FILE}"


def _capture_session_env(console) -> None:
    """Snapshot the running session's environment, or fail saying why."""
    _s, out = console.run(
        "pid=$(pgrep -u $(id -un) -x plasmashell | head -1); "
        f"tr '\\0' '\\n' < /proc/$pid/environ 2>/dev/null "
        "| grep -aE '^(WAYLAND_DISPLAY|XDG_RUNTIME_DIR|DISPLAY|DBUS_SESSION_BUS_ADDRESS)=' "
        f"| sed 's/^/export /' > {SESSION_ENV_FILE}; "
        f"echo VARS=$(grep -c . {SESSION_ENV_FILE} 2>/dev/null || echo 0)",
        timeout=90,
    )
    count = 0
    match = re.search(r"VARS=(\d+)", out)
    if match:
        count = int(match.group(1))
    if count < 2:
        raise AssertionError(
            "could not capture the session environment from plasmashell "
            f"(found {count} variable(s)).\n"
            f"  guest said: {out.strip()[:200]!r}\n"
            "  Without WAYLAND_DISPLAY and XDG_RUNTIME_DIR every GUI command "
            "fails with 'could not connect to display', and the frames would be "
            "of a session that never changed."
        )
    print(f"theme: captured session environment ({count} variables)")


def _capture(vm: VM, name: str, theme: str) -> None:
    # Nudge the display first. Between captures there are long settles with no
    # input, and the screen blanks: the dark window frame came back at detail
    # 0.00264 — black — and the blank guard refused it. A screensaver is not a
    # theme defect, but a black frame in a colour review is worse than no frame.
    vm.qmp.wake_display()
    time.sleep(SETTLE)
    wait_for_screen(vm, f"{name} ({theme})", keep_as=f"theme-{theme}-{name}")
    print(f"theme: captured {name} ({theme})")


def _apply(console, theme: str) -> None:
    """Switch the session's colour scheme and let Plasma repaint.

    `plasma-apply-colorscheme` is Plasma's own tool, so this exercises the same
    path a user takes in Settings rather than writing config behind its back —
    which would prove the file parses, not that the theme applies (R-I).
    """
    scheme = "MeridianDark" if theme == "dark" else "MeridianLight"
    _status, out = console.run(
        f"{SESSION_ENV}; plasma-apply-colorscheme {scheme} 2>&1 || echo APPLY-FAILED",
        timeout=180,
    )
    if "APPLY-FAILED" in out or "not found" in out.lower():
        raise AssertionError(
            f"could not apply {scheme}: {out.strip()[:300]}\n"
            "  The scheme ships in /usr/share/color-schemes. If Plasma cannot\n"
            "  apply it, the file is present and inert — which is exactly the\n"
            "  failure R-I names, and capturing frames now would photograph the\n"
            "  previous theme while labelling it the new one."
        )
    print(f"theme: applied {scheme}")
    time.sleep(6)


def _stand_down_greenboot(console) -> None:
    """Stop greenboot rebooting the VM out from under a capture.

    `10-meridian-desktop.sh` polls `graphical.target` with a 90s deadline that
    the target clears in ~80s on this VM. A lost race makes greenboot reboot the
    machine about three minutes in — mid-capture, which surfaced as `kwrite`
    "timing out" and read as a theme fault. See STATUS.md: the underlying defect
    is real and is NOT fixed by this; capturing screenshots is simply not the
    suite that should be proving boot health.

    Disclosed in the run report as `greenboot_suppressed` so no one reads a
    green theme capture as evidence that the boot was healthy.
    """
    _, out = console.run(
        "sudo -n systemctl stop greenboot-healthcheck.service redboot-auto-reboot.service"
        " 2>&1; sudo -n systemctl mask --runtime redboot-auto-reboot.service"
        " greenboot-healthcheck.service 2>&1; echo MASKED=$?",
        timeout=120,
    )
    if "MASKED=0" not in out:
        raise RuntimeError(
            "could not stand greenboot down; a mid-capture reboot would be "
            f"misread as a theme failure. Output: {out.strip()[-300:]}"
        )
    print("theme: greenboot auto-reboot masked for the capture (disclosed in report)")


def run(vm: VM, credentials: dict) -> None:
    console = vm.console
    user, password = credentials["user"], credentials["password"]

    console.login(user, password, timeout=600)
    _stand_down_greenboot(console)
    console.wait_until(
        "systemctl is-active display-manager",
        lambda out: any(line.strip() == "active" for line in out.splitlines()),
        timeout=300,
        description="display-manager to be active",
    )
    vm.qmp.wake_display()
    wait_for_screen(vm, "the greeter", keep_as="theme-greeter")
    vm.qmp.type_text(password)
    vm.qmp.key("ret")
    console.wait_until(
        "pgrep -a plasmashell || true",
        lambda out: "plasmashell" in out,
        timeout=420,
        description="plasmashell after the GUI login",
    )
    time.sleep(10)
    _capture_session_env(console)

    # Record what the session ACTUALLY resolved, so the montage can state it
    # rather than leaving the reviewer to guess whether the brand face rendered.
    _s, raw = console.run(
        "echo UI=$(fc-match -f '%{family}' sans-serif) "
        "MONO=$(fc-match -f '%{family}' monospace)",
        timeout=90,
    )
    resolved = " ".join(
        p for p in raw.replace(",", " ").split() if p.startswith(("UI=", "MONO="))
    )
    if not resolved:
        raise AssertionError(
            "could not read the resolved font families.\n"
            f"  guest said: {raw.strip()[:200]!r}\n"
            "  The sheet must STATE which typeface rendered. A montage that leaves"
            " it to inference is how a silent fallback gets approved."
        )
    print(f"theme: fonts resolved to {resolved}")

    for theme in ("light", "dark"):
        _apply(console, theme)
        _capture(vm, "desktop", theme)

        console.run(
            f"{SESSION_ENV}; "
            "(kwrite /usr/share/meridian/branding.json &) >/dev/null 2>&1",
            timeout=90,
        )
        time.sleep(8)
        _capture(vm, "window", theme)

        # A context menu, opened where one exists: right-click in the window.
        vm.qmp.move_pointer(16000, 16000)
        vm.qmp.click("right")
        _capture(vm, "menu", theme)
        vm.qmp.key("esc")

        # An actual error state, for the ForegroundNegative coupling check.
        console.run(
            # Generic copy on purpose: the frame is here to show the error
            # PALETTE, and the product name belongs in branding.json, not in a
            # test string that would survive a rebrand.
            f"{SESSION_ENV}; "
            "(kdialog --error 'That file could not be opened.' &) >/dev/null 2>&1",
            timeout=90,
        )
        time.sleep(8)
        _capture(vm, "error", theme)
        vm.qmp.key("ret")
        console.run("pkill kwrite; pkill kdialog; true", timeout=60)
        time.sleep(3)

    # NOT "theme-<arch>": run.py writes the per-run verdict under that name and
    # would replace this. The same collision cost the first over-budget perf run
    # its whole memory breakdown; the guard that caught it then caught this.
    vm.write_report(
        f"theme-capture-{vm.arch}",
        {
            "fonts_resolved": resolved.strip(),
            # Not a footnote: a reader must not take a green capture as
            # evidence that the boot was healthy. See STATUS.md.
            "greenboot_suppressed": True,
            "greenboot_suppressed_why": (
                "10-meridian-desktop.sh loses its 90s race against "
                "graphical.target and reboots the VM mid-capture"
            ),
        },
    )
    print("theme: all surfaces captured, both themes")
