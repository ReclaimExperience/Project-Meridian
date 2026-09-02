"""Boot a built disk image and drive it (PRD 7.4).

One class, `VM`, owns a QEMU process and its side channels: a QMP socket for
control, a serial log for boot diagnosis, and an evidence directory that
survives the run so a failure can be read after the fact.

Design rules, each learned from something that went wrong in WP-01:

  * **Fail loudly, never silently.** Every guard prints what it looked for.
    WP-01 lost two CI cycles to `$(find ... | head -1)` aborting under
    `set -o pipefail` with no output at all.
  * **Never bake credentials into a published image.** The image under test is
    byte-identical to the one that ships; the throwaway account exists only in
    the local disk image built from it (PRD 7.4).
  * **Wait for conditions, not clocks.** PRD WP-03 forbids tests that depend on
    wall-clock timing without waits.
"""

from __future__ import annotations

import json
import os
import platform
import shutil
import signal
import subprocess
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from typing import Self

from .console import Console
from .qmp import QMP, QMPError

ROOT = Path(__file__).resolve().parents[2]

# Where UEFI firmware lives, by distro. Searched in order; the first existing
# CODE file wins and its VARS half is derived by substitution so the pair always
# matches — globbing for VARS independently can pair plain CODE with
# Microsoft-keyed VARS, and ADR-013 has Secure Boot off for 1.0.
FIRMWARE_DIRS = (
    "/usr/share/OVMF",
    "/usr/share/edk2/ovmf",
    "/usr/share/edk2/x64",
    "/usr/share/AAVMF",
    "/usr/share/edk2/aarch64",
    "/usr/share/qemu-efi-aarch64",
    "/usr/share/qemu",
)
FIRMWARE_NAMES = {
    "x86_64": ("OVMF_CODE_4M.fd", "OVMF_CODE.fd", "edk2-x86_64-code.fd"),
    "aarch64": ("AAVMF_CODE.fd", "QEMU_EFI.fd", "edk2-aarch64-code.fd"),
}


class VMError(RuntimeError):
    pass


def host_arch() -> str:
    machine = platform.machine()
    return "aarch64" if machine in ("arm64", "aarch64") else machine


def _brew_qemu_share() -> str | None:
    if not shutil.which("brew"):
        return None
    try:
        prefix = subprocess.run(
            ["brew", "--prefix", "qemu"], capture_output=True, text=True, check=True
        ).stdout.strip()
    except (subprocess.CalledProcessError, OSError):
        return None
    return f"{prefix}/share/qemu" if prefix else None


def find_firmware(arch: str) -> tuple[str, str | None]:
    """Return (code, vars_or_None) for `arch`, or raise saying where it looked."""
    dirs = list(FIRMWARE_DIRS)
    if brew := _brew_qemu_share():
        dirs.insert(0, brew)
    for name in FIRMWARE_NAMES[arch]:
        for directory in dirs:
            code = Path(directory) / name
            if code.is_file():
                # OVMF_CODE_4M.fd -> OVMF_VARS_4M.fd, edk2-x86_64-code.fd ->
                # edk2-x86_64-vars.fd. Both cases matter: a case-sensitive
                # CODE->VARS substitution silently no-ops on the lowercase edk2
                # names and returns the CODE file as if it were VARS, which
                # would attach the read-only firmware as the writable half.
                variables = None
                for old_s, new_s in (("CODE", "VARS"), ("code", "vars")):
                    candidate = Path(str(code).replace(old_s, new_s))
                    if candidate != code and candidate.is_file():
                        variables = str(candidate)
                        break
                return str(code), variables
    raise VMError(
        f"no UEFI firmware for {arch}. Looked for {FIRMWARE_NAMES[arch]} in:\n  "
        + "\n  ".join(dirs)
        + "\nInstall it: macOS 'brew install qemu'; Fedora 'edk2-ovmf'/'edk2-aarch64'; "
        "Debian/Ubuntu 'ovmf'/'qemu-efi-aarch64'."
    )


def choose_accelerator(arch: str) -> str:
    """KVM on a matching Linux host, HVF on Apple Silicon, else TCG.

    WP-01 established that hosted GitHub runners DO expose a usable /dev/kvm
    once its permissions are relaxed, so the TCG fallback is genuinely a
    fallback here rather than the normal path.
    """
    if arch != host_arch():
        return "tcg"
    if platform.system() == "Darwin":
        return "hvf"
    if os.path.exists("/dev/kvm") and os.access("/dev/kvm", os.R_OK | os.W_OK):
        return "kvm"
    return "tcg"


@dataclass
class VM:
    """A booted disk image, with control and evidence channels."""

    disk: Path
    arch: str = field(default_factory=host_arch)
    memory_mb: int = 4096
    cpus: int = 4
    capture: bool = False  # write every guest packet to a pcap (ADR-011 audit)
    evidence: Path = field(default=None)  # type: ignore[assignment]
    _process: subprocess.Popen | None = field(default=None, init=False, repr=False)
    _qmp: QMP | None = field(default=None, init=False, repr=False)
    _console: Console | None = field(default=None, init=False, repr=False)

    def __post_init__(self) -> None:
        self.disk = Path(self.disk)
        if not self.disk.is_file():
            raise VMError(f"disk image not found: {self.disk}")
        if self.evidence is None:
            self.evidence = ROOT / "build" / "evidence"
        self.evidence = Path(self.evidence)
        self.evidence.mkdir(parents=True, exist_ok=True)

    # ----------------------------------------------------------- lifecycle --

    @property
    def serial_log(self) -> Path:
        return self.evidence / f"serial-{self.arch}.log"

    @property
    def qmp_socket(self) -> Path:
        return self.evidence / f"qmp-{self.arch}.sock"

    @property
    def capture_file(self) -> Path:
        return self.evidence / f"capture-{self.arch}.pcap"

    @property
    def serial_socket(self) -> Path:
        return self.evidence / f"serial-{self.arch}.sock"

    def start(self) -> Self:
        accel = choose_accelerator(self.arch)
        code, variables = find_firmware(self.arch)

        firmware: list[str] = []
        if variables:
            # Split firmware must be attached as pflash; qemu refuses it via
            # -bios outright, and the VARS half has to be a writable per-boot
            # copy rather than the shared read-only system file.
            local_vars = self.evidence / f"vars-{self.arch}.fd"
            shutil.copy(variables, local_vars)
            local_vars.chmod(0o644)
            firmware = [
                "-drive",
                f"if=pflash,format=raw,unit=0,readonly=on,file={code}",
                "-drive",
                f"if=pflash,format=raw,unit=1,file={local_vars}",
            ]
        else:
            firmware = ["-bios", code]

        if self.arch == "aarch64":
            machine = [
                "-M",
                "virt",
                "-cpu",
                "host" if accel == "hvf" else "max",
                "-device",
                "virtio-gpu-pci",
            ]
        else:
            machine = ["-M", "q35", "-device", "virtio-vga"]

        self.qmp_socket.unlink(missing_ok=True)
        self.serial_socket.unlink(missing_ok=True)
        self.serial_log.unlink(missing_ok=True)
        if self.capture:
            self.capture_file.unlink(missing_ok=True)

        command = [
            f"qemu-system-{self.arch}",
            "-accel",
            accel,
            "-m",
            str(self.memory_mb),
            "-smp",
            str(self.cpus),
            *firmware,
            *machine,
            "-drive",
            f"file={self.disk},if=virtio,format=qcow2",
            "-device",
            "virtio-net-pci,netdev=n0",
            "-netdev",
            "user,id=n0",
            "-device",
            "virtio-rng-pci",
            *(
                # qemu mirrors every frame the guest sends or receives. Capturing
                # on the host means the guest needs no tcpdump, no capabilities
                # and no awareness it is being watched — so the ADR-011 audit
                # measures the shipping image, not a special build of it.
                ["-object", f"filter-dump,id=dump0,netdev=n0,file={self.capture_file}"]
                if self.capture
                else []
            ),
            "-device",
            "qemu-xhci",
            "-device",
            "usb-kbd",
            "-device",
            "usb-tablet",
            "-display",
            "none",
            "-serial",
            f"unix:{self.serial_socket},server,nowait",
            "-qmp",
            f"unix:{self.qmp_socket},server,nowait",
        ]
        print(f"vm: booting {self.disk.name} arch={self.arch} accel={accel}")
        self._process = subprocess.Popen(
            command, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE, text=True
        )
        try:
            self._qmp = QMP(self.qmp_socket)
            self._console = Console(self.serial_socket, self.serial_log)
        except (QMPError, VMError) as exc:
            raise VMError(f"{exc}\n{self._qemu_stderr()}") from exc
        return self

    def _qemu_stderr(self) -> str:
        if self._process is None or self._process.stderr is None:
            return ""
        if self._process.poll() is None:
            return "(qemu still running; no stderr collected)"
        return "qemu said:\n  " + (self._process.stderr.read() or "").strip().replace(
            "\n", "\n  "
        )

    @property
    def console(self) -> Console:
        if self._console is None:
            raise VMError("VM is not started")
        return self._console

    def stop(self) -> None:
        if self._console is not None:
            self._console.close()
            self._console = None
        if self._qmp is not None:
            self._qmp.close()
            self._qmp = None
        if self._process is not None and self._process.poll() is None:
            self._process.send_signal(signal.SIGTERM)
            try:
                self._process.wait(timeout=15)
            except subprocess.TimeoutExpired:
                self._process.kill()
        self._process = None
        self.qmp_socket.unlink(missing_ok=True)
        self.serial_socket.unlink(missing_ok=True)

    def __enter__(self) -> Self:
        return self.start()

    def __exit__(self, *_exc) -> None:
        self.stop()

    # -------------------------------------------------------------- control --

    @property
    def qmp(self) -> QMP:
        if self._qmp is None:
            raise VMError("VM is not started")
        return self._qmp

    def screenshot(self, name: str) -> Path:
        ppm = self.evidence / f"{name}.ppm"
        self.qmp.screendump(ppm)
        try:
            from PIL import Image

            png = ppm.with_suffix(".png")
            Image.open(ppm).save(png)
            ppm.unlink(missing_ok=True)
            return png
        except ImportError:
            return ppm

    # --------------------------------------------------------------- serial --

    def serial_text(self) -> str:
        """Boot log with ANSI colour stripped, for grepping and for evidence."""
        # The LOG, not the live transcript. Console.run() clears its buffer on
        # every command, so the transcript holds only the last command by the
        # time a report is written — which made every evidence file record
        # "units_ok: 0, failed_units: []", a no-failures record that could not
        # have recorded a failure.
        if self.serial_log.exists():
            raw = self.serial_log.read_text(errors="replace")
        elif self._console is not None:
            raw = self._console.transcript()
        else:
            return ""
        import re

        return re.sub(r"\x1b\[[0-9;]*m", "", raw)

    def failed_units(self) -> list[str]:
        """Lines systemd printed as [FAILED].

        Deliberately not a count of the word 'failed': UEFI firmware prints
        'Image at ... start failed' before Linux even starts, and WP-01 briefly
        reported five firmware messages as if they were unit failures.
        """
        return [
            line.strip()
            for line in self.serial_text().split("\n")
            if line.startswith("[FAILED]") or " [FAILED] " in line
        ]

    def units_ok(self) -> int:
        return sum(
            1 for line in self.serial_text().split("\n") if line.startswith("[  OK  ]")
        )

    # ----------------------------------------------------------------- wait --

    def wait_for_serial(
        self, pattern: str, timeout: float = 300.0, poll: float = 2.0
    ) -> bool:
        """Wait until `pattern` appears in the boot log.

        This is the harness's only sanctioned way to wait for the guest to reach
        a state: PRD WP-03 forbids tests that sleep on a wall clock instead.
        """
        import re

        compiled = re.compile(pattern)
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            if self._process is not None and self._process.poll() is not None:
                raise VMError(
                    f"qemu exited while waiting for {pattern!r}\n{self._qemu_stderr()}"
                )
            if compiled.search(self.serial_text()):
                return True
            time.sleep(poll)
        return False

    # ------------------------------------------------------------- evidence --

    def write_report(self, name: str, extra: dict | None = None) -> Path:
        report = {
            "disk": str(self.disk),
            "arch": self.arch,
            "accelerator": choose_accelerator(self.arch),
            "units_ok": self.units_ok(),
            "failed_units": self.failed_units(),
            **(extra or {}),
        }
        path = self.evidence / f"{name}.json"
        path.write_text(json.dumps(report, indent=2) + "\n")
        return path
