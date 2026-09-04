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

from harness.screen import (
    changed_region,
    dominant_colours,
    nearest_distance,
    wait_for_screen,
)
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
    """Snapshot the FULL session environment, or fail saying why.

    It used to take four variables — WAYLAND_DISPLAY, XDG_RUNTIME_DIR, DISPLAY,
    DBUS_SESSION_BUS_ADDRESS — on the reasoning that those are what a GUI
    command needs to reach the compositor. They are what it needs to *draw*. They
    are not what it needs to look right.

    Missing from that set was XDG_CURRENT_DESKTOP=KDE, which is how Qt6 selects
    the KDE platform theme, which is what reads the colour scheme out of
    kdeglobals. Dolphin launched without it rendered a white interior under a
    dark scheme that was correctly applied and correctly written to config — and
    the compare sheet showed a "dark" window that was light inside. The harness
    was the defect, and it looked exactly like a theming defect.

    So: take the whole environment, quoted properly, and assert the variable
    that decides theming is in it. Launching an app with less than the session
    gives it is not testing the app the user runs.
    """
    _s, out = console.run(
        "pid=$(pgrep -u $(id -un) -x plasmashell | head -1); "
        "tr '\\0' '\\n' < /proc/$pid/environ 2>/dev/null | "
        "while IFS= read -r line; do "
        "key=${line%%=*}; val=${line#*=}; "
        "case \"$key\" in ''|*[!A-Za-z0-9_]*) continue;; esac; "
        'printf "export %s=\'%s\'\\n" "$key" '
        "\"$(printf '%s' \"$val\" | sed \"s/'/'\\\\''/g\")\"; "
        f"done > {SESSION_ENV_FILE}; "
        f"echo VARS=$(grep -c . {SESSION_ENV_FILE} 2>/dev/null || echo 0)",
        timeout=90,
    )
    count = 0
    match = re.search(r"VARS=(\d+)", out)
    if match:
        count = int(match.group(1))
    if count < 10:
        raise AssertionError(
            "could not capture the session environment from plasmashell "
            f"(found {count} variable(s), expected the session's full set).\n"
            f"  guest said: {out.strip()[:200]!r}"
        )
    _s, check = console.run(
        f"{SESSION_ENV}; echo DESKTOP=[$XDG_CURRENT_DESKTOP] "
        "RUNTIME=[$XDG_RUNTIME_DIR] WAYLAND=[$WAYLAND_DISPLAY]",
        timeout=60,
    )
    if "DESKTOP=[KDE]" not in check.upper().replace("PLASMA", "KDE"):
        raise AssertionError(
            "XDG_CURRENT_DESKTOP is not in the captured session environment.\n"
            f"  guest said: {check.strip()[:200]!r}\n"
            "  Qt6 selects the KDE platform theme from it, and the platform "
            "theme is what applies the colour scheme to app interiors. Without "
            "it every app renders light under a correctly applied dark theme, "
            "and the sheet blames the theme."
        )
    if "RUNTIME=[]" in check or "WAYLAND=[]" in check:
        raise AssertionError(
            f"the session environment is missing display variables: {check.strip()[:200]!r}"
        )
    print(
        f"theme: captured session environment ({count} variables, XDG_CURRENT_DESKTOP present)"
    )


def _capture(vm: VM, name: str, theme: str, disturb: bool = True) -> None:
    # Nudge the display first. Between captures there are long settles with no
    # input, and the screen blanks: the dark window frame came back at detail
    # 0.00264 — black — and the blank guard refused it. A screensaver is not a
    # theme defect, but a black frame in a colour review is worse than no frame.
    # disturb=False for transient popups: the wake's click dismisses them.
    vm.qmp.wake_display(click=disturb)
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


APPS = ("dolphin", "kwrite", "kdialog", "konsole")
# The wallpaper the mockup shows, so the desktop row compares like with like.
# WHICH gradient pairs with which theme is an owner decision that has not been
# made; in KDE the wallpaper is a desktop setting, independent of the colour
# scheme, so using one for both themes is the honest default rather than a
# choice smuggled in by the test.
WALLPAPER = "softViolet"
# From docs/design/tokens.json — the gradient's own stops. Asserted against the
# PIXELS, not against the shipped file: proving the SVG exists is precisely the
# nothing that let three wallpapers ship without ever being on screen.
WALLPAPER_STOPS = ((0xC3, 0xBF, 0xE3), (0x6D, 0x7A, 0xC2), (0x2C, 0x48, 0x8E))


def _close_apps(console) -> None:
    """Close every app window, and assert none survived.

    A precondition, not housekeeping. The dark desktop frame came back with the
    light pass's window still in it, and nothing objected — the suite had no
    notion of what a desktop frame must NOT contain. A process cannot have a
    window, so an empty process list is a sound proof of an empty desktop.
    """
    console.run("pkill -f '" + "|".join(APPS) + "' 2>/dev/null; true", timeout=60)
    for app in APPS:
        console.run(f"pkill -x {app} 2>/dev/null; true", timeout=30)
    time.sleep(3)
    _s, out = console.run(
        "echo LEFT=$(pgrep -x " + " -x ".join(APPS) + " 2>/dev/null | wc -l)",
        timeout=60,
    )
    match = re.search(r"LEFT=(\d+)", out)
    if not match:
        raise AssertionError(
            f"could not count app processes; guest said {out.strip()[:200]!r}"
        )
    if int(match.group(1)) != 0:
        raise AssertionError(
            f"{match.group(1)} app process(es) still running before a desktop "
            "capture. The frame would contain a window and be labelled 'desktop'."
        )


def _set_wallpaper(console) -> None:
    """Set the wallpaper with Plasma's own tool, and fail loudly if it refuses."""
    _s, out = console.run(
        f"{SESSION_ENV}; plasma-apply-wallpaperimage "
        f"/usr/share/wallpapers/{WALLPAPER}.svg 2>&1 || echo WALL-FAILED",
        timeout=180,
    )
    if "WALL-FAILED" in out or "error" in out.lower():
        raise AssertionError(
            f"could not set the wallpaper: {out.strip()[:300]}\n"
            "  Three generated gradients have shipped in /usr/share/wallpapers "
            "since WP-05 began and none has ever been rendered — present and "
            "inert, and invisible because nothing asked for the effect."
        )
    time.sleep(6)


def _assert_wallpaper_rendered(frame, theme: str) -> None:
    """The gradient's colours must be ON SCREEN, not merely installed."""
    palette = dominant_colours(frame)
    distances = [nearest_distance(c, list(WALLPAPER_STOPS)) for c in palette]
    if min(distances) > 90:
        raise AssertionError(
            f"the {theme} desktop frame does not contain the {WALLPAPER} gradient.\n"
            f"  dominant colours: {palette}\n"
            f"  nearest distance to a gradient stop: {min(distances):.0f} (need <= 90)\n"
            "  The base image's own wallpaper is what previous sheets showed, "
            "so a desktop row was comparing Fedora's art to the mockup's."
        )


def _assert_portal_scheme(console, theme: str) -> None:
    """The xdg-desktop-portal colour-scheme preference must follow the theme.

    Layer 4 of the dark contract (docs/design/theming.md). GTK apps and every
    Flatpak read this, not the Plasma scheme, so it is the layer that decides
    whether a browser looks like part of the system. Asserted now, before any
    GTK app exists to show it, because a preference that silently stops flipping
    is exactly the kind of inert-but-present this project keeps finding late.
    """
    want = 1 if theme == "dark" else 2  # 0 = no preference, 1 = dark, 2 = light
    _s, out = console.run(
        f"{SESSION_ENV}; gdbus call --session "
        "--dest org.freedesktop.portal.Desktop "
        "--object-path /org/freedesktop/portal/desktop "
        "--method org.freedesktop.portal.Settings.ReadOne "
        "org.freedesktop.appearance color-scheme 2>&1",
        timeout=120,
    )
    match = re.search(r"uint32\s+(\d+)", out)
    if not match:
        raise AssertionError(
            "could not read the portal colour-scheme preference.\n"
            f"  guest said: {out.strip()[:250]!r}\n"
            "  Without it, dark theme stops at Plasma's own chrome and every "
            "GTK app stays light — the tell that sinks the illusion."
        )
    got = int(match.group(1))
    if got != want:
        raise AssertionError(
            f"portal colour-scheme is {got}, expected {want} for the {theme} "
            "theme. Plasma's chrome and the portal preference have diverged, so "
            "GTK apps and Flatpaks would disagree with the desktop around them."
        )
    print(f"theme: portal colour-scheme = {got} ({theme})")


def _open_menu_asserted(vm: VM, console, theme: str) -> None:
    """Right-click, and prove a menu appeared before photographing it.

    The failure this replaces: the suite right-clicked, called the capture, and
    the capture's own wake_display() clicked the menu away. It then wrote
    theme-<theme>-menu.png and printed "captured menu". Three frames reached the
    owner with the subject absent.

    KWin's scripting `print` does not reach the journal, so a window-list check
    is not available here. For a capture suite the stronger claim is anyway
    about pixels: a menu is a bounded region of the screen that was not there a
    moment ago.
    """
    before = vm.screenshot(f"theme-{theme}-premenu")
    vm.qmp.move_pointer(16384, 16384)
    time.sleep(0.6)
    vm.qmp.click("right")
    time.sleep(3)
    after = vm.screenshot(f"theme-{theme}-menucheck")
    fraction, bbox = changed_region(before, after)
    if bbox is None or fraction < 0.004:
        raise AssertionError(
            f"no menu appeared after the right-click ({fraction:.4%} of pixels "
            "changed). The frame would be the window behind it, labelled 'menu'."
        )
    if fraction > 0.45:
        raise AssertionError(
            f"{fraction:.1%} of the screen changed after the right-click — too "
            "much for a context menu. Something else repainted (a theme change "
            "still settling, or a window opening), so the frame cannot be "
            "trusted to show a menu."
        )
    width, height = bbox[2] - bbox[0], bbox[3] - bbox[1]
    print(
        f"theme: menu on screen ({fraction:.2%} of pixels, {width}x{height} at "
        f"{bbox[0]},{bbox[1]})"
    )


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

    _set_wallpaper(console)

    for theme in ("light", "dark"):
        _apply(console, theme)
        _assert_portal_scheme(console, theme)

        # Desktop: nothing on it. Asserted, because the dark frame arrived with
        # the light pass's window in it and the suite had no opinion about that.
        _close_apps(console)
        _capture(vm, "desktop", theme)
        _assert_wallpaper_rendered(vm.evidence / f"theme-{theme}-desktop.png", theme)

        # Window: Dolphin, not KWrite. The mockup's window is a file manager, so
        # comparing KWrite to it made every chrome difference unreadable — noise
        # where the row is supposed to carry signal. Dolphin also sidesteps the
        # editor-view colour scheme, which is layer 2 of the dark contract and
        # is NOT wired yet (docs/design/theming.md).
        console.run(f"{SESSION_ENV}; (dolphin &) >/dev/null 2>&1", timeout=90)
        time.sleep(12)
        _s, out = console.run("echo DOLPHIN=$(pgrep -x dolphin | wc -l)", timeout=60)
        if "DOLPHIN=0" in out:
            raise AssertionError(
                "dolphin did not start, so the window frame would be a desktop "
                "labelled 'window'."
            )
        _capture(vm, "window", theme)

        # Menu: proven on screen before the shutter, and captured without the
        # wake-click that used to dismiss it.
        _open_menu_asserted(vm, console, theme)
        _capture(vm, "menu", theme, disturb=False)
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
        _close_apps(console)

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
