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
# It refuses anything it is not certain about instead of guessing, because this
# file decides which packages are installed and REMOVED from the OS. A parser
# that quietly returns the wrong list drops a driver from someone's machine.
#
# READ THIS BEFORE EDITING: a value can arrive by two routes — a block item
# ("- foo") or a flow sequence ("[foo, bar]"). Validation MUST live in
# validate_scalar() so both routes get it. A previous version guarded only the
# block route; the shipped packages.yml uses the flow form on every list, so the
# guards were on the path the real file never takes, and
# `mask: ["baloo\x5Ffile.service"]` masked a nonexistent unit with a green
# build. Add a rule once, here, not per branch.

path, dotted = sys.argv[1], sys.argv[2]
want = dotted.split(".")

KEY = re.compile(r"^(?P<indent> *)(?P<key>[a-z_][a-z0-9_]*):(?P<rest>| .*)$")
ITEM = re.compile(r"^(?P<indent> *)- +(?P<value>.+)$")

# Mirrors catalog/schemas/packages.schema.json. The schema is only checked by
# the lint workflow; the build path (build.yml -> ci/build.sh -> podman build)
# never validates it, so the structure has to be enforced here too.
REQUIRED_TOP = ("version", "add", "remove")
KNOWN = {(): {"version", "add", "remove", "systemd"}, ("systemd",): {"mask", "disable"}}


def die(lineno, line, why):
    sys.stderr.write(
        f"apply-packages: {path}:{lineno}: {why}\n"
        f"    {line.rstrip()}\n"
        f"    Refusing to guess. packages.yml must use the plain form:\n"
        f"      add:\n        - package-name\n"
        f"    or the inline empty form 'add: []'.\n")
    raise SystemExit(2)


def strip_comment(line):
    """Remove a trailing comment without cutting inside a quoted scalar."""
    out, quote = [], None
    for ch in line:
        if quote:
            out.append(ch)
            if ch == quote:
                quote = None
        elif ch in "'\"":
            quote = ch
            out.append(ch)
        elif ch == "#":
            break
        else:
            out.append(ch)
    return "".join(out)


def validate_scalar(lineno, raw, value):
    """The single gate every value passes, whichever syntax delivered it."""
    value = value.strip()
    if not value:
        die(lineno, raw, "empty value")
    if value[0] in "&*!{[":
        die(lineno, raw, "anchors, aliases, tags and nested collections are not "
                         "supported; write the value literally")
    if "\\" in value:
        # PyYAML decodes "\x5F" to "_"; this parser does not. For a unit name
        # that is silent breakage, because `systemctl mask` accepts any string.
        die(lineno, raw, "backslash escapes are not supported; write the value literally")
    if value[0] in "'\"":
        if len(value) < 2 or value[-1] != value[0]:
            die(lineno, raw, "unterminated quoted scalar")
        inner = value[1:-1]
        if value[0] in inner:
            die(lineno, raw, "nested quotes are not supported")
        value = inner
    if not value or any(c.isspace() for c in value):
        die(lineno, raw, "values must be single words with no whitespace")
    return value


items, stack, capturing, seen = [], [], False, set()

LIST_KEYS = ("add", "remove", "mask", "disable")

for lineno, source in enumerate(open(path), 1):
    # Document markers are NOT harmless: skipping them silently merges a
    # multi-document stream into one key space, where PyYAML would refuse the
    # file outright. `version: 1 / add: [alpha] / --- / remove: []` would have
    # installed alpha.
    if source.strip() in ("---", "..."):
        die(lineno, source, "multiple YAML documents are not supported; "
                            "packages.yml must be a single document")
    if "\t" in source:
        # PyYAML rejects tabs used for indentation outright. Accepting them
        # here would mean parsing a file no real YAML reader would accept.
        die(lineno, source, "tabs are not valid YAML indentation; use spaces")
    line = strip_comment(source).rstrip()
    if not line.strip():
        continue

    m = KEY.match(line)
    if m:
        indent = len(m.group("indent"))
        if indent % 2:
            die(lineno, source, f"indent of {indent} is not a multiple of two")
        depth = indent // 2
        if depth > len(stack):
            die(lineno, source, "indented deeper than its parent key allows")
        stack = stack[:depth] + [m.group("key")]

        parent = tuple(stack[:-1])
        if parent and parent[-1] in LIST_KEYS:
            # A mapping nested under a list key was structurally accepted and
            # silently yielded an empty list.
            die(lineno, source, f"'{parent[-1]}' takes a list of names, not a mapping")
        if parent in KNOWN and stack[-1] not in KNOWN[parent]:
            die(lineno, source, f"unknown key '{'.'.join(stack)}'")
        if tuple(stack) in seen:
            die(lineno, source, f"duplicate key '{'.'.join(stack)}' "
                                "(PyYAML would silently keep only the last one)")
        seen.add(tuple(stack))

        inline = m.group("rest").strip()
        capturing = stack == want

        if inline:
            if inline.startswith("["):
                if not inline.endswith("]"):
                    die(lineno, source, "a flow sequence must open and close on one line")
                body = inline[1:-1].strip()
                elements = [e for e in body.split(",")] if body else []
                if body and body.rstrip().endswith(","):
                    die(lineno, source, "trailing comma in a flow sequence")
                for element in elements:
                    value = validate_scalar(lineno, source, element)
                    if capturing:
                        items.append(value)
            elif stack[-1] in ("add", "remove", "mask", "disable"):
                die(lineno, source, f"expected a list for '{'.'.join(stack)}', found a scalar")
            elif stack[-1] != "version":
                die(lineno, source, f"unexpected scalar for '{'.'.join(stack)}'")
            capturing = False
        continue

    m = ITEM.match(line)
    if m:
        if not stack:
            die(lineno, source, "list item before any key")
        value = validate_scalar(lineno, source, m.group("value"))
        if capturing:
            items.append(value)
        continue

    die(lineno, source, "unrecognized line")

missing = [k for k in REQUIRED_TOP if (k,) not in seen]
if missing:
    sys.stderr.write(
        f"apply-packages: {path}: missing required key(s): {', '.join(missing)}\n"
        f"    An absent key is not the same as an empty one. Write 'add: []'\n"
        f"    explicitly so a typo or a truncated file cannot read as 'do nothing'.\n")
    raise SystemExit(2)

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

# INSTALL FIRST, THEN REMOVE. The other order looks natural and is wrong: the
# install step drags removed packages back in as dependencies, and the build
# still reports success. WP-02 hit this — plasma-welcome was removed and then
# reinstalled as a weak dependency, so the OOBE wizard the removal existed to
# delete was still in the image at the end.
#
# --setopt=install_weak_deps=False for the same reason and for pillar 4: a
# Recommends is someone else's opinion about what a desktop should include, and
# this product's whole claim is that it ships ~12 apps.
if [[ ${#ADD[@]} -gt 0 ]]; then
    echo "apply-packages: installing ${ADD[*]}"
    dnf -y --setopt=install_weak_deps=False install "${ADD[@]}"
fi

if [[ ${#REMOVE[@]} -gt 0 ]]; then
    echo "apply-packages: removing ${REMOVE[*]}"
    # Snapshot first. `dnf remove` takes everything that DEPENDS on a package
    # with it, so a one-line removal can silently delete the desktop: removing
    # kmenuedit took plasma-desktop, plasma-workspace and sddm, and the build
    # reported success. Verifying that the listed packages are gone does not
    # catch that — it is the UNLISTED casualties that matter.
    before_removal="$(mktemp)"
    rpm -qa --qf '%{NAME}\n' | sort -u > "$before_removal"

    dnf -y remove "${REMOVE[@]}"

    after_removal="$(mktemp)"
    rpm -qa --qf '%{NAME}\n' | sort -u > "$after_removal"

    wanted="$(mktemp)"
    printf '%s\n' "${REMOVE[@]}" | sort -u > "$wanted"

    collateral="$(comm -23 <(comm -23 "$before_removal" "$after_removal") "$wanted")"
    rm -f "$before_removal" "$after_removal" "$wanted"

    if [[ -n "$collateral" ]]; then
        echo >&2
        echo "apply-packages: removal took packages that were NOT listed:" >&2
        printf '%s\n' "$collateral" | sed 's/^/    /' >&2
        echo >&2
        echo "    dnf removes everything that depends on a package. One of the" >&2
        echo "    entries in packages.yml is dependency-locked, and forcing it out" >&2
        echo "    took these with it." >&2
        echo "    PRD WP-02: 'Escalate if a 3.2 removal is dependency-locked into" >&2
        echo "    Plasma (document, propose substitute, wait).' Do not force it." >&2
        exit 1
    fi
fi

# Prove the removals actually stuck. dnf can report success while a package
# returns as a dependency of something installed later, and a de-bloat that
# silently leaves the software in place is worse than none: it makes a false
# claim about what ships.
still_present=()
for package in "${REMOVE[@]+"${REMOVE[@]}"}"; do
    if rpm -q "$package" >/dev/null 2>&1; then
        still_present+=("$package")
    fi
done
if [[ ${#still_present[@]} -gt 0 ]]; then
    echo "apply-packages: these were listed for removal but are STILL INSTALLED:" >&2
    for package in "${still_present[@]}"; do
        echo "    ${package}  <- required by: $(rpm -q --whatrequires "$package" 2>/dev/null | tr '\n' ' ' || echo 'nothing (weak dependency?)')" >&2
    done
    echo >&2
    echo "    A removal that does not remove is a false claim about what ships." >&2
    echo "    If the package is dependency-locked into Plasma, PRD WP-02 says to" >&2
    echo "    escalate and hide it rather than force it out (ADR-006's pattern for" >&2
    echo "    konsole: hidden is not the same as removed)." >&2
    exit 1
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
