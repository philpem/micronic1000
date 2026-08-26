#!/usr/bin/env python3
"""Decode DIPOSB boot-load chains and analyse fn=2 enqueued far-call targets.

Chains live at the tail of each ROM bank, pointed to by (0x7FFC):
  bank 0 (micron1.bin): 0x7D58
  bank 1 (micron2.bin): 0x7E15

Grammar (confirmed from dispatcher handlers):
  {fn=0000, addr, count}      memset(addr, 0, count)
  {fn=0001, src, dst, count}  memcpy(dst <- src, count)
  {fn=0002, N, word[N]}       enqueue N deferred banked-call stubs
  {fn=FFFF}                   terminate
"""
import sys
from collections import Counter

BANK0 = open("/home/philpem/Micronic-1000/micronic/micron1.bin", "rb").read()
BANK1 = open("/home/philpem/Micronic-1000/micronic/micron2.bin", "rb").read()

def w(b, o): return b[o] | (b[o+1] << 8)

def decode_chain(bank, start, name):
    print(f"\n=== {name}: chain at {start:04X} ===")
    off = start
    records = []
    enqueued = []
    while True:
        fn = w(bank, off)
        if fn == 0xFFFF:
            print(f"  {off:04X}  FFFF terminate")
            records.append(("term", off))
            break
        elif fn == 0x0000:
            addr, cnt = w(bank, off+2), w(bank, off+4)
            print(f"  {off:04X}  memset {addr:04X}..{addr+cnt-1:04X} ({cnt})")
            records.append(("memset", off, addr, cnt)); off += 6
        elif fn == 0x0001:
            src, dst, cnt = w(bank, off+2), w(bank, off+4), w(bank, off+6)
            print(f"  {off:04X}  memcpy {dst:04X} <- {src:04X} ({cnt})")
            records.append(("memcpy", off, src, dst, cnt)); off += 8
        elif fn == 0x0002:
            n = w(bank, off+2)
            words = [w(bank, off+4+2*i) for i in range(n)]
            print(f"  {off:04X}  enqueue N={n}")
            for i, t in enumerate(words):
                print(f"        [{i:3d}] call bank[f791]:{t:04X}")
            records.append(("enqueue", off, n, words)); enqueued.extend(words)
            off += 4 + 2*n
        else:
            print(f"  {off:04X}  UNKNOWN fn={fn:04X} - stop")
            records.append(("unknown", off, fn))
            break
    return records, enqueued

def region(addr):
    if 0x369D <= addr < 0x3BAA: return "kernel-image(F180 copy)"
    if 0x0100 <= addr < 0x1900: return "low-ROM(vectors/dispatch/selftest)"
    if 0x1900 <= addr < 0x2300: return "tty/lcd/console"
    if 0x2300 <= addr < 0x2600: return "irq-worker/comms-cfg"
    if 0x2800 <= addr < 0x3000: return "selftest/powerdown"
    if 0x3000 <= addr < 0x3700: return "cfg/kernel-install"
    if 0x4300 <= addr < 0x4700: return "commstar-session"
    if 0x7000 <= addr < 0x8000: return "dispatch-module/scripts"
    return "uncharacterised"

recs_a, words_a = decode_chain(BANK0, 0x7D58, "bank 0")
recs_b, words_b = decode_chain(BANK1, 0x7E15, "bank 1")

for label, words in (("chain A", words_a), ("chain B", words_b)):
    print(f"\n--- {label}: {len(words)} enqueued far-call targets ---")
    c = Counter(words)
    for t, n in sorted(c.items()):
        print(f"  {t:04X} x{n:<2}  [{region(t)}]")
    regs = Counter(region(t) for t in words)
    print("  by region:", dict(regs))

# both = set(words_a) & set(words_b)
both = set(words_a) & set(words_b)
print(f"\ntargets enqueued by BOTH chains: {len(both)} -> {sorted(hex(x) for x in both)[:20]}")

