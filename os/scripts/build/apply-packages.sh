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

path, dotted = sys.argv[1], sys.argv[2]
want = dotted.split(".")
items, stack, capturing = [], [], False

for raw in open(path):
    line = raw.split("#", 1)[0].rstrip()
    if not line.strip():
        continue
    indent = len(line) - len(line.lstrip())

    m = re.match(r"^(\s*)([A-Za-z_][A-Za-z0-9_]*):\s*(.*)$", line)
    if m:
        stack = stack[: indent // 2] + [m.group(2)]
        inline = m.group(3).strip()
        capturing = stack == want
        if capturing and inline:
            # inline form: `add: []` or `add: [a, b]`
            if inline.startswith("["):
                body = inline.strip("[]").strip()
                items += [x.strip().strip("'\"") for x in body.split(",") if x.strip()]
            capturing = False
        continue

    m = re.match(r"^\s*-\s+(.+)$", line)
    if m and capturing:
        items.append(m.group(1).strip().strip("'\""))

if items:
    print("\n".join(items))
PY
}

mapfile_compat() {  # bash 3.2 on the Mac has no mapfile; CI has bash 5.
    local -n _dest="$1"; shift
    _dest=()
    local line
    while IFS= read -r line; do
        if [[ -n "$line" ]]; then _dest+=("$line"); fi
    done < <("$@")
}

mapfile_compat ADD     read_list add
mapfile_compat REMOVE  read_list remove
mapfile_compat MASK    read_list systemd.mask
mapfile_compat DISABLE read_list systemd.disable

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
