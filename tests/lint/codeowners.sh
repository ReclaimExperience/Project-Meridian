#!/usr/bin/env bash
# CODEOWNERS path sanity (PRD 7.5, rule R-H).
#
# A CODEOWNERS pattern that matches nothing is worse than no pattern: GitHub
# applies no review requirement and the file still *looks* like a gate. WP-01
# moved os/rootfs/usr/etc/ to os/rootfs/etc/ and left two rules — polkit and the
# image signing policy — pointing into space. Nobody noticed until review.
#
# Rules are allowed to point at paths that do not exist YET (most are owned by
# unstarted WPs). What is not allowed is a rule under a parent directory that
# itself does not exist, which is what a stale relocation looks like.
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$ROOT"

fail=0
while read -r pattern _; do
    case "$pattern" in ''|'#'*) continue ;; esac
    rel="${pattern#/}"; rel="${rel%/}"
    [ -e "$rel" ] && continue
    parent="$(dirname "$rel")"
    while [ "$parent" != "." ] && [ ! -d "$parent" ]; do parent="$(dirname "$parent")"; done
    if [ "$parent" = "." ]; then
        echo "codeowners-lint: '$pattern' has no existing ancestor directory —"
        echo "                 it can never match, so it gates nothing."
        fail=1
    fi
done < .github/CODEOWNERS

if [ "$fail" -ne 0 ]; then
    echo "codeowners-lint: FAILED"
    exit 1
fi
echo "codeowners-lint: clean (every rule can match something)"
