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

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tests"))

from harness.suites.perf import (
    BUDGETS,
    _duration_seconds,
    _parse_systemd_analyze,
    _verdict,
    idle_ram_budget,
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
    budgets_under_test = [("boot_seconds", "s", BUDGETS["boot_seconds"])]
    for software in (True, False):
        _gate, _target, _name = idle_ram_budget(software)
        budgets_under_test.append(
            (_name, " MiB", {"gate": _gate, "target": _target, "conditions": _name})
        )
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
                print(
                    f"  FAIL  {key} {label}: failure message does not say to escalate"
                )
                failures += 1
            else:
                print(f"  ok    {key} {label} ({measured}{unit})")

    # Budgets must match PRD 2. A gate that drifts from the document it
    # implements is worse than no gate: it looks authoritative.
    # --- ADR-017: the two names, and the offset's provenance ----------------
    print("\nADR-017 — idle RAM has two names because it is two numbers")
    idle = BUDGETS["idle_ram"]
    product_gate = idle["product"]["gate_mib"]
    offset = idle["render_offset"]
    ci_gate, ci_target, ci_name = idle_ram_budget(software_rendering=True)
    pr_gate, _pr_target, pr_name = idle_ram_budget(software_rendering=False)

    for ok, why in [
        (pr_name == "ram.idle.product", "a GPU-rendered run gates on ram.idle.product"),
        (ci_name == "ram.idle.ci", "a software-rendered run gates on ram.idle.ci"),
        (pr_gate == product_gate, "the product gate is the PRD 1.5 number"),
        (
            ci_gate == product_gate + offset["value_mib"],
            "the CI gate is product + offset, computed",
        ),
        (
            ci_target == idle["product"]["target_mib"] + offset["value_mib"],
            "the CI target is offset the same way",
        ),
        (
            pr_gate < ci_gate,
            (
                "the product gate is the stricter of the two, so a GPU run is "
                "never judged by the tripwire"
            ),
        ),
    ]:
        print(f"  {'ok  ' if ok else 'FAIL'}  {why}")
        failures += 0 if ok else 1

    # The CI gate must appear nowhere as a literal (ADR-017 clause 2): it is
    # computed so that moving it means editing the offset's provenance record and
    # saying what was re-measured. This test computes the string rather than
    # spelling it, so the test file does not itself contain the number it forbids.
    budgets_raw = (ROOT / "tests" / "perf" / "budgets.json").read_text()
    for value, label in ((ci_gate, "CI gate"), (ci_target, "CI target")):
        if str(value) in budgets_raw:
            print(f"  FAIL  the {label} appears as a literal in budgets.json.")
            print("      ADR-017 clause 2 requires it computed from product +")
            print("      offset, so it cannot move without the provenance moving.")
            failures += 1
        else:
            print(f"  ok    the {label} is computed, not stored")

    # An offset without provenance is a fudge factor: clause 3 lets it change
    # only to a newly measured pair, which nobody can verify without this.
    missing = [
        k
        for k in ("value_mib", "method", "build_id", "plasma", "mesa", "date")
        if not offset.get(k)
    ]
    if missing:
        print(f"  FAIL  render_offset is missing provenance: {missing}")
        failures += 1
    else:
        print(f"  ok    render_offset carries full provenance ({offset['date']})")

    prd = (ROOT / "docs" / "PRD.md").read_text()
    for needle, why in (
        ("ram.idle.product", "PRD 1.5 must name the product budget"),
        ("ram.idle.ci", "PRD 1.5 must name the CI tripwire"),
        ("≤ 15 s", "the boot time gate"),
    ):
        if needle not in prd:
            print(f"  FAIL  {why}: {needle!r} is not in the PRD.")
            failures += 1
        else:
            print(f"  ok    PRD states {needle!r}")
    if product_gate != 1126 or BUDGETS["boot_seconds"]["gate"] != 15:
        print("  FAIL  budgets.json does not match the PRD (1126 MiB, 15 s).")
        print("      R-E: budgets are laws. Changing one needs an ADR, not an edit.")
        failures += 1
    else:
        print("  ok    budgets.json matches the PRD")

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
