#!/usr/bin/env python3
"""Measure a Keysight packed D0-D7 CSV from an Uno feedback stimulus.

The scope D-bit numbers are pod inputs, not Arduino pin numbers. Defaults
follow the existing capture wiring (scope D2=Uno D5, D3=Uno D6); override
them if the probes moved. Times are measured at the scope's sample grid.
"""

from __future__ import annotations

import argparse
import bisect
import csv
from dataclasses import asdict, dataclass
import json
from pathlib import Path
import statistics


@dataclass
class Pulse:
    rise_us: float
    fall_us: float | None
    width_us: float | None


def read_capture(path: Path) -> tuple[list[float], list[int]]:
    """Accept ordinary x-axis,D0-D7 exports and points/segment exports."""
    times: list[float] = []
    masks: list[int] = []
    header_seen = False
    with path.open(newline="") as capture:
        for line, row in enumerate(csv.reader(capture), 1):
            if not row:
                continue
            if row[0].strip() == "x-axis":
                if len(row) != 2 or row[1].strip() != "D0-D7":
                    raise ValueError(f"{path}:{line}: expected x-axis,D0-D7")
                header_seen = True
                continue
            if not header_seen or row[0].strip() == "second":
                continue
            if len(row) != 2:
                raise ValueError(f"{path}:{line}: expected time,mask")
            try:
                time_s = float(row[0])
                value = row[1].strip()
                mask = int(value, 16 if value.lower().startswith("0x") else 10)
            except ValueError as exc:
                raise ValueError(f"{path}:{line}: invalid time or mask") from exc
            if not 0 <= mask <= 255 or (times and time_s <= times[-1]):
                raise ValueError(f"{path}:{line}: invalid mask or time order")
            times.append(time_s)
            masks.append(mask)
    if not header_seen or len(times) < 3:
        raise ValueError(f"{path}: missing digital header or capture samples")
    return times, masks


def pulses(times: list[float], masks: list[int], bit: int) -> list[Pulse]:
    result: list[Pulse] = []
    level = bool(masks[0] & (1 << bit))
    if level:
        result.append(Pulse(times[0] * 1e6, None, None))
    for time_s, mask in zip(times[1:], masks[1:]):
        new_level = bool(mask & (1 << bit))
        if new_level and not level:
            result.append(Pulse(time_s * 1e6, None, None))
        elif level and not new_level:
            result[-1].fall_us = time_s * 1e6
            result[-1].width_us = result[-1].fall_us - result[-1].rise_us
        level = new_level
    return result


def _stimulus_cells(flag: int, payload: bytes, stuffing: int,
                    close_flag: bool) -> list[int]:
    """Return transmitted MSB-first cells; flag bytes are never stuffed."""
    cells = [(flag >> shift) & 1 for shift in range(7, -1, -1)]
    run = 0
    for byte in payload:
        for shift in range(7, -1, -1):
            bit = (byte >> shift) & 1
            if stuffing and run == 5:
                cells.append(0 if stuffing == 1 else 1)
                run = 0
            cells.append(bit)
            if stuffing:
                run = run + 1 if (bit if stuffing == 1 else not bit) else 0
    if stuffing and run == 5:
        cells.append(0 if stuffing == 1 else 1)
    if close_flag:
        cells.extend((flag >> shift) & 1 for shift in range(7, -1, -1))
    return cells


def measure(path: Path, clock_bit: int, data_bit: int, lead: int,
            flag: int, cell_us: float, payload: bytes = b"",
            stuffing: int = 0, close_flag: bool = False) -> dict:
    if not (0 <= clock_bit <= 7 and 0 <= data_bit <= 7) or clock_bit == data_bit:
        raise ValueError("scope clock/data bits must be distinct D0..D7")
    if (not 0 <= lead <= 32 or not 0 <= flag <= 255 or cell_us <= 0
            or stuffing not in (0, 1, 2)):
        raise ValueError("invalid lead, flag, stuffing mode, or cell duration")
    if not isinstance(payload, bytes):
        raise ValueError("payload must be bytes")
    times, masks = read_capture(path)
    clock = pulses(times, masks, clock_bit)
    data = pulses(times, masks, data_bit)
    intervals = [b.rise_us - a.rise_us for a, b in zip(clock, clock[1:])]
    cells = _stimulus_cells(flag, payload, stuffing, close_flag)
    expected_ones = [lead + index for index, bit in enumerate(cells) if bit]
    sampled_bits = []
    for pulse in clock[lead:lead + len(cells)]:
        sample = bisect.bisect_right(times, pulse.rise_us / 1e6) - 1
        sampled_bits.append(int(bool(masks[sample] & (1 << data_bit))))
    sampled_flag = (int("".join(map(str, sampled_bits[:8])), 2)
                    if len(sampled_bits) >= 8 else None)
    pairs = []
    for pulse, clock_index in zip(data, expected_ones):
        if clock_index < len(clock):
            pairs.append({"clock_index": clock_index,
                          "data_minus_clock_us": pulse.rise_us - clock[clock_index].rise_us})
    step_us = statistics.median((b - a) * 1e6 for a, b in zip(times, times[1:]))
    return {
        "source": str(path), "samples": len(times), "sample_step_us": step_us,
        "scope_clock_bit": clock_bit, "scope_data_bit": data_bit,
        "lead_cells": lead, "flag_hex": f"{flag:02X}",
        "payload_hex": payload.hex().upper(), "stuffing": stuffing,
        "close_flag": close_flag, "requested_cell_us": cell_us,
        "sampled_flag_hex": f"{sampled_flag:02X}" if sampled_flag is not None else None,
        "expected_cells": len(cells), "expected_sampled_bits": len(cells),
        "sampled_bits": "".join(map(str, sampled_bits)),
        "expected_clock_pulses": lead + len(cells),
        "expected_data_pulses": len(expected_ones),
        "clock": [asdict(p) for p in clock], "data": [asdict(p) for p in data],
        "clock_intervals_us": intervals, "data_clock_pairs": pairs,
        "lead_interval_median_us": statistics.median(intervals[:lead-1])
            if lead > 1 and len(intervals) >= lead-1 else None,
        "later_interval_median_us": statistics.median(intervals[lead+1:])
            if len(intervals) > lead+1 else None,
    }


def report(result: dict) -> str:
    def duration(value: float | None) -> str:
        return f"{value:.1f}" if value is not None else "unavailable"

    lines = [f"{result['source']}: {result['samples']} samples, "
             f"{result['sample_step_us']:.3f} us/sample",
             f"scope D{result['scope_clock_bit']} clock: "
             f"{len(result['clock'])}/{result['expected_clock_pulses']} pulses; "
             f"scope D{result['scope_data_bit']} data: "
             f"{len(result['data'])}/{result['expected_data_pulses']} pulses",
             "", "Clock # | Rise (us) | Width (us) | Next rise (us)",
             "---:|---:|---:|---:"]
    for index, pulse in enumerate(result["clock"]):
        period = result["clock_intervals_us"][index] if index < len(result["clock_intervals_us"]) else None
        width = f"{pulse['width_us']:.1f}" if pulse["width_us"] is not None else "clipped"
        next_rise = f"{period:.1f}" if period is not None else "-"
        lines.append(f"{index:>3} | {pulse['rise_us']:.1f} | {width} | {next_rise}")
    lines += ["", "Data # | Rise (us) | Width (us) | Paired clock # | Data minus clock (us)",
              "---:|---:|---:|---:|---:"]
    for index, pulse in enumerate(result["data"]):
        pair = result["data_clock_pairs"][index] if index < len(result["data_clock_pairs"]) else None
        width = f"{pulse['width_us']:.1f}" if pulse["width_us"] is not None else "clipped"
        clock_index = str(pair["clock_index"]) if pair else "-"
        phase = f"{pair['data_minus_clock_us']:.1f}" if pair else "-"
        lines.append(f"{index:>3} | {pulse['rise_us']:.1f} | {width} | "
                     f"{clock_index} | {phase}")
    lines += ["", f"Requested cell: {result['requested_cell_us']:.1f} us; "
              f"first lead interval median: {duration(result['lead_interval_median_us'])} us; "
              f"later interval median: {duration(result['later_interval_median_us'])} us"]
    lines.append(f"Data at eight candidate clock rises: "
                 f"{result['sampled_flag_hex'] or 'incomplete'} "
                 f"(requested {result['flag_hex']})")
    lines.append(f"Sampled candidate cells: "
                 f"{result['sampled_bits'] or 'incomplete'} "
                 f"({len(result['sampled_bits'])}/{result['expected_sampled_bits']})")
    return "\n".join(lines)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("capture", type=Path)
    parser.add_argument("--clock-bit", type=int, default=2,
                        help="scope pod bit for Uno proposed clock (default D2)")
    parser.add_argument("--data-bit", type=int, default=3,
                        help="scope pod bit for Uno proposed data (default D3)")
    parser.add_argument("--lead", type=int, default=5)
    parser.add_argument("--flag", type=lambda x: int(x, 16), default=0x7E)
    parser.add_argument("--payload", default="", help="payload bytes as even-length hex")
    parser.add_argument("--stuff", type=int, choices=(0, 1, 2), default=0,
                        help="0=none, 1=zero after five ones, 2=one after five zeros")
    parser.add_argument("--close", type=int, choices=(0, 1), default=0,
                        help="append an unstuffed closing flag")
    parser.add_argument("--cell-us", type=float, default=122.0)
    parser.add_argument("--json-out", type=Path, help="optional machine-readable measurements")
    args = parser.parse_args()
    try:
        payload = bytes.fromhex(args.payload)
    except ValueError as exc:
        parser.error(f"--payload must be even-length hexadecimal: {exc}")
    result = measure(args.capture, args.clock_bit, args.data_bit,
                     args.lead, args.flag, args.cell_us, payload,
                     args.stuff, bool(args.close))
    print(report(result))
    if args.json_out:
        args.json_out.write_text(json.dumps(result, indent=2) + "\n")


if __name__ == "__main__":
    main()
