#!/usr/bin/env python3
"""Audit the four-wire digital MSO captures from the IR responder tests.

Keysight CSV exports encode digital pod channels D0-D7 as one integer mask.
The captures use these four scope channels (these are not the Arduino pin
numbers printed in the sketch):

    D0  handheld data emitter        D1  handheld clock emitter
    D2  Arduino clock emitter        D3  Arduino data emitter

The export contains a fixed number of samples per segmented acquisition.  Its
time column is absolute across segments, so retry cadence can be measured from
the trigger time of adjacent segments.  This decoder characterises what was
actually emitted in every segment; it does not reconstruct Arduino sweep state
from segment numbers.

Usage:
    scope_ir_experiments.py CAPTURE.csv [CAPTURE.csv ...]
        [--addresses] [--groups] [--segments]
"""

from __future__ import annotations

import argparse
from collections import Counter
from dataclasses import dataclass
from pathlib import Path
from statistics import median


HANDHELD_CLOCK_BIT = 1
HANDHELD_DATA_BIT = 0
ARDUINO_CLOCK_BIT = 2
ARDUINO_DATA_BIT = 3
TRIGGER_OFFSET_S = 2e-3
FLAG_BITS = "10000001"


@dataclass(frozen=True)
class Segment:
    index: int
    start_s: float
    end_s: float
    handheld_bits: str
    handheld_end_ms: float | None
    arduino_bits: str
    arduino_clock_rises: int
    arduino_data_rises: int
    arduino_start_ms: float | None
    arduino_end_ms: float | None
    arduino_dark_after_handheld_ms: float | None
    arduino_end_censored: bool


def bit(mask: int, owner_bit: int) -> int:
    return (mask >> owner_bit) & 1


def rises(samples: list[int], owner_bit: int) -> list[int]:
    return [
        index
        for index in range(1, len(samples))
        if not bit(samples[index - 1], owner_bit)
        and bit(samples[index], owner_bit)
    ]


def parse_segment(index: int, times: list[float], samples: list[int]) -> Segment:
    handheld_clock_rises = rises(samples, HANDHELD_CLOCK_BIT)
    handheld_bits = "".join(
        str(bit(samples[sample], HANDHELD_DATA_BIT))
        for sample in handheld_clock_rises
    )
    arduino_clock_rises = rises(samples, ARDUINO_CLOCK_BIT)
    arduino_data_rises = rises(samples, ARDUINO_DATA_BIT)
    arduino_bits = "".join(
        str(bit(samples[sample], ARDUINO_DATA_BIT))
        for sample in arduino_clock_rises
    )
    # The established response follows illumination of the handheld's data
    # detector, so timing must use the physical Arduino data emitter (scope
    # D3), not the union of clock and data activity.  A free-running clock is
    # otherwise falsely classified as light that never went dark.
    active = [
        sample
        for sample, mask in enumerate(samples)
        if bit(mask, ARDUINO_DATA_BIT)
    ]
    trigger_s = times[0] + TRIGGER_OFFSET_S
    handheld_end_ms = (
        (times[handheld_clock_rises[-1]] - trigger_s) * 1e3
        if handheld_clock_rises
        else None
    )
    if active:
        arduino_start_ms = (times[active[0]] - trigger_s) * 1e3
        arduino_end_ms = (times[active[-1]] - trigger_s) * 1e3
        arduino_dark_after_handheld_ms = (
            arduino_end_ms - handheld_end_ms
            if handheld_end_ms is not None
            else None
        )
        capture_end_ms = (times[-1] - trigger_s) * 1e3
        arduino_end_censored = capture_end_ms - arduino_end_ms < 0.2
    else:
        arduino_start_ms = None
        arduino_end_ms = None
        arduino_dark_after_handheld_ms = None
        arduino_end_censored = False
    return Segment(
        index=index,
        start_s=times[0],
        end_s=times[-1],
        handheld_bits=handheld_bits,
        handheld_end_ms=handheld_end_ms,
        arduino_bits=arduino_bits,
        arduino_clock_rises=len(arduino_clock_rises),
        arduino_data_rises=len(arduino_data_rises),
        arduino_start_ms=arduino_start_ms,
        arduino_end_ms=arduino_end_ms,
        arduino_dark_after_handheld_ms=arduino_dark_after_handheld_ms,
        arduino_end_censored=arduino_end_censored,
    )


def load(path: Path) -> tuple[int, list[Segment]]:
    with path.open() as capture:
        first = capture.readline().strip()
        try:
            points = int(first.split("=", 1)[1])
        except (IndexError, ValueError) as exc:
            raise ValueError(f"{path}: missing points/segment header") from exc
        if capture.readline().strip() != "x-axis,D0-D7":
            raise ValueError(f"{path}: not a packed digital-channel CSV")
        capture.readline()

        segments = []
        times: list[float] = []
        samples: list[int] = []
        for line_number, line in enumerate(capture, 4):
            try:
                time_text, mask_text = line.rstrip().split(",", 1)
                times.append(float(time_text))
                samples.append(int(mask_text))
            except ValueError as exc:
                raise ValueError(f"{path}:{line_number}: malformed sample") from exc
            if len(times) == points:
                segments.append(parse_segment(len(segments), times, samples))
                times = []
                samples = []
        if times:
            raise ValueError(
                f"{path}: trailing partial segment ({len(times)}/{points})"
            )
    return points, segments


def quantiles(values: list[float]) -> str:
    if not values:
        return "-"
    ordered = sorted(values)
    indexes = (0, len(ordered) // 4, len(ordered) // 2,
               3 * len(ordered) // 4, len(ordered) - 1)
    return "/".join(f"{ordered[index]:.3f}" for index in indexes)


def cadence_reacted(value_ms: float) -> bool | None:
    """Classify the two measured retry-cadence populations."""
    if 90 <= value_ms < 100:
        return False
    if 105 <= value_ms <= 115:
        return True
    return None


def show_bits(bits: str, limit: int = 72) -> str:
    if not bits:
        return "<idle>"
    return bits if len(bits) <= limit else f"{bits[:limit]}...({len(bits)})"


def destuff(bits: str) -> str:
    output = []
    zero_run = 0
    for value in bits:
        if zero_run == 5:
            zero_run = 0
            continue
        output.append(value)
        zero_run = zero_run + 1 if value == "0" else 0
    return "".join(output)


def response_address(bits: str) -> int | None:
    flag = bits.find(FLAG_BITS)
    if flag < 0:
        return None
    field = destuff(bits[flag + len(FLAG_BITS):])
    return int(field[:8], 2) if len(field) >= 8 else None


def summarize(
    path: Path,
    points: int,
    segments: list[Segment],
    show_addresses: bool,
    show_groups: bool,
    verbose: bool,
) -> None:
    trigger_s = [segment.start_s + TRIGGER_OFFSET_S for segment in segments]
    cadence_ms = [
        (later - earlier) * 1e3
        for earlier, later in zip(trigger_s, trigger_s[1:])
    ]
    valid_cadence_ms = [
        value for value in cadence_ms if cadence_reacted(value) is not None
    ]
    normal_cadence_ms = [
        value for value in cadence_ms if cadence_reacted(value) is False
    ]
    reacted_cadence_ms = [
        value for value in cadence_ms if cadence_reacted(value) is True
    ]
    capture_gaps = sum(value > 150 for value in cadence_ms)
    other_cadence = len(cadence_ms) - len(valid_cadence_ms) - capture_gaps
    forms = Counter(segment.handheld_bits for segment in segments)
    activity = [segment for segment in segments if segment.arduino_end_ms is not None]
    ends = [segment.arduino_end_ms for segment in activity]
    edge_forms = Counter(
        (segment.arduino_clock_rises, segment.arduino_data_rises)
        for segment in segments
    )
    arduino_forms = Counter(
        segment.arduino_bits for segment in segments
        if segment.arduino_clock_rises
    )
    reaction = Counter()
    for segment, cadence in zip(segments, cadence_ms):
        reacted = cadence_reacted(cadence)
        if reacted is None:
            continue
        if segment.arduino_dark_after_handheld_ms is None:
            timing = "silent"
        elif segment.arduino_end_censored:
            timing = "still active at capture end"
        elif segment.arduino_dark_after_handheld_ms < 9.92:
            timing = "dark before 9.92 ms"
        else:
            timing = "dark at/after 9.92 ms"
        reaction[(timing, reacted)] += 1

    print(f"{path.name}: {len(segments)} segments x {points} samples")
    print(
        "  handheld forms: "
        + ", ".join(
            f"{show_bits(bits)} x{count}"
            for bits, count in forms.most_common(8)
        )
        + (f", ... ({len(forms)} forms)" if len(forms) > 8 else "")
    )
    print(
        "  retry cadence ms min/q1/median/q3/max (90-100 or 105-115 ms): "
        f"{quantiles(valid_cadence_ms)}; gaps>150 ms={capture_gaps}; "
        f"other excluded={other_cadence}"
    )
    if normal_cadence_ms and reacted_cadence_ms:
        normal_median = median(normal_cadence_ms)
        reacted_median = median(reacted_cadence_ms)
        print(
            f"  cadence populations: normal n={len(normal_cadence_ms)} "
            f"median={normal_median:.3f} ms; reacted "
            f"n={len(reacted_cadence_ms)} median={reacted_median:.3f} ms; "
            f"delta={reacted_median - normal_median:.3f} ms"
        )
    print(
        f"  Arduino data-emitter active: {len(activity)}/{len(segments)}; "
        f"end ms min/q1/median/q3/max: {quantiles(ends)}"
    )
    print(
        "  Arduino rise-count forms (scope D2 clock,D3 data): "
        + ", ".join(
            f"{clock}/{data} x{count}"
            for (clock, data), count in edge_forms.most_common(12)
        )
    )
    if arduino_forms:
        print(
            "  Arduino sampled-bit forms: "
            + ", ".join(
                f"{show_bits(bits)} x{count}"
                for bits, count in arduino_forms.most_common(12)
            )
            + (f", ... ({len(arduino_forms)} forms)" if len(arduino_forms) > 12 else "")
        )
    for timing in (
        "silent",
        "dark before 9.92 ms",
        "dark at/after 9.92 ms",
        "still active at capture end",
    ):
        normal = reaction[(timing, False)]
        delayed = reaction[(timing, True)]
        total = normal + delayed
        if total:
            print(
                f"  cadence reaction, {timing}: "
                f"{delayed}/{total} ({100 * delayed / total:.1f}%)"
            )
    if show_groups:
        grouped: dict[tuple[int, int], list[tuple[Segment, float | None]]] = {}
        for index, segment in enumerate(segments):
            cadence = cadence_ms[index] if index < len(cadence_ms) else None
            grouped.setdefault(
                (segment.arduino_clock_rises, segment.arduino_data_rises), []
            ).append((segment, cadence))
        print("  groups by Arduino rise counts:")
        for (clock, data), observations in sorted(
            grouped.items(), key=lambda item: (-len(item[1]), item[0])
        ):
            valid = [
                cadence for _, cadence in observations
                if cadence is not None and cadence_reacted(cadence) is not None
            ]
            delayed = sum(cadence_reacted(cadence) is True for cadence in valid)
            dark = [
                segment.arduino_dark_after_handheld_ms
                for segment, _ in observations
                if segment.arduino_dark_after_handheld_ms is not None
            ]
            bits = Counter(segment.arduino_bits for segment, _ in observations)
            common_bits = ",".join(
                f"{show_bits(value, 40)}x{count}"
                for value, count in bits.most_common(3)
            )
            ratio = "-" if not valid else f"{delayed}/{len(valid)}"
            print(
                f"    D2r/D3r={clock}/{data} n={len(observations)} "
                f"reaction={ratio} dark-ms={quantiles(dark)} bits={common_bits}"
            )
    if show_addresses:
        addressed: dict[int, list[float]] = {}
        for index, segment in enumerate(segments[:-1]):
            address = response_address(segment.arduino_bits)
            cadence = cadence_ms[index]
            if address is not None and cadence_reacted(cadence) is not None:
                addressed.setdefault(address, []).append(cadence)
        print(f"  decoded address values: {len(addressed)}")
        for address, cadences in sorted(addressed.items()):
            delayed = sum(cadence_reacted(cadence) is True for cadence in cadences)
            print(
                f"    address={address:02X} reaction={delayed}/{len(cadences)} "
                f"cadence-ms={quantiles(cadences)}"
            )
    if verbose:
        for index, segment in enumerate(segments):
            cadence = cadence_ms[index] if index < len(cadence_ms) else None
            start = (
                "-"
                if segment.arduino_start_ms is None
                else f"{segment.arduino_start_ms:.3f}"
            )
            end = (
                "-"
                if segment.arduino_end_ms is None
                else f"{segment.arduino_end_ms:.3f}"
            )
            dark = (
                "-"
                if segment.arduino_dark_after_handheld_ms is None
                else f"{segment.arduino_dark_after_handheld_ms:.3f}"
            )
            delta = "-" if cadence is None else f"{cadence:.3f}"
            print(
                f"  seg{segment.index:03d} cells={len(segment.handheld_bits):3d} "
                f"bits={segment.handheld_bits or '-'} "
                f"D2r={segment.arduino_clock_rises:3d} "
                f"D3r={segment.arduino_data_rises:3d} "
                f"tx={start}..{end} ms dark_after={dark} ms "
                f"next={delta} ms"
            )


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("captures", nargs="+", type=Path)
    parser.add_argument("--addresses", action="store_true")
    parser.add_argument("--groups", action="store_true")
    parser.add_argument("--segments", action="store_true")
    args = parser.parse_args()
    for path in args.captures:
        points, segments = load(path)
        summarize(
            path,
            points,
            segments,
            args.addresses,
            args.groups,
            args.segments,
        )


if __name__ == "__main__":
    main()
