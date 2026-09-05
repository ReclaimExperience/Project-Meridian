"""Measure how long the boot actually takes, on a real built image.

The greenboot health check has a deadline, and the deadline is the single dial
between two failure modes that have both now been observed:

  * too tight — the original 90s against a target that cleared at ~80s. Every
    lost race spent a boot attempt, and a machine was found with none left.
  * too loose — the current 300s. The rollback drill showed the check correctly
    refusing a sabotaged boot but taking the full deadline to decide, so
    rollback needs ~3 x 300s and overruns the drill's own 900s patience.

Picking a number between those by feel is how the first one was chosen. This
suite produces the measurement PRD 10.2's Boot->greeter column asks for, and it
runs in CI because that is where a freshly built image and its per-build
credentials already sit together — no credential has to travel to measure it.
"""

from __future__ import annotations

import re

from harness.vm import VM


def _monotonic_us(console, unit: str) -> int | None:
    """When `unit` finished activating, in microseconds since boot."""
    _s, out = console.run(
        f"systemctl show -p ActiveEnterTimestampMonotonic --value {unit} 2>&1",
        timeout=90,
    )
    match = re.search(r"(\d+)", out)
    value = int(match.group(1)) if match else 0
    return value or None


def run(vm: VM, credentials: dict) -> None:
    console = vm.console
    console.login(credentials["user"], credentials["password"], timeout=600)

    _s, mask = console.run(
        "systemctl is-enabled NetworkManager-wait-online.service 2>&1", timeout=90
    )
    masked = "masked" in mask
    print(f"boottime: NetworkManager-wait-online is {mask.strip()[-12:]!r}")

    # Wait for the target so the measurement is of a settled boot, not a
    # snapshot taken mid-way.
    console.wait_until(
        "systemctl is-active graphical.target || true",
        lambda out: "active" in out and "inactive" not in out,
        timeout=420,
        description="graphical.target to settle",
    )

    greeter = _monotonic_us(console, "display-manager.service")
    graphical = _monotonic_us(console, "graphical.target")
    if not greeter or not graphical:
        raise AssertionError(
            "could not read activation timestamps "
            f"(greeter={greeter}, graphical={graphical})"
        )
    greeter_s, graphical_s = greeter / 1e6, graphical / 1e6
    print(
        f"boottime: greeter at {greeter_s:.1f}s, graphical.target at {graphical_s:.1f}s"
    )

    _s, chain = console.run(
        "systemd-analyze critical-chain graphical.target --no-pager 2>&1 | head -12",
        timeout=120,
    )
    print("boottime: critical chain\n" + chain.strip()[:700])

    # The recommendation, stated so nobody has to infer it: double the slowest
    # thing the check waits on. Doubling is the margin; the measurement is the
    # basis. Slow real hardware will move this, which is why 10.2 has a column.
    suggested = max(60, int(graphical_s * 2))
    print(
        f"boottime: measured deadline basis {graphical_s:.0f}s -> suggest "
        f"{suggested}s (slowest observed x 2)"
    )

    vm.write_report(
        f"boottime-{vm.arch}",
        {
            "greeter_seconds": round(greeter_s, 1),
            "graphical_target_seconds": round(graphical_s, 1),
            "wait_online_masked": masked,
            "suggested_deadline_seconds": suggested,
            "note": (
                "CI VM under llvmpipe. PRD 10.2's low-end row governs the "
                "shipped deadline; this is a floor, not that number."
            ),
        },
    )
