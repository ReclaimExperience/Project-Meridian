#!/usr/bin/env bash
# WP-04's flagship test: a bad update must undo itself (ADR-008).
#
#   ci/rollback-drill.sh <arch>
#
# Builds a deliberately broken image, serves it from a throwaway registry the VM
# can reach, and runs the drill. Nothing here fakes the failure detection — the
# sabotage breaks graphical.target, the health check observes that on its own,
# and greenboot decides. WP-04 forbids shortening the drill any other way.
#
# The registry is local and plain HTTP because the alternative is credentials in
# a VM, and the drill is about rollback, not about registry auth.
set -euo pipefail

ARCH="${1:-x86_64}"
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

BRANDING=os/rootfs/usr/share/meridian/branding.json
IMAGE="$(python3 -c "import json;d=json.load(open('${BRANDING}'));print(d['registry']['namespace']+'/'+d['registry']['image'])")"
LOCAL="${IMAGE}:testing-${ARCH}"
REGISTRY_PORT=5000
SABOTAGE_REF="10.0.2.2:${REGISTRY_PORT}/meridian/sabotage:${ARCH}"

cleanup() {
    podman rm -f meridian-drill-registry >/dev/null 2>&1 || true
}
trap cleanup EXIT

echo "::group::sabotage image"
podman image exists "$LOCAL" || {
    echo "rollback-drill: ${LOCAL} is not in the local store. Build it first —" >&2
    echo "                the drill compares against the image under test." >&2
    exit 1
}
podman build --build-arg "BASE_IMAGE=${LOCAL}" \
    -t "localhost/meridian-sabotage:${ARCH}" -f os/sabotage/Containerfile os/
echo "::endgroup::"

echo "::group::throwaway registry"
cleanup
podman run -d --name meridian-drill-registry -p "${REGISTRY_PORT}:5000" \
    docker.io/library/registry:2 >/dev/null
# Wait for it rather than sleeping a guess: a push against a registry that is
# still starting fails in a way that looks like a drill problem.
for _ in $(seq 1 30); do
    curl -sf "http://127.0.0.1:${REGISTRY_PORT}/v2/" >/dev/null 2>&1 && break
    sleep 1
done
curl -sf "http://127.0.0.1:${REGISTRY_PORT}/v2/" >/dev/null 2>&1 || {
    echo "rollback-drill: the throwaway registry never came up." >&2
    exit 1
}
podman push --tls-verify=false "localhost/meridian-sabotage:${ARCH}" \
    "127.0.0.1:${REGISTRY_PORT}/meridian/sabotage:${ARCH}"
echo "::endgroup::"

echo "::group::drill"
MERIDIAN_SABOTAGE_REF="$SABOTAGE_REF" python3 tests/harness/run.py rollback --arch "$ARCH"
echo "::endgroup::"
