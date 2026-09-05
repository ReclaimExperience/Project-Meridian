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

    # PREVENTION first, on the boot we already have: a healthy boot must give
    # a life back. Everything below tests recovery from a machine that already
    # ran out of them.
    console.login(user, password, timeout=600)
    _assert_counter_resets(console)

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
