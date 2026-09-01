#!/usr/bin/env bash
# Boot the built disk image once and photograph the login greeter.
#
# WP-01 STOPGAP. Its acceptance asks for a "manual screenshot attached to PR"
# and says the harness arrives in WP-03. This is that one-off photograph, not a
# test framework: no assertions, no baselines, no story scripts. WP-03 owns the
# real harness (PRD 7.4) and should DELETE this file when it lands, rather than
# growing it — two half-harnesses is worse than one.
#
# It exists in CI because the x86_64 disk image cannot be built on the owner's
# Apple Silicon machine at all: bootc-image-builder runs podman inside itself and
# the nested podman fails under emulation ("failed to open 2048 locks in
# /libpod_lock"). CI runners are native, so this is the only place x86_64 can be
# booted today.
#
# It also answers the PRD 7.3 `[VERIFY /dev/kvm on hosted runners]` flag, which
# WP-03's whole plan depends on, and reports the answer either way.
set -euo pipefail

ARCH="${1:?usage: ci/boot-screenshot.sh <x86_64|aarch64>}"
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

OUT="build/evidence"
mkdir -p "$OUT"

echo "::group::[VERIFY] KVM availability on this runner (PRD 7.3)"
if [[ -e /dev/kvm ]]; then
    ls -l /dev/kvm
    if [[ ! -r /dev/kvm || ! -w /dev/kvm ]]; then
        # Hosted runners ship /dev/kvm as root:kvm and the runner user is not in
        # that group, so it is present but unusable until this is done.
        echo "  present but not accessible to $(id -un); granting access"
        sudo chmod 666 /dev/kvm || true
    fi
    if [[ -r /dev/kvm && -w /dev/kvm ]]; then
        echo "RESULT: /dev/kvm is USABLE on this runner (after 'sudo chmod 666 /dev/kvm')."
        echo "        WP-03 can plan on KVM rather than the 3x-timeout TCG fallback,"
        echo "        provided it grants access the same way."
        KVM=yes
    else
        echo "RESULT: /dev/kvm present but could NOT be made accessible."
        echo "        WP-03's TCG fallback applies."
        KVM=no
    fi
else
    echo "RESULT: /dev/kvm ABSENT. WP-03's fallback applies: TCG with 3x timeouts."
    KVM=no
fi
echo "::endgroup::"

echo "::group::build the disk image"
just vm-image "$ARCH"
echo "::endgroup::"

DISK="$(find build -name '*.qcow2' | head -1)"
[[ -n "$DISK" ]] || { echo "no qcow2 produced"; exit 1; }

# TCG boots a full Plasma desktop far slower than KVM; give it room rather than
# reporting a failure that is really a timeout.
if [[ "$KVM" == yes ]]; then SETTLE=90; ACCEL=kvm; else SETTLE=420; ACCEL=tcg; fi

echo "::group::boot ${DISK} (accel=${ACCEL}, settle=${SETTLE}s)"
case "$ARCH" in
    x86_64)
        BIN=qemu-system-x86_64
        FW=$(find /usr/share/OVMF /usr/share/edk2/ovmf -name 'OVMF_CODE*.fd' 2>/dev/null | head -1)
        MACHINE=(-M q35 -device virtio-vga)
        ;;
    aarch64)
        BIN=qemu-system-aarch64
        FW=$(find /usr/share/AAVMF /usr/share/edk2/aarch64 \
                  -name 'AAVMF_CODE*.fd' -o -name 'QEMU_EFI*.fd' 2>/dev/null | head -1)
        MACHINE=(-M virt -cpu max -device virtio-gpu-pci)
        ;;
    *) echo "unknown arch $ARCH"; exit 1 ;;
esac
[[ -n "$FW" ]] || { echo "no UEFI firmware found on the runner"; exit 1; }

rm -f "${OUT}/qmp.sock"
"$BIN" -accel "$ACCEL" -m 4096 -smp 4 -bios "$FW" "${MACHINE[@]}" \
    -drive "file=${DISK},if=virtio,format=qcow2" \
    -device virtio-net-pci,netdev=n0 -netdev user,id=n0 \
    -device qemu-xhci -device usb-kbd -device usb-tablet \
    -display none -serial "file:${OUT}/serial-${ARCH}.log" \
    -qmp "unix:${OUT}/qmp.sock,server,nowait" &
QEMU_PID=$!
trap 'kill "$QEMU_PID" 2>/dev/null || true' EXIT

python3 ci/qmp-screenshot.py "${OUT}/qmp.sock" "${OUT}/greeter-${ARCH}.ppm" "$SETTLE"
echo "::endgroup::"

echo "::group::boot health"
sed 's/\x1b\[[0-9;]*m//g' "${OUT}/serial-${ARCH}.log" > "${OUT}/serial-${ARCH}.txt"
echo "  units OK:              $(grep -cE '^\[ *OK *\] ' "${OUT}/serial-${ARCH}.txt" || true)"
echo "  systemd unit failures: $(grep -cE '^\[ *FAILED *\]' "${OUT}/serial-${ARCH}.txt" || true)"
echo "::endgroup::"

python3 -c "
from PIL import Image
import sys
src, dst = sys.argv[1], sys.argv[2]
im = Image.open(src); im.save(dst)
print(f'screenshot: {im.size[0]}x{im.size[1]} -> {dst}')
" "${OUT}/greeter-${ARCH}.ppm" "${OUT}/greeter-${ARCH}.png"
rm -f "${OUT}/greeter-${ARCH}.ppm"

echo "ci/boot-screenshot.sh: ${ARCH} booted; evidence in ${OUT}/"
