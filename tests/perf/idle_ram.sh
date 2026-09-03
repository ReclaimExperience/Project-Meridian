#!/usr/bin/env bash
# ram.idle.product / ram.idle.ci — idle RAM after login (PRD 1.5, ADR-017)
#
# These are TWO numbers with one behaviour, and the suite picks between them by
# what the run actually rendered with:
#
#   ram.idle.product   GPU-rendered, gate 1126 MiB (target 950). The PRD 1.5
#                      metric, measured on the 10.2 low-end row. The ONLY number
#                      a release claim may cite.
#   ram.idle.ci        the llvmpipe VM CI can run, gate = product + render_offset.
#                      A per-PR tripwire. Green here says a regression did not
#                      land; it says nothing about idle RAM on real hardware.
#
# Run with MERIDIAN_VM_GL=1 on a host with a DRM render node to measure the
# product number. Without it you are measuring the tripwire, and the suite will
# say so in its output rather than letting the two be confused — conflating them
# is what turned a 116 MiB problem into a 300 MiB one.
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
# Rule R-E: never edit a budget to make a run pass. They live in
# tests/perf/budgets.json, and the CI gate is COMPUTED from the product budget
# plus a calibration constant whose provenance is recorded beside it, so it
# cannot be moved without saying what was re-measured (ADR-017 clause 2).
set -euo pipefail

cd "$(dirname "${BASH_SOURCE[0]}")/../.."
exec python3 tests/harness/run.py perf --only idle_ram_mib "$@"
