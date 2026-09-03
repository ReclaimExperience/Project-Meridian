#!/usr/bin/env python3
"""The perf gates' arithmetic, checked without booting anything.

A budget gate has two ways to be useless, and only one of them is loud:

  1. it fails a good build — noticed within the hour;
  2. it PASSES a bad one — noticed never.

The second is the risk here, because the number comes from parsing text a
guest printed. A parse that quietly returns 0.0 for "1min 3.2s" reports a
one-minute boot as instant and every future run agrees. So the parser is tested
against real `systemd-analyze` shapes, including the ones that do not look like
the common case, and the verdict function is tested on both sides of both
budgets.

These run in `just test-lint` with no VM, which is the point: if the gates are
only exercised by the nightly VM job, a broken gate ships for a day.
"""

from __future__ import annotations

import math
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tests"))

from harness.suites.perf import (
    BUDGETS,
    _duration_seconds,
    _parse_systemd_analyze,
    _verdict,
    median,
    steady_budget,
)

# Real shapes. systemd omits stages that did not happen (no firmware line on
# some VMs, an initrd line only when one was used) and switches to "1min 2.3s"
# past sixty seconds — the case where a silent parse failure reports a slow
# boot as a fast one.
ANALYZE_CASES = [
    (
        (
            "Startup finished in 3.494s (firmware) + 2.1s (loader) + 4.3s (kernel)"
            " + 12.9s (userspace) = 22.8s"
        ),
        {"firmware": 3.494, "loader": 2.1, "kernel": 4.3, "userspace": 12.9},
        22.8,
    ),
    (
        "Startup finished in 984ms (kernel) + 1min 2.3s (userspace) = 1min 3.2s",
        {"kernel": 0.984, "userspace": 62.3},
        63.2,
    ),
    (
        "Startup finished in 1.2s (kernel) + 3.4s (initrd) + 5.6s (userspace) = 10.2s",
        {"kernel": 1.2, "initrd": 3.4, "userspace": 5.6},
        10.2,
    ),
]

DURATIONS = [
    ("984ms", 0.984),
    ("4.5s", 4.5),
    ("1min 2.3s", 62.3),
    ("2min 0.5s", 120.5),
]


def main() -> int:
    failures = 0

    print("systemd-analyze parsing")
    for text, want_parts, want_total in ANALYZE_CASES:
        got = _parse_systemd_analyze(text)
        total = got.pop("total", None)
        if got != want_parts or total is None or abs(total - want_total) > 0.01:
            print(f"  FAIL  {text[:52]}...")
            print(f"      stages: want {want_parts} got {got}")
            print(f"      total:  want {want_total} got {total}")
            failures += 1
        else:
            print(f"  ok    total {total}s from {len(want_parts)} stage(s)")

    print("\nduration parsing")
    for text, want in DURATIONS:
        got = _duration_seconds(text)
        if abs(got - want) > 0.001:
            print(f"  FAIL  {text!r}: want {want}, got {got}")
            failures += 1
        else:
            print(f"  ok    {text!r} -> {got}s")

    # A boot time that parses to zero is the failure mode that matters most:
    # it is the only wrong answer that passes every gate forever.
    if _parse_systemd_analyze("Startup finished in mumble") != {}:
        print("  FAIL  unparseable output produced a number instead of nothing")
        failures += 1
    else:
        print("  ok    unparseable output yields no number (the suite then raises)")

    print("\nverdicts — a gate must fail above it and pass below it")
    steady = BUDGETS["steady"]
    budgets_under_test = [
        ("boot_seconds", "s", BUDGETS["boot_seconds"]),
        (
            "steady",
            " MiB",
            {
                "gate": steady["gate_mib"],
                "target": steady["target_mib"],
                "conditions": "steady.product",
            },
        ),
    ]
    for key, unit, budget in budgets_under_test:
        gate, target = budget["gate"], budget["target"]
        for measured, want_ok, label in (
            (target - 1, True, "under target"),
            (target + 1, True, "between target and gate"),
            (gate + 1, False, "over gate"),
            (gate, True, "exactly at the gate"),
        ):
            ok, message = _verdict(key, measured, unit, budget)
            if ok != want_ok:
                print(f"  FAIL  {key} {label}: {measured} -> ok={ok}, wanted {want_ok}")
                failures += 1
            elif not ok and "escalate" not in message:
                print(f"  FAIL  {key} {label}: message does not say to escalate")
                failures += 1
            else:
                print(f"  ok    {key} {label} ({measured}{unit})")

    # --- ADR-018 §1: the protocol -------------------------------------------
    print("\nADR-018 — the median of 3, because one noisy run is a coin flip")
    for values, want, why in [
        ([1123.1, 1122.4, 1174.1], 1123.1, "a real marginal set medians to its middle"),
        ([10.0, 1.0, 5.0], 5.0, "unsorted input is sorted first"),
        ([2.0, 4.0], 3.0, "an even count averages the middle pair"),
        ([7.0], 7.0, "a single run is its own median"),
    ]:
        got = median(values)
        ok = abs(got - want) < 0.001
        print(f"  {'ok  ' if ok else 'FAIL'}  {why} ({values} -> {got})")
        failures += 0 if ok else 1

    proto = BUDGETS["protocol"]
    for ok, why in [
        (proto["runs"] == 3, "3 runs"),
        (proto["statistic"] == "median", "median"),
        (proto["settle_seconds"] == 120, "the 2-minute settle is preserved"),
        (proto.get("shmem_window_seconds") == 60, "shmem gets a 60 s window"),
    ]:
        print(f"  {'ok  ' if ok else 'FAIL'}  {why}")
        failures += 0 if ok else 1

    # --- ADR-020 §1: the numbers must re-derive from their provenance -------
    print("\nADR-020 — every gate re-derives from the runs it was set from")

    def round_up_25(value: float) -> int:
        return int(math.ceil(value / 25.0) * 25)

    prov = steady["floor_provenance"]
    med, spr = prov["median_mib"], prov["spread_mib"]
    shmem = BUDGETS["shmem"]
    for ok, why in [
        (
            round_up_25(med + 2 * spr) == steady["gate_mib"],
            f"steady gate {steady['gate_mib']} = round_up_25(median + 2*spread)",
        ),
        (
            round_up_25(med + spr) == steady["target_mib"],
            f"steady target {steady['target_mib']} = round_up_25(median + spread)",
        ),
        (
            round_up_25(2 * max(shmem["observed_runs_mib"])) == shmem["ceiling_mib"],
            f"shmem ceiling {shmem['ceiling_mib']} = round_up_25(2 x observed max)",
        ),
        (
            "Shmem" not in steady["components"],
            (
                "Shmem is NOT in steady — its 64.4 MiB spread WAS the whole "
                "variance that made the combined statistic fail its trigger"
            ),
        ),
        (
            steady["gate_mib"] - med >= 3 * spr,
            (
                "the gate has several times its own noise as headroom — the "
                "property 1126, 1200 and the committed denomination all lacked"
            ),
        ),
    ]:
        print(f"  {'ok  ' if ok else 'FAIL'}  {why}")
        failures += 0 if ok else 1

    # --- ADR-020 §3: an offset may not be carried across denominations ------
    offset = BUDGETS["render_offset"]
    if offset["value_mib"] is None:
        gate, _t, name = steady_budget(software_rendering=True)
        ok = gate is None and "not yet measured" in name
        print(
            f"  {'ok  ' if ok else 'FAIL'}  with no steady-denominated offset, a "
            "software-rendered run reports without gating"
        )
        failures += 0 if ok else 1
    else:
        gate, _t, name = steady_budget(software_rendering=True)
        ok = gate == steady["gate_mib"] + offset["value_mib"]
        print(
            f"  {'ok  ' if ok else 'FAIL'}  the CI gate is product + offset, computed"
        )
        failures += 0 if ok else 1
        raw = (ROOT / "tests" / "perf" / "budgets.json").read_text()
        if str(gate) in raw:
            print("  FAIL  the CI gate appears as a literal in budgets.json")
            failures += 1
        else:
            print("  ok    the CI gate is computed, not stored")

    # --- ADR-018 §3: the ratchet is the SENSITIVE one -----------------------
    print("\nADR-018 — the ratchet must be tighter than the gate's slack")
    ratchet = BUDGETS["userspace_pss"]
    slack = steady["gate_mib"] - med
    for ok, why in [
        (ratchet["allowed_delta_mib"] == 25, "the ratchet allows +25 MiB"),
        (bool(ratchet.get("acknowledgement_marker")), "there is an ack marker"),
        (
            ratchet["allowed_delta_mib"] < slack,
            (
                "the ratchet is tighter than the gate's slack, or it detects "
                "nothing the gate would not already catch"
            ),
        ),
    ]:
        print(f"  {'ok  ' if ok else 'FAIL'}  {why}")
        failures += 0 if ok else 1

    # --- the PRD must name what is gated ------------------------------------
    prd = (ROOT / "docs" / "PRD.md").read_text()
    for needle, why in (
        ("steady", "PRD 1.5 must name the steady instrument"),
        ("≤ 15 s", "the boot time gate"),
    ):
        if needle not in prd:
            print(f"  FAIL  {why}: {needle!r} is not in the PRD.")
            failures += 1
        else:
            print(f"  ok    PRD states {needle!r}")

    # run.py writes the per-run verdict as "<suite>-<arch>.json". A suite that
    # writes its own report under that same name is overwritten by the runner,
    # and the loss is silent - the file exists, with the wrong contents. The
    # first over-budget run lost its whole memory breakdown to this.
    print("\nevidence filenames must not collide with the runner's")
    suites = ROOT / "tests" / "harness" / "suites"
    for path in sorted(suites.glob("*.py")):
        name = path.stem
        source = path.read_text()
        if f'write_report(f"{name}-{{vm.arch}}"' in source:
            print(f"  FAIL  {name}.py writes '{name}-<arch>.json', which run.py")
            print("      overwrites with its own verdict. Pick another name.")
            failures += 1
    print("  ok    no suite writes under the runner's report name")

    # --- ADR-018 clause 1: the protocol ------------------------------------
    print()
    if failures:
        print(f"perf-gates: {failures} failure(s)")
        return 1
    print(
        f"perf-gates: {len(ANALYZE_CASES)} analyze shape(s), {len(DURATIONS)} "
        "duration format(s), 8 verdict(s) and the PRD budgets all agree"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
