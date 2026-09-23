#!/usr/bin/env python3
"""Passively record Uno stock-context events and correlate their timings.

The logger sends no bytes to the Uno. It records complete serial lines with
host UTC and monotonic timestamps in a newly created JSONL file.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import re
import sys
import time

from ir_feedback import SerialLines

UINT32_MASK = 0xFFFFFFFF
UINT32_HALF = 0x80000000
TX_RE = re.compile(r"(?:^|\s)tx_start_us=(\d+)(?:\s|$)")
SWAP_RE = re.compile(r"(?:^|\s)swap=(\S+)(?:\s|$)")
YELLOW_RE = re.compile(
    r"^#\s*STOCK_YELLOW\s+rise_us=(\d+)\s+low_us=(\d+)(?:\s|$)"
)


def correlate_lines(lines: list[str], association_window_us: int = 250_000) -> list[dict]:
    """Correlate yellow pulses with the closest preceding TX by Uno time.

    Uno ``micros()`` values wrap at 32 bits. A TX is considered temporally
    preceding when the unsigned pulse-fall-minus-start delta is below
    half-range and within ``association_window_us``. FREE_TX ``# TX`` lines
    and RX_NARROW ``burst`` reports both carry that timestamp. They can be
    printed after emission, so a history is searched instead of trusting log
    order alone. A missing or garbled TX is reported as a control/silent event.
    """
    if not 0 <= association_window_us < UINT32_HALF:
        raise ValueError("association window must be between 0 and 2^31-1 us")
    tx_history: list[tuple[int, int, str, str | None]] = []
    output = []
    for line_number, line in enumerate(lines, 1):
        tx_match = TX_RE.search(line)
        stripped = line.lstrip()
        if (stripped.startswith("# TX") or stripped.startswith("burst ")) and tx_match:
            swap_match = SWAP_RE.search(line)
            tx_history.append((line_number, int(tx_match.group(1)) & UINT32_MASK,
                               line, swap_match.group(1) if swap_match else None))
            continue
        event_match = YELLOW_RE.match(line.strip())
        if not event_match:
            continue
        rise = int(event_match.group(1)) & UINT32_MASK
        low = int(event_match.group(2))
        event_start = (rise - low) & UINT32_MASK
        event = {
            "line": line_number,
            "rise_us": rise,
            "low_us": low,
            "event_start_us": event_start,
        }
        candidates = []
        for tx_line_number, tx_start, tx_line, swap in tx_history:
            elapsed = (event_start - tx_start) & UINT32_MASK
            if elapsed < UINT32_HALF and elapsed <= association_window_us:
                candidates.append((elapsed, tx_line_number, tx_start, tx_line, swap))
        if not candidates:
            event["tx"] = None
            event["classification"] = "no preceding TX (silent/control)"
        else:
            elapsed, tx_line_number, tx_start, tx_line, swap = min(candidates)
            event.update(tx_start_us=tx_start, tx_elapsed_us=elapsed,
                         swap=swap, tx_line_number=tx_line_number,
                         tx_line=tx_line, classification="preceding TX")
        output.append(event)
    return output


def analyze(path: Path, association_window_us: int = 250_000) -> list[dict]:
    records = []
    with path.open() as source:
        for number, raw in enumerate(source, 1):
            try:
                record = json.loads(raw)
                if isinstance(record, dict) and isinstance(record.get("line"), str):
                    records.append(record["line"])
            except json.JSONDecodeError:
                continue
    return correlate_lines(records, association_window_us)


def record_line(log, line: str) -> None:
    record = {
        "utc": datetime.now(timezone.utc).isoformat(),
        "monotonic_s": time.monotonic(),
        "direction": "rx",
        "line": line,
    }
    log.write(json.dumps(record) + "\n")
    log.flush()
    print(line, flush=True)


def capture(port: str, path: Path, duration: float) -> None:
    # Exclusive creation makes every capture a distinct evidence record.
    with path.open("x", encoding="utf-8") as log:
        serial = SerialLines(port)
        try:
            deadline = time.monotonic() + duration
            while True:
                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    break
                try:
                    line = serial.read(min(remaining, 0.25))
                except RuntimeError as exc:
                    # An overlong boot fragment should not kill a passive
                    # recording; SerialLines has already consumed the bytes.
                    if "exceeds 8192 bytes" in str(exc):
                        serial.pending.clear()
                        continue
                    raise
                if line is not None:
                    record_line(log, line)
        finally:
            serial.close()


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--port", default="/dev/ttyACM0", help="serial port")
    parser.add_argument("--log", type=Path, required=True,
                        help="new JSONL log path; existing files are never overwritten")
    parser.add_argument("--duration", type=float,
                        help="passively capture for this many seconds")
    parser.add_argument("--analyze", action="store_true",
                        help="correlate TX and STOCK_YELLOW records in --log")
    parser.add_argument("--association-window-ms", type=float, default=250.0,
                        help="maximum TX-to-pulse-fall interval for analysis (default 250)")
    args = parser.parse_args(argv)
    if args.analyze:
        if args.duration is not None:
            parser.error("--analyze and --duration cannot be combined")
        if args.association_window_ms < 0:
            parser.error("--association-window-ms cannot be negative")
        try:
            events = analyze(args.log, round(args.association_window_ms * 1000))
        except (OSError, ValueError) as exc:
            print(str(exc), file=sys.stderr)
            return 1
        for event in events:
            print(json.dumps(event, sort_keys=True))
        return 0
    if args.duration is None or args.duration <= 0:
        parser.error("--duration must be positive unless --analyze is used")
    try:
        capture(args.port, args.log, args.duration)
    except KeyboardInterrupt:
        return 130
    except (OSError, ValueError, RuntimeError) as exc:
        print(str(exc), file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
