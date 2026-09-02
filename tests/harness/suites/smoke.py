"""Smoke suite (PRD WP-03): boots to SDDM, login succeeds, plasmashell alive,
`systemctl --failed` empty.

This is the suite every later work package's acceptance leans on, so it asserts
the minimum that makes a build worth looking at and nothing more. Anything
richer belongs in a Zero-Terminal story (PRD 10.1), where a failure names a user
outcome rather than a daemon.

Two things learned building it, worth knowing before adding suites:

  * **systemd does not narrate the display manager to serial.** 71 unit lines
    reach the console and the graphical stage is not among them - plymouth's
    console handoff swallows it. Ask systemd directly rather than scraping the
    boot log for a unit description that will never appear.
  * **A console login is not a desktop login.** `plasmashell` starts when a
    session begins through SDDM, so the GUI login has to actually happen. An
    earlier version asserted plasmashell after a serial-console login and would
    have failed on a perfectly good image.

No assertion here depends on the network: PRD WP-03 forbids that in smoke,
because a registry hiccup must never read as a broken image.
"""

from __future__ import annotations

from harness.vm import VM


def run(vm: VM, credentials: dict) -> None:
    console = vm.console
    user, password = credentials["user"], credentials["password"]

    # --- 1. userspace comes up ----------------------------------------------
    print("smoke: waiting for the console login prompt")
    console.login(user, password, timeout=600)
    print(f"smoke: logged in on the console as {user}")

    # --- 2. the display manager is actually running --------------------------
    console.wait_until(
        "systemctl is-active display-manager",
        # NOT endswith("active"): "inactive" ends with "active".
        # Any line, not the last: a kernel printk can land after the
        # output on this console. And not endswith: "inactive" ends
        # with "active". Empty output must not raise IndexError.
        lambda out: any(ln.strip() == "active" for ln in out.splitlines()),
        timeout=300,
        description="display-manager to be active",
    )
    print("smoke: display-manager is active")

    # --- 3. the greeter is drawn ---------------------------------------------
    #
    # A unit being active is not a greeter on screen. Nudge the pointer first:
    # SDDM's Breeze theme opens on a clock overlay and reveals the password
    # field only on input - WP-01's first screenshot was misread for want of it.
    vm.qmp.wake_display()
    print(f"smoke: greeter screenshot {vm.screenshot('smoke-greeter').name}")
    assert vm.qmp.is_running(), "VM stopped running before the greeter appeared"

    # --- 4. a real GUI login -------------------------------------------------
    #
    # The password field has focus once the form is revealed, so this types
    # straight into it. Typing is deliberately slow (see QMP.type_text): SDDM
    # drops keys delivered faster than a human types, and a password that loses
    # a character fails in a way that looks like a real defect.
    # Negative pre-check: prove no session exists YET, so the assertion below
    # is about our typed password and not about a session that was already
    # running. Without this, enabling autologin in a later WP would leave smoke
    # claiming "GUI login through SDDM" while the keystrokes went nowhere.
    _status, before = console.run("pgrep -a plasmashell || true", timeout=30)
    assert "plasmashell" not in before, (
        "plasmashell was already running BEFORE the GUI login, so this suite "
        "cannot tell whether logging in works.\n"
        f"  console said: {before.strip()!r}\n"
        "  If autologin is now on by design, this suite needs rewriting to "
        "assert that instead — do not delete the check."
    )

    print(f"smoke: logging in through SDDM as {user}")
    vm.qmp.type_text(password)
    vm.qmp.key("ret")

    # --- 5. the desktop shell is alive ---------------------------------------
    #
    # Checked from the console rather than by comparing pixels, so a failure
    # says which process is missing instead of "the screen differs".
    console.wait_until(
        "pgrep -a plasmashell || true",
        lambda out: "plasmashell" in out,
        timeout=420,
        description="plasmashell to start after the GUI login",
    )
    print("smoke: plasmashell is running")
    print(f"smoke: desktop screenshot {vm.screenshot('smoke-desktop').name}")

    # --- 6. no failed units --------------------------------------------------
    #
    # Last, so it sees the state after a full login rather than mid-boot.
    # `--no-legend --plain` so the parse does not depend on systemd's decorative
    # output, which differs between versions.
    _status, output = console.run("systemctl --failed --no-legend --plain", timeout=60)
    failed = [
        line
        for line in output.split("\n")
        if line.strip() and "systemctl --failed" not in line
    ]
    assert not failed, "systemctl --failed is not empty:\n  " + "\n  ".join(failed)
    print("smoke: systemctl --failed is empty")

    # --- 7. the image is ours ------------------------------------------------
    _status, output = console.run("cat /usr/lib/os-release", timeout=30)
    assert "ID=meridian" in output, f"unexpected os-release:\n{output}"
    print("smoke: os-release identifies the product")
