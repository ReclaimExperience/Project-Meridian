#!/usr/bin/env bash
# Run harness suites against a real booted image in CI (PRD 7.3 vm-test row).
#
#   ci/vm-test.sh <arch> [--repeat N] <suite> [suite...]
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
    # Validate the VALUE, not just its presence: `--repeat 0` produced an empty
    # loop and exited 0, i.e. a green run that tested nothing — reachable from
    # the nightly's free-text dispatch input. (BSD seq would run it twice: same
    # missing validation, different symptom.)
    if ! [[ "$REPEAT" =~ ^[1-9][0-9]*$ ]]; then
        echo "ci/vm-test.sh: --repeat must be a positive integer, got '${REPEAT}'" >&2
        exit 2
    fi
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
# bootc-image-builder refuses to run rootless, so the image has to be in ROOT's
# store before a disk can be made. CI builds rootless, so this transfer is the
# normal path: an 8.7 GiB `podman save | sudo podman load`, about 4m12s.
#
# Building rootful to avoid it was tried and reverted — it cost two credential
# failures and then a 1h45m hang at the first RUN step. The check below stays
# because it is cheap and correct either way: assuming the store would turn a
# rootful build into "image not known", surfacing four minutes later as a
# bootc-image-builder manifest error rather than "it is in the wrong store".
BRANDING=os/rootfs/usr/share/meridian/branding.json
IMAGE="$(python3 -c "import json;d=json.load(open('${BRANDING}'));print(d['registry']['namespace']+'/'+d['registry']['image'])")"
LOCAL_REF="${IMAGE}:testing-${ARCH}"

if [[ "$(podman info --format '{{ .Host.Security.Rootless }}')" == "true" ]]; then
    # HOME is set explicitly, and -E is NOT used. `sudo -E` preserves the
    # caller's HOME, so root's podman then reads the USER's
    # ~/.config/containers/storage.conf — the one ci/prepare-runner.sh writes
    # with graphroot on /mnt. Rootful podman would report that graphroot, the
    # store's database would record /mnt/..., and bootc-image-builder would be
    # handed a store whose recorded path disagreed with where it was mounted:
    #
    #   database static dir "/mnt/containers/storage/libpod" does not match
    #   our static dir "/var/lib/containers/storage/libpod"
    #
    # prepare-runner.sh already solves this properly for the rootful store by
    # bind-mounting the big volume UNDER the canonical path. `-E` was quietly
    # undoing that. PATH is still passed through, which is all -E was wanted for.
    # CONTAINERS_STORAGE_CONF names the store explicitly, because root does
    # NOT reliably resolve to /var/lib/containers/storage on its own here —
    # measured, not assumed (see ci/prepare-runner.sh).
    SUDO=(sudo env "PATH=${PATH}" "HOME=/root"
          "CONTAINERS_STORAGE_CONF=/etc/containers/storage-root.conf")
    if "${SUDO[@]}" podman image exists "${LOCAL_REF}"; then
        echo "  ${LOCAL_REF} is already in rootful storage; no transfer needed"
    else
        echo "  ${LOCAL_REF} is only in the rootless store — transferring."
        echo "  This copies ~8.7 GiB and takes about four minutes. It happens"
        echo "  when the image was built rootless; CI builds rootful to skip it."
        podman save "${LOCAL_REF}" | "${SUDO[@]}" podman load
    fi
else
    SUDO=()
fi
# Empty-array expansion is an unbound-variable error under `set -u` on bash 3.2,
# which is what macOS ships and which this repo targets (PRD 7.2).
"${SUDO[@]+"${SUDO[@]}"}" just vm-image "$ARCH"
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
