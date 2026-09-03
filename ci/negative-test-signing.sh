#!/usr/bin/env bash
# The negative test: an unsigned image in our namespace must be REFUSED.
#
#   ci/negative-test-signing.sh <signed-ref> [unsigned-ref]
#
# ADR-022: "negative test green" is a HARD GATE on the first :stable image.
# Until this passes, signature enforcement is unproven whatever policy.json says
# — a policy file is a claim, and this is the only thing that turns it into
# evidence.
#
# Three assertions, and the order matters:
#
#   1. POSITIVE CONTROL — the policy must REJECT something. If a deliberately
#      unsignable reference is accepted, the policy is not being enforced and the
#      other two results are noise. Learned from ADR-022's own VERIFY, whose
#      first version used a command that does not consult policy at all and
#      "passed" three shapes it never evaluated.
#   2. ACCEPT — the correctly signed image passes. Without this the test could be
#      satisfied by a policy that refuses everything, which is not security, it
#      is an unbootable machine.
#   3. REFUSE — an unsigned image in the same namespace is rejected. This is the
#      property the gate exists for.
set -euo pipefail

BRANDING=os/rootfs/usr/share/meridian/branding.json
IMAGE="$(python3 -c "import json;d=json.load(open('${BRANDING}'));print(d['registry']['namespace']+'/'+d['registry']['image'])")"

SIGNED="${1:-${IMAGE}:testing-x86_64}"
UNSIGNED="${2:-}"

# Find an unsigned reference in OUR namespace if none was given. Pull requests
# build and push `pr-*` tags and never reach the signing job, so one of those is
# exactly what this test needs: an image inside the scope the policy governs,
# without a signature. An out-of-scope image only exercises the control.
if [[ -z "$UNSIGNED" ]]; then
    candidate="$(skopeo list-tags "docker://${IMAGE}" 2>/dev/null |
        python3 -c "
import json, sys
try:
    tags = json.load(sys.stdin).get('Tags', [])
except Exception:
    tags = []
prs = sorted(t for t in tags if t.startswith('pr-'))
print(prs[-1] if prs else '')
" || true)"
    [[ -n "$candidate" ]] && UNSIGNED="${IMAGE}:${candidate}"
fi
PUBKEY="os/rootfs/etc/pki/containers/meridian.pub"
WORK="$(mktemp -d)"
trap 'rm -rf "$WORK"' EXIT

command -v skopeo >/dev/null 2>&1 || { echo "negative-test: skopeo required" >&2; exit 2; }
[[ -r "$PUBKEY" ]] || { echo "negative-test: ${PUBKEY} not readable" >&2; exit 2; }

cp "$PUBKEY" "${WORK}/meridian.pub"
repo="${SIGNED%%:*}"
cat > "${WORK}/policy.json" <<POLICY
{
  "default": [{"type": "reject"}],
  "transports": {
    "docker": {
      "${repo}": [
        {
          "type": "sigstoreSigned",
          "keyPath": "${WORK}/meridian.pub",
          "signedIdentity": {"type": "matchRepository"}
        }
      ]
    }
  }
}
POLICY

copy_allowed() {
    rm -rf "${WORK}/out"
    skopeo --policy "${WORK}/policy.json" copy "docker://${1}" "dir:${WORK}/out" \
        >/dev/null 2>&1
}

failures=0

echo "negative-test: 1. positive control — the policy must reject SOMETHING"
if copy_allowed "quay.io/fedora/fedora:44"; then
    echo "  FAIL  an out-of-scope image was accepted under a reject-by-default"
    echo "        policy, so policy is not being enforced and nothing below means"
    echo "        anything."
    failures=$((failures + 1))
else
    echo "  ok    an out-of-scope image is rejected (policy is live)"
fi

echo "negative-test: 2. the signed image must be ACCEPTED"
if copy_allowed "$SIGNED"; then
    echo "  ok    ${SIGNED} verifies against the shipped public key"
else
    echo "  FAIL  the correctly signed image was REJECTED."
    echo "        A policy that refuses everything is not enforcement, it is an"
    echo "        unbootable machine. Check that CI signed this digest and that"
    echo "        ${PUBKEY} matches the signing key."
    failures=$((failures + 1))
fi

if [[ -n "$UNSIGNED" ]]; then
    echo "negative-test: 3. an UNSIGNED image in our namespace must be REFUSED"
    if copy_allowed "$UNSIGNED"; then
        echo "  FAIL  ${UNSIGNED} was ACCEPTED without a valid signature."
        echo "        This is the gate's whole purpose. Enforcement is not working."
        failures=$((failures + 1))
    else
        echo "  ok    ${UNSIGNED} is refused"
    fi
else
    echo "negative-test: 3. SKIPPED — no unsigned reference given."
    echo "        The gate is NOT satisfied by runs 1 and 2 alone: they show the"
    echo "        policy accepts what it should, not that it refuses what it must."
    failures=$((failures + 1))
fi

echo
if [[ "$failures" -gt 0 ]]; then
    echo "negative-test: ${failures} failure(s) — signature enforcement is UNPROVEN."
    echo "  ADR-022: this is a hard gate on the first :stable image (promote 7.5)."
    exit 1
fi
echo "negative-test: signed accepted, unsigned refused, policy demonstrably live."
