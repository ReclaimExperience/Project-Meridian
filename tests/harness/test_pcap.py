#!/usr/bin/env python3
"""Prove the pcap reader actually sees traffic (PRD WP-03).

A parser that silently returns nothing would make the ADR-011 audit pass
vacuously — an idle system that phoned home every minute would look clean. That
is the same shape as every serious defect found in WP-01, so the reader is
tested against synthetic captures with known contents rather than trusted.
"""

from __future__ import annotations

import struct
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from harness import pcap  # noqa: E402


def dns_query(name: str) -> bytes:
    labels = b"".join(bytes([len(p)]) + p.encode() for p in name.split(".")) + b"\x00"
    return struct.pack(">HHHHHH", 0x1234, 0x0100, 1, 0, 0, 0) + labels + struct.pack(">HH", 1, 1)


def udp_packet(dst: str, dport: int, payload: bytes) -> bytes:
    udp = struct.pack(">HHHH", 40000, dport, 8 + len(payload), 0) + payload
    ip = (bytes([0x45, 0, 0, 0, 0, 0, 0, 0, 64, 17, 0, 0])
          + bytes(int(o) for o in "10.0.2.15".split("."))
          + bytes(int(o) for o in dst.split(".")))
    ip = ip[:2] + struct.pack(">H", len(ip) + len(udp)) + ip[4:]
    return b"\x52\x55\x0a\x00\x02\x02" + b"\x52\x54\x00\x12\x34\x56" + b"\x08\x00" + ip + udp


def tcp_packet(dst: str, dport: int) -> bytes:
    tcp = struct.pack(">HHIIBBHHH", 40001, dport, 0, 0, 0x50, 0x02, 0, 0, 0)
    ip = (bytes([0x45, 0, 0, 0, 0, 0, 0, 0, 64, 6, 0, 0])
          + bytes(int(o) for o in "10.0.2.15".split("."))
          + bytes(int(o) for o in dst.split(".")))
    ip = ip[:2] + struct.pack(">H", len(ip) + len(tcp)) + ip[4:]
    return b"\x52\x55\x0a\x00\x02\x02" + b"\x52\x54\x00\x12\x34\x56" + b"\x08\x00" + ip + tcp


def write_pcap(path: Path, frames: list[bytes]) -> None:
    out = [struct.pack("<IHHiIII", 0xA1B2C3D4, 2, 4, 0, 0, 65535, 1)]
    for frame in frames:
        out.append(struct.pack("<IIII", 0, 0, len(frame), len(frame)) + frame)
    path.write_bytes(b"".join(out))


def main() -> int:
    failures = 0
    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / "c.pcap"

        # 1. a capture with known contents must be read back exactly
        write_pcap(path, [
            udp_packet("10.0.2.3", 53, dns_query("telemetry.example.com")),
            udp_packet("10.0.2.3", 53, dns_query("ghcr.io")),
            tcp_packet("140.82.121.5", 443),
        ])
        flows, names, _resolved = pcap.read(path)
        for expected in ("telemetry.example.com", "ghcr.io"):
            if expected not in names:
                print(f"  FAIL  did not see DNS query for {expected}: {names}")
                failures += 1
        if not any(f.destination == "140.82.121.5" and f.port == 443 for f in flows):
            print(f"  FAIL  did not see the TCP flow: {[str(f) for f in flows]}")
            failures += 1
        if not failures:
            print(f"  ok    read {len(flows)} flow(s) and {len(names)} DNS name(s)")

        # 2. an EMPTY capture must read as empty, not raise — but it must also
        #    not be how a broken parser hides.
        write_pcap(path, [])
        flows, names, _resolved = pcap.read(path)
        if flows or names:
            print(f"  FAIL  empty capture produced {flows} / {names}")
            failures += 1
        else:
            print("  ok    empty capture reads as empty")

        # 3. a non-pcap file must raise rather than silently read as clean
        path.write_bytes(b"not a pcap at all, really")
        try:
            pcap.read(path)
            print("  FAIL  garbage file was accepted as a clean capture")
            failures += 1
        except ValueError:
            print("  ok    garbage file is rejected, not read as clean")

    if failures:
        print(f"\npcap-reader: {failures} failure(s)")
        return 1
    print("\npcap-reader: sees known traffic, and cannot pass by seeing nothing")
    return 0


if __name__ == "__main__":
    sys.exit(main())
