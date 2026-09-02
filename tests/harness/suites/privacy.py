"""Privacy suite: ADR-011's zero-telemetry claim, enforced (PRD WP-03).

ADR-011 lists every automatic outbound connection a fresh install is allowed to
make, and says the claim must be "literally, auditably true". This is the audit:
boot an idle system, capture every packet from OUTSIDE the guest, and fail on
any destination the ADR does not permit.

Capturing on the host matters. The guest needs no tcpdump, no capabilities and
no awareness it is being watched, so what is measured is the image that ships
rather than a special build of it — which is the difference between an audit and
a self-report.

The idle period is 10 minutes per ADR-011. Shorten it locally with --idle while
iterating, but the gate is the full duration: a daily check-in would be missed
by a two-minute sample, and a daily check-in is exactly what this exists to
catch.
"""

from __future__ import annotations

import ipaddress
import os
import time

from harness import pcap
from harness.vm import ROOT, VM

ALLOWLIST = ROOT / "tests" / "privacy" / "allowed-destinations.txt"
DEFAULT_IDLE_SECONDS = 600


def load_allowlist() -> dict[str, str]:
    allowed = {}
    for raw in ALLOWLIST.read_text().split("\n"):
        line = raw.split("#", 1)[0].strip()
        if not line:
            continue
        suffix, _, reason = line.partition(" ")
        allowed[suffix.strip().lower()] = reason.strip()
    return allowed


def is_local(address: str) -> bool:
    """Addresses that cannot leave the local network.

    Out of scope for ADR-011: private ranges, loopback, link-local, multicast
    (mDNS, SSDP) and broadcast (DHCP). None of them is a "destination contacted"
    in the sense the ADR means — they cannot reach anyone outside the room.
    """
    try:
        ip = ipaddress.ip_address(address)
    except ValueError:
        return False
    return (
        ip.is_private
        or ip.is_loopback
        or ip.is_link_local
        or ip.is_multicast
        or ip.is_reserved
        or ip.is_unspecified
    )


def is_reverse_lookup(name: str) -> bool:
    """PTR queries resolve an address to a name — the opposite direction.

    A reverse lookup contacts no new destination: it goes to the resolver the
    system already uses. Anything it reveals about actual contact shows up in
    the flow check, which is the stricter test.
    """
    lowered = name.lower().rstrip(".")
    return lowered.endswith((".in-addr.arpa", ".ip6.arpa"))


def permitted(name: str, allowed: dict[str, str]) -> str | None:
    name = name.lower().rstrip(".")
    for suffix, reason in allowed.items():
        if name == suffix or name.endswith("." + suffix):
            return reason
    return None


def run(vm: VM, credentials: dict) -> None:
    if not vm.capture:
        raise AssertionError(
            "the privacy suite needs packet capture; run it via `just vm-test privacy`"
        )

    idle = int(os.environ.get("MERIDIAN_IDLE_SECONDS", DEFAULT_IDLE_SECONDS))
    console = vm.console
    console.login(credentials["user"], credentials["password"], timeout=600)

    # Let the system finish starting BEFORE the idle window opens. Boot-time
    # traffic is in scope, but a system still starting services is not "idle",
    # and timing the window from boot would make the result depend on how slow
    # the host is.
    console.wait_until(
        "systemctl is-system-running || true",
        lambda out: "running" in out or "degraded" in out,
        timeout=420,
        description="systemd to finish starting",
    )
    print(f"privacy: system settled; watching an idle system for {idle}s")

    started = time.monotonic()
    while time.monotonic() - started < idle:
        remaining = idle - (time.monotonic() - started)
        time.sleep(min(60, remaining))
        elapsed = int(time.monotonic() - started)
        if elapsed % 120 < 60:
            print(f"privacy:   {elapsed}s / {idle}s")

    # Read the capture only after the window closes: qemu flushes as it goes,
    # and parsing mid-flight would race the writer for the final frames.
    if not vm.capture_file.is_file():
        raise AssertionError(
            f"no capture at {vm.capture_file} — the audit did not observe anything, "
            f"so it cannot report a clean result."
        )

    flows, names, resolved = pcap.read(vm.capture_file)
    allowed = load_allowlist()

    # POSITIVE CONTROL. qemu writes the 24-byte pcap header the moment it opens
    # the file, so an unattached filter-dump, a NIC that never came up, or a
    # future second netdev all yield a VALID, EMPTY capture — and an audit that
    # sees nothing would otherwise print "ADR-011 holds". The one place this
    # check is structurally blind is the one place it must not fail open.
    #
    # A booted, networked guest always produces DHCP and DNS. If neither is
    # here, the capture is not working; that is a broken audit, not a clean run.
    control = [f for f in flows if f.port in (53, 67, 68)]
    assert control, (
        f"the capture contains {len(flows)} flow(s) and no DHCP or DNS at all, so "
        f"the audit is not observing this guest's traffic.\n"
        f"  A green result here would mean 'saw nothing', not 'nothing happened'.\n"
        f"  Check that filter-dump is attached to the NIC the guest actually uses.\n"
        f"  Capture: {vm.capture_file} ({vm.capture_file.stat().st_size} bytes)"
    )

    print(
        f"privacy: {len(flows)} flow(s), {len(names)} DNS name(s), "
        f"{len(resolved)} address(es) attributed to a name "
        f"[capture live: {len(control)} DHCP/DNS flow(s)]"
    )

    violations, accepted = [], []

    # 1. Names the system asked for.
    for name in sorted(names):
        if is_reverse_lookup(name):
            continue
        reason = permitted(name, allowed)
        if reason:
            accepted.append(f"queried {name}  ({reason})")
        else:
            violations.append(f"queried {name}  — not on the ADR-011 list")

    # 2. Where traffic ACTUALLY went. The stricter half: ADR-011's claim is
    #    about connections, and a system could contact a hard-coded address
    #    without ever asking DNS about it. Everything that left the local
    #    network must trace back to a permitted name.
    for flow in sorted(flows, key=str):
        if is_local(flow.destination):
            continue
        name = resolved.get(flow.destination)
        if name is None:
            violations.append(
                f"contacted {flow} with no DNS name behind it — a hard-coded "
                f"address is exactly what a check-in looks like"
            )
            continue
        reason = permitted(name, allowed)
        if reason:
            accepted.append(f"contacted {flow} = {name}  ({reason})")
        else:
            violations.append(f"contacted {flow} = {name}  — not on the ADR-011 list")

    for entry in sorted(set(accepted)):
        print(f"  permitted: {entry}")

    assert not violations, (
        "ADR-011 violation — an idle system contacted destinations the ADR does "
        "not permit:\n  "
        + "\n  ".join(sorted(set(violations)))
        + f"\n\nADR-011 says the complete list of automatic outbound connections is "
        f"update\nchecks, fwupd metadata, NTP, OOBE geoip and captive-portal "
        f"detection. Either\nstop the traffic or amend {ALLOWLIST.relative_to(ROOT)} — "
        f"that file is owner-gated,\nbecause every line means a fresh install talks "
        f"somewhere new.\n\nFull capture: {vm.capture_file}"
    )
    vm.write_report(
        "privacy-audit",
        {
            "idle_seconds_measured": idle,
            "idle_seconds_gate": DEFAULT_IDLE_SECONDS,
            "at_gate_duration": idle >= DEFAULT_IDLE_SECONDS,
            "flows": len(flows),
            "public_flows": len([f for f in flows if not is_local(f.destination)]),
            "dns_names": sorted(names),
            "permitted": sorted(set(accepted)),
        },
    )
    if idle < DEFAULT_IDLE_SECONDS:
        print(
            f"privacy: ADR-011 holds over a {idle}s window — but the GATE is "
            f"{DEFAULT_IDLE_SECONDS}s, and this run does not meet it. A daily "
            f"check-in is invisible to a short sample."
        )
    else:
        print(
            f"privacy: ADR-011 holds over the full {idle}s gate window — no "
            f"unpermitted destination"
        )
