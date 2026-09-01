#!/usr/bin/env bash
# Make a GitHub-hosted runner able to hold an OS image (PRD 7.3).
#
# Hosted runners give ~14 GB free on / but mount a much larger ephemeral volume
# at /mnt. Our x86_64 base (ublue kinoite-main, which carries the full driver and
# codec stack per ADR-002) does not fit in the former: the first CI run died with
#
#   unable to copy from source docker://ghcr.io/ublue-os/kinoite-main:44:
#   write /usr/lib64/libgallium-26.1.4.so: no space left on device
#
# So: reclaim the obvious dead weight, then move container storage to /mnt.
# aarch64 happens to fit today because the Fedora Kinoite dev base is smaller —
# that is luck, not headroom, so this runs for both arches.
set -euo pipefail

echo "before:"
df -h / /mnt 2>/dev/null | sed 's/^/  /'

# Preinstalled toolchains this project never uses. Failure to remove any one of
# them is not fatal — they are a bonus, not the mechanism.
for dir in /usr/share/dotnet /usr/local/lib/android /opt/ghc \
           /usr/local/share/boost /opt/hostedtoolcache/CodeQL; do
    if [[ -e "$dir" ]]; then
        sudo rm -rf "$dir" || echo "  (could not remove $dir — continuing)"
    fi
done

# The real fix: put the container store on the big volume. podman runs rootless
# on the runner, so this is the per-user config, not /etc/containers.
STORAGE_ROOT=/mnt/containers
sudo mkdir -p "${STORAGE_ROOT}/storage"
sudo chown -R "$(id -u):$(id -g)" "$STORAGE_ROOT"

mkdir -p "${HOME}/.config/containers"
cat > "${HOME}/.config/containers/storage.conf" <<CONF
[storage]
driver = "overlay"
graphroot = "${STORAGE_ROOT}/storage"
runroot = "/run/user/$(id -u)/containers"
CONF

# bootc-image-builder refuses to run rootless, so the ROOT store needs space
# too — and root's default graphroot is on /, which cannot hold an OS image.
#
# Do this with a BIND MOUNT rather than by relocating graphroot in
# storage.conf. bootc-image-builder bind-mounts the host store into itself at
# /var/lib/containers/storage, and the nested podman then compares that path
# against the one recorded in the store's own database:
#
#   database static dir "/mnt/containers/storage-root/libpod" does not match
#   our static dir "/var/lib/containers/storage/libpod"
#
# Keeping the canonical path and moving only the bytes underneath it avoids the
# mismatch entirely.
sudo mkdir -p "${STORAGE_ROOT}/storage-root" /var/lib/containers/storage
sudo mount --bind "${STORAGE_ROOT}/storage-root" /var/lib/containers/storage

echo "after:"
df -h / /mnt 2>/dev/null | sed 's/^/  /'
echo "podman graphroot: $(podman info --format '{{ .Store.GraphRoot }}')"
