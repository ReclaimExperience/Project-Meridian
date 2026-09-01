#!/usr/bin/env bash
# ADR-002 base image verification — the [VERIFY] gate the whole stack rests on.
#
# ADR-002 requires, for the Universal Blue Plasma base:
#   a) the image exists and is pullable
#   b) it was built recently (< 30 days) — a stale base means ublue stopped building
#   c) its manifest covers both amd64 and arm64
#
# (c) is the interesting one. ADR-002 pre-authorizes a split base WITHOUT
# escalation when arm64 is absent (historically common for ublue main images):
# ublue for x86_64 (user-facing), Fedora Kinoite + our hardware-enablement layer
# for the aarch64 dev-loop image. This script decides which of the three ADR-002
# paths applies and prints it in a form the Containerfile and STATUS.md consume.
#
# Exit 0 = a usable path was found (check DECISION in the output).
# Exit 1 = no usable path; escalate per PRD 14.6.
set -euo pipefail

FEDORA_RELEASE="${FEDORA_RELEASE:-44}"
MAX_AGE_DAYS="${MAX_AGE_DAYS:-30}"

UBLUE_MAIN="ghcr.io/ublue-os/kinoite-main:${FEDORA_RELEASE}"
UBLUE_NVIDIA="ghcr.io/ublue-os/kinoite-nvidia:${FEDORA_RELEASE}"
FEDORA_KINOITE="quay.io/fedora/fedora-kinoite:${FEDORA_RELEASE}"

command -v skopeo >/dev/null || { echo "verify-base: skopeo is required"; exit 1; }

# --- helpers ----------------------------------------------------------------

# Architectures in an image's manifest. A single (non-index) manifest reports
# exactly one arch, read from its config.
arches_of() {
    local ref="$1" raw attempt
    # Retry before concluding an image is missing. arches_of() returning empty
    # drives DECISION=fedora-fallback, which swaps the user-facing x86_64 base
    # for one without ublue's driver stack — far too consequential to trigger on
    # a single transient registry error.
    for attempt in 1 2 3; do
        raw="$(skopeo inspect --raw "docker://${ref}" 2>/dev/null)" && break
        [ "$attempt" -lt 3 ] && sleep $((attempt * 3))
    done
    [ -n "${raw:-}" ] || return 1
    if printf '%s' "$raw" | grep -q '"manifests"'; then
        printf '%s' "$raw" | python3 -c '
import json,sys
d=json.load(sys.stdin)
a=sorted({m["platform"]["architecture"] for m in d.get("manifests",[])
          if m.get("platform",{}).get("architecture") not in (None,"unknown")})
print(" ".join(a))'
    else
        skopeo inspect "docker://${ref}" 2>/dev/null \
            | python3 -c 'import json,sys; print(json.load(sys.stdin).get("Architecture","?"))'
    fi
}

# `skopeo inspect` (non-raw) cannot inspect a multi-arch index without being told
# which arch to resolve, and fails with a JSON parse error if you do not. Always
# pin an arch that the image actually has, otherwise a perfectly healthy
# multi-arch image reports no build date and looks stale.
created_of() {
    local ref="$1" arch="$2"
    skopeo inspect --override-os linux --override-arch "$arch" "docker://${ref}" 2>/dev/null \
        | python3 -c 'import json,sys; print(json.load(sys.stdin).get("Created","")[:19])' 2>/dev/null
}

# Prints whole days since the given UTC timestamp, or "unknown" if unparseable.
# It never invents a number: a bogus age would either hide a stale base or raise
# a false alarm about a healthy one.
age_days() {
    python3 -c '
import datetime, sys
raw = sys.argv[1] if len(sys.argv) > 1 else ""
try:
    d = datetime.datetime.fromisoformat(raw).replace(tzinfo=datetime.timezone.utc)
except ValueError:
    print("unknown"); raise SystemExit
print((datetime.datetime.now(datetime.timezone.utc) - d).days)' "${1:-}"
}

report() {
    local ref="$1" arches created age probe
    if ! arches="$(arches_of "$ref")" || [[ -z "$arches" ]]; then
        printf '  %-46s MISSING\n' "$ref"
        return 1
    fi
    probe="${arches%% *}"                      # resolve dates against an arch it has
    created="$(created_of "$ref" "$probe")"
    age="$(age_days "$created")"
    printf '  %-46s arches=[%s] built=%s (%s d ago)\n' \
        "$ref" "$arches" "${created:-unknown}" "$age"

    if [[ "$age" == "unknown" ]]; then
        printf '      WARNING: could not read a build date — freshness UNVERIFIED for this image\n'
        return 2
    fi
    if (( age > MAX_AGE_DAYS )); then
        printf '      WARNING: %s days old (gate is %s) — upstream may have stopped building this tag\n' \
            "$age" "$MAX_AGE_DAYS"
        return 2
    fi
    return 0
}

# --- verification -----------------------------------------------------------

echo "ADR-002 base image verification (Fedora ${FEDORA_RELEASE}, freshness gate ${MAX_AGE_DAYS}d)"
echo

main_ok=0;   report "$UBLUE_MAIN"     || main_ok=$?
nvidia_ok=0; report "$UBLUE_NVIDIA"   || nvidia_ok=$?
report "$FEDORA_KINOITE" || true
echo

MAIN_ARCHES="$(arches_of "$UBLUE_MAIN" 2>/dev/null || echo "")"
FEDORA_ARCHES="$(arches_of "$FEDORA_KINOITE" 2>/dev/null || echo "")"

has() { [[ " $1 " == *" $2 "* ]]; }

if [[ "$main_ok" -gt 1 ]] || [[ -z "$MAIN_ARCHES" ]]; then
    if [[ -z "$FEDORA_ARCHES" ]]; then
        echo "DECISION=escalate"
        echo "REASON=ublue base unusable AND the ADR-002 fallback (Fedora Kinoite) is also unreachable."
        echo "ACTION=Open a DECISION-NEEDED issue per PRD 14.6. Do not improvise a third base."
        exit 1
    fi
    echo "DECISION=fedora-fallback"
    echo "REASON=ublue base missing or stale. ADR-002's documented fallback applies."
    echo "BASE_X86_64=${FEDORA_KINOITE}"
    echo "BASE_AARCH64=${FEDORA_KINOITE}"
    echo "NOTE=Requires os/layers/hardware-enablement.inc replicating ublue's driver/codec"
    echo "NOTE=stack (~2 extra agent sessions). Record the cost in STATUS.md."
    exit 0
fi

if has "$MAIN_ARCHES" amd64 && has "$MAIN_ARCHES" arm64; then
    echo "DECISION=ublue-both"
    echo "REASON=ublue base covers both architectures. The ADR-002 happy path applies."
    echo "BASE_X86_64=${UBLUE_MAIN}"
    echo "BASE_AARCH64=${UBLUE_MAIN}"
    [[ "$nvidia_ok" -eq 0 ]] && echo "BASE_NVIDIA=${UBLUE_NVIDIA}"
    exit 0
fi

if has "$MAIN_ARCHES" amd64 && ! has "$MAIN_ARCHES" arm64; then
    if ! has "$FEDORA_ARCHES" arm64; then
        echo "DECISION=escalate"
        echo "REASON=No arm64 base anywhere: ublue lacks it and Fedora Kinoite lacks it too."
        echo "ACTION=The Mac dev loop (PRD 7.2) has no image. Escalate per PRD 14.6."
        exit 1
    fi
    echo "DECISION=split-base"
    echo "REASON=ublue is amd64-only. ADR-002 PRE-AUTHORIZES this split without escalation."
    echo "BASE_X86_64=${UBLUE_MAIN}"
    echo "BASE_AARCH64=${FEDORA_KINOITE}"
    [[ "$nvidia_ok" -eq 0 ]] && echo "BASE_NVIDIA=${UBLUE_NVIDIA}"
    echo "NOTE=aarch64 is a development-only target (ADR-013). It needs the hardware-"
    echo "NOTE=enablement layer; x86_64 inherits it from ublue. Note this in STATUS.md."
    exit 0
fi

echo "DECISION=escalate"
echo "REASON=ublue manifest reports an unexpected architecture set: [${MAIN_ARCHES}]"
exit 1
