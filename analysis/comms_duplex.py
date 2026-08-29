#!/usr/bin/env python3
"""Directed byte-latch plumbing between LinkPeer and M1000 firmware.

Direction 1 seeds the firmware FDEA descriptor and captures raw OUT(4Dh)
bytes. Direction 2 queues opaque bytes and confirms latch consumption only.

This does not supply a validated Commstar frame or prove a session exchange.
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

# ---- port bus bridge ---------------------------------------------------
peer = proto.LinkPeer()
m1000_rx_count = [0]

def rd(a): return mem[a & 0xFFFF]
def wr(a,v): mem[a & 0xFFFF] = v & 0xFF

def ich_m1000(*a):
    p = a[0]; p = p[0] if isinstance(p,tuple) else p; p &= 0xFF
    if p == 0x4E:
        m1000_rx_count[0] += 1
        return peer.read_rx()
    if p == 0x4B:
        return peer.firmware_status()
    if p == 0x05: return 0x19
    return 0x00

def och_m1000(*a):
    p,v = (a[0],a[1]) if len(a)>=2 else (a[0],0xFF)
    p = p[0] if isinstance(p,tuple) else p; p &= 0xFF; v &= 0xFF
    if p == 0x4D:
        peer.write_tx(v)
    elif p == 0x4A:
        peer.write_control(v)
    elif p == 0x4C:
        peer.write_command(v)
    elif p == 0x4F:
        peer.write_probe(v)
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

# ---- reusable peer model -----------------------------------------------
adapter = peer.make_adapter_link()

print("=== Direction 1: M1000 -> model ===")
# seed FDEA descriptor {count, ptr}
payload1 = bytes([0x04, 0x44, 0x00]) + b"from-M1000"
PPTR = 0xFD00
mem[PPTR:PPTR+len(payload1)] = payload1
mem[0xFDEA] = len(payload1) & 0xFF
mem[0xFDEB] = (len(payload1)>>8) & 0xFF
mem[0xFDEC] = PPTR & 0xFF; mem[0xFDED] = (PPTR>>8) & 0xFF
mem[0xFDD8] = len(payload1)
mach.set_memory_block(PPTR, payload1)
mach.set_memory_block(0xFDEA, bytes(mem[0xFDEA:0xFDEE]))
mach.set_memory_block(0xFDD8, bytes([mem[0xFDD8]]))
mach.pc = 0x2F86
ok1 = run_until(lambda: peer.pending_tx >= len(payload1) + 1)
wire1 = peer.peek_tx()
print("  M1000 OUT(4Dh):", wire1.hex())
expected1 = bytes([LINK_ID & 0x1F]) + payload1
rx = adapter.rx(len(expected1), timeout=100000) if ok1 else None
d1_ok = rx == expected1
print("  raw bytes match seeded descriptor:", d1_ok)
print("  direction1:", "OK" if d1_ok else "FAIL")

print("=== Direction 2: model -> M1000 ===")
test_bytes = bytes([0x05, 0x03, 0x04, 0xE0]) + b"reply-to-M"
m1000_rx_count[0] = 0
adapter.tx(test_bytes)
print("  queued opaque bytes:", test_bytes.hex())
# Seed the firmware's RX descriptor at its frame buffer (FE0E) so
# LinkBlockRx's 3508 count read knows how many bytes to expect.
RXBUF = 0xFC80
descriptor_count = max(0, len(test_bytes) - 1)  # one initial controller read
mem[0xFE0E] = descriptor_count & 0xFF
mem[0xFE0F] = (descriptor_count >> 8) & 0xFF
mem[0xFE10] = RXBUF & 0xFF; mem[0xFE11] = RXBUF >> 8
mem[0xFE12:0xFE16] = b"\x00" * 4           # non-overlapping terminator
mach.set_memory_block(0xFE0E, bytes(mem[0xFE0E:0xFE16]))
mach.pc = 0x2FBD
ok2 = run_until(lambda: peer.pending_rx == 0)
print(
    "  M1000 LINK_RXD reads: %d; queued bytes consumed: %d/%d"
    % (m1000_rx_count[0], len(test_bytes) - peer.pending_rx, len(test_bytes))
)
# LinkBlockRx performs a controller-facing read before its descriptor pump.
# Count queued bytes, not raw port reads, as the transport completion result.
d2_ok = ok2 and peer.pending_rx == 0
print("  direction2 latch consumption:", "observed" if d2_ok else "incomplete")

print("  LINK_CTRL writes:", [f"{v:02X}" for v in peer.ctrl_writes])
print("  LINK_CMD writes:", [f"{v:02X}" for v in peer.command_writes])

print("=== RESULT: DIRECTED BYTE-LATCH TESTS ONLY ===")
