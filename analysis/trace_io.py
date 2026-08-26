#!/usr/bin/env python3
import gc
gc.disable()  # slice-assign inside port callbacks can re-enter GC
"""trace_io.py - chronological I/O trace focused on the boot RTC/status
window. Starts at 0202h (first status-device call) with a sane stack,
so we skip the slow byte-wise RAM test entirely.

Note: the z80 module reports the full 16-bit I/O address for
`OUT (n),A` as (A<<8)|n; ports are masked to 8 bits below because all
peripherals decode only the low byte.
"""
from collections import Counter
import z80

B0 = open("/home/philpem/Micronic-1000/micronic/micron1.bin", "rb").read()
B1 = open("/home/philpem/Micronic-1000/micronic/micron2.bin", "rb").read()

mem = bytearray(0x10000)
mem[0x0000:0x8000] = B0
mem[0xD681:0xD681+0x212] = B0[0x7030:0x7242]         # dispatch module
mem[0xF180:0xF180+0x50D] = B0[0x369D:0x369D+0x50D]   # kernel image
pat = bytes([0x21, 0x01, 0x00, 0xC9])
off = 0xED1C
while off < 0xF180:
    mem[off:off+4] = pat
    off += 4
mem[0xFD84:0xFD84+19] = B0[0x2352:0x2352+19]
mem[0xFE93:0xFEA3] = B0[0x3257:0x3267]
mem[0xFE83:0xFE93] = B0[0x3267:0x3277]
mem[0xFC05] = 0x70

RAM_PAGES = [bytearray(0x8000) for _ in range(6)]
cur_bank = 0

io_log = []

def rd_cb(addr):
    return mem[addr & 0xFFFF]

def wr_cb(addr, val):
    mem[addr & 0xFFFF] = val & 0xFF

def in_cb(*a):
    port = a[0]
    if isinstance(port, tuple):
        port = port[0]
    port &= 0xFFFF
    # realistic idle levels:
    #   28h : comms status - bit7 clear = ready
    #   49h : boot keys - bits clear = none held -> normal cold start
    #   00h : keyboard sense - 0 = no keys pressed (active high)
    if port == 0x28 or port == 0x49 or port == 0x00:
        v = 0x00
    else:
        v = 0xFF
    io_log.append((mach.pc & 0xFFFF, "IN", port & 0xFF, v))
    return v

def out_cb(*a):
    port, val = (a[0], a[1]) if len(a) >= 2 else (a[0], 0xFF)
    if isinstance(port, tuple):
        port = port[0]
    port &= 0xFF                      # mask (A<<8)|n artefact
    val &= 0xFF
    io_log.append((mach.pc & 0xFFFF, "OUT", port & 0xFF, val & 0xFF))
    global cur_bank
    if port == 0x47:
        cur_bank = val
        if val == 0:
            img = B0
        elif val == 1:
            img = B1
        elif 2 <= val <= 7:
            img = RAM_PAGES[val - 2]
        else:
            img = b"\xff" * 0x8000
        mem[0x0000:0x8000] = img
        mem[0xF791] = val

mach = z80.Z80Machine()
mach.set_memory_block(0, bytes(mem))
mach.set_read_callback(rd_cb)
mach.set_write_callback(wr_cb)
mach.set_input_callback(in_cb)
mach.set_output_callback(out_cb)

mach.pc = 0x014B               # reset_entry
mach.sp = 0xF000
mem[0xFBD0] = 0x00             # seed saved-SP word read at entry
mem[0xFBD1] = 0xF0

print("running boot from reset_entry...")
for chunk in range(600):
    mach.ticks_to_stop = 500_000
    try:
        mach.run()
    except Exception as e:
        print(f"chunk {chunk}: {type(e).__name__}: {e} at PC={mach.pc:04X}")
        break

    # ---- RAM TEST SKIP -----------------------------------------------
    # ram_page_test_4banks fills/verifies pages byte-by-byte - far too
    # slow under emulation. Detect its entry, fake a PASS result, and
    # leave the banked RAM pages containing the final test pattern.
    if mach.pc == 0x2530:
        for pi, pg in enumerate(RAM_PAGES):
            hi = (0x80 + pi * 0x20) & 0xFF
            pg[:] = bytes([(~hi) & 0xFF]) * 0x8000
        mem[0xFEAF] = 0xFF        # all-pages-good bitmap
        mem[0xFDB0] = 0x00        # no failure flag
        mach.pc = 0x01BE          # resume right after the test
        print("[skip] RAM test bypassed with PASS result")
        continue
    # -------------------------------------------------------------------

    if mach.pc == 0x02D8:
        mach.a = 0x0D
        mach.pc = 0x02DB
        print(f"[gate] banner ENTER injected (chunk {chunk})")
        continue
    if mach.pc == 0xD6AC:
        print(f"IDLE REACHED (chunk {chunk})")
        break
    if mach.pc == 0x22E8:
        print(f"comms poll parked (chunk {chunk}, PC=22E8)")
        break
else:
    print(f"budget exhausted: PC={mach.pc:04X}")

print(f"final: PC={mach.pc:04X} SP={mach.sp:04X} bank={cur_bank}")
print(f"I/O transactions logged: {len(io_log)}")

ports = sorted({p for _, _, p, _ in io_log})
print("\nper-port counts:")
for p in ports:
    o = sum(1 for _, d, pp, _ in io_log if pp == p and d == "OUT")
    i = sum(1 for _, d, pp, _ in io_log if pp == p and d == "IN")
    print(f"  {p:02X}h  OUT x{o:<5} IN x{i:<5}")

with open("/tmp/opencode/io_trace.txt", "w") as f:
    for seq, (pc, d, p, v) in enumerate(io_log):
        f.write(f"{seq:6d}  PC={pc:04X}  {d}  {p:02X}h = {v:02X}h\n")
print("full chronological log -> /tmp/opencode/io_trace.txt")

print("\n--- first 120 transactions (chronological) ---")
for seq, (pc, d, p, v) in enumerate(io_log[:120]):
    print(f"{seq:5d}  PC={pc:04X}  {d} {p:02X}h = {v:02X}h")
