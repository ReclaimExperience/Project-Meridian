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

from harness.screen import wait_for_screen
from harness.vm import VM

BUDGETS = json.loads(
    (Path(__file__).resolve().parents[2] / "perf" / "budgets.json").read_text()
)

SETTLE_SECONDS = 120

# Processes an ADR says must not be running once the desktop is idle, and why.
# This belongs to the perf suite because "is it running" and "what does idle
# cost" are the same question: every one of these was disabled for a resource
# reason, and a disable that did not take is invisible until someone measures.
#
# baloo_file is here because masking baloo_file.service did NOT stop it. It is
# started by /etc/xdg/autostart/baloo_file.desktop, whose condition defaults to
# true when unset, so the mask was recorded as satisfying ADR-016 while the
# indexer ran anyway — found at 28.4 MiB in the first real measurement.
FORBIDDEN_AT_IDLE = {
    "baloo_file": (
        "ADR-016 disables Baloo. Masking baloo_file.service is not sufficient: "
        "the XDG autostart entry starts it regardless unless "
        "/etc/xdg/baloofilerc sets Indexing-Enabled=false."
    ),
}


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


def idle_ram_budget(software_rendering: bool) -> tuple[int, int, str]:
    """The applicable idle-RAM gate and target, and which name they are.

    ADR-017: idle RAM has two names because it is two numbers.

      ram.idle.product  GPU-rendered. The PRD 1.5 metric, and the only one a
                        release claim may cite.
      ram.idle.ci       product + render_offset. The llvmpipe VM we can run per
                        PR. A tripwire, not evidence.

    The CI gate is COMPUTED here and stored nowhere, so moving it means editing
    the offset's provenance record in budgets.json and saying what was
    re-measured — which is the difference between a calibration and a fudge.

    Choosing by what the run ACTUALLY rendered with, not by a flag, is the whole
    point: comparing a software-rendered number against the product gate is the
    error that made this look like a 300 MiB problem when it was 116.
    """
    idle = BUDGETS["idle_ram"]
    gate = idle["product"]["gate_mib"]
    target = idle["product"]["target_mib"]
    if not software_rendering:
        return gate, target, "ram.idle.product"
    offset = idle["render_offset"]["value_mib"]
    return gate + offset, target + offset, "ram.idle.ci"


def _verdict(
    name: str, measured: float, unit: str, budget: dict | None = None
) -> tuple[bool, str]:
    budget = budget or BUDGETS[name]
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
    if vm.gl:
        # Under GL the framebuffer is a dmabuf and QMP screendump answers "no
        # surface", so the picture-based check is unavailable — and ADR-017 makes
        # the GPU-rendered number the PRODUCT metric, so "cannot screenshot"
        # must not mean "cannot measure".
        #
        # Wait for the greeter's own session instead. This is weaker than seeing
        # the screen, so it is backed up below: plasmashell appearing after the
        # password is typed is itself proof the keystrokes landed. If they had
        # gone nowhere, that wait fails and says so, rather than a number being
        # reported from a VM that never logged in.
        console.wait_until(
            "loginctl list-sessions --no-legend 2>/dev/null || true",
            lambda out: "plasmalogin" in out or "seat0" in out,
            timeout=300,
            description="a greeter session (GL: screenshots unavailable)",
        )
        print("perf: greeter session is up (no screenshot: GL framebuffer)")
    else:
        # See smoke: typing a password at a black screen produces a timeout that
        # blames whatever is waited on next.
        wait_for_screen(vm, "the greeter", keep_as=f"perf-greeter-{vm.arch}")
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

    # What is drawing the desktop, recorded alongside the number it explains.
    # The harness boots virtio-vga with no host GL passthrough, so the guest may
    # be rendering in software (llvmpipe), which allocates per-thread tile
    # buffers and costs hundreds of MiB that no machine with a working GPU driver
    # pays. PRD 2 sets the budget "in a 4 GB VM", so if this says llvmpipe then
    # part of what the gate measures is an artifact of how we measure it, and
    # that belongs in the evidence rather than in someone's memory.
    _status, renderer = console.run(
        "journalctl -b --no-pager 2>/dev/null | "
        "grep -aoiE 'llvmpipe|softpipe|virgl|swrast' | sort -u | head -5; "
        "echo '--drm--'; ls /sys/class/drm/ 2>/dev/null | head -5",
        timeout=90,
    )
    software_rendering = any(
        word in renderer.lower() for word in ("llvmpipe", "softpipe", "swrast")
    )

    forbidden_running = {}
    for name in FORBIDDEN_AT_IDLE:
        _status, found = console.run(f"pgrep -a {name} || true", timeout=30)
        if name in found:
            forbidden_running[name] = found.strip()

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

    # --- where the memory went -----------------------------------------------
    #
    # Captured on every run, not only on failure. "Idle RAM is 1448 MiB" is a
    # number; "user.slice holds 900 MiB and the top process is X" is something a
    # work package can act on. Collecting it only when the gate trips means the
    # first over-budget run has to be repeated before anyone can start.
    _status, by_process = console.run(
        "ps -eo rss=,comm= --sort=-rss | head -20", timeout=60
    )
    # PSS, because RSS is not a savings list and reading it as one is how an
    # afternoon gets spent. plasma-keyboard was second by RSS at 256 MiB;
    # killing it in a live session freed -5.6 MiB, because almost all of that
    # was shared Qt/QML pages plasmashell and kwin map too. PSS divides each
    # shared page among its mappers, so these figures approximately SUM to what
    # is actually in use — which makes them the ones worth acting on.
    _status, by_pss = console.run(
        "for f in /proc/[0-9]*/smaps_rollup; do "
        "p=${f%/smaps_rollup}; "
        "v=$(awk '/^Pss:/{print $2; exit}' \"$f\" 2>/dev/null); "
        '[ -n "$v" ] && echo "$v $(cat ${p}/comm 2>/dev/null)"; '
        "done | sort -rn | head -20",
        timeout=120,
    )
    _status, by_slice = console.run(
        "for s in user.slice system.slice init.scope; do "
        "printf '%s %s\\n' \"$s\" "
        '"$(cat /sys/fs/cgroup/$s/memory.current 2>/dev/null || echo 0)"; done',
        timeout=60,
    )
    top = []
    for line in by_process.splitlines():
        parts = line.split(None, 1)
        if len(parts) == 2 and parts[0].isdigit():
            top.append(
                {"mib": round(int(parts[0]) / 1024, 1), "comm": parts[1].strip()}
            )
    pss = []
    for line in by_pss.splitlines():
        parts = line.split(None, 1)
        if len(parts) == 2 and parts[0].isdigit():
            pss.append(
                {"mib": round(int(parts[0]) / 1024, 1), "comm": parts[1].strip()}
            )

    slices = {}
    for line in by_slice.splitlines():
        parts = line.split()
        if len(parts) == 2 and parts[1].isdigit():
            slices[parts[0]] = round(int(parts[1]) / 1024 / 1024, 1)

    return {
        "idle_ram_mib": round(used_mib, 1),
        "mem_total_mib": round(fields["MemTotal"] / 1024, 1),
        "boot_seconds": round(boot["total"], 2),
        "boot_breakdown": {k: round(v, 2) for k, v in boot.items() if k != "total"},
        "wall_clock_to_console_seconds": round(wall_clock_to_console, 2),
        "settle_seconds": SETTLE_SECONDS,
        "systemd_analyze_raw": analyze.strip(),
        "forbidden_running": forbidden_running,
        "renderer_probe": renderer.strip(),
        "software_rendering": software_rendering,
        "top_processes_mib": top[:20],
        "top_processes_pss_mib": pss[:20],
        "pss_total_visible_mib": round(sum(e["mib"] for e in pss), 1),
        "cgroup_slices_mib": slices,
    }


def run(vm: VM, credentials: dict, only: str | None = None) -> None:
    """Measure both, then apply the gates.

    `only` lets tests/perf/idle_ram.sh and boot_time.sh each enforce one budget
    while paying for a single boot. Both numbers are always MEASURED and always
    recorded — narrowing the gate must never narrow the evidence, or the
    unreported number is free to drift.
    """
    results = measure(vm, credentials)

    ram_gate, ram_target, ram_name = idle_ram_budget(
        bool(results.get("software_rendering"))
    )
    results["idle_ram_budget_name"] = ram_name
    results["idle_ram_gate_mib"] = ram_gate
    results["idle_ram_target_mib"] = ram_target
    if ram_name == "ram.idle.ci":
        offset = BUDGETS["idle_ram"]["render_offset"]
        results["render_offset_mib"] = offset["value_mib"]
        print(
            f"perf: gating on {ram_name} = {ram_gate} MiB "
            f"({BUDGETS['idle_ram']['product']['gate_mib']} product "
            f"+ {offset['value_mib']} render offset, ADR-017)."
        )
        print("perf: this is the TRIPWIRE, not the product number. A green run here")
        print("perf: does not support a claim about idle RAM on real hardware.")
    else:
        print(f"perf: gating on {ram_name} = {ram_gate} MiB (GPU-rendered, ADR-017)")

    checks = {
        "idle_ram_mib": (
            "idle RAM",
            results["idle_ram_mib"],
            " MiB",
            {
                "gate": ram_gate,
                "target": ram_target,
                "conditions": f"{ram_name}, ADR-017",
            },
        ),
        "boot_seconds": ("boot time", results["boot_seconds"], "s", None),
    }
    print(f"perf: boot breakdown {results['boot_breakdown']}")
    print(f"perf: RAM measured in a {results['mem_total_mib']:.0f} MiB VM")
    if results.get("software_rendering"):
        print(
            "perf: NOTE — the guest is rendering in SOFTWARE. Some of the idle\n"
            "perf:        RAM below is llvmpipe's tile buffers, which a machine\n"
            "perf:        with a real GPU driver does not allocate."
        )
    if results.get("cgroup_slices_mib"):
        print(f"perf: by slice {results['cgroup_slices_mib']}")
    if results.get("top_processes_pss_mib"):
        print("perf: by PSS (shared pages divided among mappers; these ~sum):")
        for entry in results["top_processes_pss_mib"][:12]:
            print(f"perf:   {entry['mib']:>7.1f} MiB  {entry['comm']}")
        print(
            f"perf:   {results['pss_total_visible_mib']:>7.1f} MiB  "
            "= total of the processes visible to this user"
        )
    else:
        print("perf: PSS unavailable; RSS below OVERSTATES per-process cost")
        for entry in results.get("top_processes_mib", [])[:12]:
            print(f"perf:   {entry['mib']:>7.1f} MiB  {entry['comm']} (RSS)")

    failures = []
    for name, detail in results.get("forbidden_running", {}).items():
        print(f"perf: {name} is RUNNING and must not be")
        failures.append(
            f"{name} is running at idle.\n  {FORBIDDEN_AT_IDLE[name]}\n"
            f"  guest said: {detail}"
        )
    if not results.get("forbidden_running"):
        print(f"perf: none of {sorted(FORBIDDEN_AT_IDLE)} are running (as required)")

    for key, (label, measured, unit, budget) in checks.items():
        ok, message = _verdict(key, measured, unit, budget)
        print(f"perf: {label} {'ok' if ok else 'OVER GATE'} — {message}")
        results[f"{key}_within_gate"] = ok
        if not ok and (only is None or only == key):
            failures.append(f"{label}: {message}")

    # NOT "perf-<arch>": run.py writes the per-run verdict under
    # "<suite>-<arch>.json", so that name collides and the runner's report - the
    # one written last - silently replaced every measurement this suite took.
    # The first over-budget run lost its own breakdown that way.
    vm.write_report(f"perf-budgets-{vm.arch}", results)
    if failures:
        raise AssertionError("\n".join(failures))
