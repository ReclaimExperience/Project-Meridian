#!/usr/bin/env bash
# Proves tests/lint/branding.sh actually catches a violation (WP-00 acceptance).
# Plants a hardcoded product name in a tracked scratch file, asserts the lint
# fails, removes it, asserts the lint passes again.
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$ROOT"

PLANT="shell/theme/branding/.branding-lint-fixture.qml"
cleanup() { rm -f "$PLANT"; git rm --cached -q "$PLANT" 2>/dev/null || true; }
trap cleanup EXIT

echo "1/5 clean tree must pass"
./tests/lint/branding.sh >/dev/null || { echo "FAIL: clean tree did not pass"; exit 1; }

echo "2/5 planted violation must fail"
NAME="$(python3 -c 'import json;print(json.load(open("os/rootfs/usr/share/meridian/branding.json"))["name"])')"
printf 'Text { text: "Welcome to %s" }\n' "$NAME" > "$PLANT"
git add -f "$PLANT" >/dev/null 2>&1     # lint walks `git ls-files`
if ./tests/lint/branding.sh >/dev/null 2>&1; then
  echo "FAIL: lint did NOT catch the planted violation in $PLANT"; exit 1
fi
echo "    caught it"
cleanup   # remove step 2's fixture before the later steps assert anything

echo "3/5 an exemption prefix must not leak to look-alike filenames"
# `=~` does not anchor, so an unanchored exclusion would exempt README.md.probe.
LEAK="README.md.probe"
printf 'Text { text: "%s" }\n' "$NAME" > "$LEAK"
git add -f "$LEAK" >/dev/null 2>&1
if ./tests/lint/branding.sh >/dev/null 2>&1; then
  echo "FAIL: '$LEAK' wrongly inherited README.md's exemption"; rm -f "$LEAK"
  git rm --cached -q "$LEAK" 2>/dev/null; exit 1
fi
rm -f "$LEAK"; git rm --cached -q "$LEAK" 2>/dev/null || true
echo "    not exempt"

echo "4/5 the docs/ tree must still be exempt"
# Over-anchoring ('docs/' + '(/|$)') silently unexcludes all of docs/, which is
# full of legitimate brand-name prose. Assert the exemption still holds.
./tests/lint/branding.sh >/dev/null || { echo "FAIL: docs/ lost its exemption"; exit 1; }
grep -qF "$NAME" docs/PRD.md || { echo "FAIL: fixture assumption broken"; exit 1; }
echo "    exempt (docs/PRD.md contains the name and does not trip the lint)"

echo "5/5 removing the violation must pass again"
cleanup; trap - EXIT
./tests/lint/branding.sh >/dev/null || { echo "FAIL: did not recover after removal"; exit 1; }

echo "branding-lint self-test: PASS"
