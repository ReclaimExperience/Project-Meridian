"""Security suite: ADR-015's listening-socket rule, enforced (PRD WP-03).

ADR-015 promises "no non-loopback listening sockets after boot except the
explicit printing/discovery allowlist". That is a claim about every installed
machine, so it needs to be a test rather than an intention — this suite is the
form in which the promise can fail.

The allowlist lives in tests/security/allowed-ports.txt and is CODEOWNERS-gated:
widening it widens the attack surface of every machine, which is an owner
decision (rule R-H).
"""

from __future__ import annotations

import re

from harness.vm import ROOT, VM

ALLOWLIST = ROOT / "tests" / "security" / "allowed-ports.txt"

# Addresses that are not reachable from the network. A listener bound here is
# out of scope by design — ADR-015 explicitly permits CUPS and ipp-usb this way.
LOOPBACK = ("127.", "::1", "[::1]", "localhost")


def load_allowlist() -> dict[str, str]:
    allowed = {}
    for raw in ALLOWLIST.read_text().split("\n"):
        line = raw.split("#", 1)[0].strip()
        if not line:
            continue
        key, _, reason = line.partition(" ")
        allowed[key.strip()] = reason.strip()
    return allowed


def parse_sockets(output: str) -> list[tuple[str, str, str]]:
    """Return (proto, local_address, process) for every LISTEN/UNCONN socket."""
    sockets = []
    for line in output.split("\n"):
        fields = line.split()
        if len(fields) < 5 or fields[0] not in ("tcp", "udp"):
            continue
        proto, state, local = fields[0], fields[1], fields[4]
        # UDP sockets show UNCONN rather than LISTEN; both are bound and both
        # count. Filtering on LISTEN alone would have missed mDNS entirely.
        if state not in ("LISTEN", "UNCONN"):
            continue
        process = " ".join(fields[6:]) if len(fields) > 6 else ""
        sockets.append((proto, local, process))
    return sockets


def is_loopback(address: str) -> bool:
    host = address.rsplit(":", 1)[0]
    return host.startswith(LOOPBACK) or host in ("*%lo", "")


def run(vm: VM, credentials: dict) -> None:
    console = vm.console
    console.login(credentials["user"], credentials["password"], timeout=600)

    # Wait for the system to settle: a socket that appears 20 seconds after
    # boot is still a socket, and asserting too early would pass by luck.
    console.wait_until(
        "systemctl is-system-running || true",
        lambda out: re.search(r"running|degraded", out) is not None,
        timeout=420,
        description="systemd to finish starting",
    )

    _status, output = console.run("ss -tulpn 2>/dev/null || ss -tuln", timeout=60)
    sockets = parse_sockets(output)
    assert sockets, f"could not read any sockets — is `ss` present?\n{output}"

    allowed = load_allowlist()
    violations = []
    listed = []
    for proto, local, process in sockets:
        if is_loopback(local):
            continue
        port = local.rsplit(":", 1)[-1]
        key = f"{proto}/{port}"
        if key in allowed:
            listed.append(f"{key} on {local} ({allowed[key]})")
            continue
        violations.append(f"{key} listening on {local}   {process}")

    print(
        f"security: {len(sockets)} bound socket(s); "
        f"{len(listed)} allowlisted, {len(violations)} not"
    )
    for entry in listed:
        print(f"  allowed: {entry}")

    assert not violations, (
        "ADR-015 violation — non-loopback listeners that are not on the allowlist:\n  "
        + "\n  ".join(violations)
        + f"\n\nEither bind these to loopback, stop shipping them, or add them to\n"
        f"{ALLOWLIST.relative_to(ROOT)} with a reason — that file is owner-gated,\n"
        f"because every line in it widens the attack surface of every machine."
    )
    print("security: ADR-015 listening-socket rule holds")

    # ADR-015 also says, flatly, "no SSH daemon". A disabled unit is not the
    # same as an absent daemon: it is one `systemctl enable` — or one
    # compromised polkit rule — away from listening, and it is
    # attack surface shipped to every machine for no user-facing purpose.
    _status, sshd = console.run("command -v sshd || true", timeout=30)
    assert "sshd" not in sshd, (
        f"ADR-015 violation — an SSH daemon ships in the image: {sshd.strip()}\n"
        "  ADR-015 says 'no SSH daemon'. It is currently installed but disabled,\n"
        "  which is one `systemctl enable` away from listening and is surface\n"
        "  shipped to every machine for no user-facing purpose.\n"
        "  Remove openssh-server via os/packages.yml (WP-02)."
    )
    print("security: no SSH daemon in the image (ADR-015)")
