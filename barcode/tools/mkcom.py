#!/usr/bin/env python3
"""Wrap the assembled decoder as a .COM that copies it up and installs it.

The alternative to a DIP, and simpler to build: a flat image that carries
the decoder as data, copies it into fixed RAM when it runs, and points the
hook socket at the copy.  Unbanked RAM is mapped throughout, so an LDIR
reaches it with no ceremony.

The trade-off against a DIP is only that the payload is carried twice --
once in the image, once at its destination -- and that placement happens at
run time rather than load time.
"""
import argparse
import sys
from pathlib import Path

HOOK_THUNK = 0xFBC0
HOOK_BANK = 0xFBC1
HOOK_ADDR = 0xFBC2
COM_ORIGIN = 0x0100


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("binary", type=Path, help="assembled decoder")
    ap.add_argument("-o", "--output", type=Path, required=True)
    ap.add_argument("--addr", type=lambda s: int(s, 16), default=0xC000,
                    help="where the decoder is linked (hex, default C000)")
    ap.add_argument("--bank", type=int, default=0)
    args = ap.parse_args()

    payload = args.binary.read_bytes()
    end = args.addr + len(payload)
    if end > 0xD081:
        sys.exit(f"decoder ends at {end:04X}, past the D081h load ceiling")
    if args.addr < 0x8000:
        sys.exit(f"{args.addr:04X} is in the banked window; a hook there dies "
                 "when the next program loads")

    # The payload is appended after the loader, so its address depends on
    # the loader's own length.  Build with a placeholder, measure, patch.
    def loader(payload_src):
        return bytes([
            0x21, payload_src & 0xFF, payload_src >> 8,     # LD HL,payload
            0x11, args.addr & 0xFF, args.addr >> 8,         # LD DE,dest
            0x01, len(payload) & 0xFF, len(payload) >> 8,   # LD BC,length
            0xED, 0xB0,                                     # LDIR
            0x21, args.addr & 0xFF, args.addr >> 8,         # LD HL,dest
            0x22, HOOK_ADDR & 0xFF, HOOK_ADDR >> 8,         # LD (FBC2),HL
            0x3E, args.bank & 0xFF,                         # LD A,bank
            0x32, HOOK_BANK & 0xFF, HOOK_BANK >> 8,         # LD (FBC1),A
            0x3E, 0xD7,                                     # LD A,0D7h (RST 10h)
            0x32, HOOK_THUNK & 0xFF, HOOK_THUNK >> 8,       # LD (FBC0),A
            0xC9,                                           # RET
        ])

    code = loader(0)                       # length is independent of the operand
    code = loader(COM_ORIGIN + len(code))  # now place the payload after it

    args.output.write_bytes(code + payload)
    print(f"{args.output}: {len(code) + len(payload)} bytes "
          f"({len(code)}-byte loader, {len(payload)} decoder -> {args.addr:04X}h)")


if __name__ == "__main__":
    main()
