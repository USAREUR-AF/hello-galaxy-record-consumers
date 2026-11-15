#!/usr/bin/env python3
"""The simulated harbour buoy: sends the messages of icd/HB-ICD-001-A.md.

    device/buoy.py --to <host>:47200 --count 9 [--interval 0.2] [--buoy 7]

It sends Status, Sea State and Position in turn, one UDP datagram each, with
values that change from one round to the next, and prints one JSON line per
datagram with the values it encoded. The layout is typed from the document's
tables with `struct`; nothing here reads the dictionary or uses first-bite.
Python standard library only. Every value is synthetic.
"""
import argparse
import json
import socket
import struct
import sys
import time

MODES = {0: "Standby", 1: "Reporting", 2: "Low Power"}


def header(message_id: int, words: int, buoy: int, sequence: int) -> bytes:
    # Table 4-1: ID and length in word 1, buoy number and sequence in word 2.
    return struct.pack(">BBH", message_id, words, buoy << 12 | sequence & 0xFFF)


def status(buoy: int, sequence: int, turn: int):
    mode, lamp, alarm, fix = 1, turn % 2, int(turn == 2), 1
    centivolts, minutes = 1260 - 3 * turn, 1440 + turn
    word3 = mode << 14 | lamp << 13 | alarm << 12 | fix << 11 | centivolts
    values = {
        "operating_mode": MODES[mode], "lamp_on": bool(lamp), "mooring_alarm": bool(alarm),
        "position_fix": bool(fix), "battery_voltage": centivolts / 100, "uptime": minutes,
    }
    return "Status", header(1, 4, buoy, sequence) + struct.pack(">HH", word3, minutes), values


def sea_state(buoy: int, sequence: int, turn: int):
    water, height, period = -125 + 40 * turn, 235 + 7 * turn, 17 + turn
    direction, speed, pressure = (285 + 5 * turn) % 360, 25 + turn, 10032 - 4 * turn
    payload = header(2, 6, buoy, sequence) + struct.pack(
        ">hHHH", water, height << 6 | period, direction << 7 | speed, pressure
    )
    values = {
        "water_temperature": water / 100, "significant_wave_height": height / 100,
        "wave_period": period / 2, "wind_direction": direction, "wind_speed": speed / 2,
        "air_pressure": pressure / 10,
    }
    return "Sea State", payload, values


def position(buoy: int, sequence: int, turn: int):
    latitude, longitude = 445012345 - 1500 * turn, -302543210 + 2100 * turn
    course, speed, satellites, height = 135, 7 + turn, 9, -15 + turn
    payload = header(3, 8, buoy, sequence) + struct.pack(
        ">iiHH", latitude, longitude, course << 7 | speed, satellites << 12 | height & 0xFFF
    )
    values = {
        "latitude": latitude / 1e7, "longitude": longitude / 1e7, "drift_course": course,
        "drift_speed": speed / 20, "satellites_in_view": satellites, "antenna_height": height / 10,
    }
    return "Position", payload, values


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--to", required=True, help="<host>:<port> of the shore station")
    parser.add_argument("--count", type=int, default=9, help="datagrams to send")
    parser.add_argument("--interval", type=float, default=0.2, help="seconds between datagrams")
    parser.add_argument("--buoy", type=int, default=7, help="buoy number, 1 to 15")
    parser.add_argument("--first-sequence", type=int, default=100)
    args = parser.parse_args()
    host, port = args.to.rsplit(":", 1)
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    builders = (status, sea_state, position)
    for index in range(args.count):
        sequence = (args.first_sequence + index) & 0xFFF
        message, payload, values = builders[index % 3](args.buoy, sequence, index // 3)
        sock.sendto(payload, (host, int(port)))
        print(json.dumps({"sent": index + 1, "message": message, "sequence_number": sequence,
                          "bytes": payload.hex(), **values}), flush=True)
        time.sleep(args.interval)
    print(f"buoy {args.buoy}: sent {args.count} datagrams to {args.to}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
