#!/usr/bin/env python3
"""watch_queue.py - catch the deferred-call queue consumer red-handed.

Runs DIPOSB dispatcher startup (ram:D681) under the z80-module
emulator with a Python-side memory mirror:
  * every CPU memory read/write is served/captured through callbacks,
    so we can log ANY access into the deferred-call queue arena
    (ED1C-F17F) together with the PC that made it.
  * fn=2 enqueue writes will show up with PC in D733-D748;
    THE CONSUMER will show up with some other PC - that's the target.
"""
import sys

B0 = open("/home/philpem/Micronic-1000/micronic/micron1.bin", "rb").read()
B1 = open("/home/philpem/Micronic-1000/micronic/micron2.bin", "rb").read()

import z80

# ---------------------------------------------------------------- memory
mem = bytearray(0x10000)
mem[0x0000:0x8000] = B0                      # bank 0 mapped at reset
mem[0xD681:0xD681+0x212] = B0[0x7030:0x7242] # dispatch module
mem[0xF180:0xF180+0x50D] = B0[0x369D:0x369D+0x50D]  # kernel image
pat = mem[0xD6D7:0xD6DB]                     # LD HL,1 / RET
off = 0xED1C
while off < 0xF180:
    mem[off:off+4] = pat
    off += 4
mem[0xFD84:0xFD84+19] = B0[0x2352:0x2352+13+6]
mem[0xFE93:0xFEA3] = B0[0x3257:0x3267]
mem[0xFE83:0xFE93] = B0[0x3267:0x3277]

QLO, QHI = 0xED1C, 0xF17F

reads_q = []      # (pc, addr) queue-arena READS
writes_q = []     # (pc, addr, val) queue-arena WRITES
all_writers = {}

def rd_cb(addr):
    if QLO <= addr <= QHI:
        reads_q.append((mach.pc, addr))
    return mem[addr & 0xFFFF]

def wr_cb(addr, val):
    mem[addr & 0xFFFF] = val & 0xFF
    if QLO <= addr <= QHI:
        writes_q.append((mach.pc, addr, val & 0xFF))
        all_writers[mach.pc] = all_writers.get(mach.pc, 0) + 1

def in_cb(*a):
    port = a[0] if a else 0
    if isinstance(port, tuple):
        port = port[0]
    return 0x00 if port == 0x28 else 0xFF

def out_cb(*a):
    pass  # bank switching not needed for this window

mach = z80.Z80Machine()
mach.set_memory_block(0, bytes(mem))
mset = mach.get_state_view()
try:
    mach.set_read_callback(rd_cb)
    mach.set_write_callback(wr_cb)
    mach.set_input_callback(in_cb)
    mach.set_output_callback(out_cb)
except TypeError as e:
    print("callback signature problem:", e)
    sys.exit(2)

mach.pc = 0xD681
mach.sp = 0xF000

print("running dispatcher startup...")
try:
    for chunk in range(400):
        if mach.pc == 0xD6AC:
            print("IDLE REACHED")
            break
        if mach.halted:
            print("HALTED")
            break
        mach.ticks_to_stop = 500_000
        mach.run()
except Exception as e:
    print("emulator exception:", type(e).__name__, e)

print(f"stopped: PC={mach.pc:04X} SP={mach.sp:04X}")

print(f"\nqueue-arena READS: {len(reads_q)}")
for pc, a in reads_q[:25]:
    print(f"   READ  {a:04X} from PC={pc:04X}")
print(f"queue-arena WRITES: {len(writes_q)}")
pcs = sorted(all_writers.items(), key=lambda kv: -kv[1])
for pc, n in pcs[:15]:
    print(f"   writer PC={pc:04X} x{n}")
if writes_q:
    print(f"   arena write range: {min(w[1] for w in writes_q):04X}..{max(w[1] for w in writes_q):04X}")
