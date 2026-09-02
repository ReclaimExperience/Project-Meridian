#!/usr/bin/env python3
"""Run a harness suite (PRD 7.4). Entry point for `just vm-test [suite]`.

Suites live in tests/harness/suites/ and expose `run(vm) -> None`, raising
AssertionError on failure. The runner owns everything around them: finding the
disk image, booting it, collecting evidence, and reporting.

Evidence is written on success AND failure. A suite that only leaves artifacts
behind when it fails is a suite you cannot compare against a previous good run.
"""

from __future__ import annotations

import argparse
import importlib
import json
import sys
import time
import traceback
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from harness.vm import ROOT, VM, VMError, choose_accelerator, host_arch

SUITES = ("smoke",)


def find_disk(arch: str) -> Path:
    build = ROOT / "build"
    candidates = sorted(build.rglob("*.qcow2")) if build.is_dir() else []
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
    args = parser.parse_args()

    disk = Path(args.disk) if args.disk else find_disk(args.arch)
    credentials = load_credentials()
    module = importlib.import_module(f"harness.suites.{args.suite}")

    print(
        f"harness: suite={args.suite} arch={args.arch} "
        f"accel={choose_accelerator(args.arch)}"
    )
    print(f"harness: disk={disk}")

    started = time.monotonic()
    vm = VM(disk=disk, arch=args.arch)
    failure: BaseException | None = None
    try:
        vm.start()
        module.run(vm, credentials)
    except (AssertionError, VMError, Exception) as exc:  # noqa: BLE001
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
