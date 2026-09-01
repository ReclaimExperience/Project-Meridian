#!/usr/bin/env bash
# The lint job's real body (PRD 7.3 row 1). The workflow file in
# .github/workflows/ is a thin shim over this, so the exact same checks are
# runnable locally with `bash ci/lint.sh` — no "works in CI only" drift (PRD 7.1).
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

echo "::group::tool versions"
bash --version | head -1
just --version
shellcheck --version | grep -E '^version:'
ruff --version
python3 --version
markdownlint --version 2>/dev/null || echo "markdownlint: absent"
echo "::endgroup::"

echo "::group::lint suite"
just lint
echo "::endgroup::"

echo "::group::lint self-tests (the lints must catch what they claim to)"
just test-lint
echo "::endgroup::"
