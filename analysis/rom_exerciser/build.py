#!/usr/bin/env python3
"""Assemble the link exerciser and patch it into a copy of ROM00.

Produces a burnable image; the original micron1.bin is never modified.  Two
edits are made and both are checked before they are applied:

  1. the exerciser is placed in the 7E96-7FF9 filler block, which must be
     entirely zero beforehand -- if it is not, this ROM is not the one this
     script was written against and it refuses rather than clobbering code;
  2. the cold-boot entry at 014B is replaced with a jump to the exerciser,
     a three-byte edit, after checking it still holds the prologue we expect.

Usage:  build.py [-o OUT]        default out: micron1_exerciser.bin
"""
import sys, pathlib, argparse

HERE = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))
from micronic.z80asm import assemble

ORIGIN   = 0x7E96          # start of the filler block
FREE_END = 0x7FF9          # last byte of it, inclusive
# The cold-boot entry itself, not the vector that reaches it: 0000 jumps to
# 0103 which jumps here, and the emulator harness starts directly at 014B, so
# patching here is exercised identically on hardware and in the emulator.
BOOT_ENTRY = 0x014B
BOOT_ORIG  = bytes.fromhex("f3 2a d0 fb f9 ed 56")   # DI/LD HL,(FBD0)/LD SP,HL/IM 1

ap = argparse.ArgumentParser()
ap.add_argument("-o", "--out", default=str(HERE / "micron1_exerciser.bin"))
ap.add_argument("--rom", default=str(HERE.parent.parent / "micronic" / "micron1.bin"))
a = ap.parse_args()

rom = bytearray(pathlib.Path(a.rom).read_bytes())
if len(rom) != 0x8000:
    sys.exit(f"expected a 32K image, got {len(rom)}")

code, sym = assemble((HERE / "exerciser.asm").read_text(), origin=ORIGIN)
end = ORIGIN + len(code) - 1
if end > FREE_END:
    sys.exit(f"exerciser is {len(code)} bytes, overruns the filler block by {end-FREE_END}")

if any(rom[ORIGIN:FREE_END + 1]):
    sys.exit(f"{ORIGIN:04X}-{FREE_END:04X} is not empty in this image -- refusing to patch")
if bytes(rom[BOOT_ENTRY:BOOT_ENTRY + len(BOOT_ORIG)]) != BOOT_ORIG:
    sys.exit(f"{BOOT_ENTRY:04X} does not hold the expected cold-boot prologue -- refusing")

rom[ORIGIN:ORIGIN + len(code)] = code
rom[BOOT_ENTRY:BOOT_ENTRY + 3] = bytes([0xC3]) + ORIGIN.to_bytes(2, "little")
pathlib.Path(a.out).write_bytes(rom)

print(f"exerciser  {len(code)} bytes at {ORIGIN:04X}-{end:04X} "
      f"({FREE_END-end} bytes of the block still free)")
print(f"boot entry {BOOT_ENTRY:04X}: JP {ORIGIN:04X} (was {BOOT_ORIG.hex(' ')})")
print(f"wrote {a.out}")
orig = pathlib.Path(a.rom).read_bytes()
print(f"\nbytes changed vs the original: "
      f"{sum(1 for i in range(0x8000) if rom[i] != orig[i])}")
# The chips are labelled with this number (DIP1 ACF8, DIP2 2E12) -- see
# doc/re-notes/method.md.  Label the burned part with the one printed here so
# it is never mistaken for a stock ROM.
print(f"sum16: {sum(orig)&0xFFFF:04X} in -> {sum(rom)&0xFFFF:04X} out")
