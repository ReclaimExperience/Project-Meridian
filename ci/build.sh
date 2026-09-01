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

echo "::group::ADR-002 base verification"
# Verify at build time, not just at authoring time. If ublue moves under us, the
# build must say so rather than quietly using a stale committed decision.
just verify-base
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
fi

echo "ci/build.sh: ${ARCH} done"
