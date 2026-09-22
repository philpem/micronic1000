#!/usr/bin/env python3
"""Patch the STOCK ROM with measurement hooks and read results on the LCD.

This is the instrumentation path that replaces replaying the firmware.  The
stock boot, menu and session code all run unchanged, so the link controller is
driven by the firmware's own sequence in the firmware's own environment; we
only splice a small sampling routine into a stock loop and print what it saw on
the glass.

Why this exists: the boot-replacing exerciser reproduces every latch write the
stock Link_BlockTx makes, and the stock TX-time port state, yet the controller
still will not clock a frame out (see doc/re-notes/exerciser-test-plan.md).
The replay is the remaining variable; this removes it.

Mechanism
---------
* Hook code is assembled into a genuinely-free stock region (default
  0x7E96-7FF9, an all-zero 356-byte gap; guarded so a non-empty region refuses).
* Named stock addresses are patched with CALL/JP (or raw bytes) to that block;
  every patch site is byte-guarded, so a wrong ROM revision refuses to build.
* Hooks may sample ports, keep accumulators in free upper-TPA RAM, and write
  directly to the HD61830 (ports 23h/03h) for the readout.  The stock firmware
  never refreshes the LCD again once a hook halts, so the result persists.

Hook sets:
  bit6 (default) -- snapshot Link_BlockTx's bit6-wait result.
      - 32F0-32FF stock bit6-clear poll -> JP hook6 (+ NOPs)
      - 3356      stock error-EE entry  -> JP show
    hook6 reproduces the stock polling instructions verbatim and snapshots the
    final status and flags only after the loop.  On timeout the stock code
    reaches 3356; show prints `O xx A xx Bx` and halts.
  rx -- detect a received burst on the interrupt-driven receive path.
      - 2FBD  LinkRxDispatcher entry -> JP hook_rx
    When the controller reports a pending receive (LINK_STATUS bit 4) the IRQ
    handler calls LinkRxDispatcher; hook_rx prints `I ss rr` (LINK_STATUS,
    LINK_RXD if byte-ready) and halts.  If no burst is accepted, the firmware
    runs its normal error path and nothing is printed.

Usage:  stock_instrument.py [--hook bit6|rx|rxb|rxb2] [-o OUT] [--rom ROM]
"""
import hashlib
import pathlib
import sys

HERE = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))
from micronic.z80asm import assemble

DEFAULT_ROM = HERE.parent.parent / "micronic" / "micron1.bin"

# Free ROM for hook code.  MUST be genuinely free: unlike the boot-replacing
# exerciser, the stock boot runs here, so the exerciser's 0250-02FD "reclaimed"
# region is NOT usable (it is the stock boot's own continuation at 024D).  7E96
# is a 356-byte all-zero gap with no CALL/JP into it.
CODE_ORG = 0x7E96
CODE_END = 0x7FF9

# Shared HD61830 helpers.  Register-indexed: port 23h picks the register, port
# 03h carries the byte.  Same sequence as the stock Lcd_Init / exerciser.
COMMON = r"""
LCD_REG     equ 0x23
LCD_DAT     equ 0x03

lcd_home:       ld a,0x0A
                out (LCD_REG),a
                xor a
                out (LCD_DAT),a
                ld a,0x0B
                out (LCD_REG),a
                ld a,0x00
                out (LCD_DAT),a
                ret
lcd_putc:       push af
                ld a,0x0C
                out (LCD_REG),a
                pop af
                out (LCD_DAT),a
                ret
lcd_hex:        push af
                rrca
                rrca
                rrca
                rrca
                call lcd_nib
                pop af
lcd_nib:        and 0x0F
                add a,0x30
                cp 0x3A
                jr c,lh_out
                add a,0x07
lh_out:         jp lcd_putc
"""

BIT6 = r"""
LINK_STAT   equ 0x4B
V_LAST      equ 0xC7E0          ; upper TPA, free in the stock firmware
V_FLAGS     equ 0xC7E1

; hook6 -- replaces LinkBlockTx's bit6-clear poll at ROM00:32F0-32FF.
; The polling body below is byte-for-byte the stock body.  The entry JP takes
; the 10 T-states of the overwritten LD DE,nn and this relocated copy then
; executes LD DE,nn, so the first sample is 10 T-states (about 2.7 us) later.
; The 620 loop iterations themselves are unchanged.  It records B and F only
; after the decision, restores AF/DE, and jumps to stock 3300.  Thus B, HL,
; and the Z result consumed by stock JR Z,3356 are unchanged.  The snapshot
; costs a further 107 T-states after the final poll (about 29.0 us at 3.6864
; MHz).  LCD output occurs only on timeout.
hook6:          ld de,0x026c
h6_loop:        in a,(LINK_STAT)
                ld b,a
                cpl
                and 0x40
                jr nz,h6_done
                dec de
                ld a,d
                or e
                jr nz,h6_loop
h6_done:        push de
                push af
                pop de                      ; D=A, E=F from the stock exit
                ld a,b
                ld (V_LAST),a
                ld a,e
                ld (V_FLAGS),a
                push de
                pop af                      ; exact stock A/F, including Z
                pop de
                jp 0x3300

; show -- entered from the stock error path (ROM00:3356).  Prints the
; final LINK_STATUS and its saved flags on the top LCD row and halts.
show:           call lcd_home
                ld a,'O'
                call lcd_putc
                ld a,(V_LAST)
                call lcd_hex
                ld a,'F'
                call lcd_putc
                ld a,(V_FLAGS)
                call lcd_hex
                ld a,'B'
                call lcd_putc
                ld a,(V_LAST)
                and 0x40
                jr z,sh_b0
                ld a,'1'
                jr sh_b1
sh_b0:          ld a,'0'
sh_b1:          call lcd_putc
show_loop:      jr show_loop
"""

RX = r"""
LINK_STAT   equ 0x4B
LINK_RXD    equ 0x4E
V_STAT      equ 0xC7E0
V_RXD       equ 0xC7E1

; hook_rx -- replaces LinkRxDispatcher's entry (ROM00:2FBD).  Reached only when
; the link IRQ (source 2) found LINK_STATUS bit 4 set, i.e. the controller
; reported a pending receive.  Prints `I ss rr` (LINK_STATUS, and LINK_RXD when
; bit 0 says a byte is ready) and halts, so an accepted return burst is visible
; on the glass.  A sweep of Arduino conventions maps convention -> acceptance.
hook_rx:        in a,(LINK_STAT)
                ld (V_STAT),a
                xor a
                ld (V_RXD),a
                ld a,(V_STAT)
                bit 0,a                     ; byte ready?
                jr z,rx_show
                in a,(LINK_RXD)
                ld (V_RXD),a
rx_show:        call lcd_home
                ld a,'I'
                call lcd_putc
                ld a,(V_STAT)
                call lcd_hex
                ld a,(V_RXD)
                call lcd_hex
rx_loop:        jr rx_loop
"""

RXB = r"""
LINK_STAT   equ 0x4B
LINK_RXD    equ 0x4E
V_STAT      equ 0xC7E0
V_CNT       equ 0xC7E1
V_B0        equ 0xC7E2
V_B1        equ 0xC7E3
V_B2        equ 0xC7E4

; hook_rxb -- replaces LinkRxDispatcher's entry (ROM00:2FBD).  Reached only
; when the link IRQ (source 2) found LINK_STATUS bit 4 set (a pending
; receive).  Waits (bounded) for LINK_STATUS bit 0 and captures up to 3 bytes
; from LINK_RXD, then prints `I ss n b0 b1 b2` and halts.
; n = bytes captured by this non-stock probe.  n=0 only says that this hook
; did not observe byte-ready before its own bound; it does not diagnose the
; optical data convention because this hook omits the stock receive arm.
hook_rxb:       in a,(LINK_STAT)
                ld (V_STAT),a
                xor a
                ld (V_CNT),a
                ld (V_B0),a
                ld (V_B1),a
                ld (V_B2),a
                ld hl,V_B0
                ld b,0x03
rxb_loop:       push bc
                push hl
                ld de,0x0800                ; ~16 ms per byte
rxb_wait:       in a,(LINK_STAT)
                bit 0,a
                jr nz,rxb_got
                dec de
                ld a,d
                or e
                jr nz,rxb_wait
                pop hl
                pop bc
                jr rxb_show
rxb_got:        pop hl
                pop bc
                in a,(LINK_RXD)
                ld (hl),a
                inc hl
                ld a,(V_CNT)
                inc a
                ld (V_CNT),a
                djnz rxb_loop
rxb_show:       call lcd_home
                ld a,'I'
                call lcd_putc
                ld a,(V_STAT)
                call lcd_hex
                ld a,(V_CNT)
                call lcd_hex
                ld a,(V_B0)
                call lcd_hex
                ld a,(V_B1)
                call lcd_hex
                ld a,(V_B2)
                call lcd_hex
rxb_halt:       jr rxb_halt
"""

RXB2 = r"""
V_A         equ 0xC7E0
V_STAT      equ 0xC7E1
V_FLAGS     equ 0xC7E2
V_NLO       equ 0xC7E3
V_NHI       equ 0xC7E4
V_B0        equ 0xC7E5
V_B1        equ 0xC7E6
V_B2        equ 0xC7E7
V_PLLO      equ 0xC7E8
V_PLHI      equ 0xC7E9

; hook_rxb2 -- replaces LinkRxDispatcher's entry (ROM00:2FBD).  Instead of
; reading LINK_RXD itself (which missed the stock arm), it calls the STOCK
; Link_BlockRx (ROM00:3378): that performs the full RX arm (bit0=0, bit5=1,
; dummy LINK_RXD read, bit4=1, settle, bit5=0), reads the frame through the
; dispatcher's descriptor chain, and tears down.  The first descriptor's
; destination word is at +2 (as in the stock dispatcher), not the descriptor
; bytes themselves.  It records the first descriptor's length and never
; writes the destination before the stock reader does.  It then prints
; `I ss aa ff nnnn b0 b1 b2` and halts:
;   ss = LINK_CTRL shadow after the call
;   aa = raw Link_BlockRx return A
;   ff = raw Link_BlockRx return F (carry set means its error exit)
;   nnnn = controller bytes read (DE+2) on carry-clear success; FFFF when no
;          count is valid
;   bN = first-descriptor destination bytes only when both nnnn and that
;        descriptor's own length cover the byte; `--` denotes unavailable
;        data, never a stale buffer byte.
; This hook deliberately stops before LinkRxDispatcher's frame validator, so
; aa/ff diagnose Link_BlockRx only; they do not claim header validation.
hook_rxb2:      ld hl,(0xFDDC)
                ld a,(hl)
                ld (V_PLLO),a               ; descriptor +0: first length
                inc hl
                ld a,(hl)
                ld (V_PLHI),a
                inc hl
                ld e,(hl)                    ; descriptor +2: destination
                inc hl
                ld d,(hl)
                ld a,0xFF
                ld (V_NLO),a                 ; error count is unavailable
                ld (V_NHI),a
                ld hl,(0xFDDC)               ; stock call still takes list
                call 0x3378                 ; stock Link_BlockRx: arm + read
                push af
                pop bc                       ; B=A, C=exact return flags
                ld a,b
                ld (V_A),a
                ld a,c
                ld (V_FLAGS),a
                bit 0,c
                jr nz,rxb2_show              ; error: do not display buffer
                inc de                        ; success: DE = received - 2
                inc de
                ld a,e
                ld (V_NLO),a
                ld a,d
                ld (V_NHI),a
                ; Bound the actual destination reads before touching it:
                ; preview = min(received count, first descriptor length, 3).
                ld a,d
                or a
                jr nz,rxb2_copy_three
                ld a,e
                cp 0x03
                jr nc,rxb2_copy_three
                ld b,a
                jr rxb2_bound_copy
rxb2_copy_three:
                ld b,0x03
rxb2_bound_copy:
                ld a,(V_PLHI)
                or a
                jr nz,rxb2_copy_start
                ld a,(V_PLLO)
                cp b
                jr nc,rxb2_copy_start
                ld b,a
rxb2_copy_start:
                ld hl,(0xFDDC)
                inc hl
                inc hl
                ld e,(hl)
                inc hl
                ld d,(hl)
                ex de,hl
                ld de,V_B0
rxb2_copy_byte:
                ld a,b
                or a
                jr z,rxb2_show
                ld a,(hl)
                ld (de),a
                inc hl
                inc de
                dec b
                jr rxb2_copy_byte
rxb2_show:      ld a,(0xF794)
                ld (V_STAT),a
                call lcd_home
                ld a,'I'
                call lcd_putc
                ld a,(V_STAT)
                call lcd_hex
                ld a,(V_A)
                call lcd_hex
                ld a,(V_FLAGS)
                call lcd_hex
                ld a,(V_NHI)
                call lcd_hex
                ld a,(V_NLO)
                call lcd_hex
                ld a,(V_FLAGS)
                and 0x01
                jr nz,rxb2_no_bytes
                ld a,(V_NHI)
                or a
                jr nz,rxb2_three_bytes
                ld a,(V_NLO)
                cp 0x03
                jr nc,rxb2_three_bytes
                ld b,a
                jr rxb2_bound_first
rxb2_three_bytes:
                ld b,0x03
rxb2_bound_first:
                ld a,(V_PLHI)
                or a
                jr nz,rxb2_bytes
                ld a,(V_PLLO)
                cp b
                jr nc,rxb2_bytes
                ld b,a
rxb2_bytes:    ld hl,V_B0
                ld d,0x03
rxb2_byte:     ld a,b
                or a
                jr z,rxb2_dash
                ld a,(hl)
                call lcd_hex
                dec b
                jr rxb2_next
rxb2_dash:     ld a,'-'
                call lcd_putc
                call lcd_putc
rxb2_next:     inc hl
                dec d
                jr nz,rxb2_byte
                jr rxb2_halt
rxb2_no_bytes: ld b,0x00
                jr rxb2_bytes
rxb2_halt:     jr rxb2_halt
"""

# name -> (hook source, patches).  Patch = (addr, expected stock bytes, expr).
HOOKS = {
    "bit6": (BIT6, [
        (0x32F0, bytes.fromhex("11 6c 02 db 4b 47 2f e6 40 20 05 1b 7a b3 20 f3"),
         "jp hook6"),
        (0x3356, bytes.fromhex("3e ee 18"), "jp show"),
    ]),
    "rx": (RX, [
        (0x2FBD, bytes.fromhex("2a dc fd"), "jp hook_rx"),
    ]),
    "rxb": (RXB, [
        (0x2FBD, bytes.fromhex("2a dc fd"), "jp hook_rxb"),
    ]),
    "rxb2": (RXB2, [
        (0x2FBD, bytes.fromhex("2a dc fd"), "jp hook_rxb2"),
    ]),
}
# NOTE (2026-09-20): a RAM-test page-bound patch at 26C8 (41h->09h) was tried
# and REMOVED -- it hung the batteries-out cold boot (the RAM test initialises
# RAM).  Do not re-add without understanding 267a fully.


def build_image(hook="bit6", rom_path=None):
    if hook not in HOOKS:
        raise SystemExit(f"unknown hook {hook!r}; choose from {list(HOOKS)}")
    src = f"        org 0x{CODE_ORG:04X}\n" + COMMON + HOOKS[hook][0]
    patches = HOOKS[hook][1]

    orig = pathlib.Path(rom_path or DEFAULT_ROM).read_bytes()
    if len(orig) != 0x8000:
        raise SystemExit(f"expected a 32K image, got {len(orig)}")
    rom = bytearray(orig)

    if any(orig[CODE_ORG:CODE_END + 1]):
        raise SystemExit(
            f"{CODE_ORG:04X}-{CODE_END:04X} is not empty in this image "
            "-- refusing to patch")
    code, sym = assemble(src, origin=CODE_ORG)
    if CODE_ORG + len(code) > CODE_END + 1:
        raise SystemExit(
            f"hook code is {len(code)} bytes, overruns {CODE_ORG:04X}-"
            f"{CODE_END:04X} by {CODE_ORG + len(code) - CODE_END - 1}")
    rom[CODE_ORG:CODE_ORG + len(code)] = code

    for addr, expect, expr in patches:
        if bytes(orig[addr:addr + len(expect)]) != expect:
            raise SystemExit(
                f"{addr:04X} does not hold the expected stock bytes -- refusing")
        if expr.startswith("bytes "):
            blob = bytes.fromhex(expr[len("bytes "):])
            if len(blob) != len(expect):
                raise SystemExit(
                    f"raw patch at {addr:04X} is {len(blob)} bytes, expected "
                    f"{len(expect)}")
            rom[addr:addr + len(expect)] = blob
            print(f"patched {addr:04X}: {expr}")
            continue
        mnem, label = expr.split()
        if label not in sym:
            raise SystemExit(f"patch label {label} not defined")
        target = sym[label]
        if mnem == "call":
            blob = bytes([0xCD]) + target.to_bytes(2, "little")
        elif mnem == "jp":
            blob = bytes([0xC3]) + target.to_bytes(2, "little")
        else:
            raise SystemExit(f"unsupported patch mnemonic {mnem}")
        blob = blob + bytes(len(expect) - len(blob))   # NOP pad
        rom[addr:addr + len(expect)] = blob
        print(f"patched {addr:04X}: {expr} -> {target:04X} ({len(blob)} bytes)")

    return bytes(rom), sym, orig


def main(argv=None):
    import argparse

    ap = argparse.ArgumentParser()
    ap.add_argument("--hook", default="bit6", choices=sorted(HOOKS))
    ap.add_argument("-o", "--out", default=None)
    ap.add_argument("--rom", default=str(DEFAULT_ROM))
    a = ap.parse_args(argv)
    if a.out is None:
        a.out = str(HERE / ("micron1_stockhook.bin" if a.hook == "bit6"
                            else f"micron1_stockhook_{a.hook}.bin"))

    rom, sym, orig = build_image(a.hook, a.rom)
    pathlib.Path(a.out).write_bytes(rom)
    print(f"wrote {a.out}")
    print(f"bytes changed vs the original: "
          f"{sum(1 for i in range(0x8000) if rom[i] != orig[i])}")
    print(f"md5: {hashlib.md5(rom).hexdigest()}")
    print(f"sum16: {sum(rom) & 0xFFFF:04X}")
    print(f"sum24: {sum(rom) & 0xFFFFFF:06X}")
    print(f"sha256: {hashlib.sha256(rom).hexdigest()}")


if __name__ == "__main__":
    main()
