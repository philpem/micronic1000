#!/usr/bin/env python3
"""Decode segmented two-channel Micronic IR oscilloscope CSV captures.

Keysight CSV export is streamed one segment at a time: CH1 is the clock and
CH2 is sampled at each rising clock edge.  The output deliberately preserves
edge times and pulse counts so an inferred byte framing can be reviewed.
"""

from __future__ import annotations

import argparse
import csv
import json
import statistics
from pathlib import Path
from typing import Iterator


def percentile(values: list[float], fraction: float) -> float:
    ordered = sorted(values)
    return ordered[round((len(ordered) - 1) * fraction)]


def threshold(values: list[float], specified: float | None) -> float:
    if specified is not None:
        return specified
    return (percentile(values, 0.10) + percentile(values, 0.90)) / 2


def decode_segment(
    segment: list[tuple[float, float, float]],
    clock_threshold: float | None,
    data_threshold: float | None,
    data_offset: int,
    min_edge_samples: int,
) -> dict[str, object]:
    times, clock, data = zip(*segment)
    clk = threshold(list(clock), clock_threshold)
    dat = threshold(list(data), data_threshold)
    candidates: list[int] = []
    previous = clock[0] >= clk
    for index in range(1, len(clock)):
        current = clock[index] >= clk
        if current and not previous:
            candidates.append(index)
        previous = current

    if min_edge_samples == 0 and len(candidates) > 2:
        intervals = [times[right] - times[left] for left, right in zip(candidates, candidates[1:])]
        sample_period = times[1] - times[0]
        min_edge_samples = round(0.60 * statistics.median(intervals) / sample_period)
    edges: list[int] = []
    for index in candidates:
        if not edges or index - edges[-1] >= min_edge_samples:
            edges.append(index)

    sample_indices = [
        index + data_offset
        for index in edges
        if 0 <= index + data_offset < len(data)
    ]
    bits = "".join("1" if data[index] >= dat else "0" for index in sample_indices)
    intervals = [times[right] - times[left] for left, right in zip(edges, edges[1:])]
    nominal_interval = statistics.median(intervals) if intervals else 0.0
    cell_indices = [edges[0]]
    unclocked_cell_positions = []
    for left, right in zip(edges, edges[1:]):
        cell_count = max(1, round((times[right] - times[left]) / nominal_interval))
        for step in range(1, cell_count + 1):
            if step == cell_count:
                cell_indices.append(right)
                continue
            sample_time = times[left] + step * nominal_interval
            cell_indices.append(round((sample_time - times[0]) / (times[1] - times[0])))
            unclocked_cell_positions.append(len(cell_indices) - 1)
    cell_sample_indices = [
        index + data_offset
        for index in cell_indices
        if 0 <= index + data_offset < len(data)
    ]
    cell_bits = "".join("1" if data[index] >= dat else "0" for index in cell_sample_indices)
    return {
        "start_s": times[0],
        "end_s": times[-1],
        "sample_period_s": times[1] - times[0],
        "clock_threshold_v": clk,
        "data_threshold_v": dat,
        "clock_rising_edges": len(edges),
        "bits": bits,
        "clock_cells": len(cell_indices),
        "cell_bits": cell_bits,
        "unclocked_cell_positions": unclocked_cell_positions,
        "edge_times_s": [times[index] for index in edges],
        "clock_intervals_s": intervals,
    }


def segments(path: Path) -> Iterator[list[tuple[float, float, float]]]:
    with path.open(newline="") as capture:
        first = capture.readline().strip()
        if not first.startswith("points/segment = "):
            raise ValueError("expected Keysight 'points/segment = N' first line")
        points = int(first.split("=", 1)[1])
        capture.readline()  # x-axis,1,2
        capture.readline()  # second,Volt,Volt
        reader = csv.reader(capture)
        segment: list[tuple[float, float, float]] = []
        for row in reader:
            if len(row) != 3:
                continue
            segment.append((float(row[0]), float(row[1]), float(row[2])))
            if len(segment) == points:
                yield segment
                segment = []
        if segment:
            raise ValueError(f"truncated final segment: {len(segment)} of {points} points")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("capture", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--clock-threshold", type=float)
    parser.add_argument("--data-threshold", type=float)
    parser.add_argument("--data-offset-samples", type=int, default=0)
    parser.add_argument(
        "--min-edge-samples",
        type=int,
        default=0,
        help="reject closer clock edges; 0 derives 60%% of the median interval",
    )
    args = parser.parse_args()

    decoded = [
        decode_segment(
            segment,
            args.clock_threshold,
            args.data_threshold,
            args.data_offset_samples,
            args.min_edge_samples,
        )
        for segment in segments(args.capture)
    ]
    args.output.write_text(json.dumps(decoded, indent=2) + "\n")
    for number, result in enumerate(decoded):
        print(f"segment {number}: {result['clock_rising_edges']:2d} edges  {result['bits']}")


if __name__ == "__main__":
    main()
