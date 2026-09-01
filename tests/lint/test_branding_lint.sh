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

echo "1/3 clean tree must pass"
./tests/lint/branding.sh >/dev/null || { echo "FAIL: clean tree did not pass"; exit 1; }

echo "2/3 planted violation must fail"
NAME="$(python3 -c 'import json;print(json.load(open("os/rootfs/usr/share/meridian/branding.json"))["name"])')"
printf 'Text { text: "Welcome to %s" }\n' "$NAME" > "$PLANT"
git add -f "$PLANT" >/dev/null 2>&1     # lint walks `git ls-files`
if ./tests/lint/branding.sh >/dev/null 2>&1; then
  echo "FAIL: lint did NOT catch the planted violation in $PLANT"; exit 1
fi
echo "    caught it:"; ./tests/lint/branding.sh 2>&1 | sed 's/^/      /' || true

echo "3/3 removing the violation must pass again"
cleanup; trap - EXIT
./tests/lint/branding.sh >/dev/null || { echo "FAIL: did not recover after removal"; exit 1; }

echo "branding-lint self-test: PASS"
