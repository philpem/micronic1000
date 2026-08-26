#!/usr/bin/env python3
"""Disassemble the chain-loaded DIPOSB modules and hunt for:
   - deferred-call queue access (ED1C arena / d684 cursor)
   - port I/O (48h/49h IR pair, 08h/28h indexed comms)
   - indirect jumps/calls (computed task entry)

Modules (source -> destination):
  A: bank0 0x73CE..0x7C2E -> ram D893..E0F3  (2145 B)
  B: bank1 0x7BCB..0x7E14 -> ram D081..D2CA  (586 B)
"""
import sys
from z80 import Z80InstrBuilder

b0 = open("/home/philpem/Micronic-1000/micronic/micron1.bin", "rb").read()
b1 = open("/home/philpem/Micronic-1000/micronic/micron2.bin", "rb").read()

MODULES = [
    ("A", b0, 0x73CE, 0x7C2F - 0x73CE, 0xD893),
    ("B", b1, 0x7BCB, 0x7E15 - 0x7BCB, 0xD081),
]

builder = Z80InstrBuilder()

def disassemble(tag, bank, src, length, dst):
    print(f"\n=== MODULE {tag}: rom {src:04X}-{src+length-1:04X} -> ram {dst:04X} ===")
    interesting = []
    off = 0
    while off < length:
        addr = dst + off          # runtime address (module runs from RAM)
        try:
            ins = builder.build_instr(addr, bank[src+off:])
            size = max(1, getattr(ins, "size", 0)) if hasattr(ins, "size") else instr_size_guess(bank[src+off])
        except Exception:
            # fall back: single byte
            off += 1
            continue
        text = str(ins)
        low = text.lower()
        hit = None
        if " out " in f" {low} " or low.startswith("out(") or ", (" in low and "out" in low:
            hit = "IO-OUT"
        if low.startswith("in ") or low.startswith("in("):
            hit = hit or "IO-IN"
        for k, v in (("ed1c", "QUEUE-BASE"), ("d684", "QUEUE-CURSOR"),
                     ("e36f", "WORKLIST"), ("e3bd", "MODPTR")):
            if v in low.replace("0x", "").replace("(", "") :
                hit = hit or f"REF-{k}"
        if "(hl)" in low and ("jp" in low or "call" in low):
            hit = hit or "INDIRECT"
        if "jp (" in low or "call (" in low or low.strip().startswith("jp ("):
            hit = hit or "INDIRECT"
        if hit:
            interesting.append((addr, text, hit))
        step = instr_size(bank, src+off)
        off += step

    for a, t, h in interesting:
        print(f"  {a:04X}  {t:<22} [{h}]")
    print(f"  ({len(interesting)} interesting sites)")

SIZE2 = {0x01:3,0x11:3,0x21:3,0x31:3,0x06:2,0x0e:2,0x16:2,0x1e:2,0x26:2,0x2e:2,
         0xc6:2,0xd3:2,0xdb:2,0xe6:2,0xee:2,0xf6:2,0xfe:2,0x18:2,0x20:2,0x28:2,
         0x30:2,0x38:2,0x10:2}
def instr_size(bank, off):
    op = bank[off]
    if op == 0xCB or op == 0xDD or op == 0xED or op == 0xFD:
        return 2  # rough; good enough for sweep
    return SIZE2.get(op, 1)

if __name__ == "__main__":
    for tag, bank, src, ln, dst in MODULES:
        disassemble(tag, bank, src, ln, dst)
