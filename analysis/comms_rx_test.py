#!/usr/bin/env python3
"""comms_rx_test.py - verify the firmware RX path by feeding it a
frame (with the unit's link id at address offset +5) and calling the
RX dispatcher (2FBD), capturing any response on port 4Dh.
"""
import gc; gc.disable()
import sys, time
sys.path.insert(0, "/home/philpem/Micronic-1000/analysis")
import z80

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

LINK_ID = 0x45
mem[0xFDD4] = LINK_ID
mem[0xFDD5] = 0x03
mem[0xFDD6] = 0x32
mem[0xFDDC] = 0x0E; mem[0xFDDD] = 0xFE   # fddc = word 0xFE0E (frame pointer)

# frame: [type=4][cmd_hi=44][cmd_lo=00][addr=LINK_ID][data="OK"]
# (LinkValidateFrameHeader checks byte[+5] == fdd4 after a 2-byte len)
frame = bytes([4,0x44,0x00,LINK_ID]) + b"OK"
full = bytes([len(frame)&0xFF, (len(frame)>>8)&0xFF]) + frame
deliver = list(full)
rx_i = [0]

resp = []
def rd(a): return mem[a & 0xFFFF]
def wr(a,v): mem[a & 0xFFFF] = v & 0xFF
def ich(*a):
    p = a[0]; p = p[0] if isinstance(p,tuple) else p; p &= 0xFF
    if p == 0x4E:
        if rx_i[0] < len(deliver):
            v = deliver[rx_i[0]]; rx_i[0] += 1
            return v
        return 0
    if p == 0x4B:
        # bit0 = RX buffer full (bytes remaining); bit7 = TX empty
        rem = len(deliver) - rx_i[0]
        return (0x80 if rem == 0 else 0x81)
    if p == 0x05: return 0x19
    return 0x00
def och(*a):
    p,v = (a[0],a[1]) if len(a)>=2 else (a[0],0xFF)
    p = p[0] if isinstance(p,tuple) else p; p &= 0xFF; v &= 0xFF
    if p in (0x4D,0x4A,0x4B,0x4C,0x4F):
        resp.append((p,v))
    elif p == 0x47:
        img = B0 if v==0 else B1 if v==1 else b"\x00"*0x8000
        mem[0:0x8000] = img

m = z80.Z80Machine()
m.set_memory_block(0, bytes(mem))
m.set_read_callback(rd); m.set_write_callback(wr)
m.set_input_callback(ich); m.set_output_callback(och)
m.pc = 0x2FBD
m.sp = 0xF000

t0 = time.time()
for _ in range(100000):
    m.ticks_to_stop = 20000
    m.run()
    if len(resp) > 0:
        break
    if time.time() - t0 > 20:
        break
print("frame fed:", full.hex())
print("4x port activity:", [(hex(p),hex(v)) for p,v in resp])