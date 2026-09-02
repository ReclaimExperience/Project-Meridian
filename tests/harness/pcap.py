"""Minimal pcap reader for the ADR-011 network audit (PRD WP-03).

Only what the privacy audit needs: which hosts the guest talked to, and which
names it asked DNS about. Deliberately dependency-free — the audit that proves
"zero telemetry" should not itself rest on a third-party parser nobody reads.

Everything here is read-only over bytes qemu wrote. It never runs in the guest,
so the image under audit is the image that ships (see VM.capture).
"""

from __future__ import annotations

import struct
from dataclasses import dataclass
from pathlib import Path

PCAP_MAGIC_LE = 0xA1B2C3D4
PCAP_MAGIC_BE = 0xD4C3B2A1
LINKTYPE_ETHERNET = 1


@dataclass(frozen=True)
class Flow:
    protocol: str  # "tcp" | "udp"
    destination: str  # dotted IPv4 or colon IPv6
    port: int

    def __str__(self) -> str:
        return f"{self.protocol}/{self.destination}:{self.port}"


def _ipv6(raw: bytes) -> str:
    parts = [f"{raw[i] << 8 | raw[i + 1]:x}" for i in range(0, 16, 2)]
    return ":".join(parts)


def _read_name(payload: bytes, offset: int) -> tuple[str, int]:
    """Decode a DNS name, following compression pointers.

    Answers almost always compress the owner name into a pointer back to the
    question, so a parser that cannot follow pointers reads answers as garbage —
    and would then attribute no IP to any name, quietly making the audit blind.
    """
    labels: list[str] = []
    jumped = False
    end_offset = offset
    hops = 0
    while offset < len(payload) and hops < 32:
        length = payload[offset]
        if length == 0:
            offset += 1
            if not jumped:
                end_offset = offset
            break
        if length & 0xC0 == 0xC0:
            if offset + 1 >= len(payload):
                break
            pointer = ((length & 0x3F) << 8) | payload[offset + 1]
            if not jumped:
                end_offset = offset + 2
            offset = pointer
            jumped = True
            hops += 1
            continue
        offset += 1
        labels.append(payload[offset : offset + length].decode("ascii", "replace"))
        offset += length
        if not jumped:
            end_offset = offset
    return ".".join(labels), end_offset


def _dns_message(payload: bytes) -> tuple[list[str], dict[str, str]]:
    """Return (question names, {resolved_ip: name}) from a DNS message.

    The answers matter as much as the questions: ADR-011's claim is about the
    connections a system makes, and a bare destination IP in a capture means
    nothing until it can be traced back to the name that produced it.
    """
    if len(payload) < 12:
        return [], {}
    question_count, answer_count = struct.unpack_from(">HH", payload, 4)

    names: list[str] = []
    offset = 12
    for _ in range(min(question_count, 8)):
        name, offset = _read_name(payload, offset)
        offset += 4  # qtype + qclass
        if name:
            names.append(name)

    resolved: dict[str, str] = {}
    for _ in range(min(answer_count, 32)):
        if offset + 10 > len(payload):
            break
        owner, offset = _read_name(payload, offset)
        rtype, _rclass, _ttl, rdlength = struct.unpack_from(">HHIH", payload, offset)
        offset += 10
        rdata = payload[offset : offset + rdlength]
        offset += rdlength
        if rtype == 1 and len(rdata) == 4:  # A
            resolved[".".join(str(b) for b in rdata)] = owner
        elif rtype == 28 and len(rdata) == 16:  # AAAA
            resolved[_ipv6(rdata)] = owner
        elif rtype == 5:  # CNAME — keep the chain
            target, _ = _read_name(rdata, 0)
            if target:
                resolved.setdefault(target, owner)
    return names, resolved


def read(path: str | Path) -> tuple[list[Flow], list[str], dict[str, str]]:
    """Return (outbound flows, DNS names queried, {resolved_ip: name})."""
    data = Path(path).read_bytes()
    if len(data) < 24:
        return [], []

    magic = struct.unpack_from("<I", data, 0)[0]
    if magic == PCAP_MAGIC_LE:
        endian = "<"
    elif magic == PCAP_MAGIC_BE:
        endian = ">"
    else:
        raise ValueError(f"{path} is not a pcap file (magic {magic:#x})")

    linktype = struct.unpack_from(f"{endian}I", data, 20)[0]
    if linktype != LINKTYPE_ETHERNET:
        raise ValueError(f"unexpected pcap linktype {linktype}, expected Ethernet")

    flows: dict[Flow, None] = {}
    names: dict[str, None] = {}
    resolved: dict[str, str] = {}
    offset = 24
    while offset + 16 <= len(data):
        _ts, _us, captured, _original = struct.unpack_from(
            f"{endian}IIII", data, offset
        )
        offset += 16
        frame = data[offset : offset + captured]
        offset += captured
        if len(frame) < 14:
            continue

        ethertype = struct.unpack_from(">H", frame, 12)[0]
        if ethertype == 0x0800 and len(frame) >= 34:  # IPv4
            ihl = (frame[14] & 0x0F) * 4
            protocol_number = frame[23]
            destination = ".".join(str(b) for b in frame[30:34])
            transport = frame[14 + ihl :]
        elif ethertype == 0x86DD and len(frame) >= 54:  # IPv6
            protocol_number = frame[20]
            destination = _ipv6(frame[38:54])
            transport = frame[54:]
        else:
            continue

        if protocol_number == 6:
            protocol = "tcp"
        elif protocol_number == 17:
            protocol = "udp"
        else:
            continue
        if len(transport) < 4:
            continue

        port = struct.unpack_from(">H", transport, 2)[0]
        flows[Flow(protocol, destination, port)] = None

        # DNS questions tell us the NAME the guest wanted, which is what an
        # allowlist can be written against; a bare IP tells us almost nothing.
        # Watch BOTH directions of port 53: the question is in the outbound
        # packet and the answer in the inbound one, and the answer is what maps
        # a destination IP back to a name.
        source_port = struct.unpack_from(">H", transport, 0)[0]
        if protocol == "udp" and 53 in (port, source_port) and len(transport) > 8:
            message_names, message_resolved = _dns_message(transport[8:])
            for name in message_names:
                names[name] = None
            resolved.update(message_resolved)

    return list(flows), list(names), resolved
