#!/usr/bin/env bash
# cold boot to login screen (PRD 2: ≤ 15 s, target 10 s)
#
# PRD WP-02 names this script, so it exists under this name and is callable on
# its own. It does not re-implement a VM: WP-03's harness already boots images,
# logs in and talks to the guest, and a second copy of that would drift from the
# first and disagree about what a boot even is.
#
# Both budgets are measured on every run and written to build/evidence — this
# script only decides which one FAILS the build. Measuring only the budget you
# are enforcing lets the other drift unobserved until it breaks.
#
# ADR-018 clause 1: this takes the MEDIAN OF 3 consecutive boots, 2-minute
# settle each, and records all three. One run with ~50 MiB of noise decided
# a gate with under 4 MiB of headroom once; that is a coin flip, not a gate.
#
# Rule R-E: never edit a budget to make a run pass. They live in
# tests/perf/budgets.json, one file, deliberately awkward to change quietly.
set -euo pipefail

cd "$(dirname "${BASH_SOURCE[0]}")/../.."
exec python3 tests/harness/run.py perf --only boot_seconds "$@"
