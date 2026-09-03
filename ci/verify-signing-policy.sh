#!/usr/bin/env bash
# ADR-022's VERIFY, as something you can run rather than something I concluded.
#
# The question: can `containers-policy.json` pin a KEYLESS sigstore identity —
# specifically the GitHub Actions workflow that signed the image?
#
# It matters because GitHub's OIDC certificates carry the workflow identity in a
# URI SAN, e.g.
#   https://github.com/OWNER/REPO/.github/workflows/build.yml@refs/heads/main
# and a policy can only enforce fields the parser actually supports. A policy
# that LOOKS like it pins an identity but silently enforces nothing is worse than
# no policy, because it is indistinguishable from a real one in review.
#
# Two properties are established, and the first is what makes the second mean
# anything:
#
#   1. POSITIVE CONTROL — a reject-everything policy must actually reject. If it
#      does not, the tool is not enforcing policy at all and every other result
#      here is noise. (Learned the hard way: `skopeo inspect` does NOT enforce
#      policy, so an earlier version of this check "passed" three shapes that
#      were never evaluated.)
#   2. FIELD ENUMERATION — the parser rejects unknown keys, so offering it a
#      candidate field name and seeing whether it complains is a direct read of
#      what the schema supports on THIS machine's containers-image.
#
# Re-run this when containers-image is updated. If an identity field appears,
# ADR-022's keyless design becomes implementable and the key-pair fallback can be
# retired.
set -euo pipefail

REF="${1:-quay.io/fedora/fedora:44}"
WORK="$(mktemp -d)"
trap 'rm -rf "$WORK"' EXIT

command -v skopeo >/dev/null 2>&1 || {
    echo "verify-signing-policy: skopeo is required." >&2
    exit 2
}

echo "verify-signing-policy: containers-image via $(skopeo --version)"
echo "verify-signing-policy: probing with ${REF}"

# --- 1. positive control -------------------------------------------------
printf '{"default":[{"type":"reject"}]}' > "${WORK}/reject.json"
if skopeo --policy "${WORK}/reject.json" copy "docker://${REF}" "dir:${WORK}/out" >/dev/null 2>&1; then
    echo "verify-signing-policy: POSITIVE CONTROL FAILED — a reject-everything" >&2
    echo "    policy allowed a copy, so policy is not being enforced and nothing" >&2
    echo "    below would mean anything." >&2
    exit 1
fi
echo "  positive control: a reject-all policy does reject"

probe_field() {
    local field="$1"
    printf '{"default":[{"type":"reject"}],"transports":{"docker":{"%s":[{"type":"sigstoreSigned","fulcio":{"oidcIssuer":"https://token.actions.githubusercontent.com","caData":"","%s":"probe"},"rekorPublicKeyPath":"/nonexistent","signedIdentity":{"type":"matchRepository"}}]}}}' \
        "${REF%:*}" "$field" > "${WORK}/probe.json"
    # Capture, then match. NOT `skopeo ... | grep -q`: under `set -o pipefail`,
    # grep -q exits the instant it matches, skopeo dies of SIGPIPE (141), and
    # pipefail makes the PIPELINE non-zero — so `if` reads false exactly when the
    # match succeeded, inverting every result. This function reported that all
    # seven candidate fields were supported, which is the dangerous direction:
    # it would have concluded that identity pinning works when it does not.
    local output
    output="$(skopeo --policy "${WORK}/probe.json" copy "docker://${REF}" \
        "dir:${WORK}/out" 2>&1 || true)"
    case "$output" in
        *"Unknown key"*) return 1 ;;
    esac
    return 0
}

echo "  fulcio identity fields supported here:"
supported=()
for field in subjectEmail subjectHostname subjectURI certificateIdentity \
             certificateIdentityRegexp identityRegexp subject; do
    if probe_field "$field"; then
        supported+=("$field")
        printf "    %-28s yes\n" "$field"
    else
        printf "    %-28s no\n" "$field"
    fi
done

echo
identity_capable=no
for field in "${supported[@]+"${supported[@]}"}"; do
    case "$field" in
        subjectEmail) ;;  # an email SAN, which GitHub Actions certs do not have
        *) identity_capable=yes ;;
    esac
done

if [[ "$identity_capable" == "yes" ]]; then
    echo "verify-signing-policy: KEYLESS IDENTITY PINNING IS AVAILABLE."
    echo "    ADR-022's primary design is implementable. Retire the key-pair"
    echo "    fallback and pin the release workflow ref."
    exit 0
fi

echo "verify-signing-policy: keyless identity pinning is NOT available."
echo "    The only identity field is subjectEmail, which matches an email SAN."
echo "    GitHub Actions OIDC certificates carry the workflow identity as a URI"
echo "    SAN and have no email SAN, so neither field can express"
echo "    'signed by our release workflow'."
echo
echo "    ADR-022's pre-authorized fallback applies: a cosign key pair, public"
echo "    key baked into the image policy, private key in a GitHub Environment"
echo "    secret with required reviewers and documented rotation."
echo
echo "    This is a statement about containers-image on THIS machine. Re-run"
echo "    after an update; if an identity field appears, keyless becomes"
echo "    implementable and this fallback should be retired."
exit 0
