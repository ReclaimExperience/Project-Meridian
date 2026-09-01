#!/usr/bin/env bash
# Entry point named by PRD 6.3. Logic lives in strings.py (ruff-linted).
set -euo pipefail
exec python3 "$(dirname "${BASH_SOURCE[0]}")/strings.py" "$@"
