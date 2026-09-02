#!/usr/bin/env bash
# Branding lint — PRD 6.5 / WP-00.
#
# The product name MUST live in exactly one place: branding.json. Everything
# user-visible reads it at runtime (QML), or is templated from it (`just assets`,
# os-release). This lint proves the WP-26 rename stays a one-PR change.
#
# Scope note: this lint polices the user-visible product NAME ("Meridian OS" /
# "Meridian"), case-sensitively. It deliberately does NOT police the lowercase
# brand *id* ("meridian"), which the PRD itself bakes into paths and D-Bus names
# (6.1 layout, 8.0 contracts) and which therefore cannot be a one-PR rename.
#
# Exit 0 = clean. Exit 1 = at least one hardcoded occurrence.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$ROOT"

BRANDING="os/rootfs/usr/share/meridian/branding.json"
[[ -f "$BRANDING" ]] || { echo "branding-lint: FATAL: $BRANDING missing"; exit 1; }

# Read the names to police straight out of the source of truth, so this script
# never hardcodes them either.
NAME="$(python3 -c 'import json,sys;print(json.load(open(sys.argv[1]))["name"])' "$BRANDING")"
SHORT="$(python3 -c 'import json,sys;print(json.load(open(sys.argv[1]))["shortName"])' "$BRANDING")"

# Files exempt from the lint, with the reason each is exempt:
#   branding.json          — the source of truth itself
#   docs/                  — PRD, ADRs, help copy, design notes (prose, swept at WP-26)
#   STATUS.md              — agent shared memory (prose, not shipped)
#   CONTRIBUTING-AGENTS.md — verbatim copy of PRD section 14 (prose, not shipped)
#   README.md              — repo front door (prose, swept at WP-26)
#   tests/lint/branding.sh — this file's own comments
# End-anchored: bash's =~ does not anchor, so without (/|$) a file named
# README.md.probe or branding.json.tmpl would silently inherit the exemption.
# Directory entries carry NO trailing slash: the (/|$) suffix supplies it.
# Writing 'docs/' here would require a literal 'docs//' and silently unexclude
# the entire docs tree.
EXCLUDE_RE='^(os/rootfs/usr/share/meridian/branding\.json|docs|STATUS\.md|CONTRIBUTING-AGENTS\.md|README\.md|tests/lint/branding\.sh)(/|$)'

fail=0
while IFS= read -r file; do
  [[ "$file" =~ $EXCLUDE_RE ]] && continue
  # -F fixed string, -w word boundary for the short name so "meridian" the brand
  # id (lowercase, legitimately used in paths) does not trip the lint.
  if hits="$(grep -nF -- "$NAME" "$file" 2>/dev/null)"; then
    echo "branding-lint: hardcoded product name in $file"
    awk '{print "    " $0}' <<<"$hits"
    fail=1
  fi
  if hits="$(grep -nFw -- "$SHORT" "$file" 2>/dev/null)"; then
    echo "branding-lint: hardcoded short name in $file"
    awk '{print "    " $0}' <<<"$hits"
    fail=1
  fi
done < <(git ls-files)

if (( fail )); then
  echo
  echo "branding-lint: FAILED — read the product name from $BRANDING instead."
  echo "               QML/C++: load it at runtime. Static assets: template it via 'just assets'."
  exit 1
fi
echo "branding-lint: clean (no hardcoded '$NAME' / '$SHORT' outside the allowed set)"
