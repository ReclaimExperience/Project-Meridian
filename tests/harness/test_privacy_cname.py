#!/usr/bin/env python3
"""A permitted lookup answered through a CDN must be judged by the name asked.

The ADR-011 audit failed on eight nightly runs out of ten with:

    contacted tcp/151.101.201.91:443 = dualstack.n.sni.global.fastly.net
      — not on the ADR-011 list

The capture showed what the guest actually did:

    A? dl.flathub.org.
    dl.flathub.org. CNAME dualstack.n.sni.global.fastly.net.,
    dualstack.n.sni.global.fastly.net. A 151.101.201.91

`dl.flathub.org` is permitted (Flatpak update checks, ADR-004). The parser maps
an answered IP to its record's owner, which after a CNAME is the CDN hostname,
and the audit judged THAT. The CNAME link back to the question was recorded and
never walked.

Two things are pinned here, because either failure is serious:

  * a permitted name behind a CDN is permitted — or the audit is red on a system
    doing exactly what ADR-011 allows, and a red that means nothing teaches
    people to ignore it;
  * a name the guest asked for that is NOT permitted stays a violation even when
    it CNAMEs to something that sounds harmless — walking the chain must never
    become a way to launder a destination.
"""

from __future__ import annotations

import struct
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from harness import pcap
from harness.suites.privacy import asked_for, load_allowlist, permitted


def encode(name: str) -> bytes:
    return b"".join(bytes([len(p)]) + p.encode() for p in name.split(".")) + b"\x00"


def response(question: str, chain: list[str], address: str) -> bytes:
    """A DNS response: question, then CNAME hops, then the final A record."""
    answers = b""
    owner = question
    for target in chain:
        rdata = encode(target)
        answers += encode(owner) + struct.pack(">HHIH", 5, 1, 60, len(rdata)) + rdata
        owner = target
    ip = bytes(int(o) for o in address.split("."))
    answers += encode(owner) + struct.pack(">HHIH", 1, 1, 60, 4) + ip
    header = struct.pack(">HHHHHH", 0x1234, 0x8180, 1, len(chain) + 1, 0, 0)
    return header + encode(question) + struct.pack(">HH", 1, 1) + answers


def main() -> int:
    failures = 0
    allowed = load_allowlist()

    # 1. The real nightly case: permitted name, answered through a CDN.
    names, resolved = pcap._dns_message(
        response(
            "dl.flathub.org", ["dualstack.n.sni.global.fastly.net"], "151.101.201.91"
        )
    )
    head = asked_for("151.101.201.91", resolved)
    if head != "dl.flathub.org":
        print(f"FAIL: CDN-hosted permitted lookup attributed to {head!r}")
        failures += 1
    elif not permitted(head, allowed):
        print("FAIL: dl.flathub.org is not permitted by the allowlist")
        failures += 1

    # 2. Laundering: an unpermitted name that CNAMEs to a permitted zone must
    #    still be judged by the name the guest asked for.
    names, resolved = pcap._dns_message(
        response("telemetry.example.com", ["mirror.flathub.org"], "203.0.113.9")
    )
    head = asked_for("203.0.113.9", resolved)
    if head != "telemetry.example.com":
        print(f"FAIL: chain head should be the question, got {head!r}")
        failures += 1
    elif permitted(head, allowed):
        print(
            "FAIL: an unpermitted name was accepted by CNAMEing into a permitted zone"
        )
        failures += 1

    # 3. No CNAME at all: unchanged behaviour.
    names, resolved = pcap._dns_message(response("fwupd.org", [], "198.51.100.4"))
    if asked_for("198.51.100.4", resolved) != "fwupd.org":
        print("FAIL: a plain A record no longer attributes to its own name")
        failures += 1

    # 4. Multi-hop chains walk all the way back.
    names, resolved = pcap._dns_message(
        response("dl.flathub.org", ["a.cdn.example", "b.edge.example"], "192.0.2.7")
    )
    if asked_for("192.0.2.7", resolved) != "dl.flathub.org":
        print("FAIL: a two-hop CNAME chain did not walk back to the question")
        failures += 1

    # 5. An address nobody resolved stays unattributed, so the audit's
    #    hard-coded-address check still fires.
    if asked_for("192.0.2.200", resolved) is not None:
        print("FAIL: an unresolved address was given a name")
        failures += 1

    if failures:
        print(f"privacy-cname: {failures} failure(s)")
        return 1
    print(
        "privacy-cname: CDN-hosted permitted lookups pass, CNAME laundering "
        "is still caught, multi-hop chains walk back, unresolved stays unnamed"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
