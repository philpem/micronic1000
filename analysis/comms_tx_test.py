#!/usr/bin/env python3
"""Directed comparison of LinkBlockTx output with a seeded descriptor.

Seeds the session/link state and calls LinkTransferService (2F86)
which runs the firmware's own frame serialisation to port 4Dh. We
capture every 4Dh write and compare the complete prelude-plus-payload stream.
This verifies mechanical descriptor pumping, not a Commstar session grammar.

Run: python3 comms_tx_test.py
"""
import gc; gc.disable()
import sys
import z80
sys.path.insert(0, "/home/philpem/Micronic-1000/analysis")
from micronic import proto

B0 = open("/home/philpem/Micronic-1000/micronic/micron1.bin","rb").read()
B1 = open("/home/philpem/Micronic-1000/micronic/micron2.bin","rb").read()
mem = bytearray(0x10000)
mem[0:0x8000] = B0
mem[0xD681:0xD681+0x212] = B0[0x7030:0x7242]
mem[0xF180:0xF180+0x50D] = B0[0x369D:0x369D+0x50D]
pat = bytes([0x21,1,0,0xC9])
for off in range(0xED1C,0xF180,4): mem[off:off+4] = pat
mem[0xFD84:0xFD84+19] = B0[0x2352:0x2352+19]
mem[0xFE93:0xFEA3] = B0[0x3257:0x3267]
mem[0xFE83:0xFE93] = B0[0x3267:0x3277]
mem[0xFC05] = 0x70

# ---- seed the link state for a TX --------------------------------
LINK_ID = 0x45               # 'E' - the commstar-open default
mem[0xFDD4] = LINK_ID        # fdd4 = link id
mem[0xFDD5] = 0x03           # fdd5 = 3 (connected/data) - TX path
mem[0xFDD6] = 0x01           # fdd6 = link-ready retry (30FC: 0 -> not ready)
# TX buffer at FDEA is a DESCRIPTOR: {count_lo, count_hi, ptr_lo, ptr_hi}
# 3508 reads C=[0],B=[1],E=[2],D=[3]; sends `count` bytes from *(DE).
PAYLOAD = bytes([0x04, 0x44, 0x00, 0x41, 0x42, 0x43, 0x44])
PAYPTR = 0xFD00   # arbitrary free RAM for the payload
mem[PAYPTR:PAYPTR+len(PAYLOAD)] = PAYLOAD
mem[0xFDEA] = len(PAYLOAD) & 0xFF
mem[0xFDEB] = (len(PAYLOAD) >> 8) & 0xFF
mem[0xFDEC] = PAYPTR & 0xFF
mem[0xFDED] = (PAYPTR >> 8) & 0xFF
mem[0xFDD8] = len(PAYLOAD)   # fdd8 = tx length (used by service)

# ---- capture port 4Dh (TX) and 4A/4B/4C/4F ----
outb4d = []
other = []
def rd(a): return mem[a & 0xFFFF]
def wr(a,v): mem[a & 0xFFFF] = v & 0xFF
def ich(*a):
    p = a[0]; p = p[0] if isinstance(p,tuple) else p; p &= 0xFF
    if p == 0x4B: return 0x80      # Bit7 set; bits 4, 5, and 6 clear.
    if p == 0x05: return 0x19
    if p == 0x28: return 0x00
    if p == 0x00: return 0x00
    if p == 0x49: return 0x00
    return 0x00
def och(*a):
    p,v = (a[0],a[1]) if len(a)>=2 else (a[0],0xFF)
    p = p[0] if isinstance(p,tuple) else p; p &= 0xFF; v &= 0xFF
    if p == 0x4D:
        outb4d.append(v & 0xFF)
    elif p in (0x4A,0x4B,0x4C,0x4F):
        other.append((p,v))
    elif p == 0x47:
        img = B0 if v==0 else B1 if v==1 else b"\x00"*0x8000
        mem[0:0x8000]=img; mem[0xF791]=v

mach = z80.Z80Machine()
mach.set_memory_block(0, bytes(mem))
mach.set_read_callback(rd); mach.set_write_callback(wr)
mach.set_input_callback(ich); mach.set_output_callback(och)
mach.pc = 0x2F86          # LinkTransferService entry
mach.sp = 0xF000

# Run until the complete seeded descriptor has been emitted or we time out.
import time
t0=time.time()
expected = bytes([LINK_ID & 0x1F]) + PAYLOAD
for _ in range(20000):
    mach.ticks_to_stop = 20000
    mach.run()
    if len(outb4d) >= len(expected):
        break
    if time.time()-t0 > 20:
        print("TIMEOUT waiting for TX bytes; pc=", hex(mach.pc))
        break
print("captured 4Dh bytes:", [f"{b:02X}" for b in outb4d])
print("expected bytes:", [f"{b:02X}" for b in expected])
print("other link-port traffic:", [ (hex(p),hex(v)) for p,v in other])
if bytes(outb4d) != expected:
    raise SystemExit("incomplete or mismatched directed TX trace")
