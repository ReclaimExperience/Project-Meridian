#!/usr/bin/env bash
# Image build job body (PRD 7.3 build rows). Kept out of the workflow file so a
# CI failure is reproducible locally with the same script (PRD 7.1).
#
#   ci/build.sh <arch> [--push <tag>]
#
# Signing is scaffolded here but enforced in WP-04, which owns cosign and the
# containers policy that makes clients refuse unsigned images.
set -euo pipefail

ARCH="${1:?usage: ci/build.sh <x86_64|aarch64> [--push <tag>]}"
shift || true

PUSH_TAG=""
while [[ $# -gt 0 ]]; do
    case "$1" in
        --push) PUSH_TAG="$2"; shift 2 ;;
        *) echo "ci/build.sh: unknown argument: $1" >&2; exit 2 ;;
    esac
done

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

echo "::group::ADR-002 base verification (compare-only)"
# Verify at build time — but COMPARE against the committed decision rather than
# overwriting it. Regenerating here meant a transient registry error could flip
# DECISION to fedora-fallback mid-job and silently build the user-facing x86_64
# image on a base with none of ublue's driver stack, then push it to :testing.
# Green build, wrong OS. The committed os/base-images.env is the contract; CI's
# job is to notice when reality has moved away from it, not to redefine it.
committed="os/base-images.env"
[[ -f "$committed" ]] || { echo "ci/build.sh: $committed missing — run 'just verify-base'"; exit 1; }

live="$(mktemp)"
trap 'rm -f "$live"' EXIT
./os/scripts/build/verify-base.sh > "$live" || {
    echo "ci/build.sh: verify-base.sh failed:"; cat "$live"; exit 1
}

if ! diff -u <(grep -E '^(DECISION|BASE_[A-Z0-9_]+)=' "$committed") \
             <(grep -E '^(DECISION|BASE_[A-Z0-9_]+)=' "$live"); then
    echo
    echo "ci/build.sh: the live ADR-002 decision differs from the committed one."
    echo "  This is a real event, not a flake to retry past: the base images moved."
    echo "  Run 'just verify-base', review the diff, and commit it deliberately."
    exit 1
fi
echo "base decision matches the committed record:"
grep -E '^(DECISION|BASE_)' "$committed" | sed 's/^/  /'
echo "::endgroup::"

echo "::group::build ${ARCH}"
just build "${ARCH}"
echo "::endgroup::"

BRANDING="os/rootfs/usr/share/meridian/branding.json"
IMAGE="$(python3 -c "import json;d=json.load(open('${BRANDING}'));print(d['registry']['namespace']+'/'+d['registry']['image'])")"
LOCAL_TAG="${IMAGE}:testing-${ARCH}"

echo "::group::labels"
# WP-01 acceptance: the pushed image must carry our labels.
podman image inspect "${LOCAL_TAG}" \
    --format '{{ range $k, $v := .Labels }}{{ $k }}={{ $v }}
{{ end }}' | grep -E '^(org\.opencontainers\.image\.(title|version|revision|source|base\.name)|org\.meridian\.)' | sort
echo "::endgroup::"

echo "::group::os-release from the built image"
podman run --rm --entrypoint /bin/sh "${LOCAL_TAG}" -c 'cat /usr/lib/os-release'
echo "::endgroup::"

if [[ -n "$PUSH_TAG" ]]; then
    echo "::group::push ${PUSH_TAG}"
    podman tag "${LOCAL_TAG}" "${PUSH_TAG}"
    podman push "${PUSH_TAG}"
    echo "::endgroup::"

    echo "::group::verify pushed labels"
    # WP-01 acceptance: the labels must be on the PUSHED image, not just locally.
    skopeo inspect "docker://${PUSH_TAG}" \
        | python3 -c 'import json,sys; L=json.load(sys.stdin)["Labels"] or {}; [print(f"  {k}={v}") for k,v in sorted(L.items()) if k.startswith(("org.opencontainers.image.","org.meridian.","containers."))]'
    echo "::endgroup::"
fi

echo "ci/build.sh: ${ARCH} done"
