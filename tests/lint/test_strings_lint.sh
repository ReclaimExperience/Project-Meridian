#!/usr/bin/env bash
# Proves tests/lint/strings.sh catches both failure classes (WP-00 acceptance).
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$ROOT"

PLANT="docs/help/.strings-lint-fixture.md"
cleanup() { rm -f "$PLANT"; git rm --cached -q "$PLANT" 2>/dev/null || true; }
trap cleanup EXIT

echo "1/4 clean tree must pass"
./tests/lint/strings.sh >/dev/null || { echo "FAIL: clean tree did not pass"; exit 1; }

echo "2/4 INV-0 violation must fail"
echo "If the drive does not appear, open a terminal and try again." > "$PLANT"
git add -f "$PLANT" >/dev/null 2>&1
out="$(./tests/lint/strings.sh 2>&1 || true)"
./tests/lint/strings.sh >/dev/null 2>&1 && { echo "FAIL: missed INV-0 violation"; exit 1; }
grep -q "INV-0 violation" <<<"$out" || { echo "FAIL: wrong diagnostic"; echo "$out"; exit 1; }
echo "    caught it"

echo "3/4 jargon violation must fail"
echo "Select the partition you want to use." > "$PLANT"
git add -f "$PLANT" >/dev/null 2>&1
out="$(./tests/lint/strings.sh 2>&1 || true)"
./tests/lint/strings.sh >/dev/null 2>&1 && { echo "FAIL: missed jargon violation"; exit 1; }
grep -q "jargon 'partition'" <<<"$out" || { echo "FAIL: wrong diagnostic"; echo "$out"; exit 1; }
echo "    caught it"

echo "4/4 plain-language wording must pass"
echo "Choose the disk you want to use." > "$PLANT"
git add -f "$PLANT" >/dev/null 2>&1
./tests/lint/strings.sh >/dev/null || { echo "FAIL: rejected acceptable wording"; exit 1; }
echo "    accepted"

cleanup; trap - EXIT
echo "strings-lint self-test: PASS"
