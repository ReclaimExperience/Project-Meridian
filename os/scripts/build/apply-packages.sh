#!/usr/bin/env bash
# Applies os/packages.yml to the image being built (PRD 6.2).
#
# This script is the ONLY place RPMs are added or removed. WP-02 and later WPs
# edit packages.yml — data — and never this file. That is what makes "what is in
# this OS and why" answerable by reading one short YAML file.
set -euo pipefail

MANIFEST="${1:?usage: apply-packages.sh <packages.yml>}"
[[ -f "$MANIFEST" ]] || { echo "apply-packages: manifest not found: $MANIFEST" >&2; exit 1; }

# packages.yml uses a deliberately tiny subset of YAML — flat keys, one level of
# nesting, lists of plain strings — and CI validates it against
# catalog/schemas/packages.schema.json before it ever reaches this script. So we
# read it with a restricted parser rather than pulling PyYAML into the image
# build just to parse twenty lines.
read_list() {
    python3 - "$MANIFEST" "$1" <<'PY'
import re, sys

# STRICT parser for the canonical form of packages.yml.
#
# It refuses anything it is not certain about instead of guessing. That matters
# more than convenience: this file decides which packages are installed and
# REMOVED from the OS, and a parser that quietly returns the wrong list would
# silently drop a driver. Review found seven schema-valid inputs where a lenient
# version disagreed with PyYAML — multi-line flow sequences, quoted keys,
# anchors/aliases, duplicate keys, odd indentation, space before the colon, and
# flow mappings. Every one now hard-errors here rather than returning [].
#
# If you hit one of these errors: write packages.yml in the plain form the
# schema documents. Do not loosen this parser.

path, dotted = sys.argv[1], sys.argv[2]
want = dotted.split(".")

KEY = re.compile(r"^(?P<indent> *)(?P<key>[a-z_][a-z0-9_]*):(?P<rest>| .*)$")
ITEM = re.compile(r"^(?P<indent> *)- +(?P<value>.+)$")


def die(lineno, line, why):
    sys.stderr.write(
        f"apply-packages: {path}:{lineno}: {why}\n"
        f"    {line.rstrip()}\n"
        f"    Refusing to guess. packages.yml must use the plain form:\n"
        f"      add:\n        - package-name\n"
        f"    or the inline empty form 'add: []'.\n")
    raise SystemExit(2)


items, stack, capturing, seen = [], [], False, set()

for lineno, raw in enumerate(open(path), 1):
    line = raw.split("#", 1)[0].rstrip()
    if not line.strip():
        continue

    m = KEY.match(line)
    if m:
        indent = len(m.group("indent"))
        if indent % 2:
            die(lineno, raw, f"indent of {indent} is not a multiple of two")
        depth = indent // 2
        if depth > len(stack):
            die(lineno, raw, "indented deeper than its parent key allows")
        stack = stack[:depth] + [m.group("key")]

        path_key = tuple(stack)
        if path_key in seen:
            die(lineno, raw, f"duplicate key '{'.'.join(stack)}' "
                             "(PyYAML would silently keep only the last one)")
        seen.add(path_key)

        inline = m.group("rest").strip()
        capturing = stack == want

        if inline:
            if inline.startswith(("&", "*")):
                die(lineno, raw, "YAML anchors and aliases are not supported")
            if inline.startswith("!"):
                die(lineno, raw, "YAML tags are not supported")
            if inline.startswith("{"):
                die(lineno, raw, "flow mappings are not supported")
            if inline.startswith("["):
                if not inline.endswith("]"):
                    die(lineno, raw, "a flow sequence must open and close on one line")
                if capturing:
                    body = inline[1:-1].strip()
                    items += [x.strip().strip("'\"")
                              for x in body.split(",") if x.strip()]
            elif capturing:
                die(lineno, raw, f"expected a list for '{dotted}', found a scalar")
            capturing = False
        continue

    m = ITEM.match(line)
    if m:
        if not stack:
            die(lineno, raw, "list item before any key")
        if capturing:
            value = m.group("value").strip()
            if value.startswith(("&", "*", "{", "[", "!")):
                die(lineno, raw, "list items must be plain scalars "
                                 "(no anchors, aliases, tags, or nested collections)")
            # A double-quoted scalar containing a backslash carries escapes that
            # PyYAML decodes and this parser does not: "haruna\x2Dextra" is
            # 'haruna-extra' to YAML but stays literal here. For a unit name that
            # is silent breakage — `systemctl mask` accepts any string.
            if "\\" in value:
                die(lineno, raw, "backslash escapes are not supported; "
                                 "write the value literally")
            items.append(value.strip("'\""))
        continue

    die(lineno, raw, "unrecognized line")

if items:
    print("\n".join(items))
PY
}

# Read one key, or abort the whole build.
#
# The previous version piped the parser through `< <(...)`, which DISCARDS the
# command's exit status: every strict rejection printed its error to stderr and
# then became an empty list, and the script exited 0. That was worse than having
# no strict parser at all — one ambiguous line emptied all four lists, so
# packages were silently not installed, removals silently not performed, and
# masks silently not applied, with a green build.
#
# A simple assignment DOES carry the command's status, so `|| ` is reached.
# Written without `local -n` so it also runs on bash 3.2 (the Mac dev loop).
parse_key() {
    local key="$1" raw
    if ! raw="$(read_list "$key")"; then
        echo "apply-packages: refusing to continue — the parser rejected" >&2
        echo "                ${MANIFEST} while reading '${key}' (see above)." >&2
        exit 2
    fi
    printf '%s' "$raw"
}

# Split captured text into ITEMS. A here-string keeps the loop in this shell, so
# nothing here can swallow a failure in a subshell either.
ITEMS=()
to_items() {
    ITEMS=()
    local line
    while IFS= read -r line; do
        if [ -n "$line" ]; then ITEMS+=("$line"); fi
    done <<< "${1:-}"
}

command -v python3 >/dev/null || {
    echo "apply-packages: python3 is required to read ${MANIFEST}." >&2
    echo "                Refusing to continue: without it every list would" >&2
    echo "                silently read as empty." >&2
    exit 2
}

ADD_RAW="$(parse_key add)"
to_items "$ADD_RAW";     ADD=("${ITEMS[@]+"${ITEMS[@]}"}")
REMOVE_RAW="$(parse_key remove)"
to_items "$REMOVE_RAW";  REMOVE=("${ITEMS[@]+"${ITEMS[@]}"}")
MASK_RAW="$(parse_key systemd.mask)"
to_items "$MASK_RAW";    MASK=("${ITEMS[@]+"${ITEMS[@]}"}")
DISABLE_RAW="$(parse_key systemd.disable)"
to_items "$DISABLE_RAW"; DISABLE=("${ITEMS[@]+"${ITEMS[@]}"}")

echo "apply-packages: add=${#ADD[@]} remove=${#REMOVE[@]} mask=${#MASK[@]} disable=${#DISABLE[@]}"

if [[ ${#REMOVE[@]} -gt 0 ]]; then
    echo "apply-packages: removing ${REMOVE[*]}"
    dnf -y remove "${REMOVE[@]}"
fi

if [[ ${#ADD[@]} -gt 0 ]]; then
    echo "apply-packages: installing ${ADD[*]}"
    dnf -y install "${ADD[@]}"
fi

for unit in "${MASK[@]+"${MASK[@]}"}"; do
    echo "apply-packages: masking $unit"
    systemctl mask "$unit"
done

for unit in "${DISABLE[@]+"${DISABLE[@]}"}"; do
    echo "apply-packages: disabling $unit"
    systemctl disable "$unit"
done

if [[ ${#ADD[@]} -gt 0 || ${#REMOVE[@]} -gt 0 ]]; then
    dnf clean all
    rm -rf /var/cache/libdnf5 /var/cache/dnf
fi

echo "apply-packages: done"
