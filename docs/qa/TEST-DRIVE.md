# Test-driving Meridian by hand

Three ways to put hands on the OS, what each one can and cannot tell you, and
the exact commands. They answer different questions — picking the wrong one
gives a confident answer to a question you were not asking.

| Path | Answers | Cannot answer |
|---|---|---|
| 1. aarch64 in UTM on Apple Silicon | Does it *feel* right? Responsiveness, clicking through the desktop | Whether the shipping x86_64 bits work; anything about real hardware |
| 2. x86_64 qcow2 under emulation on a Mac | Do the exact shipping bits work? | Anything about speed — emulation is 10–50× slower |
| 3. x86_64 on a spare PC from USB | Does real hardware work — Wi-Fi, GPU, battery, drivers | Nothing about the installer; this is a one-off boot |

**A VM only ever shows you virtio devices.** Path 3 is the only one that tests
the "hardware just works" pillar, because paths 1 and 2 substitute an idealised
virtual device for every real one.

## Credentials, for all three paths

Every disk image gets a **randomly generated password** for a local `mtest`
account, created by `just vm-image`. It exists in the disk image alone —
`ci/check-no-test-user.sh` independently proves the account is absent from every
published container image.

* **Local build:** `build/dev-credentials.json`, written beside the image.
* **CI image:** the password is echoed into the workflow log by the `vm-image`
  step — search the run's log for `dev login: mtest /`.

Treat it as what it is: a throwaway credential on a test image. Do not reuse it,
and see the warning in path 3 about putting such an image on real hardware.

## Path 1 — aarch64 in UTM on Apple Silicon (the fluid one)

Native virtualisation through HVF, so the desktop responds at roughly real
speed. This is the path for judging feel: menus, window dragging, Files,
Settings, triggering an update.

### Getting an aarch64 qcow2

Two sources.

**From CI** (no local privilege needed) — the nightly publishes
`meridian-qcow2-aarch64` alongside the x86_64 one:

```bash
gh run download <run-id> -n meridian-qcow2-aarch64 -D ~/meridian-image
```

**Or build locally.** `bootc-image-builder` refuses to run rootless, so the
podman machine must be rootful — and rootful storage is separate, so the image
has to be rebuilt into it:

```bash
podman machine stop && podman machine set --rootful && podman machine start
just build aarch64        # rebuild into rootful storage
just vm-image aarch64     # produces build/qcow2/disk.qcow2 + dev-credentials.json
```

### Running it

The repo's own runner picks HVF automatically on Apple Silicon:

```bash
just vm-run aarch64 gui
```

For UTM specifically: **New → Virtualize → Linux**, uncheck "Boot from kernel
image", set the qcow2 as the drive, 4 GB RAM / 4 CPUs, and leave display on
`virtio-gpu-pci`. UTM must be in *Virtualize* mode, not *Emulate* — emulating
aarch64 on an aarch64 host throws away the entire point.

### What to look at

Responsiveness of the Start menu and window dragging; Files opening and
browsing; Settings pages; triggering an update from Settings → Updates. If
something feels slow here, it is genuinely slow — this path does not add
overhead worth blaming.

## Path 2 — the exact x86_64 bits, emulated on a Mac

This boots **literally what ships**. It is slow — TCG emulation across
architectures — so it answers "does it work", never "is it fast".

```bash
gh run download <run-id> -n meridian-qcow2-x86_64 -D ~/meridian-image
cd ~/meridian-image && unzip -o meridian-qcow2-x86_64.zip

qemu-system-x86_64 \
  -m 4096 -smp 4 \
  -drive file=disk.qcow2,if=virtio,format=qcow2 \
  -bios "$(brew --prefix qemu)/share/qemu/edk2-x86_64-code.fd" \
  -device virtio-vga -display default,show-cursor=on \
  -device virtio-net-pci,netdev=n0 -netdev user,id=n0 \
  -device qemu-xhci -device usb-kbd -device usb-tablet
```

Expect the greeter to take **minutes** rather than the ~10s it takes with
hardware acceleration. Judge correctness only: does the desktop come up, do apps
launch, does an update apply.

## Path 3 — real hardware, from a USB stick

The only path that tests the pillar the whole product rests on. Everything
above shows you virtio devices; this shows you a real Wi-Fi chipset, a real GPU,
a real battery.

**This is a one-off boot of a disk image, not an installation.** There is no
installer yet (WP-17), so this is crude: real bits on real metal, now.

### Read this before running `dd`

* **`dd` to the wrong device destroys that disk, immediately and silently.**
  Check the device name twice. On macOS use `diskutil list` and note that the
  raw device is `/dev/rdiskN`, not `/dev/diskN`.
* The image carries a **test account with a known password** (see above). Do not
  leave the machine on a network you care about, and wipe the stick afterwards.
  The image ships no SSH daemon (ADR-015), so the exposure is local, not remote.
* **Secure Boot must be disabled** in firmware — 1.0 ships unsigned
  (PRD 10.4). The machine will refuse to boot otherwise.
* Target a **spare** machine or an external SSD. Not your daily driver.

### Convert and write

```bash
# qcow2 -> raw. Needs ~20 GB free; the raw file is the disk's full virtual size.
qemu-img convert -f qcow2 -O raw disk.qcow2 meridian.img

# macOS: find the stick, unmount it (do NOT eject), write to the RAW device.
diskutil list
diskutil unmountDisk /dev/diskN
sudo dd if=meridian.img of=/dev/rdiskN bs=4m status=progress
sync
```

On Linux the equivalent target is `/dev/sdX` (the whole device, not a
partition), with `sudo dd if=meridian.img of=/dev/sdX bs=4M status=progress
conv=fsync`.

### Boot it

Firmware boot menu (usually F12 / F2 / Esc), select the USB device, and pick
**UEFI**, not legacy/CSM — the image is UEFI-only.

### What to check, in the order that matters

1. **Does it reach the greeter at all**, and how long did that take? Time it —
   that number fills the empty `Boot→greeter` column in PRD §10.2, and it is
   what the greenboot health-check ceiling should be derived from
   (slowest observed × 2). Today that ceiling is a provisional 300s because no
   real-hardware number exists.
2. **Wi-Fi**: does the adapter appear, can it see networks, does it connect?
3. **Graphics**: correct resolution, no tearing, external display if you have
   one.
4. **Battery** (laptops): does the level report, does it change on unplug?
5. **Sound**, **trackpad/gestures**, **webcam**, **suspend/resume**.
6. Anything that needs a proprietary blob — the trouble-hardware seat in §10.2
   exists for exactly this.

Log what fails per machine against the §10.2 matrix row. A failure here is worth
more than a hundred green VM runs, because the VM cannot fail this way at all.

## What none of these do

* **No installer.** WP-17 has not landed; nothing here writes to an internal
  disk or sets up a real user account.
* **No signature verification of the image you booted.** These are development
  artifacts, not `:stable` releases.
* **The x86_64 CI image is the tested one.** The aarch64 image is built by the
  same recipe but is exercised by far fewer automated suites — treat surprises
  there as plausibly arch-specific rather than product-wide.
