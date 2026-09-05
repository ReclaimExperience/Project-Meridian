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

# And say so EXPLICITLY, in a file whose path we pass to podman directly.
#
# Relying on root resolving its own config was wrong three times. Measured on
# the runner: with HOME=/root, no /etc/containers/storage.conf and no
# /root/.config/containers/storage.conf, `sudo podman info` still reported
# graphroot=/mnt/containers/storage — the rootless value — so root was reading
# the invoking user's config by some path that is not worth reverse-engineering.
# CONTAINERS_STORAGE_CONF leaves nothing to resolve.
sudo mkdir -p /etc/containers
sudo tee /etc/containers/storage-root.conf >/dev/null <<CONF
[storage]
# The driver line stays. Runs 33947223804 and 33949149449 both built the qcow2
# successfully WITH it — those are the only two successful disk builds this
# project has ever had. It was removed after a single failure
# (database graph driver "" does not match our graph driver "overlay"), and
# removing it brought back the original static-dir mismatch, which is worse and
# is the failure this whole config exists to prevent.
#
# The driver-mismatch run is unexplained and recorded as such: it most likely
# hit a store that had never been initialised, since the preceding job step had
# already failed. That is a hypothesis, not a finding. Do not remove this line
# again without evidence stronger than one red run.
driver = "overlay"
graphroot = "/var/lib/containers/storage"
runroot = "/run/containers/storage"
CONF
echo "root store config: /etc/containers/storage-root.conf -> /var/lib/containers/storage"

echo "after:"
df -h / /mnt 2>/dev/null | sed 's/^/  /'
echo "podman graphroot: $(podman info --format '{{ .Store.GraphRoot }}')"
