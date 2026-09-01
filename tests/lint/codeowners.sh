#!/usr/bin/env bash
# CODEOWNERS path sanity (PRD 7.5, rule R-H).
#
# A CODEOWNERS rule that matches nothing is worse than no rule: GitHub requires
# no review and the file still reads like a gate. WP-01 moved
# os/rootfs/usr/etc/ to os/rootfs/etc/ and left the polkit and image-signing
# rules pointing into space; nobody noticed until review.
#
# The rule here: a pattern's IMMEDIATE parent directory must exist, or the line
# must carry an explicit "# planned: WP-NN" marker. Most owner-gated paths are
# owned by WPs that have not started, so "must already exist" is too strict —
# but "some ancestor exists" is far too weak, which is how the first version of
# this lint passed the exact stale rules it was written to catch. The marker
# makes the difference between "not built yet" and "moved and forgotten" an
# explicit, reviewable statement rather than a guess.
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$ROOT"

fail=0 checked=0 planned=0
lineno=0
while IFS= read -r line || [ -n "$line" ]; do
    lineno=$((lineno + 1))
    rule="${line%%#*}"
    pattern="$(printf '%s' "$rule" | awk '{print $1}')"
    [ -z "$pattern" ] && continue
    checked=$((checked + 1))

    rel="${pattern#/}"; rel="${rel%/}"
    if [ -e "$rel" ]; then continue; fi

    parent="$(dirname "$rel")"
    if [ -d "$parent" ]; then continue; fi

    if printf '%s' "$line" | grep -qE '#[[:space:]]*planned:[[:space:]]*WP-[0-9]{2}'; then
        planned=$((planned + 1))
        continue
    fi

    echo "codeowners-lint: line ${lineno}: '${pattern}'"
    echo "    its parent directory '${parent}' does not exist, so this rule can"
    echo "    never match and the path is NOT owner-gated."
    echo "    If the path is simply not built yet, say so explicitly:"
    echo "        ${pattern}    @org/team   # planned: WP-NN"
    fail=1
done < .github/CODEOWNERS

if [ "$fail" -ne 0 ]; then
    echo "codeowners-lint: FAILED"
    exit 1
fi
echo "codeowners-lint: clean (${checked} rule(s); ${planned} marked planned)"
