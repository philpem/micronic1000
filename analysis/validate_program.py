#!/usr/bin/env python3
"""validate_program - CLI for COM/DIP validation (host-side, no hardware).

Uses analysis.micronic.program which implements ONLY the CONFIRMED grammar
from doc/manual/program-formats.md. Exit codes: 0=valid, 1=invalid,
2=error (missing file etc.). Supports human and JSON output.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

# Allow running as `python3 analysis/validate_program.py` without install
sys.path.insert(0, str(Path(__file__).resolve().parent))

from micronic.program import validate, classify, COM_MAX, DIP_HEADER_SIZE

def format_result(res, verbose: bool = False) -> str:
    lines = []
    lines.append(f"kind: {res.kind}")
    lines.append(f"valid: {res.valid}")
    lines.append(f"size: {res.data_len} byte(s)")
    if res.kind == "COM":
        lines.append(f"COM limit: 0x{COM_MAX:04X} ({COM_MAX})")
        if res.data_len > COM_MAX:
            lines.append(f"  -> exceeds limit by {res.data_len - COM_MAX}")
    if res.header is not None:
        h = res.header
        lines.append(
            f"DIP header: magic=0x{h.magic:04X} system=0x{h.system_id:04X} "
            f"entry_bank=0x{h.entry_bank_offset:04X} image_size=0x{h.image_size:04X}"
            + (f" (clamped 0x{h.image_size_clamped:04X})" if h.image_size_was_clamped else "")
            + f" run_bank=0x{h.run_bank_offset:04X} entry=0x{h.entry_address:04X} blocks={h.block_count}"
        )
        for b in res.blocks:
            lines.append(
                f"  block {b.index}: type={b.type} bank_off=0x{b.dest_bank_offset:04X} "
                f"addr=0x{b.dest_address:04X} payload_len={b.payload_len}"
            )
        if res.trailing_bytes:
            lines.append(f"trailing bytes: {res.trailing_bytes}")
    if res.errors:
        lines.append("errors:")
        for e in res.errors:
            lines.append(f"  - {e}")
    else:
        lines.append("errors: none")
    if verbose and res.warnings:
        lines.append("warnings:")
        for w in res.warnings:
            lines.append(f"  - {w}")
    return "\n".join(lines)


def main(argv=None) -> int:
    p = argparse.ArgumentParser(
        description="Validate a Micronic 1000 COM/DIP image (host-side, no hardware). "
        "Implements ONLY the CONFIRMED grammar from doc/manual/program-formats.md.",
        epilog="Exit 0=valid, 1=invalid, 2=error. COM/DIP is decided by the first-chunk rule: "
        "<14 bytes or first word != C9 C8 -> COM.",
    )
    p.add_argument("file", nargs="?", help="path to image file (if omitted, reads stdin)")
    p.add_argument("--json", action="store_true", help="emit JSON instead of human text")
    p.add_argument("-v", "--verbose", action="store_true", help="include warnings")
    p.add_argument("--expect", choices=["COM", "DIP"], help="fail if kind != expected")
    args = p.parse_args(argv)

    if args.file is None or args.file == "-":
        data = sys.stdin.buffer.read()
        name = "<stdin>"
    else:
        path = Path(args.file)
        if not path.is_file():
            print(f"error: not found: {args.file}", file=sys.stderr)
            return 2
        data = path.read_bytes()
        name = str(path)

    res = validate(data)

    # optional kind expectation
    if args.expect and res.kind != args.expect:
        msg = f"kind mismatch: got {res.kind}, expected {args.expect}"
        if args.json:
            out = {
                "file": name,
                "kind": res.kind,
                "valid": False,
                "errors": [str(e) for e in res.errors] + [msg],
                "data_len": res.data_len,
            }
            json.dump(out, sys.stdout, indent=2)
            sys.stdout.write("\n")
        else:
            print(format_result(res, verbose=args.verbose))
            print(f"error: {msg}", file=sys.stderr)
        return 1

    if args.json:
        out = {
            "file": name,
            "kind": res.kind,
            "valid": res.valid,
            "data_len": res.data_len,
            "header": None
            if res.header is None
            else {
                "magic": f"0x{res.header.magic:04X}",
                "system_id": f"0x{res.header.system_id:04X}",
                "entry_bank_offset": res.header.entry_bank_offset,
                "image_size": res.header.image_size,
                "image_size_clamped": res.header.image_size_clamped,
                "image_size_was_clamped": res.header.image_size_was_clamped,
                "run_bank_offset": res.header.run_bank_offset,
                "entry_address": f"0x{res.header.entry_address:04X}",
                "block_count": res.header.block_count,
            },
            "blocks": [
                {
                    "index": b.index,
                    "type": b.type,
                    "dest_bank_offset": b.dest_bank_offset,
                    "dest_address": f"0x{b.dest_address:04X}",
                    "payload_len": b.payload_len,
                }
                for b in res.blocks
            ],
            "trailing_bytes": res.trailing_bytes,
            "errors": [
                {"identifier": e.identifier, "code": e.code, "message": e.message, "detail": e.detail, "text": str(e)}
                for e in res.errors
            ],
            "warnings": [
                {"identifier": w.identifier, "message": w.message, "detail": w.detail, "text": str(w)}
                for w in res.warnings
            ],
        }
        json.dump(out, sys.stdout, indent=2)
        sys.stdout.write("\n")
    else:
        print(f"file: {name}")
        print(format_result(res, verbose=args.verbose))

    return 0 if res.valid else 1


if __name__ == "__main__":
    raise SystemExit(main())
