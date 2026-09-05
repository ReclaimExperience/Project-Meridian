"""The bootloader must have a floor: no reachable state leaves a machine dead.

The mirror of the rollback drill, and the case that drill never covered. The
rollback drill proves greenboot rolls back **when a fallback deployment
exists**. This one proves the machine still boots when it does not — which is
the state a real machine was found in:

    boot_counter=-1   boot_success=0   saved_entry=1

...against a menu with one entry. GRUB was pointed at a deployment that is not
there, so it booted nothing, handed control back to the firmware, and the
machine was dead at the bootloader. On a machine with no terminal by design
(INV-0) and a read-only `/boot` that makes `grub2-editenv` fail from inside the
OS, there is no in-band way back.

Acceptance is one sentence: **no reachable state leaves the machine
unbootable.**

The drill deliberately corrupts the boot environment the way a real exhausted
machine does, then asserts a login prompt still appears.
"""

from __future__ import annotations

import time

from harness.vm import VM

# The states a machine can actually reach on its own. Each is applied to the
# real grubenv from the GRUB command line, then the machine is rebooted.
CORRUPTIONS = (
    (
        "counter exhausted, single deployment",
        # Exactly what was found in the wild.
        ("set boot_counter=-1", "set boot_success=0", "set saved_entry=1"),
    ),
    (
        "saved_entry far out of range",
        ("set saved_entry=99", "set boot_success=0"),
    ),
)


def _at_grub(console, timeout: float = 90.0) -> None:
    """Catch GRUB's menu and drop to its command line."""
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if "GRUB version" in console._clean():
            break
        time.sleep(0.02)
    else:
        raise AssertionError(
            "no GRUB banner within "
            f"{timeout:.0f}s — the firmware never reached the bootloader."
        )
    console.send("c")
    time.sleep(1.5)


def _grubenv(console) -> dict:
    """Read the boot environment as a dict, or fail saying why."""
    _s, out = console.run(
        "sudo -n grub2-editenv /boot/grub2/grubenv list 2>&1", timeout=90
    )
    env = {}
    for line in out.splitlines():
        line = line.strip()
        if "=" in line and not line.startswith("#") and " " not in line.split("=")[0]:
            key, _, value = line.partition("=")
            env[key.strip()] = value.strip()
    if not env:
        raise AssertionError(
            f"could not read grubenv; guest said: {out.strip()[:200]!r}"
        )
    return env


def _assert_greenboot_live(console) -> None:
    """Refuse to judge the product on a disk whose greenboot has been muzzled.

    The theme capture suite masks greenboot-healthcheck and redboot-auto-reboot
    so a mid-capture reboot cannot ruin a screenshot, and those masks are
    persistent — they live in /etc on a disk that survives every later run. A
    prevention check on such a disk observes boot_success staying 0 and blames
    the product for a silence the harness imposed.

    So the environment is asserted before the verdict is. A contaminated disk
    must fail LOUDLY as contamination, not quietly as a defect.
    """
    _s, out = console.run(
        "systemctl is-enabled greenboot-healthcheck.service 2>&1; "
        "systemctl is-enabled redboot-auto-reboot.service 2>&1",
        timeout=90,
    )
    if "masked" in out:
        raise AssertionError(
            "greenboot is MASKED on this disk, so nothing can confirm a boot "
            "and boot_success can never reach 1.\n"
            f"  guest said: {out.strip()[:160]!r}\n"
            "  This is harness contamination, not a product defect: the theme "
            "capture suite masks these and the mask persists on the disk. Run "
            "against a freshly built image, or unmask before judging."
        )


def _await_greenboot(console, timeout: float = 420.0) -> None:
    """Let the health check FINISH before judging what it did.

    greenboot runs asynchronously. The console is ready long before the check
    is: it polls for a usable desktop, which on this image takes ~80s, and only
    then does anything write boot_success. Reading grubenv at login therefore
    always sees boot_success=0 and a counter not yet returned — and reports the
    accretion defect on a machine that is about to behave perfectly.

    That is a race in the TEST, and it produced a convincing false positive:
    counter 3 -> 2, boot_success 0, exactly the real defect's signature.
    """
    deadline = time.monotonic() + timeout
    last = ""
    while time.monotonic() < deadline:
        _s, out = console.run(
            "systemctl show -p ActiveState -p SubState --value "
            "greenboot-healthcheck.service 2>&1 | tr '\\n' '/'",
            timeout=90,
        )
        last = out.strip()
        # activating/start means it is still polling; anything settled is done.
        if "activating" not in last and "start" not in last:
            print(f"bootfloor: greenboot settled at {last[-40:]!r}")
            return
        time.sleep(10)
    raise AssertionError(
        f"greenboot-healthcheck never finished within {timeout:.0f}s "
        f"(last state {last[-60:]!r}). A health check that never completes "
        "cannot confirm a boot, so the counter is never returned — which is "
        "the accretion path to an unbootable machine."
    )


def _assert_counter_resets(console) -> None:
    """A healthy boot must clear the boot counter.

    The cure proves a machine recovers from a corrupt boot environment. This is
    the other half: corruption must not ACCRETE in the first place. The wild
    brick was reached one decrement at a time over many ordinary boots, because
    nothing ever reset the counter — each boot spent one more life and no boot
    ever gave one back.

    greenboot resets it via grub2-editenv on a healthy boot, so this asserts
    the outcome of that rather than the presence of the unit (R-I).
    """
    env = _grubenv(console)
    counter = env.get("boot_counter")
    success = env.get("boot_success")
    print(f"bootfloor: after a healthy boot grubenv is {env}")
    if success != "1":
        raise AssertionError(
            f"boot_success is {success!r} after a healthy boot, not '1'. "
            "GRUB treats the boot as unconfirmed and will spend a life on the "
            "next one; enough of those and the machine has none left."
        )
    # Absent is the ideal: greenboot removes the key entirely once a boot is
    # confirmed. A counter still at its ceiling is also fine. A counter part
    # way down means lives are being spent and never returned.
    if counter is not None and counter not in ("3", "-1"):
        pass
    if counter is not None and counter.isdigit() and int(counter) < 3:
        raise AssertionError(
            f"boot_counter is {counter} after a HEALTHY boot: it is being "
            "decremented and never reset. That is how a machine walks itself "
            "down to unbootable one ordinary boot at a time."
        )


def run(vm: VM, credentials: dict) -> None:
    console = vm.console
    user, password = credentials["user"], credentials["password"]
    results = []

    # ---------------------------------------------------------- prevention --
    #
    # ARM the counter first. Reading grubenv on a machine that already has
    # boot_success=1 proves nothing: it passes whether greenboot reset it this
    # boot or it happened to be sitting that way already. The first version of
    # this check did exactly that and passed trivially.
    #
    # /boot is read-only from userspace — that is half of why a bricked machine
    # cannot heal itself — so the counter is armed from the GRUB command line,
    # which is the only writer available before Linux is up.
    print("bootfloor: arming a boot counter, then booting healthy")
    _at_grub(console)
    for command in (
        "set boot_counter=3",
        "set boot_success=0",
        "save_env boot_counter boot_success",
        # `reboot`, not `boot`. At the grub> prompt no kernel has been loaded,
        # so `boot` has nothing to start and the machine sits there until the
        # console times out — which reads as "the VM never got past the
        # bootloader" and looks exactly like the brick this suite hunts.
        # save_env has already persisted the change; the next boot picks it up.
        "reboot",
    ):
        console.send(command + "\n")
        time.sleep(1.2)

    console.login(user, password, timeout=600)
    _assert_greenboot_live(console)
    _await_greenboot(console)
    _assert_counter_resets(console)
    console.send_line("sudo -n systemctl reboot")
    time.sleep(5)

    # ---------------------------------------------------------------- cure --
    for name, commands in CORRUPTIONS:
        print(f"bootfloor: applying '{name}'")
        _at_grub(console)
        for command in (*commands, "save_env boot_counter boot_success saved_entry"):
            console.send(command + "\n")
            time.sleep(1.2)
        # save_env only takes effect on the NEXT boot: `normal` does not
        # re-enter the boot path in the same session.
        console.send("reboot\n")
        time.sleep(3)

        try:
            console.login(user, password, timeout=420)
            results.append((name, True, ""))
            print(f"bootfloor: PASS — machine still booted after '{name}'")
        except Exception as exc:  # noqa: BLE001 — the failure IS the result
            results.append((name, False, str(exc)[:200]))
            print(f"bootfloor: FAIL — '{name}' left the machine unbootable")
            break

        console.send_line("sudo -n systemctl reboot")
        time.sleep(5)

    vm.write_report(
        f"bootfloor-{vm.arch}",
        {
            "cases": [
                {"state": n, "still_booted": ok, "error": err} for n, ok, err in results
            ]
        },
    )
    dead = [n for n, ok, _ in results if not ok]
    if dead:
        raise AssertionError(
            "the bootloader has no floor: "
            f"{dead} left the machine unbootable.\n"
            "  A machine that cannot boot cannot be recovered by its owner: "
            "/boot is read-only from userspace, so grub2-editenv fails from "
            "inside the OS, and INV-0 means there is no terminal to use anyway."
        )
    print(f"bootfloor: all {len(results)} corrupt state(s) still booted")
