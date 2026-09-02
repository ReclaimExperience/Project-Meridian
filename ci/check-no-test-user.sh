#!/usr/bin/env bash
# Prove the PUBLISHED image carries no test access (PRD 7.4, WP-03 acceptance).
#
#   ci/check-no-test-user.sh <image-ref>
#
# The harness logs in as `mtest`, so the obvious question is whether that account
# ships. It must not: PRD 7.4 requires no published image contain test
# credentials, so a `:testing` digest stays promotable to `:stable` by pure
# retag (7.3).
#
# It does not ship, by construction — the account is created in the local DISK
# image by bootc-image-builder, never in the container image. This is the proof
# rather than the claim, and it inspects the ref that was actually pushed.
#
# Scope: test-credential hygiene only. ADR-015 concerns such as "is sshd
# installed" belong to the security suite, so that a violation there fails the
# ADR-015 gate rather than this one.
set -euo pipefail

REF="${1:?usage: ci/check-no-test-user.sh <image-ref>}"

echo "checking published image for test access: ${REF}"
# Only reach for the registry when the image is not already here: `podman pull`
# on a present tag still round-trips, which hangs a local run for no reason.
if ! podman image exists "$REF" 2>/dev/null; then
    if ! podman pull -q "$REF" >/dev/null 2>&1; then
        # Exit 1, not whatever podman returned: a non-zero status here means
        # "could not check", and the caller must not have to distinguish
        # podman's exit codes from ours to know the image is unverified.
        echo "FAIL — could not obtain ${REF}, so it has NOT been checked."
        exit 1
    fi
fi

# One container, all checks. A positive control is emitted FIRST: if it is
# missing from the output, the container never ran and the whole result is
# meaningless. Without it, any podman failure — wrong arch, missing /bin/bash,
# OCI runtime error, storage problem — produced empty output that read as
# "nothing found", so this check could report a clean image without ever having
# looked at one.
SENTINEL="__probe_ran__"
set +e
output="$(podman run --rm --entrypoint /bin/bash "$REF" -c "
    echo ${SENTINEL}
    getent passwd mtest 2>/dev/null | sed 's/^/mtest in passwd: /'
    grep -h '^mtest:' /etc/passwd /usr/lib/passwd 2>/dev/null | sed 's/^/mtest in passwd file: /'
    ls -d /home/mtest /var/home/mtest 2>/dev/null | sed 's/^/mtest home: /'
    grep -rl mtest /usr/lib/systemd /etc/systemd 2>/dev/null | sed 's/^/systemd unit mentions mtest: /'
    find / -name authorized_keys -not -path '/proc/*' 2>/dev/null | sed 's/^/authorized_keys: /'
    true
" 2>&1)"
run_status=$?
set -e

if [[ "$run_status" -ne 0 ]] || ! grep -qF "$SENTINEL" <<<"$output"; then
    echo "FAIL — the probe never ran, so this image has NOT been checked."
    echo "  podman exit status: ${run_status}"
    echo "  output:"
    printf '%s\n' "$output" | sed 's/^/    /'
    echo
    echo "A green result here must mean 'the image is clean', never 'the check"
    echo "did not run'. Refusing to report clean."
    exit 1
fi

# `grep -v` exits 1 when it filters EVERYTHING out — which is the clean case
# here — and under `set -o pipefail` that aborts the script before it can report
# success. The clean path must not depend on grep finding something.
findings="$(grep -vF "$SENTINEL" <<<"$output" | sed '/^[[:space:]]*$/d' || true)"

if [[ -n "$findings" ]]; then
    echo "FAIL — this image carries test access and MUST NOT be promoted to :stable:"
    printf '%s\n' "$findings" | sed 's/^/    /'
    echo
    echo "PRD 7.4: no published image contains test credentials. The harness"
    echo "injects them into the local disk image instead, so the container image"
    echo "that ships is byte-identical to the one that was tested."
    exit 1
fi

echo "  ok  no mtest account, no home, no credential unit, no authorized_keys"
echo "published image is clean (PRD 7.4)"
