#!/usr/bin/env python3
"""comms_duplex.py - bidirectional data exchange between the reusable
micronic.proto model (peer/adapter) and the actual M1000 firmware.

Direction 1 (M1000 -> model): seed the firmware FDEA {count,ptr}
descriptor, call LinkTransferService (2F86); capture OUT(4Dh) and
have the model parse it.

Direction 2 (model -> M1000): build a frame with the model, run it
through proto.Link.tx(); feed those bytes back into the M1000's
port-4Eh and let the firmware RX dispatcher (2FBD) consume them.

Both use the firmware-verified wire format:
  prelude (link_id & 0x1F) + [type][cmd_hi][cmd_lo][data...]
"""
import gc; gc.disable()
import sys, time
sys.path.insert(0, "/home/philpem/Micronic-1000/analysis")
import z80
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

LINK_ID = 0x45
mem[0xFDD4] = LINK_ID; mem[0xFDD5] = 0x03; mem[0xFDD6] = 0x32
mem[0xFDDC] = 0x0E; mem[0xFDDD] = 0xFE

# ---- port bus bridges --------------------------------------------------
mto_mod = []      # M1000 OUT(4Dh) -> model read (IN 4Eh of the model)
mod_to_m = []     # model tx -> M1000 IN(4Eh)
m_rxi = [0]

def rd(a): return mem[a & 0xFFFF]
def wr(a,v): mem[a & 0xFFFF] = v & 0xFF

def ich_m1000(*a):
    p = a[0]; p = p[0] if isinstance(p,tuple) else p; p &= 0xFF
    if p == 0x4E:
        if m_rxi[0] < len(mod_to_m):
            v = mod_to_m[m_rxi[0]]; m_rxi[0] += 1; return v
        return 0
    if p == 0x4B:
        return 0x80 | (0x01 if (len(mod_to_m) - m_rxi[0]) > 0 else 0)
    if p == 0x05: return 0x19
    return 0x00

def och_m1000(*a):
    p,v = (a[0],a[1]) if len(a)>=2 else (a[0],0xFF)
    p = p[0] if isinstance(p,tuple) else p; p &= 0xFF; v &= 0xFF
    if p == 0x4D:
        mto_mod.append(v & 0xFF)
    elif p == 0x47:
        img = B0 if v==0 else B1 if v==1 else b"\x00"*0x8000
        mem[0:0x8000] = img

mach = z80.Z80Machine()
mach.set_memory_block(0, bytes(mem))
mach.set_read_callback(rd); mach.set_write_callback(wr)
mach.set_input_callback(ich_m1000); mach.set_output_callback(och_m1000)
mach.sp = 0xF000

def run_until(fn, cap=400000):
    t0=time.time()
    for _ in range(cap):
        mach.ticks_to_stop=20000
        mach.run()
        if fn(): return True
        if time.time()-t0>25: return False
    return False

# ---- the peer model -----------------------------------------------------
# Direction 1: the model's port-in reads bytes the M1000 put on 4Dh
model_buf = []
peer = proto.Link(
    port_out=lambda b: mod_to_m.append(b & 0xFF),
    port_in=lambda: (mto_mod.pop(0) if mto_mod else 0),
    port_status=lambda: (0x81 if mto_mod else 0x80),
    port_ctrl=lambda v: None,
    id_byte=LINK_ID)

print("=== Direction 1: M1000 -> model ===")
# seed FDEA descriptor {count, ptr}
payload1 = bytes([proto.TYPE_COMMAND, 0x44, 0x00]) + b"from-M1000"
PPTR = 0xFD00
mem[PPTR:PPTR+len(payload1)] = payload1
mem[0xFDEA] = len(payload1) & 0xFF
mem[0xFDEB] = (len(payload1)>>8) & 0xFF
mem[0xFDEC] = PPTR & 0xFF; mem[0xFDED] = (PPTR>>8) & 0xFF
mem[0xFDD8] = len(payload1)
mach.pc = 0x2F86
ok1 = run_until(lambda: len(mto_mod) >= len(payload1)+1)
wire1 = bytes(mto_mod)
print("  M1000 OUT(4Dh):", wire1.hex())
# model receives: prelude + payload
rx = peer.rx(max_len=len(payload1))
d1_ok = False
if rx:
    print("  model parsed: type=%d cmd=0x%04X payload=%r" %
          (rx.type, rx.cmd, rx.payload.decode(errors="replace")))
    d1_ok = (rx.type==proto.TYPE_COMMAND and rx.cmd==0x4400
             and rx.payload==b"from-M1000")
print("  direction1:", "OK" if d1_ok else "FAIL")

print("=== Direction 2: model -> M1000 ===")
reply = proto.Frame(proto.TYPE_ANSWER, 0x04E0, b"reply-to-M")
mod_to_m.clear(); m_rxi[0]=0
peer2 = proto.Link(
    port_out=lambda b: mod_to_m.append(b & 0xFF),
    port_in=lambda: 0,
    port_status=lambda: 0x80,
    port_ctrl=lambda v: None,
    id_byte=LINK_ID)
peer2.tx(reply)
wire2 = bytes(mod_to_m)
print("  model wire:", wire2.hex())
# Seed the firmware's RX descriptor at its frame buffer (FE0E) so
# LinkBlockRx's 3508 count read knows how many bytes to expect.
mem[0xFE0E] = len(wire2) & 0xFF
mem[0xFE0F] = (len(wire2)>>8) & 0xFF
mem[0xFE10] = 0x12; mem[0xFE11] = 0xFE     # ptr = FE12 (payload buffer)
mach.pc = 0x2FBD
ok2 = run_until(lambda: m_rxi[0] >= len(wire2))
print("  M1000 consumed %d/%d bytes" % (m_rxi[0], len(wire2)))
d2_ok = (m_rxi[0] == len(wire2))
print("  direction2:", "OK" if d2_ok else "partial/FAIL")

print("=== RESULT:", "BIDIRECTIONAL EXCHANGE OK" if (d1_ok and d2_ok) else "CHECK NEEDED")