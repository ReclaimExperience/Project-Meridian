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
import json, sys, shlex

branding_path, version, channel, base, id_like = sys.argv[1:6]
b = json.load(open(branding_path))

version = version or b["version"]
version_id = version.split("-")[0]
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

def emit(key, value):
    value = str(value)
    # os-release values need quoting only when they contain whitespace or quotes.
    if any(ch in value for ch in ' \t"\''):
        value = shlex.quote(value)
    print(f"{key}={value}")


print("# Generated at image build from branding.json by gen-os-release.sh.")
print("# Do not edit: your change will be overwritten on the next build (PRD 6.5).")
for key, value in fields:
    if value != "":
        emit(key, value)
PY

# /etc/os-release must point at the generated file, not be a stale copy of it.
ln -sf ../usr/lib/os-release /etc/os-release

echo "gen-os-release: wrote /usr/lib/os-release"
grep -E '^(NAME|PRETTY_NAME|ID|VERSION|IMAGE_ID)=' /usr/lib/os-release | sed 's/^/    /'
