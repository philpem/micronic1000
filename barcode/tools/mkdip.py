#!/usr/bin/env python3
"""Wrap the assembled decoder as a .DIP image that installs itself.

A DIP is the tidiest way to get resident code onto the handheld: the
loader places each block for you, and a block's destination may be
anywhere up to the load ceiling at D081h -- which is above 8000h, so the
payload lands in fixed, battery-backed, bank-independent RAM.  That is
verified, not assumed; see doc/reference/program-formats.md.

The image has two blocks:

    block 0   the decoder, at its link address (default C000h)
    block 1   a small installer stub at 0100h, which the loader runs

The stub is needed because a block cannot write the hook socket itself:
FBC0h is above the D081h ceiling, so the loader would reject it.
"""
import argparse
import struct
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT / "analysis"))
from micronic.program import build_dip_file          # noqa: E402

HOOK_THUNK = 0xFBC0
HOOK_BANK = 0xFBC1
HOOK_ADDR = 0xFBC2


def installer_stub(decoder_addr, bank=0):
    """Z80 that points the hook socket at the decoder, then returns.

    Writing the three cells directly rather than calling the firmware's
    installer keeps ram:F9B0, the scan re-arm window, exactly as the
    system left it -- the documented call consumes HL for that and a
    caller who does not know to set it corrupts it.
    """
    return bytes([
        0x21, decoder_addr & 0xFF, decoder_addr >> 8,   # LD HL,decoder
        0x22, HOOK_ADDR & 0xFF, HOOK_ADDR >> 8,         # LD (FBC2),HL
        0x3E, bank & 0xFF,                              # LD A,bank
        0x32, HOOK_BANK & 0xFF, HOOK_BANK >> 8,         # LD (FBC1),A
        0x3E, 0xD7,                                     # LD A,0D7h  (RST 10h)
        0x32, HOOK_THUNK & 0xFF, HOOK_THUNK >> 8,       # LD (FBC0),A
        0xC9,                                           # RET
    ])


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("binary", type=Path, help="assembled decoder")
    ap.add_argument("-o", "--output", type=Path, required=True)
    ap.add_argument("--addr", type=lambda s: int(s, 16), default=0xC000,
                    help="where the decoder is linked (hex, default C000)")
    ap.add_argument("--bank", type=int, default=0,
                    help="bank byte for the hook socket (default 0)")
    args = ap.parse_args()

    payload = args.binary.read_bytes()
    end = args.addr + len(payload)
    if end > 0xD081:
        sys.exit(f"decoder ends at {end:04X}, past the D081h load ceiling")
    if args.addr < 0x8000:
        sys.exit(f"{args.addr:04X} is in the banked window; a hook there dies "
                 "when the next program loads")

    stub = installer_stub(args.addr, args.bank)
    image = build_dip_file(
        header_kwargs={"system_id": 0x00E5, "entry_bank_offset": 0,
                       "image_size": len(stub), "run_bank_offset": 0,
                       "entry_address": 0x0100},
        blocks=[(0, 0, args.addr, payload),
                (0, 0, 0x0100, stub)])
    args.output.write_bytes(image)
    print(f"{args.output}: {len(image)} bytes "
          f"({len(payload)} decoder at {args.addr:04X}h, "
          f"{len(stub)}-byte installer at 0100h)")


if __name__ == "__main__":
    main()
