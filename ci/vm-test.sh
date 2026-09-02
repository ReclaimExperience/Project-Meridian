#!/usr/bin/env bash
# Run harness suites against a real booted image in CI (PRD 7.3 vm-test row).
#
#   ci/vm-test.sh <arch> <suite> [suite...]
#
# Replaces WP-01's boot-screenshot stopgap, which was a one-off photograph with
# no assertions. Everything it did — KVM access, rootful transfer, disk build —
# is still needed, so that knowledge moved here rather than being rediscovered.
set -euo pipefail

ARCH="${1:?usage: ci/vm-test.sh <arch> [--repeat N] <suite> [suite...]}"
shift

# The flaky-rate gate runs the same suite ten times. Repeat only the SUITE, not
# the disk build: rebuilding each pass would make a 45-second check a 5-minute
# one, and a gate nobody wants to run is a gate that stops being run.
REPEAT=1
if [[ "${1:-}" == "--repeat" ]]; then
    REPEAT="${2:?--repeat needs a count}"
    shift 2
fi

SUITES=("$@")
[[ ${#SUITES[@]} -gt 0 ]] || SUITES=(smoke)

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

echo "::group::accelerator"
if [[ -e /dev/kvm ]]; then
    if [[ ! -r /dev/kvm || ! -w /dev/kvm ]]; then
        # Hosted runners ship /dev/kvm as root:kvm with the runner user outside
        # that group: present, but unusable until this. Established in WP-01;
        # without it every suite silently drops to TCG and takes 3x as long.
        echo "  /dev/kvm present but not accessible to $(id -un); granting access"
        sudo chmod 666 /dev/kvm || true
    fi
    [[ -r /dev/kvm && -w /dev/kvm ]] && echo "  KVM available" || echo "  KVM unusable; falling back to TCG"
else
    echo "  /dev/kvm absent; TCG (PRD 7.3's documented fallback, 3x slower)"
fi
echo "::endgroup::"

echo "::group::disk image"
# bootc-image-builder refuses to run rootless, and CI podman is rootless, so the
# image built by the runner user has to be handed to root's store first.
if [[ "$(podman info --format '{{ .Host.Security.Rootless }}')" == "true" ]]; then
    BRANDING=os/rootfs/usr/share/meridian/branding.json
    IMAGE="$(python3 -c "import json;d=json.load(open('${BRANDING}'));print(d['registry']['namespace']+'/'+d['registry']['image'])")"
    echo "  transferring ${IMAGE}:testing-${ARCH} into rootful storage"
    podman save "${IMAGE}:testing-${ARCH}" | sudo podman load
    SUDO=(sudo -E env "PATH=${PATH}")
else
    SUDO=()
fi
"${SUDO[@]}" just vm-image "$ARCH"
# The builder writes as root; the harness and the artifact upload read as the
# runner user.
sudo chown -R "$(id -u):$(id -g)" build
echo "::endgroup::"

status=0
failures=0
for pass in $(seq 1 "$REPEAT"); do
    for suite in "${SUITES[@]}"; do
        label="${suite}"
        [[ "$REPEAT" -gt 1 ]] && label="${suite} (pass ${pass}/${REPEAT})"
        echo "::group::vm-test ${label}"
        if ! just vm-test "$suite" "$ARCH"; then
            echo "::error::harness suite '${suite}' failed on ${ARCH} (pass ${pass}/${REPEAT})"
            failures=$((failures + 1))
            status=1
        fi
        echo "::endgroup::"
    done
done

if [[ "$REPEAT" -gt 1 ]]; then
    # The number that matters for PRD WP-03's flaky-rate gate. R-A treats flaky
    # as broken, so this is a pass/fail count, not a percentage to interpret.
    echo "flaky-rate: ${failures} failure(s) across ${REPEAT} consecutive pass(es)"
fi

echo "::group::evidence"
find build/evidence -maxdepth 1 -type f 2>/dev/null | sort | sed 's/^/  /' || true
echo "::endgroup::"

exit "$status"
