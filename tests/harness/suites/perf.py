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

SETTLE_SECONDS = BUDGETS["protocol"]["settle_seconds"]
PROTOCOL_RUNS = BUDGETS["protocol"]["runs"]
SHMEM_WINDOW_SECONDS = BUDGETS["protocol"]["shmem_window_seconds"]
SHMEM_INTERVAL_SECONDS = BUDGETS["protocol"]["shmem_sample_interval_seconds"]

MEMINFO_FIELDS = (
    "MemTotal|MemAvailable|MemFree|Cached|Buffers|Slab|SReclaimable|SUnreclaim|"
    "AnonPages|PageTables|Shmem|KernelStack|Mapped|Dirty"
)

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


def steady_budget(software_rendering: bool) -> tuple[float | None, float | None, str]:
    """The applicable `steady` gate and target, and which name they are.

    GPU-rendered runs gate on the product budget. Software-rendered runs would
    gate on product + render_offset — but ADR-020 §3 requires that offset to be
    re-paired in the STEADY denomination, and it has not been. The old 186.5 was
    denominated in MemTotal-MemAvailable; carrying it across denominations would
    be inventing a constant, so this returns None and the caller reports the
    numbers without pretending to judge them.
    """
    steady = BUDGETS["steady"]
    if not software_rendering:
        return steady["gate_mib"], steady["target_mib"], "steady.product"
    offset = BUDGETS["render_offset"]["value_mib"]
    if offset is None:
        return None, None, "steady.ci (offset not yet measured)"
    return steady["gate_mib"] + offset, steady["target_mib"] + offset, "steady.ci"


def pss_ratchet(software_rendering: bool) -> tuple[float, float, str, bool]:
    """The ratchet's baseline, threshold, name, and whether it GATES this run.

    ADR-021: the ratchet is a CI/llvmpipe instrument, measured directly in its own
    denomination — no offset, unlike `steady`. The asymmetry is deliberate.
    steady's canonical value is the GPU/product number, so its CI gate must
    translate forever; the ratchet's canonical value IS the CI history, so it
    translates once at bootstrap and then stops needing to.

    A GPU run therefore reports against the GPU reference and **does not gate**
    (ADR-021 §3): there are no per-PR GPU runs, and cross-comparing the two
    denominations is the exact error this ADR exists to undo — 576 was GPU-measured
    and fired at +179 on every healthy PR because llvmpipe's software-render cost
    is anonymous memory PSS counts.
    """
    ratchet = BUDGETS["userspace_pss"]
    threshold = ratchet["allowed_delta_mib"]
    if not software_rendering:
        return ratchet["gpu_reference_mib"], threshold, "pss.gpu-reference", False
    rolling = ratchet.get("rolling_baseline_mib")
    if rolling is not None:
        return rolling, threshold, "pss.ci (rolling median)", True
    return ratchet["interim_seed_mib"], threshold, "pss.ci (interim seed)", True


def _verdict(
    name: str, measured: float, unit: str, budget: dict | None = None
) -> tuple[bool, str]:
    budget = budget or BUDGETS[name]
    gate, target = budget["gate"], budget["target"]
    if measured > gate:
        return False, (
            f"{measured:.1f}{unit} EXCEEDS the {gate}{unit} gate "
            f"({budget.get('conditions', 'no conditions recorded')}).\n"
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

    # Composition, not just the total. Three structurally identical runs — same
    # processes, userspace PSS within 1.7 MiB — produced idle-RAM figures 75.4 MiB
    # apart, so the metric is moving on something that is not the desktop.
    # `MemTotal - MemAvailable` counts whatever MemAvailable's heuristic declines
    # to call reclaimable, and page cache grows as a session touches files.
    # Recording the parts is the difference between diagnosing that and arguing
    # about it.
    _status, meminfo = console.run(
        f"grep -E '^({MEMINFO_FIELDS}):' /proc/meminfo",
        timeout=60,
    )
    fields = {
        m.group(1): int(m.group(2)) for m in re.finditer(r"(\w+):\s+(\d+) kB", meminfo)
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

    composition = {
        key.lower() + "_mib": round(fields[key] / 1024, 1)
        for key in (
            "MemFree",
            "Cached",
            "Buffers",
            "Slab",
            "SReclaimable",
            "SUnreclaim",
            "AnonPages",
            "PageTables",
            "Shmem",
            "KernelStack",
            "Mapped",
            "Dirty",
        )
        if key in fields
    }

    # ADR-019 §1's candidate statistic: the claim on Pat's 4 GiB that cannot be
    # handed to the browser without swapping. File cache can be reclaimed and
    # will be; counting it made three structurally identical runs differ by
    # 75.4 MiB. Recorded alongside the old metric, gating nothing until the
    # clause 0 trigger says whether the cache account actually holds.
    # ADR-020 §1a. Shmem is deliberately NOT here: ADR-019's trigger rejected the
    # combined statistic because Shmem's 64.4 MiB spread WAS the whole variance,
    # while these four together moved by under 1 MiB. Splitting them is what lets
    # this one carry a tight gate.
    STEADY_KEYS = ("AnonPages", "SUnreclaim", "KernelStack", "PageTables")
    missing_steady = [k for k in STEADY_KEYS if k not in fields]
    if missing_steady:
        raise AssertionError(
            f"/proc/meminfo did not report {missing_steady}, so `steady` cannot be "
            "computed. Refusing to report a partial sum under a name that means a "
            f"specific set of fields.\n  guest said: {meminfo.strip()!r}"
        )
    steady_mib = sum(fields[k] for k in STEADY_KEYS) / 1024
    committed_mib = steady_mib + fields.get("Shmem", 0) / 1024
    reclaimable_mib = (
        fields.get("Cached", 0)
        + fields.get("Buffers", 0)
        + fields.get("SReclaimable", 0)
    ) / 1024

    # ADR-020 §1b: bound where the buffer pool RESTS, not where it happened to be
    # when we looked. A single sample of Shmem caught 117.8 MiB in one run and
    # ~54 in two others; the minimum across a window is the resting level, and a
    # ceiling on a transient peak would be a ceiling on luck.
    print(f"perf: sampling shmem for {SHMEM_WINDOW_SECONDS}s to find its resting level")
    shmem_samples = []
    deadline = time.monotonic() + SHMEM_WINDOW_SECONDS
    while time.monotonic() < deadline:
        _status, shm = console.run("grep '^Shmem:' /proc/meminfo", timeout=30)
        found = re.search(r"Shmem:\s+(\d+) kB", shm)
        if found:
            shmem_samples.append(int(found.group(1)) / 1024)
        time.sleep(SHMEM_INTERVAL_SECONDS)
    if not shmem_samples:
        raise AssertionError(
            "could not read Shmem across the sampling window; refusing to report a "
            "ceiling measurement this run did not take."
        )
    shmem_min_mib = min(shmem_samples)

    return {
        "steady_mib": round(steady_mib, 1),
        "shmem_min_mib": round(shmem_min_mib, 1),
        "shmem_samples_mib": [round(v, 1) for v in shmem_samples],
        "idle_ram_mib": round(used_mib, 1),
        "committed_mib": round(committed_mib, 1),
        "reclaimable_mib": round(reclaimable_mib, 1),
        "memory_composition_mib": composition,
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


def median(values: list[float]) -> float:
    ordered = sorted(values)
    middle = len(ordered) // 2
    if len(ordered) % 2:
        return ordered[middle]
    return (ordered[middle - 1] + ordered[middle]) / 2


def apply_gates(measurements: list[dict], vm: VM, only: str | None = None) -> None:
    """Judge the three instruments ADR-020 §1 defines, each per its own nature.

    Gates apply to the protocol statistic, never to a single boot. Everything is
    recorded whether or not it gates, because the number that gates and the
    number a user quotes back to us are not the same number.
    """
    stat = BUDGETS["protocol"]["statistic"]
    assert stat == "median", f"unsupported protocol statistic {stat!r}"

    steady_values = [m["steady_mib"] for m in measurements]
    shmem_values = [m["shmem_min_mib"] for m in measurements]
    pss_values = [m.get("pss_total_visible_mib", 0.0) for m in measurements]
    idle_values = [m["idle_ram_mib"] for m in measurements]
    boot_values = [m["boot_seconds"] for m in measurements]
    software = bool(measurements[-1].get("software_rendering"))

    steady = median(steady_values)
    boot = median(boot_values)
    pss = median(pss_values)
    # A CEILING, not a budget: each per-run figure is already the resting level,
    # so the question is whether the pool ever RESTED above the line — the worst
    # of them, not the middle one. Medianing here would let one run at 300 hide.
    shmem_worst = max(shmem_values)

    gate, target, name = steady_budget(software)
    results = {
        "protocol": {
            "runs": len(measurements),
            "statistic": stat,
            "steady_mib_runs": steady_values,
            "shmem_min_mib_runs": shmem_values,
            "userspace_pss_mib_runs": pss_values,
            "idle_ram_mib_runs": idle_values,
            "boot_seconds_runs": boot_values,
            "steady_spread_mib": round(max(steady_values) - min(steady_values), 1),
            "idle_ram_spread_mib": round(max(idle_values) - min(idle_values), 1),
        },
        "steady_mib": round(steady, 1),
        "shmem_worst_min_mib": round(shmem_worst, 1),
        "userspace_pss_mib": round(pss, 1),
        "idle_ram_mib": round(median(idle_values), 1),
        "boot_seconds": round(boot, 2),
        "software_rendering": software,
        "steady_budget_name": name,
        "steady_gate_mib": gate,
        "measurements": measurements,
    }

    spread = results["protocol"]["steady_spread_mib"]
    print(
        f"perf: steady {steady_values} -> {steady:.1f} MiB "
        f"(spread {spread} MiB) [{stat} of {len(measurements)}]"
    )
    print(f"perf: shmem at rest {shmem_values} -> worst {shmem_worst:.1f} MiB")
    print(
        f"perf: informational — idle (Mem-Avail) {idle_values} -> "
        f"{results['idle_ram_mib']:.1f} MiB, spread "
        f"{results['protocol']['idle_ram_spread_mib']} MiB (gates nothing)"
    )

    failures = []

    # --- 1a. steady: the tight absolute gate --------------------------------
    if gate is None:
        print(
            f"perf: steady {steady:.1f} MiB — NOT GATED: {name}.\n"
            "perf: ADR-020 §3 needs one paired GPU/llvmpipe run before a\n"
            "perf: software-rendered figure can be judged. Reporting, not judging."
        )
        results["steady_within_gate"] = None
    else:
        ok, message = _verdict(
            "steady",
            steady,
            " MiB",
            {"gate": gate, "target": target, "conditions": name},
        )
        print(f"perf: steady {'ok' if ok else 'OVER GATE'} — {message}")
        results["steady_within_gate"] = ok
        if not ok and (only is None or only in ("steady", "idle_ram_mib")):
            failures.append(f"steady: {message}")

    # --- 1b. shmem: a ceiling on the resting buffer pool --------------------
    ceiling = BUDGETS["shmem"]["ceiling_mib"]
    results["shmem_ceiling_mib"] = ceiling
    if shmem_worst > ceiling:
        results["shmem_within_ceiling"] = False
        failures.append(
            f"shared memory rested at {shmem_worst:.1f} MiB, over the "
            f"{ceiling} MiB ceiling.\n"
            "  This is a tripwire against a buffer-pool regression, not a budget\n"
            "  to tune against (ADR-020 §1b). It is deliberately loose — twice the\n"
            "  largest figure ever observed — so exceeding it means something\n"
            "  changed about how the compositor holds buffers, not that the\n"
            "  desktop got slightly heavier."
        )
        print(f"perf: shmem OVER CEILING — {shmem_worst:.1f} > {ceiling} MiB")
    else:
        results["shmem_within_ceiling"] = True
        print(
            f"perf: shmem at rest {shmem_worst:.1f} MiB, within the {ceiling} MiB "
            "ceiling"
        )

    # --- 1c. the ratchet (ADR-018 §3, re-denominated by ADR-021) ------------
    ratchet = BUDGETS["userspace_pss"]
    baseline, threshold, ratchet_name, ratchet_gates = pss_ratchet(software)
    delta = pss - baseline
    results["userspace_pss_baseline_mib"] = baseline
    results["userspace_pss_delta_mib"] = round(delta, 1)
    results["userspace_pss_instrument"] = ratchet_name
    results["userspace_pss_gated"] = ratchet_gates

    if not ratchet_gates:
        # Informational only. Reporting the delta is still useful — it is the
        # M-gate pairing check (ADR-021 §4) — but a GPU number judged against a
        # CI baseline, or vice versa, is meaningless in either direction.
        print(
            f"perf: userspace PSS {pss:.1f} MiB, {delta:+.1f} vs the GPU reference "
            f"({baseline}) — informational, {ratchet_name} does not gate (ADR-021 §3)"
        )
        results["userspace_pss_over"] = None
    elif delta > threshold:
        results["userspace_pss_over"] = True
        print(f"perf: userspace PSS {pss:.1f} MiB, {delta:+.1f} over {ratchet_name}")
        failures.append(
            f"userspace PSS rose {delta:.1f} MiB over the {ratchet_name} baseline "
            f"({baseline} MiB), past the {threshold} MiB the ratchet allows.\n"
            "  This is the creep detector (ADR-018 §3): the absolute gate has\n"
            "  slack by construction and cannot see steady growth.\n"
            f"  If intended, acknowledge it in the PR body with\n"
            f"  '{ratchet['acknowledgement_marker']} <reason>' saying what was\n"
            "  bought. Passing by explaining is allowed; passing silently is not."
        )
    else:
        results["userspace_pss_over"] = False
        print(
            f"perf: userspace PSS {pss:.1f} MiB, {delta:+.1f} vs {ratchet_name} "
            f"baseline {baseline} (allows +{threshold})"
        )

    # --- forbidden processes ------------------------------------------------
    for pname, detail in measurements[-1].get("forbidden_running", {}).items():
        print(f"perf: {pname} is RUNNING and must not be")
        failures.append(
            f"{pname} is running at idle.\n  {FORBIDDEN_AT_IDLE[pname]}\n"
            f"  guest said: {detail}"
        )
    if not measurements[-1].get("forbidden_running"):
        print(f"perf: none of {sorted(FORBIDDEN_AT_IDLE)} are running (as required)")

    # --- boot time ----------------------------------------------------------
    ok, message = _verdict("boot_seconds", boot, "s", BUDGETS["boot_seconds"])
    print(f"perf: boot time {'ok' if ok else 'OVER GATE'} — {message}")
    results["boot_seconds_within_gate"] = ok
    if not ok and (only is None or only == "boot_seconds"):
        failures.append(f"boot time: {message}")

    vm.write_report(f"perf-budgets-{vm.arch}", results)
    if failures:
        raise AssertionError("\n".join(failures))


def run(vm: VM, credentials: dict, only: str | None = None) -> None:
    """Single-boot entry point, for callers that hand us one already-booted VM.

    ADR-018 clause 1 wants the median of three FULL boots, for the CI
    measurement as well as the product one, and only run.py can arrange that —
    so it calls apply_gates() directly. This path judges one sample and says so
    in the evidence (`protocol.runs == 1`), which is right for debugging a
    single VM and wrong for deciding a gate.
    """
    apply_gates([measure(vm, credentials)], vm, only=only)
