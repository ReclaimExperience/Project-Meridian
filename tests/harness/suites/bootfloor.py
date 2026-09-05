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


def run(vm: VM, credentials: dict) -> None:
    console = vm.console
    user, password = credentials["user"], credentials["password"]
    results = []

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

        # Put it back to a sane state before the next case, so a failure is
        # attributable to the corruption under test and not to the last one.
        console.run(
            "sudo -n grub2-editenv /boot/grub2/grubenv set boot_success=1 2>&1 || true",
            timeout=90,
        )
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
