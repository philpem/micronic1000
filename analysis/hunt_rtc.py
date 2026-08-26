#!/usr/bin/env python3
"""hunt_rtc.py - find the HD146818 by watching ALL bus traffic during
self-test. Runs from dispatcher startup through the self-test window,
logging every read/write outside already-known regions, then reports
clusters - looking for a small window receiving BCD-style values
(seconds/minutes/hours = <=59/<=23 etc.) read repeatedly.
"""
import sys

B0 = open("/home/philpem/Micronic-1000/micronic/micron1.bin", "rb").read()
import z80

mem = bytearray(0x10000)
mem[0x0000:0x8000] = B0
mem[0xD681:0xD681+0x212] = B0[0x7030:0x7242]
mem[0xF180:0xF180+0x50D] = B0[0x369D:0x369D+0x50D]
pat = mem[0xD6D7:0xD6DB]
off = 0xED1C
while off < 0xF180:
    mem[off:off+4] = pat
    off += 4
# seeds
mem[0xFD84:0xFD84+19] = B0[0x2352:0x2352+19]
mem[0xFE93:0xFEA3] = B0[0x3257:0x3267]
mem[0xFE83:0xFE93] = B0[0x3267:0x3277]
mem[0xFC05] = 0x70

# known/benign regions we don't need logged
KNOWN = [(0xD681, 0xD893), (0xED1C, 0xF17F), (0xF180, 0xF68D),
         (0xFD00, 0xFEFF), (0xE200, 0xE710), (0xD081, 0xD480)]
def known(a):
    return any(lo <= a <= hi for lo, hi in KNOWN)

log_reads = []
log_writes = {}

def rd_cb(addr):
    addr &= 0xFFFF
    v = mem[addr]
    if not known(addr):
        log_reads.append((mach.pc, addr))
    return v

def wr_cb(addr, val):
    addr &= 0xFFFF
    mem[addr] = val & 0xFF
    if not known(addr):
        e = log_writes.get(addr)
        if e is None:
            log_writes[addr] = [mach.pc, [val]]
        else:
            e[1].append(val)

def in_cb(*a):
    p = a[0]
    if isinstance(p, tuple): p = p[0]
    return 0x00 if p == 0x28 else 0xFF

def out_cb(*a):
    pass

mach = z80.Z80Machine()
mach.set_memory_block(0, bytes(mem))
mach.set_read_callback(rd_cb)
mach.set_write_callback(wr_cb)
mach.set_input_callback(in_cb)
mach.set_output_callback(out_cb)
mach.pc = 0xD681
mach.sp = 0xF000

print("running...")
try:
    for chunk in range(1200):
        if mach.halted:
            break
        if mach.pc == 0xD6AC or mach.pc == 0x22E8:
            print(f"parked/IDLE at PC={mach.pc:04X} after chunk {chunk}")
            break
        mach.ticks_to_stop = 500_000
        mach.run()
except Exception as e:
    print("exception:", type(e).__name__, e)

print(f"final PC={mach.pc:04X}  reads_logged={len(log_reads)}  addrs_written={len(log_writes)}")

# cluster reads: group consecutive-ish addresses
from collections import Counter, defaultdict
rc = Counter(a for _, a in log_reads)
print("\n--- most-read unknown addresses ---")
for a, n in rc.most_common(30):
    print(f"  {a:04X} x{n}")

# BCD detector: addresses whose write values are all valid BCD pairs
def bcd_ok(vals):
    return all((v <= 0x99) and ((v & 0x0F) <= 9) for v in vals) and len(vals) >= 2

print("\n--- write clusters w/ BCD-like content ---")
addrs = sorted(log_writes.keys())
cluster = []
clusters = []
for a in addrs:
    if cluster and a - cluster[-1] > 4:
        clusters.append(cluster); cluster = []
    cluster.append(a)
if cluster: clusters.append(cluster)
for cl in clusters:
    vals = sum((log_writes[a][1] for a in cl), [])
    if len(cl) >= 4 and bcd_ok(vals):
        print(f"  {cl[0]:04X}-{cl[-1]:04X} ({len(cl)} addrs) vals={vals[:24]}")

print("\n--- read PCs (who touches unknown space) ---")
pc_c = Counter(pc for pc, _ in log_reads)
for pc, n in pc_c.most_common(15):
    print(f"  PC={pc:04X} x{n}")
