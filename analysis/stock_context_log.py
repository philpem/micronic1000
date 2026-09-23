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
DROPS_RE = re.compile(r"^#\s*STOCK_YELLOW_DROPS\s+(\d+)\s*$")
LEGACY_BOOT_PREFIX = "M1000 IR probe. Expecting "
V3_BANNER = "STOCK_CONTEXT_V3 width_us=32 drops=16"


def _is_epoch_start(line: str) -> bool:
    stripped = line.strip()
    return (stripped == "BOOT" or stripped.startswith(LEGACY_BOOT_PREFIX)
            or stripped == V3_BANNER)


def _pulse_class(width: int) -> str:
    # Broad candidate bands around observed/expected stock pulse widths.
    # These classify timing only; they do not identify the emitting routine.
    if 700 <= width <= 1100:
        return "carry_set_candidate"
    if 1500 <= width <= 2100:
        return "carry_clear_candidate"
    if 3000 <= width <= 4200:
        return "boot_signature_candidate"
    return "unclassified"


def correlate_lines(lines: list[str], association_window_us: int = 250_000) -> list[dict]:
    """Associate yellow pulses with TX reports using Uno timestamps only.

    Uno ``micros()`` values wrap at 32 bits. A TX is considered temporally
    preceding when the unsigned pulse-fall-minus-start delta is below
    half-range and within ``association_window_us``. FREE_TX ``# TX`` lines
    and RX_NARROW ``burst`` reports both carry that timestamp. They can be
    printed after emission, so log order is not used for timing. BOOT records
    begin new micros-clock epochs. Missing evidence is left unmatched.
    """
    if not 0 <= association_window_us < UINT32_HALF:
        raise ValueError("association window must be between 0 and 2^31-1 us")
    tx_history: list[tuple[int, int, int, str, str | None]] = []
    epoch = 0
    epoch_drops: dict[int, int] = {}
    epoch_schema: dict[int, str] = {0: "legacy"}
    # First pass observes drop markers anywhere in an epoch; the marker is
    # emitted after the affected events have already been drained.
    for number, raw in enumerate(lines, 1):
        if _is_epoch_start(raw):
            epoch += 1
            epoch_schema[epoch] = "v3" if raw.strip() == V3_BANNER else "legacy"
        else:
            match = DROPS_RE.match(raw.strip())
            if match:
                epoch_drops[epoch] = epoch_drops.get(epoch, 0) + int(match.group(1))
            match = TX_RE.search(raw)
            if match and (raw.lstrip().startswith("# TX") or raw.lstrip().startswith("burst ")):
                swap_match = SWAP_RE.search(raw)
                tx_history.append((epoch, number, int(match.group(1)) & UINT32_MASK,
                                   raw, swap_match.group(1) if swap_match else None))
    epoch = 0
    output = []
    for line_number, line in enumerate(lines, 1):
        if _is_epoch_start(line):
            epoch += 1
            continue
        drops_match = DROPS_RE.match(line.strip())
        if drops_match:
            continue
        tx_match = TX_RE.search(line)
        stripped = line.lstrip()
        if (stripped.startswith("# TX") or stripped.startswith("burst ")) and tx_match:
            continue
        event_match = YELLOW_RE.match(line.strip())
        if not event_match:
            continue
        rise = int(event_match.group(1))
        low = int(event_match.group(2))
        if rise > UINT32_MASK or low > UINT32_MASK:
            raise ValueError(f"serial line {line_number}: yellow timestamp/width exceeds uint32")
        event_start = (rise - low) & UINT32_MASK
        event = {
            "line": line_number,
            "epoch": epoch,
            "rise_us": rise,
            "low_us": low,
            "event_start_us": event_start,
        }
        saturated = low == 65535 and epoch_schema.get(epoch) != "v3"
        event["pulse_class"] = _pulse_class(low)
        event["schema"] = epoch_schema.get(epoch, "legacy")
        if saturated:
            event["width_saturated"] = True
        if epoch_drops.get(epoch, 0) > 0:
            event["capture_incomplete"] = True
            event["dropped_events"] = epoch_drops.get(epoch, 0)
            event["drop_count_saturated"] = epoch_drops.get(epoch, 0) >= 65535
        candidates = []
        for tx_epoch, tx_line_number, tx_start, tx_line, swap in tx_history:
            if saturated or event["pulse_class"] == "boot_signature_candidate":
                break
            if tx_epoch != epoch:
                continue
            elapsed = (event_start - tx_start) & UINT32_MASK
            if elapsed < UINT32_HALF and elapsed <= association_window_us:
                candidates.append((elapsed, tx_line_number, tx_start, tx_line, swap))
        if saturated:
            event["event_start_us"] = None
            event["tx"] = None
            event["classification"] = "unmatched: legacy width capped"
        elif event["pulse_class"] == "boot_signature_candidate":
            event["tx"] = None
            event["classification"] = "initialization signature candidate; not RX evidence"
        elif not candidates:
            event["tx"] = None
            event["classification"] = "unmatched: no TX timestamp in window"
        else:
            elapsed, tx_line_number, tx_start, tx_line, swap = min(candidates)
            event.update(tx_start_us=tx_start, tx_elapsed_us=elapsed,
                         swap=swap, tx_line_number=tx_line_number,
                         tx_line=tx_line, classification="preceding TX")
        output.append(event)
    for dropped_epoch, count in epoch_drops.items():
        if count and not any(e["epoch"] == dropped_epoch for e in output):
            output.append({"epoch": dropped_epoch, "capture_incomplete": True,
                           "dropped_events": count, "classification": "events lost; no pulse records"})
    return output


def analyze(path: Path, association_window_us: int = 250_000) -> list[dict]:
    records = []
    with path.open() as source:
        for number, raw in enumerate(source, 1):
            try:
                record = json.loads(raw)
                if isinstance(record, dict) and isinstance(record.get("line"), str):
                    records.append(record["line"])
                else:
                    raise ValueError(f"{path}:{number}: expected capture record with string line")
            except json.JSONDecodeError as exc:
                raise ValueError(f"{path}:{number}: malformed JSON; capture is incomplete") from exc
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
