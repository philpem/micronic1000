#!/usr/bin/env python3
"""Gap / coverage analysis for the Micronic 1000 ROMs.

Computes, for each ROM bank:
  - overall byte coverage by defined functions (vs Ghidra find_code_gaps)
  - the unanalysed gaps, classified as real-code vs data/pointer tables
  - candidate *function entry points* inside those gaps (direct CALL targets),
    which Ghidra missed because they are reached via the deferred-call queue,
    jump tables or the RAM-installed kernel (not toasted by linear sweep).

Used to drive GapAnalysis and CDoc updates (see doc/gap-analysis.md).
"""
import json
from z80 import Z80InstrBuilder

B0 = open("/home/philpem/Micronic-1000/micronic/micron1.bin","rb").read()
B1 = open("/home/philpem/Micronic-1000/micronic/micron2.bin","rb").read()
BUILD = Z80InstrBuilder()
ROM = {"ROM00": B0, "ROM01": B1}
SIZE = 0x8000

# find_code_gaps output (ROM01); the authoritative uncovered ranges.
ROM01_GAPS = [
 (0x0000,0x0007),(0x000b,0x001f),(0x0033,0x00ee),(0x02df,0x0302),(0x0309,0x0328),
 (0x03c3,0x0740),(0x092f,0x09c1),(0x0a67,0x0cca),(0x0ce7,0x0dee),(0x0df4,0x106e),
 (0x10cf,0x10ee),(0x115f,0x117d),(0x11e5,0x13ee),(0x14c8,0x1709),(0x1803,0x1adc),
 (0x1b7d,0x2115),(0x2120,0x214b),(0x2159,0x2296),(0x254b,0x2658),(0x288c,0x28e9),
 (0x28ed,0x28fd),(0x2b7b,0x2c23),(0x2c27,0x2c4e),(0x2c95,0x2cab),(0x2caf,0x2cd2),
 (0x34ab,0x356d),(0x3624,0x36f2),(0x38ef,0x3986),(0x3a1c,0x3adc),(0x3b56,0x3b7a),
 (0x3fcb,0x40c3),(0x4367,0x444e),(0x4587,0x45d0),(0x45d4,0x462e),(0x4981,0x4faf),
 (0x51c1,0x564b),(0x576c,0x5839),(0x5859,0x5990),(0x5994,0x627f),(0x6292,0x65bf),
 (0x65e3,0x6601),(0x6621,0x6759),(0x6768,0x6f28),(0x7121,0x71aa),(0x71e2,0x7205),
 (0x7279,0x7fff),
]

def instr_size(rom, off):
    op = rom[off]
    if op in (0xCB,0xDD,0xED,0xFD):
        return 2
    return {0x01:3,0xc3:3,0xcd:3,0x11:3,0x21:3,0x31:3,0x06:2,0x0e:2,0x16:2,0x1e:2,
            0x26:2,0x2e:2,0xc6:2,0xd3:2,0xdb:2,0xe6:2,0xee:2,0xf6:2,0xfe:2,0x18:2,
            0x20:2,0x28:2,0x30:2,0x38:2,0x10:2}.get(op, 1)

def classify(rom, s, e):
    b = rom[s:e+1]; n = len(b)
    if n < 4:
        return 'tiny', 0.0, 0.0, 0.0
    printable = sum(1 for x in b if 32 <= x < 127); zeros = b.count(0)
    fr, fz = printable/n, zeros/n
    words = b if n % 2 == 0 else b[:-1]
    ptrs = 0; nw = len(words)//2
    for i in range(0, len(words)-1, 2):
        w = words[i] | (words[i+1] << 8)
        if 0x0000 < w < 0x8000:
            ptrs += 1
    fp = ptrs/max(1, nw)
    off = 0; bad = 0
    while off < n:
        try:
            ins = BUILD.build_instr(s+off, rom[s+off:])
            sz = max(1, getattr(ins, "size", 0)) or instr_size(rom, s+off)
        except Exception:
            sz = 1; bad += 1
        off += sz
    if fp > 0.62 and fr < 0.55:
        return 'PTR-TABLE', fr, fz, fp
    if fr > 0.62:
        return 'STRINGS', fr, fz, fp
    if fz > 0.40:
        return 'DATA', fr, fz, fp
    if bad/n > 0.35:
        return 'MIXED', fr, fz, fp
    return 'CODE', fr, fz, fp

def caller_targets(rom):
    """CALL nn targets indexed to their callers (whole ROM)."""
    tgt = {}
    off = 0; n = len(rom)
    while off < n:
        op = rom[off]
        if op == 0xCD and off+2 < n:
            t = rom[off+1] | (rom[off+2] << 8)
            tgt.setdefault(t, set()).add(off)
            off += 3; continue
        if op in (0xC3,):  # JP nn - can be a tail-call (not a function entry)
            off += 3; continue
        off += instr_size(rom, off)
    return tgt

def main():
    t01 = caller_targets(B1)
    got_gap = 0
    print("Micronic 1000 ROM gap analysis")
    print("=" * 60)
    print("ROM01: %d gaps, %d bytes of %d (%.1f%%) uncovered by functions"
          % (len(ROM01_GAPS), sum(e-s+1 for s, e in ROM01_GAPS),
             SIZE, 100*sum(e-s+1 for s, e in ROM01_GAPS)/SIZE))
    print()
    rows = []
    for (gs, ge) in sorted(ROM01_GAPS, key=lambda g: -(g[1]-g[0])):
        cls, fr, fz, fp = classify(B1, gs, ge)
        entries = sorted({t for t in t01 if gs <= t <= ge})
        rows.append((gs, ge, ge-gs+1, cls, entries))
    # coverage buckets
    from collections import defaultdict
    bycls = defaultdict(int)
    for gs, ge, n, cls, _ in rows:
        bycls[cls] += n
    print("Uncovered-by-class (bytes):")
    for cls, n in sorted(bycls.items(), key=lambda kv: -kv[1]):
        print("   %-10s %5d (%.1f%%)" % (cls, n, 100*n/SIZE))
    print()
    print("CODE/MIXED gaps with candidate function entries (gap:size -> CALL-targets):")
    for gs, ge, n, cls, entries in rows:
        if cls in ('CODE', 'MIXED') and entries:
            print("  %04X-%04X %4d  [%s]  entries=%s"
                  % (gs, ge, n, cls, " ".join("%04X" % t for t in entries)))
    print()
    print("Note: 'PTR-TABLE'/'DATA' gaps may still contain jumped-to code;")
    print("the origin of every candidate entry is the strong 'create function' signal.")
    return rows

if __name__ == "__main__":
    main()