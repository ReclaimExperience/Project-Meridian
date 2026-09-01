#!/usr/bin/env bash
# Entry point kept for the lint suite. Logic lives in codeowners.py (ruff-linted).
set -euo pipefail
exec python3 "$(dirname "${BASH_SOURCE[0]}")/codeowners.py" "$@"
