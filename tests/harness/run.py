#!/usr/bin/env python3
"""Run a harness suite (PRD 7.4). Entry point for `just vm-test [suite]`.

Suites live in tests/harness/suites/ and expose `run(vm, credentials) -> None`, raising
AssertionError on failure. The runner owns everything around them: finding the
disk image, booting it, collecting evidence, and reporting.

Evidence is written on success AND failure. A suite that only leaves artifacts
behind when it fails is a suite you cannot compare against a previous good run.
"""

from __future__ import annotations

import argparse
import importlib
import json
import os
import sys
import time
import traceback
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from harness.vm import ROOT, VM, choose_accelerator, host_arch

# Every suite states its verdict with `assert`, so running under -O or
# PYTHONOPTIMIZE=1 strips them all and turns the harness into a rubber stamp:
# every suite "passes", having checked nothing. Refuse to start rather than
# report a green result that means nothing.
if not __debug__:
    raise SystemExit(
        "harness: refusing to run with assertions disabled (-O / PYTHONOPTIMIZE).\n"
        "  Every suite's verdict is an `assert`, so this mode would report a\n"
        "  green result for a system it never checked."
    )

SUITES = ("smoke", "security", "privacy", "screens", "stories", "perf", "rollback")


def find_disk(arch: str) -> Path:
    build = ROOT / "build"
    candidates = sorted(build.rglob("*.qcow2")) if build.is_dir() else []
    # Prefer a disk whose path names this arch. `arch` was previously used only
    # in the error string, so on a machine holding both images the harness
    # booted whichever sorted first and then labelled its evidence and its
    # baselines with the arch it had been ASKED for.
    matching = [p for p in candidates if arch in str(p)]
    if matching:
        return matching[0]
    if candidates and len(candidates) > 1:
        raise SystemExit(
            f"several disk images under {build}/ and none names {arch}:\n  "
            + "\n  ".join(str(p) for p in candidates)
            + "\n  Pass one explicitly:  python3 tests/harness/run.py <suite> --disk <path>"
        )
    if not candidates:
        raise SystemExit(
            f"no disk image under {build}/.\n"
            f"  Build one first:  just build {arch} && just vm-image {arch}"
        )
    return candidates[0]


def load_credentials() -> dict:
    path = ROOT / "build" / "dev-credentials.json"
    if not path.is_file():
        raise SystemExit(
            f"{path} is missing — it is written by `just vm-image`.\n"
            f"  The harness logs in over the serial console and cannot invent the password.\n"
            f"  Rebuild the disk image:  just vm-image"
        )
    return json.loads(path.read_text())


def _write_baselines(vm, credentials, module, which: str) -> None:
    """Capture screens and commit them as the new reference.

    Separate from the suite on purpose (rule R-F): a test run must never write
    its own baseline, or a regression quietly becomes the new expectation.
    """
    import shutil

    if not hasattr(module, "capture_screens"):
        raise SystemExit("suite has no capture_screens(); cannot baseline it")

    captured = module.capture_screens(vm, credentials)
    baselines = ROOT / "tests" / "baselines"
    for screen, path in captured.items():
        if which not in ("all", screen):
            continue
        directory = baselines / screen
        directory.mkdir(parents=True, exist_ok=True)
        destination = directory / f"{vm.arch}.png"
        shutil.copy(path, destination)
        print(f"baseline: wrote {destination.relative_to(ROOT)}")
    print("\nbaseline: review these as images in the PR, and commit them ON THEIR OWN")
    print("baseline: with a STATUS.md note saying what changed and why (rule R-F).")


def _perf_protocol(args, disk, credentials, module, started) -> int:
    """Boot N times, measure each, then judge the median (ADR-018 clause 1).

    Gates are applied ONCE, to the statistic. Applying them per run would turn
    three runs into three chances to fail, which is the opposite of what the
    protocol is for — the 2026-09-03 result was 1123.1 / 1122.4 / 1174.1, and
    any single one of those is a fair summary of nothing.
    """
    measurements = []
    last_vm = None
    for index in range(args.runs):
        print(f"\nharness: protocol run {index + 1}/{args.runs}")
        vm = VM(disk=disk, arch=args.arch)
        try:
            vm.start()
            measurements.append(module.measure(vm, credentials))
        except BaseException as exc:  # noqa: BLE001
            # A protocol run that did not complete must not be silently dropped:
            # medianing the two that worked would report a clean number from a
            # partly broken measurement.
            vm.stop()
            print(f"harness: protocol run {index + 1} FAILED: {exc}")
            print(f"harness: FAILED after {time.monotonic() - started:.0f}s")
            return 1
        if index + 1 < args.runs:
            vm.stop()
        else:
            last_vm = vm

    failure = None
    try:
        module.apply_gates(measurements, last_vm, only=args.only)
    except BaseException as exc:  # noqa: BLE001
        failure = exc
    finally:
        elapsed = time.monotonic() - started
        last_vm.write_report(
            f"{args.suite}-{args.arch}",
            {
                "suite": args.suite,
                "protocol_runs": args.runs,
                "seconds": round(elapsed, 1),
                "passed": failure is None,
                "error": None if failure is None else str(failure),
            },
        )
        last_vm.stop()

    if failure is not None:
        print(f"\n{failure}")
        print(f"\nharness: FAILED after {elapsed:.0f}s")
        return 1
    print(f"\nharness: PASSED after {elapsed:.0f}s")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="Run a VM harness suite.")
    parser.add_argument("suite", nargs="?", default="smoke", choices=SUITES)
    parser.add_argument("--arch", default=host_arch())
    parser.add_argument("--disk", default=None)
    parser.add_argument(
        "--keep",
        action="store_true",
        help="leave the VM running after the suite (for debugging)",
    )
    parser.add_argument(
        "--baseline",
        metavar="SCREEN",
        nargs="?",
        const="all",
        help="capture screens and WRITE them as baselines instead of comparing "
        "(rule R-F: this is deliberate, and belongs in its own commit)",
    )
    parser.add_argument(
        "--runs",
        type=int,
        default=None,
        help="perf only: how many protocol runs to take before judging. "
        "Defaults to the protocol in budgets.json — ADR-018 clause 1 requires "
        "the median of 3, for the CI measurement as well as the product one. "
        "Lower it only to debug the harness, never to decide a gate.",
    )
    parser.add_argument(
        "--only",
        default=None,
        help="perf only: enforce just this budget (idle_ram_mib or boot_seconds). "
        "Both are always measured and recorded either way — a narrower gate must "
        "not mean less evidence.",
    )
    args = parser.parse_args()
    if args.only and args.suite != "perf":
        raise SystemExit("--only applies to the perf suite")

    disk = Path(args.disk) if args.disk else find_disk(args.arch)
    credentials = load_credentials()
    # The rollback drill needs a deliberately broken image to stage. It arrives
    # by environment rather than as a flag because ci/rollback-drill.sh builds and
    # publishes it, and the suite refuses to run without one — a drill with
    # nothing to stage would pass while asserting nothing.
    if os.environ.get("MERIDIAN_SABOTAGE_REF"):
        credentials["sabotage_ref"] = os.environ["MERIDIAN_SABOTAGE_REF"]
    module = importlib.import_module(f"harness.suites.{args.suite}")

    print(
        f"harness: suite={args.suite} arch={args.arch} "
        f"accel={choose_accelerator(args.arch)}"
    )
    print(f"harness: disk={disk}")

    started = time.monotonic()

    # ADR-018 clause 1: the product metric is the median of 3 consecutive runs.
    # Each run is a FULL boot, not three samples from one — the noise being
    # averaged out lives in boot-to-boot variation of kernel and system memory,
    # so re-reading /proc/meminfo three times in one session would measure
    # nothing and report confidence.
    protocol_runs = args.runs
    if args.suite == "perf" and protocol_runs is None:
        protocol_runs = module.PROTOCOL_RUNS
    args.runs = protocol_runs
    if args.suite == "perf" and (protocol_runs or 1) > 1:
        return _perf_protocol(args, disk, credentials, module, started)

    # The privacy suite audits traffic, so it needs the capture enabled at boot
    # — it cannot be turned on once the VM is already running.
    vm = VM(disk=disk, arch=args.arch, capture=args.suite == "privacy")
    failure: BaseException | None = None
    try:
        vm.start()
        if args.baseline:
            _write_baselines(vm, credentials, module, args.baseline)
        else:
            if args.suite == "perf":
                module.run(vm, credentials, only=args.only)
            else:
                module.run(vm, credentials)
    except BaseException as exc:  # noqa: BLE001
        # BaseException, not Exception: SystemExit and KeyboardInterrupt would
        # otherwise escape and exit 0 with no verdict printed — and
        # `raise SystemExit(...)` is this file's own idiom for user errors, so a
        # suite adopting it is plausible.
        failure = exc
    finally:
        elapsed = time.monotonic() - started
        # Evidence on success too: a suite whose artifacts only appear on
        # failure gives you nothing to compare a regression against.
        try:
            vm.screenshot(f"{args.suite}-final-{args.arch}")
            vm.write_report(
                f"{args.suite}-{args.arch}",
                {
                    "suite": args.suite,
                    "seconds": round(elapsed, 1),
                    "passed": failure is None,
                    "error": None if failure is None else str(failure),
                },
            )
        except Exception as exc:  # noqa: BLE001
            print(f"harness: could not collect evidence: {exc}")
        if not args.keep:
            vm.stop()

    print(f"\nharness: units OK={vm.units_ok()} failed units={len(vm.failed_units())}")
    print(f"harness: evidence in {vm.evidence}")

    if failure is not None:
        print(f"\nharness: FAILED after {elapsed:.0f}s\n")
        traceback.print_exception(type(failure), failure, failure.__traceback__)
        return 1
    print(f"harness: {args.suite} PASSED in {elapsed:.0f}s")
    return 0


if __name__ == "__main__":
    sys.exit(main())
