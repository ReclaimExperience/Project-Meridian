#!/usr/bin/env bash
# Sign a published image with cosign (ADR-014, ADR-022's fallback).
#
#   ci/sign-image.sh <image-ref>
#
# Signs BY DIGEST, never by tag. A tag is a moving pointer: signing
# `:testing` would attest "whatever that name points at right now", which is
# exactly the thing an attacker moves. Resolving to a digest first means the
# signature covers specific bytes.
#
# The private key arrives as COSIGN_PRIVATE_KEY from a GitHub Environment secret
# behind required reviewers, so a compromised workflow cannot sign on its own —
# a human approves each release. That protection is the entire reason a key is
# tolerable here at all: ADR-022 preferred keyless precisely so no key would
# exist, and its VERIFY found the client cannot enforce a keyless identity.
set -euo pipefail

REF="${1:?usage: ci/sign-image.sh <image-ref>}"

: "${COSIGN_PRIVATE_KEY:?COSIGN_PRIVATE_KEY is not set. It lives in the 'release'
   GitHub Environment; a run without it must FAIL rather than publish an
   unsigned image that looks signed.}"
: "${COSIGN_PASSWORD:?COSIGN_PASSWORD is not set (same environment).}"

command -v cosign >/dev/null 2>&1 || {
    echo "sign-image: cosign is not installed." >&2
    exit 2
}

# Check we can WRITE before we sign. cosign signs first and pushes second, so an
# auth problem surfaces after a Rekor transparency-log entry has already been
# created for a signature that never lands — a public record of a thing that did
# not happen. The first run failed exactly that way: `skopeo login` writes the
# containers auth file, cosign reads go-containerregistry's (~/.docker/config.json),
# so cosign was pushing anonymously.
if [[ -n "${REGISTRY_AUTH_FILE:-}" && ! -s "${REGISTRY_AUTH_FILE}" ]]; then
    echo "sign-image: REGISTRY_AUTH_FILE is set to '${REGISTRY_AUTH_FILE}' but that" >&2
    echo "            file is empty or missing. Refusing to sign: the signature" >&2
    echo "            push would fail after the transparency log had recorded it." >&2
    exit 1
fi

echo "sign-image: resolving ${REF} to a digest"
digest="$(skopeo inspect --format '{{.Digest}}' "docker://${REF}" 2>/dev/null)" || {
    echo "sign-image: could not resolve ${REF}. Refusing to sign a name I cannot" >&2
    echo "            pin to bytes." >&2
    exit 1
}
repo="${REF%%:*}"
target="${repo}@${digest}"
echo "sign-image: signing ${target}"

cosign sign --yes --key env://COSIGN_PRIVATE_KEY "$target"

echo "sign-image: verifying our own signature before claiming success"
if ! cosign verify --key os/rootfs/etc/pki/containers/meridian.pub "$target" >/dev/null 2>&1; then
    echo "sign-image: FAILED — cosign reported a successful sign, but the" >&2
    echo "            signature does not verify against the public key that ships" >&2
    echo "            in the image. That combination means the key pair does not" >&2
    echo "            match, and every client would reject this image." >&2
    exit 1
fi
echo "sign-image: signed and verified against the shipped public key"
echo "  ${target}"
