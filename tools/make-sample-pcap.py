#!/usr/bin/env python3
"""Write examples/harbour-buoys.pcap: two simulated harbour buoys reporting.

    tools/make-sample-pcap.py examples/harbour-buoys.pcap

Buoy 7 sends from 198.51.100.10 and buoy 3 from 198.51.100.11, each three
rounds of Status, Sea State and Position to 198.51.100.20:47200: 18 UDP
datagrams in Ethernet and IPv4 frames, one second apart. The payloads come
from tools/buoy.py, which packs them from the interface document with
`struct`. The file is the same every time it is written. Standard library only.
"""
import struct
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import buoy  # noqa: E402

SHORE = bytes([198, 51, 100, 20])
BUOYS = ((7, bytes([198, 51, 100, 10])), (3, bytes([198, 51, 100, 11])))
PORT = 47200
FIRST_SECOND = 1_750_000_000


def checksum(data: bytes) -> int:
    if len(data) % 2:
        data += b"\0"
    total = sum(struct.unpack(f">{len(data) // 2}H", data))
    while total >> 16:
        total = (total & 0xFFFF) + (total >> 16)
    return ~total & 0xFFFF


def frame(source: bytes, payload: bytes) -> bytes:
    length = 8 + len(payload)
    pseudo = source + SHORE + struct.pack(">BBH", 0, 17, length)
    udp = struct.pack(">HHHH", 40000 + source[3], PORT, length, 0) + payload
    udp = udp[:6] + struct.pack(">H", checksum(pseudo + udp) or 0xFFFF) + udp[8:]
    ip = struct.pack(">BBHHHBBH", 0x45, 0, 20 + length, 0, 0, 64, 17, 0) + source + SHORE
    ip = ip[:10] + struct.pack(">H", checksum(ip)) + ip[12:]
    return bytes([2, 0, 0, 0, 0, 2]) + bytes([2, 0, 0, 0, 0, source[3]]) + b"\x08\x00" + ip + udp


def main() -> int:
    frames = []
    for turn in range(3):
        for build in (buoy.status, buoy.sea_state, buoy.position):
            for number, address in BUOYS:
                # Buoy 3 is two rounds further on, so its values differ from buoy 7's.
                sequence = 100 + len(frames)
                _, payload, _ = build(number, sequence, turn + (2 if number == 3 else 0))
                frames.append(frame(address, payload))
    with open(sys.argv[1], "wb") as out:
        out.write(struct.pack("<IHHiIII", 0xA1B2C3D4, 2, 4, 0, 0, 65535, 1))
        for index, data in enumerate(frames):
            out.write(struct.pack("<IIII", FIRST_SECOND + index, 0, len(data), len(data)))
            out.write(data)
    print(f"{sys.argv[1]}: {len(frames)} packets")
    return 0


if __name__ == "__main__":
    sys.exit(main())
