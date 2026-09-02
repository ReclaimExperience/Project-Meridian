#!/usr/bin/env bash
# The lint job's real body (PRD 7.3 row 1). The workflow file in
# .github/workflows/ is a thin shim over this, so the exact same checks are
# runnable locally with `bash ci/lint.sh` — no "works in CI only" drift (PRD 7.1).
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

# Warn loudly when the local toolchain differs from the pinned one: a clean
# local run means nothing if CI runs a different linter (PRD 7.1).
check_pinned() {
    local name="$1" want="$2" have="$3"
    if [[ "$want" != "$have" ]]; then
        echo "  WARNING: ${name} ${have} != pinned ${want} (ci/tool-versions.env)."
        echo "           Local and CI results can legitimately differ."
    fi
}

echo "::group::tool versions"
# Path is runtime-resolved, so shellcheck cannot follow it.
# shellcheck source=/dev/null
source "${ROOT}/ci/tool-versions.env"
check_pinned shellcheck "$SHELLCHECK_VERSION" "$(shellcheck --version | awk '/^version:/{print $2}')"
check_pinned ruff "$RUFF_VERSION" "$(ruff --version | awk '{print $2}')"
check_pinned markdownlint "$MARKDOWNLINT_VERSION" "$(markdownlint --version 2>/dev/null || echo absent)"
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
