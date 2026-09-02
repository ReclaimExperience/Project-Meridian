#!/usr/bin/env bash
# ADR-015 listening-socket audit. Thin wrapper: the assertions live in the
# harness suite so they run against a real booted image (PRD 7.4).
set -euo pipefail
cd "$(dirname "${BASH_SOURCE[0]}")/../.."
exec just vm-test security "$@"
