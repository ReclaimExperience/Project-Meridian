#!/usr/bin/env bash
# Generates /usr/lib/os-release from branding.json (PRD 6.5).
#
# Never hand-write os-release. It is the most-quoted product string in the whole
# system — About, SDDM, the installer, bug reports, `bootc status` — so if it is
# generated, the WP-26 rename is a one-file change; if it is typed, it is a
# scavenger hunt.
set -euo pipefail

BRANDING=""; VERSION=""; CHANNEL=""; BASE=""
while [[ $# -gt 0 ]]; do
    case "$1" in
        --branding) BRANDING="$2"; shift 2 ;;
        --version)  VERSION="$2";  shift 2 ;;
        --channel)  CHANNEL="$2";  shift 2 ;;
        --base)     BASE="$2";     shift 2 ;;
        *) echo "gen-os-release: unknown argument: $1" >&2; exit 2 ;;
    esac
done
[[ -f "$BRANDING" ]] || { echo "gen-os-release: branding file not found: $BRANDING" >&2; exit 1; }

# Keep the base's lineage in ID_LIKE so third-party tooling that sniffs for
# Fedora keeps working. We are a Fedora derivative and we do not hide it.
# This file only exists inside the image, so shellcheck cannot follow it.
# shellcheck source=/dev/null
BASE_ID_LIKE="$(. /usr/lib/os-release 2>/dev/null && echo "${ID_LIKE:-} ${ID:-}" | xargs || echo fedora)"

python3 - "$BRANDING" "$VERSION" "$CHANNEL" "$BASE" "$BASE_ID_LIKE" <<'PY' > /usr/lib/os-release
import json, re, sys

branding_path, version, channel, base, id_like = sys.argv[1:6]
b = json.load(open(branding_path))

version = version or b["version"]

# VERSION_ID is at most major.minor. osbuild / bootc-image-builder builds an
# internal distro name from ID + VERSION_ID and rejects more than one dot
# ("too many dots in the version"), and the os-release convention is a
# lower-precision version anyway: Fedora ships "44", RHEL ships "9.4".
# The full precision lives in VERSION and IMAGE_VERSION.
version_id = ".".join(version.split("-")[0].split(".")[:2])
codename = b.get("versionCodename") or ""
pretty = f'{b["name"]} {version}' + (f' ("{codename}")' if codename else "")
urls = b["urls"]

fields = [
    ("NAME",              b["name"]),
    ("PRETTY_NAME",       pretty),
    ("ID",                b["id"]),
    ("ID_LIKE",           id_like),
    ("VERSION",           version),
    ("VERSION_ID",        version_id),
    ("VERSION_CODENAME",  codename),
    ("VARIANT",           "Desktop"),
    ("VARIANT_ID",        "desktop"),
    ("ANSI_COLOR",        "0;38;2;0;152;192"),   # tokens.json accent.blue #0098c0
    ("LOGO",              b["id"]),
    ("HOME_URL",          urls["home"]),
    ("DOCUMENTATION_URL", urls["help"]),
    ("SUPPORT_URL",       urls["help"]),
    ("BUG_REPORT_URL",    urls["issues"]),
    ("DEFAULT_HOSTNAME",  b["id"]),
    ("IMAGE_ID",          f'{b["registry"]["namespace"]}/{b["registry"]["image"]}'),
    ("IMAGE_VERSION",     version),
]
if channel:
    fields.append(("IMAGE_CHANNEL", channel))
if base:
    fields.append(("BASE_IMAGE", base))

# os-release is machine-read by tooling that is stricter than the spec. Two
# rules learned the hard way from bootc-image-builder ("readOSRelease: invalid
# input"), both of which upstream Fedora already follows:
#
#   1. No comment lines. Some parsers do not skip them and abort on the first.
#   2. Double quotes, not single, around anything that is not a bare token.
#      An unquoted ANSI_COLOR like 0;38;2;0;152;192 breaks parsers on the ";".
#
# Do not "tidy" this by adding a provenance header. It will break image builds.
BARE = re.compile(r"^[A-Za-z0-9._:/@+-]+$")


def emit(key, value):
    value = str(value)
    if "\n" in value or "\r" in value:
        raise SystemExit(f"gen-os-release: {key} contains a newline; refusing to emit")
    if not BARE.match(value):
        # /etc/os-release is *sourced* by root-run shell scripts across the
        # system, so $ and ` must be escaped too, not just \ and ".
        for char in ("\\", '"', "$", "`"):
            value = value.replace(char, "\\" + char)
        value = f'"{value}"'
    print(f"{key}={value}")


for key, value in fields:
    if value != "":
        emit(key, value)
PY

# /etc/os-release must point at the generated file, not be a stale copy of it.
ln -sf ../usr/lib/os-release /etc/os-release

echo "gen-os-release: wrote /usr/lib/os-release"
grep -E '^(NAME|PRETTY_NAME|ID|VERSION|IMAGE_ID)=' /usr/lib/os-release | sed 's/^/    /'
