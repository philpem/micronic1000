#!/usr/bin/env python3
"""Assemble the link exerciser and patch it into a copy of ROM00.

Produces a burnable image; the original micron1.bin is never modified.  The
code is split across the two runs of 00 filler that ROM00 has room in, and
every edit is checked before it is applied:

  1. 724C-7302 (183 bytes) takes the helpers and the beacon;
  2. 7E96-7FF9 (356 bytes) takes the main body;

     both must be entirely zero beforehand -- if either is not, this ROM is
     not the one this script was written against and it refuses rather than
     clobbering code;

  3. the cold-boot entry at 014B is replaced with a jump to the exerciser,
     a three-byte edit, after checking it still holds the prologue we expect.

The two sections are one assembly, so they can call each other by name.  ORG
pads forward, so the blob spans the firmware that sits between them -- only
the two real regions are ever copied out of it.

Usage:  build.py [-o OUT]        default out: micron1_exerciser.bin
"""
import sys, pathlib, argparse

HERE = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))
from micronic.z80asm import assemble

REGIONS = [("vec", 0x00A2, 0x00FF, "vec_end"),
           ("lo",  0x724C, 0x7302, "lo_end"),
           ("mid", 0x7CE0, 0x7D0F, "mid_end"),
           ("hi",  0x7E96, 0x7FF9, "hi_end")]
# The cold-boot entry itself, not the vector that reaches it: 0000 jumps to
# 0103 which jumps here, and the emulator harness starts directly at 014B, so
# patching here is exercised identically on hardware and in the emulator.
BOOT_ENTRY = 0x014B
BOOT_ORIG  = bytes.fromhex("f3 2a d0 fb f9 ed 56")   # DI/LD HL,(FBD0)/LD SP,HL/IM 1

ap = argparse.ArgumentParser()
ap.add_argument("-o", "--out", default=str(HERE / "micron1_exerciser.bin"))
ap.add_argument("--rom", default=str(HERE.parent.parent / "micronic" / "micron1.bin"))
a = ap.parse_args()

orig = pathlib.Path(a.rom).read_bytes()
if len(orig) != 0x8000:
    sys.exit(f"expected a 32K image, got {len(orig)}")
rom = bytearray(orig)

base = REGIONS[0][1]
code, sym = assemble((HERE / "exerciser.asm").read_text(), origin=base)

entry = sym.get("start")
if entry is None:
    sys.exit("no 'start' label")

for name, lo, hi, endsym in REGIONS:
    end = sym.get(endsym)
    if end is None:
        sys.exit(f"no '{endsym}' label")
    used = end - lo
    if end > hi + 1:
        sys.exit(f"{name} section is {used} bytes, overruns {lo:04X}-{hi:04X} "
                 f"by {end - hi - 1}")
    if any(orig[lo:hi + 1]):
        sys.exit(f"{lo:04X}-{hi:04X} is not empty in this image -- refusing to patch")
    rom[lo:end] = code[lo - base:end - base]
    print(f"{name}  {used:3d} bytes at {lo:04X}-{end-1:04X} "
          f"({hi - end + 1} free)")

if bytes(orig[BOOT_ENTRY:BOOT_ENTRY + len(BOOT_ORIG)]) != BOOT_ORIG:
    sys.exit(f"{BOOT_ENTRY:04X} does not hold the expected cold-boot prologue -- refusing")
rom[BOOT_ENTRY:BOOT_ENTRY + 3] = bytes([0xC3]) + entry.to_bytes(2, "little")

pathlib.Path(a.out).write_bytes(rom)
print(f"boot entry {BOOT_ENTRY:04X}: JP {entry:04X} (was {BOOT_ORIG.hex(' ')})")
print(f"wrote {a.out}")
print(f"\nbytes changed vs the original: "
      f"{sum(1 for i in range(0x8000) if rom[i] != orig[i])}")
# The chips are labelled with this number (DIP1 ACF8, DIP2 2E12) -- see
# doc/re-notes/method.md.  Label the burned part with the one printed here so
# it is never mistaken for a stock ROM.
print(f"sum16: {sum(orig)&0xFFFF:04X} in -> {sum(rom)&0xFFFF:04X} out")
