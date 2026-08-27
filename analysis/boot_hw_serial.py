#!/usr/bin/env python3
"""boot_hw_serial.py - patched boot_hw that drives past banner + serial entry"""
import gc; gc.disable()
import sys
sys.path.insert(0, "/home/philpem/Micronic-1000/analysis")
import z80
from micronic.rtc import RTC146818

DRIVE_SERIAL = "--drive-serial" in sys.argv[1:] or "--drive-kbd" in sys.argv[1:]
# Optional: --serial TEXT (default 12345678)
SERIAL_TEXT = "12345678"
if "--serial" in sys.argv:
    try: SERIAL_TEXT = sys.argv[sys.argv.index("--serial")+1]
    except: pass

DUMP_BANK = None
if "--dump-bank" in sys.argv:
    try: DUMP_BANK = int(sys.argv[sys.argv.index("--dump-bank")+1],0)
    except: DUMP_BANK = None

B0=open("/home/philpem/Micronic-1000/micronic/micron1.bin","rb").read()
B1=open("/home/philpem/Micronic-1000/micronic/micron2.bin","rb").read()
mem=bytearray(0x10000)
mem[0:0x8000]=B0
mem[0xD681:0xD681+0x212]=B0[0x7030:0x7242]
mem[0xF180:0xF180+0x50D]=B0[0x369D:0x369D+0x50D]
pat=bytes([0x21,1,0,0xC9])
for off in range(0xED1C,0xF180,4): mem[off:off+4]=pat
mem[0xFD84:0xFD84+19]=B0[0x2352:0x2352+19]
mem[0xFE93:0xFEA3]=B0[0x3257:0x3267]
mem[0xFE83:0xFE93]=B0[0x3267:0x3277]
mem[0xFC05]=0x70
RAM={}; cb=0
log=[]
def rd(a): return mem[a & 0xFFFF]
def wr(a,v): mem[a & 0xFFFF]=v & 0xFF
rtc=RTC146818(); rtc_sel=0x00
def ich(*a):
    p=a[0]; p=p[0] if isinstance(p,tuple) else p; p&=0xFF
    if p==0x05: return 0x19
    if p==0x4B: return 0x80
    if p==0x28: return rtc.reg_read(rtc_sel) & 0xFF
    if p==0x00: return 0x00
    if p==0x49: return 0x00
    if p==0x4E: return 0x00
    if p==0x4C: return 0x00
    if p==0x48: return 0x00
    return 0xFF
def och(*a):
    global cb, rtc_sel
    p,v=(a[0],a[1]) if len(a)>=2 else (a[0],0xFF)
    p=p[0] if isinstance(p,tuple) else p; p&=0xFF; v&=0xFF
    if len(log)<200000:
        log.append((mach.pc & 0xFFFF, p, v))
    if p==0x47:
        cb=v
        img=B0 if v==0 else B1 if v==1 else RAM.setdefault(v, bytearray(0x8000))
        mem[0:0x8000]=img; mem[0xF791]=v
    elif p==0x08: rtc_sel=v & 0xFF
    elif p==0x28: rtc.reg_write(rtc_sel,v)
mach=z80.Z80Machine()
mach.set_memory_block(0, bytes(mem))
mach.set_read_callback(rd); mach.set_write_callback(wr)
mach.set_input_callback(ich); mach.set_output_callback(och)
mach.pc=0x014B; mach.sp=0xF000
mem[0xFBD0:0xFBD2]=bytes([0,0xF0])
mem[0x289E]=0xC9; mem[0xFDB7]=0xFF; mem[0xFDB6]=0x00
CPU_HZ=3_579_545
SLICE=3400
acc=0
def next_int_interval():
    p=rtc.periodic_period
    if p is None: return None
    return max(1,int(p*CPU_HZ))
ramt=False; contig=False; banner=False
W={0x2084:"RtcInit",0x2828:"ClockSelftest",0x02D8:"BannerKeyRead",0x3277:"LinkBlockTx",0x2EAB:"LinkOpen"}
hits={k:0 for k in W}
last_pc=None; stall=0
MAX_SLICES=900000
if "--max-slices" in sys.argv:
    MAX_SLICES=int(sys.argv[sys.argv.index("--max-slices")+1])
# build serial queue: banner ENTER + SERIAL_TEXT + ENTER
queue=[]
if DRIVE_SERIAL:
    queue=[0x0D] + [ord(c) for c in SERIAL_TEXT] + [0x0D]
    print(f"[init] DRIVE_SERIAL queue {len(queue)} chars: banner ENTER + '{SERIAL_TEXT}' + ENTER")
qidx=0
i=0
while i < MAX_SLICES and stall < 8000:
    if (i & 0xFFF)==0: gc.collect()
    mach.ticks_to_stop=SLICE
    try: mach.run()
    except Exception as e: print("run err",type(e).__name__,e); break
    pc=mach.pc & 0xFFFF
    acc+=SLICE
    interval=next_int_interval()
    while interval is not None and acc>=interval:
        acc-=interval
        rtc.push_tick()
        if mem[0xFFA8]!=0:
            try: mach.on_handle_active_int()
            except: pass
    # paced keyboard injection: only when bit2 clear (ready) and in HALT wait
    if DRIVE_SERIAL and qidx < len(queue) and 0x16C9 <= pc <= 0x16D2 and mem[0xFFA8]==1 and (mem[0xFBC9] & 0x04)==0:
        rp=mem[0xFBF0]|(mem[0xFBF1]<<8)
        if rp==0: rp=0xFBE8
        mem[rp]=queue[qidx] & 0xFF
        mem[0xFBC9]|=0x04
        print(f"[{i}] inject qidx={qidx} char={chr(queue[qidx])!r} pc={pc:04X} rp={rp:04X}")
        qidx+=1
    if not ramt and 0x2530 <= pc <= 0x2670:
        for k in range(0x40): mem[0xFEB0+k]=0x0F
        mem[0xFDB1]=0; mem[0xFEAF]=0xFF; mem[0xFDB0]=0
        mach.pc=0x01D0; ramt=True; print(f"[{i}] skip RAM test"); continue
    if not contig and pc==0x267A:
        for k in range(0x40): mem[0xFEB0+k]=0x0F
        mem[0xFDB1]=0; mach.pc=0x26E3; contig=True; print(f"[{i}] contig tail"); continue
    if pc==0x02D8 and not banner:
        # old banner ENTER hack is now handled via queue, but keep for compatibility when not driving serial
        if not DRIVE_SERIAL:
            mach.a=0x0D; mach.pc=0x02DB; banner=True; print(f"[{i}] banner ENTER (legacy)"); continue
    if 0x289E <= pc <= 0x28C0:
        mach.pc=0x28C1; continue
    if pc in W:
        if hits[pc]==0: print(f"[{i}] HIT {W[pc]} PC={pc:04X} bank={cb:02X}")
        hits[pc]+=1
    # fix: hits[0x02D8] never increments due to early continue above, so check queue progress instead
    if qidx>=len(queue) and qidx>0:
        fb=mem[0xFC06:0xFCA6]
        txt="".join(chr(b) if 32<=b<127 else "." for b in fb)
        if "Main Menu" in txt and i>170000:
            print(f"[{i}] Main Menu reached - boot past serial OK (qidx={qidx})")
            break
    if pc==last_pc: stall+=1
    else: stall=0; last_pc=pc
    i+=1

# final framebuffer
fb=mem[0xFC06:0xFCA6]
txt="".join(chr(b) if 32<=b<127 else "." for b in fb)
print("Framebuffer:")
for r in range(8):
    print(f" row{r}: {txt[r*20:(r+1)*20]!r}")
print("summary:",{v:hits[k] for k,v in W.items()}, f"qidx={qidx}/{len(queue)}")
rt=[x for x in log if x[1] in (0x08,0x28,0x4A,0x4B,0x4C,0x4D,0x4E,0x4F)]
print(f"RTC/link transactions: {len(rt)}; RTC rate ={rtc.periodic_hz:.1f} Hz (RS={rtc.rate_select:#x})")
with open("/tmp/opencode/micronic_boot_io.txt","w") as f:
    for seq,(pc,p,v) in enumerate(log):
        f.write(f"{seq:7d} PC={pc:04X} {p:02X} = {v:02X}\n")
print("WROTE /tmp/opencode/micronic_boot_io.txt",len(log),"lines")
if DUMP_BANK is not None:
    img=B0 if DUMP_BANK==0 else B1 if DUMP_BANK==1 else RAM.get(DUMP_BANK, bytearray(0x8000))
    path=f"/home/philpem/Micronic-1000/analysis/ram_bank_{DUMP_BANK:02x}.bin"
    with open(path,"wb") as f: f.write(bytes(img[:0x8000])+bytes(0x8000-len(img)))
    print(f"DUMPED bank {DUMP_BANK} -> {path}")
