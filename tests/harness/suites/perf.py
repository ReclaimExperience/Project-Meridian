"""Perf suite (PRD WP-02): the idle-RAM and boot-time budgets from PRD 2.

Two numbers, both hard gates, both read from the guest's own instrumentation
rather than from how long this script felt like waiting:

  * **Boot time** comes from `systemd-analyze`, which reports firmware, loader,
    kernel and userspace from timestamps the kernel and systemd recorded
    themselves. Host wall-clock is captured too, but only as a cross-check — a
    CI runner under load takes longer to fork qemu, and that is not the image
    getting slower. Failing a build for the runner's mood teaches people to
    re-run until green, which is how a gate stops meaning anything.
  * **Idle RAM** is MemTotal - MemAvailable after a real GUI login and a
    two-minute settle, because PRD 2 says "idle RAM after login" and a console
    login has no desktop in it. MemAvailable rather than MemFree: reclaimable
    page cache is not memory the user has lost, and counting it would make the
    number look bad for reasons nobody can act on.

The settle matters. Plasma is still starting services, indexing nothing (Baloo
is masked, ADR-016) and populating caches for well over a minute after the
session appears. Measuring at t+5s produces a number that is both worse and
less stable than the one a user would ever experience.

Rule R-E: the budgets live in tests/perf/budgets.json and are not edited to make
a build pass.
"""

from __future__ import annotations

import json
import re
import time
from pathlib import Path

from harness.vm import VM

BUDGETS = json.loads(
    (Path(__file__).resolve().parents[2] / "perf" / "budgets.json").read_text()
)

SETTLE_SECONDS = 120


def _parse_systemd_analyze(text: str) -> dict[str, float]:
    """Pull the component times out of `systemd-analyze time`.

    Output looks like:
      Startup finished in 3.494s (firmware) + 2.1s (loader) + 4.3s (kernel)
        + 12.9s (userspace) = 22.8s

    Parsed rather than regex-matched on the total alone so a regression says
    WHICH stage grew. "Boot got slower" is not actionable; "userspace grew 6s"
    is. Values can be "1min 2.3s", which is why this is not a simple float().
    """
    parts: dict[str, float] = {}
    for value, label in re.findall(
        r"((?:\d+min\s+)?[\d.]+m?s)\s*\((firmware|loader|kernel|initrd|userspace)\)",
        text,
    ):
        parts[label] = _duration_seconds(value)
    total = re.search(r"=\s*((?:\d+min\s+)?[\d.]+m?s)\s*$", text.strip(), re.MULTILINE)
    if total:
        parts["total"] = _duration_seconds(total.group(1))
    elif parts:
        # No "= total" when a stage is absent (containers, some firmware). Sum
        # what we have rather than silently reporting no total at all.
        parts["total"] = sum(parts.values())
    return parts


def _duration_seconds(value: str) -> float:
    """'1min 2.3s' / '984ms' / '4.5s' -> seconds."""
    seconds = 0.0
    minutes = re.search(r"(\d+)min", value)
    if minutes:
        seconds += int(minutes.group(1)) * 60
    ms = re.search(r"(?<![\d.])([\d.]+)ms", value)
    if ms:
        return seconds + float(ms.group(1)) / 1000
    rest = re.search(r"(?<![\d.])([\d.]+)s", value)
    if rest:
        seconds += float(rest.group(1))
    return seconds


def _verdict(name: str, measured: float, unit: str) -> tuple[bool, str]:
    budget = BUDGETS[name]
    gate, target = budget["gate"], budget["target"]
    if measured > gate:
        return False, (
            f"{measured:.1f}{unit} EXCEEDS the {gate}{unit} gate "
            f"({budget['conditions']}).\n"
            "  PRD WP-02: if this is over the gate, escalate — do not hide it, "
            "and do not edit the budget (rule R-E)."
        )
    if measured > target:
        return True, (
            f"{measured:.1f}{unit} is within the {gate}{unit} gate but over the "
            f"{target}{unit} target — headroom is {gate - measured:.1f}{unit}."
        )
    return True, f"{measured:.1f}{unit}, inside the {target}{unit} target."


def measure(vm: VM, credentials: dict) -> dict:
    """Boot, log in, settle, and read both numbers. Returns the evidence."""
    console = vm.console
    user, password = credentials["user"], credentials["password"]

    console.login(user, password, timeout=600)
    wall_clock_to_console = vm.uptime_seconds

    console.wait_until(
        "systemctl is-active display-manager",
        lambda out: any(ln.strip() == "active" for ln in out.splitlines()),
        timeout=300,
        description="display-manager to be active",
    )

    # --- boot time -----------------------------------------------------------
    #
    # `systemd-analyze time` fails while the boot is still in progress, so ask
    # only once the display manager is up — which is the point PRD 2 measures to.
    _status, analyze = console.run("systemd-analyze time", timeout=120)
    boot = _parse_systemd_analyze(analyze)
    if "total" not in boot:
        raise AssertionError(
            "could not read a boot time from systemd-analyze. Refusing to report "
            "a number this suite did not actually measure.\n"
            f"  guest said: {analyze.strip()!r}"
        )

    # --- idle RAM ------------------------------------------------------------
    vm.qmp.wake_display()
    _status, before = console.run("pgrep -a plasmashell || true", timeout=30)
    assert "plasmashell" not in before, (
        "plasmashell was running before the GUI login, so this measures a "
        "session this suite did not start.\n"
        f"  console said: {before.strip()!r}"
    )
    vm.qmp.type_text(password)
    vm.qmp.key("ret")
    console.wait_until(
        "pgrep -a plasmashell || true",
        lambda out: "plasmashell" in out,
        timeout=420,
        description="plasmashell to start after the GUI login",
    )

    print(f"perf: settling for {SETTLE_SECONDS}s before measuring idle RAM")
    time.sleep(SETTLE_SECONDS)

    _status, meminfo = console.run(
        "grep -E '^(MemTotal|MemAvailable|MemFree):' /proc/meminfo", timeout=60
    )
    fields = {
        m.group(1): int(m.group(2))
        for m in re.finditer(r"(MemTotal|MemAvailable|MemFree):\s+(\d+) kB", meminfo)
    }
    missing = {"MemTotal", "MemAvailable"} - fields.keys()
    if missing:
        raise AssertionError(
            f"/proc/meminfo did not report {sorted(missing)}; refusing to invent "
            f"a memory number.\n  guest said: {meminfo.strip()!r}"
        )
    used_mib = (fields["MemTotal"] - fields["MemAvailable"]) / 1024

    return {
        "idle_ram_mib": round(used_mib, 1),
        "mem_total_mib": round(fields["MemTotal"] / 1024, 1),
        "boot_seconds": round(boot["total"], 2),
        "boot_breakdown": {k: round(v, 2) for k, v in boot.items() if k != "total"},
        "wall_clock_to_console_seconds": round(wall_clock_to_console, 2),
        "settle_seconds": SETTLE_SECONDS,
        "systemd_analyze_raw": analyze.strip(),
    }


def run(vm: VM, credentials: dict, only: str | None = None) -> None:
    """Measure both, then apply the gates.

    `only` lets tests/perf/idle_ram.sh and boot_time.sh each enforce one budget
    while paying for a single boot. Both numbers are always MEASURED and always
    recorded — narrowing the gate must never narrow the evidence, or the
    unreported number is free to drift.
    """
    results = measure(vm, credentials)

    checks = {
        "idle_ram_mib": ("idle RAM", results["idle_ram_mib"], " MiB"),
        "boot_seconds": ("boot time", results["boot_seconds"], "s"),
    }
    print(f"perf: boot breakdown {results['boot_breakdown']}")
    print(f"perf: RAM measured in a {results['mem_total_mib']:.0f} MiB VM")

    failures = []
    for key, (label, measured, unit) in checks.items():
        ok, message = _verdict(key, measured, unit)
        print(f"perf: {label} {'ok' if ok else 'OVER GATE'} — {message}")
        results[f"{key}_within_gate"] = ok
        if not ok and (only is None or only == key):
            failures.append(f"{label}: {message}")

    vm.write_report(f"perf-{vm.arch}", results)
    if failures:
        raise AssertionError("\n".join(failures))
