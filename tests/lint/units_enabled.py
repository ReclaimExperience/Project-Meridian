#!/usr/bin/env python3
"""A unit that ships but is never enabled does nothing.

This build enables NOTHING automatically. There is no `systemctl preset-all`
anywhere in the Containerfile, and no package we install ships a preset that
covers its own units. `WantedBy=` in a unit file is inert until something
creates the symlink — so a unit can be installed, correct, and silently never
run.

greenboot was in exactly that state: the package installed, its health checks
present, `WantedBy=multi-user.target` written in the unit — and no symlink. The
automatic rollback ADR-008 promises would not have happened on any machine, and
the rollback drill would have been the first thing to notice, at the cost of a
full VM cycle.

So this asserts that every unit our design depends on is enabled the only way
this image enables anything: an explicit symlink under
`os/rootfs/etc/systemd/system/`. Same family as wired.py — the subject is not
whether the thing is correct, but whether anything ever invokes it.
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SYSTEMD = ROOT / "os" / "rootfs" / "etc" / "systemd" / "system"

# unit -> why the product breaks silently without it.
REQUIRED = {
    "meridian-update-status.service": (
        "Settings reads /run/meridian/update-status.json; without this the file "
        "never exists and the Updates page has nothing true to show (contract 8.0)"
    ),
    "meridian-os-update.timer": (
        "no timer, no update checks — the machine silently stops updating, which "
        "is the worst available failure for an auto-updating OS (ADR-008)"
    ),
    "meridian-flatpak-update.timer": "app updates stop (ADR-008)",
    "greenboot-healthcheck.service": (
        "the health checks never run, so a broken update is never detected and "
        "ADR-008's automatic rollback never happens. The image would ship with "
        "greenboot installed and inert"
    ),
    "greenboot-set-rollback-trigger.service": (
        "the rollback trigger is never armed for ostree-finalize-staged, so even "
        "a detected failure would not roll anything back"
    ),
}


def enablement_links() -> dict[str, list[str]]:
    """Every unit enabled by a symlink under etc/systemd/system/*.wants|requires."""
    found: dict[str, list[str]] = {}
    if not SYSTEMD.is_dir():
        return found
    for directory in SYSTEMD.iterdir():
        if not directory.is_dir():
            continue
        if not (
            directory.name.endswith(".wants") or directory.name.endswith(".requires")
        ):
            continue
        for link in directory.iterdir():
            found.setdefault(link.name, []).append(directory.name)
    return found


def main() -> int:
    failures = 0
    links = enablement_links()

    print("units this design depends on must be enabled by an explicit symlink")
    for unit, why in REQUIRED.items():
        where = links.get(unit)
        if not where:
            print(f"  FAIL  {unit} is not enabled anywhere.")
            print(f"      {why}.")
            print("      Nothing in this build runs `systemctl preset-all`, so a")
            print("      WantedBy= line in the unit file does nothing on its own.")
            failures += 1
        else:
            print(f"  ok    {unit}  <- {', '.join(sorted(where))}")

    # A symlink pointing at a unit that does not exist is worse than no symlink:
    # it reads as enabled in review and fails at boot.
    print("\nevery enablement symlink must point at a real unit path")
    for unit, dirs in sorted(links.items()):
        for directory in dirs:
            link = SYSTEMD / directory / unit
            target = Path(link.readlink()) if link.is_symlink() else None
            if target is None:
                print(f"  FAIL  {directory}/{unit} is not a symlink")
                failures += 1
            elif not str(target).startswith("/usr/lib/systemd/"):
                print(f"  FAIL  {directory}/{unit} -> {target}")
                print("      Enablement symlinks must point into /usr/lib/systemd/,")
                print("      which is where units actually live in the image.")
                failures += 1
            else:
                print(f"  ok    {directory}/{unit} -> {target}")

    print()
    if failures:
        print(f"units-enabled: {failures} failure(s)")
        return 1
    print(f"units-enabled: {len(REQUIRED)} required unit(s) enabled, all links valid")
    return 0


if __name__ == "__main__":
    sys.exit(main())
