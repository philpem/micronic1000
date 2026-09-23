#!/usr/bin/env python3
"""Validate and decode feedback-v1/v2 30-byte ROM records.

Input is a timestamped ir_feedback.py JSONL log or one hex record per line.
Mode 5/6/7 in version 2 carries status samples, not received data.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import re


RAW = re.compile(r"(?:^|\s)raw=([0-9A-Fa-f]{60})(?:\s|$)")


def decode_record(raw: bytes) -> dict:
    if len(raw) != 30 or raw[:2] != b"\xA5\x5A" or sum(raw) & 0xFF:
        raise ValueError("invalid feedback record length, magic, or checksum")
    version, mode = raw[2], raw[3]
    if version not in (1, 2) or mode > (4 if version == 1 else 7):
        raise ValueError(f"unsupported feedback version/mode {version}/{mode}")
    result = {
        "version": version,
        "mode": mode,
        "rom_sequence": int.from_bytes(raw[4:6], "little"),
        "error": raw[6],
        "link_status_probe": raw[7],
        "link_status_before": raw[8],
        "link_status_after": raw[9],
        "witness_bit4_poll": raw[10],
        "witness_bit6_poll": raw[11],
        "witness_arm": raw[12],
        "rx_return_a": raw[13],
        "rx_return_f": raw[14],
        "rx_count": int.from_bytes(raw[15:17], "little"),
        "slot_length": raw[17],
        "port_2a_shadow": raw[26],
        "port_2c_shadow": raw[27],
        "port_2d_input": raw[28],
    }
    slot = raw[18:26]
    if version == 2 and mode in (5, 6, 7):
        if raw[17] != 8:
            raise ValueError("v2 status capture must define all eight slot bytes")
        first4 = int.from_bytes(slot[2:4], "little")
        first0 = int.from_bytes(slot[4:6], "little")
        count = int.from_bytes(slot[6:8], "little")
        if count != (600 if mode == 7 else 1000):
            raise ValueError("unexpected v2 status sample count")
        if slot[1] & ~slot[0] or (first4 != 0xFFFF and first4 >= count) or (
                first0 != 0xFFFF and first0 >= count):
            raise ValueError("inconsistent v2 status summary")
        result["status_capture"] = {
            "link_status_or": slot[0],
            "link_status_and": slot[1],
            "first_link_status_bit4_sample": None if first4 == 0xFFFF else first4,
            "first_link_status_bit0_sample": None if first0 == 0xFFFF else first0,
            "sample_count": count,
        }
        if mode == 7:
            result["status_capture"]["watcher_saw_link_status_bit4"] = raw[10] == 0x10
    else:
        if raw[17] > 8:
            raise ValueError("invalid RX preview length")
        result["rx_preview"] = slot[:raw[17]].hex().upper()
    return result


def records_from_lines(lines):
    for number, line in enumerate(lines, 1):
        line = line.strip()
        if not line:
            continue
        if line.startswith("{"):
            event = json.loads(line)
            if event.get("direction") != "rx" or not event.get("line", "").startswith("RESULT "):
                continue
            line = event["line"]
        match = RAW.search(line)
        text = match.group(1) if match else re.sub(r"\s+", "", line)
        try:
            yield number, decode_record(bytes.fromhex(text))
        except ValueError as exc:
            raise ValueError(f"line {number}: {exc}") from exc


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("path", type=Path, help="feedback JSONL or hex-record file")
    args = parser.parse_args()
    try:
        for line, record in records_from_lines(args.path.read_text().splitlines()):
            print(json.dumps({"line": line, **record}, sort_keys=True))
    except ValueError as exc:
        parser.error(str(exc))


if __name__ == "__main__":
    main()
