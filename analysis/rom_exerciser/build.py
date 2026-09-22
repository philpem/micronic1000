#!/usr/bin/env python3
"""Assemble the link exerciser and patch it into a copy of ROM00.

Produces a burnable image; the original micron1.bin is never modified.  The
code is split across guarded regions of ROM00, and every edit is checked
before it is applied:

  1. 0047-0065, 0069-007F, 00A2-00FF, 724C-7302, 7CE0-7D0F and
     7E96-7FF9 take the ISR, NMI guard, keypad, helpers, LCD/contrast
     setup and main body.  Every filler run must be entirely zero
     beforehand;
  2. 0250-02FD is RECLAIMED stock code (the cold-boot/banner flow), not
     filler: it is only overwritten after its untouched bytes hash to a
     pinned digest;
  3. the cold-boot entry at 014B is replaced with a jump to the exerciser,
     a three-byte edit, after checking it still holds the prologue we expect.

The sections are one assembly, so they can call each other by name.  ORG pads
forward, so the blob spans the firmware that sits between them -- only the
declared regions are ever copied out of it.

Two variants are built from the one source:

  * default          -- streams LINK_STATUS records over the IR link
  * --witness        -- replays the full stock transaction (flag, prelude,
                        bit4-clear poll, arm, bit6-clear poll), then STOPS
                        transmitting and watches LINK_STATUS and the link
                        interrupt on the LCD (see exerciser.asm)

Usage:  build.py [-o OUT] [--witness] [--rom ROM]
        default out: micron1_exerciser.bin (or micron1_witness.bin)
"""
import hashlib
import pathlib
import sys

HERE = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))
from micronic.z80asm import assemble

REGIONS = [("isr", 0x0047, 0x0065, "isr_end"),
           ("nmi", 0x0069, 0x007F, "nmi_end"),
           ("vec", 0x00A2, 0x00FF, "vec_end"),
           ("scr", 0x0250, 0x02FD, "scr_end"),
           ("lo",  0x724C, 0x7302, "lo_end"),
           ("mid", 0x7CE0, 0x7D0F, "mid_end"),
           ("hi",  0x7E96, 0x7FF9, "hi_end")]
# The scr region is not zero filler: it reclaims the stock cold-boot/banner
# flow at 0250-02FD, which is reached only by fall-through from the warm-boot
# entry at 024D and is never CALLed (Ghidra xrefs: none).  The digest is of
# those untouched bytes in micron1.bin and must match before it is overwritten.
RECLAIMED = {
    "scr": "826a1915a2f2ec88fe5e8d25cc1c8d5d89d9327a1b544d45d2680f7346694364",
}
WITNESS_ONLY_REGIONS = set()
# The cold-boot entry itself, not the vector that reaches it: 0000 jumps to
# 0103 which jumps here, and the emulator harness starts directly at 014B, so
# patching here is exercised identically on hardware and in the emulator.
BOOT_ENTRY = 0x014B
BOOT_ORIG = bytes.fromhex("f3 2a d0 fb f9 ed 56")   # DI/LD HL,(FBD0)/LD SP,HL/IM 1
DEFAULT_ROM = HERE.parent.parent / "micronic" / "micron1.bin"

# Source markers for the two variants.  The witness block is stripped for the
# default build (keeping that image byte-identical); the witness build points
# the preamble's arm call at the wrapper in that block instead, and swaps the
# preamble's magic byte A5h for the stock prelude (link id & 1Fh = 03h for top
# V24) so the transmitted transaction matches the firmware's own.
WITNESS_BEGIN = ";@WITNESS_BEGIN@"
WITNESS_END = ";@WITNESS_END@"
ARM_CALL_DEFAULT = "call arm_tx                 ; stock flag/byte/arm order"
ARM_CALL_WITNESS = "call arm_witness            ; arm, then the RX witness takes over"
PRELUDE_DEFAULT = "ld a,0xA5"
PRELUDE_WITNESS = "ld a,0x03                   ; stock prelude: LINK_ID & 1Fh"
# Front-end latches the full stock boot sets and the boot-replacing exerciser
# never did.  Injected into nmi_safe (which runs first) for the witness build
# only, so the default record-stream image stays byte-identical.
FRONTEND_INIT = ";@FRONTEND_INIT@"
FRONTEND_WITNESS = (
    "                ld a,0x00\n"
    "                out (0x07),a\n"
    "                ld a,0x03\n"
    "                out (0x48),a"
)
# Stock probes the link controller at boot (ROM00:0202), before LcdInit.  The
# witness can only probe just after power_lcd_init, before contrast_setup: it
# gets the operator's contrast wait before the transaction, but not the LCD
# initialisation interval.  The default image keeps its original placement and
# bytes.
EARLY_PROBE = ";@EARLY_PROBE@"
EARLY_PROBE_WITNESS = (
    "xor a                       ; seed the link shadows before the reset\n"
    "                ld (CTRL_SHADOW),a\n"
    "                ld (PORT2C_SHADOW),a\n"
    "                call LinkProbe\n"
    "                ld (V_PSTAT),a"
)
LATE_PROBE = ("call LinkProbe\n"
              "                ld (V_PSTAT),a              ; it returns LINK_STATUS (34BA);")
LATE_PROBE_WITNESS = ("; probe moved to start for settling (witness build);\n"
                      "                ; V_PSTAT already holds the reset-time status")
LATE_SEED = ("xor a\n"
             "                ld (CTRL_SHADOW),a\n"
             "                ld (PORT2C_SHADOW),a\n"
             "                ld hl,V_SWEEP")
LATE_SEED_WITNESS = ("; shadows seeded before the early reset (witness build)\n"
                     "                xor a\n"
                     "                ld hl,V_SWEEP")
# The witness needs a thirteen-byte ordered teardown helper.  The common LO
# region has only seven spare bytes, so only that build relocates its eight-byte
# gap loop into the NMI padding.  To make room there it moves `dead` into the
# ISR's four-byte tail.  These are marker replacements: default 2609 keeps its
# original addresses and bytes.
WITNESS_DEAD_ISR = ";@WITNESS_DEAD_ISR@"
WITNESS_DEAD_NMI = ";@WITNESS_DEAD_NMI@"
WITNESS_GAP_NMI = ";@WITNESS_GAP_NMI@"
WITNESS_GAP_LO = ";@WITNESS_GAP_LO@"
WITNESS_FINISH_LO = ";@WITNESS_FINISH_LO@"
INIT_CLEAR_COUNT = "ld b,0x0D                  ; through stage and TX count"
INIT_CLEAR_COUNT_WITNESS = "ld b,0x10                  ; also clear witness P4/P6"
WITNESS_DEAD_ISR_CODE = "dead:           jp failure"
WITNESS_DEAD_NMI_BLOCK = WITNESS_DEAD_NMI + "\ndead:           jp failure"
WITNESS_GAP_CODE = (
    "gap:            ld b,GAP_SAMPLES\n"
    "gap_loop:       call sample\n"
    "                djnz gap_loop\n"
    "                ret"
)
WITNESS_GAP_LO_BLOCK = (
    WITNESS_GAP_LO + "\n"
    "gap:            ld b,GAP_SAMPLES\n"
    "gap_loop:       call sample                 ; sample leaves B alone\n"
    "                djnz gap_loop\n"
    "                ret"
)
WITNESS_FINISH_CODE = (
    "witness_finish: ld a,0xEF\n"
    "                call ctrl_and\n"
    "                ld a,0xFE\n"
    "                call ctrl_and\n"
    "                jp 0x34BD"
)


def exerciser_source(witness=False):
    """Return the exerciser source with the requested variant selected."""
    text = (HERE / "exerciser.asm").read_text()
    if witness:
        for marker, name in ((ARM_CALL_DEFAULT, "arm call site"),
                             (PRELUDE_DEFAULT, "preamble byte"),
                             (FRONTEND_INIT, "front-end init marker"),
                             (EARLY_PROBE, "early-probe marker"),
                             (LATE_PROBE, "late-probe code"),
                             (LATE_SEED, "late shadow seed"),
                             (WITNESS_DEAD_ISR, "ISR dead marker"),
                             (WITNESS_DEAD_NMI, "NMI dead marker"),
                             (WITNESS_GAP_NMI, "NMI gap marker"),
                             (WITNESS_GAP_LO, "LO gap marker"),
                             (WITNESS_FINISH_LO, "LO teardown marker"),
                             (INIT_CLEAR_COUNT, "witness-state clear count")):
            if marker not in text:
                raise SystemExit(f"witness: {name} not found in source")
        text = text.replace(ARM_CALL_DEFAULT, ARM_CALL_WITNESS)
        text = text.replace(PRELUDE_DEFAULT, PRELUDE_WITNESS)
        # XOR A is one byte smaller than LD A,0 while preserving the required
        # 07h=00h / 48h=03h writes.
        text = text.replace(FRONTEND_INIT, FRONTEND_WITNESS.replace(
            "ld a,0x00", "xor a"))
        text = text.replace(EARLY_PROBE, EARLY_PROBE_WITNESS)
        text = text.replace(LATE_PROBE, LATE_PROBE_WITNESS)
        text = text.replace(LATE_SEED, LATE_SEED_WITNESS)
        text = text.replace(WITNESS_DEAD_ISR, WITNESS_DEAD_ISR_CODE)
        text = text.replace(WITNESS_DEAD_NMI_BLOCK, "")
        text = text.replace(WITNESS_GAP_NMI, WITNESS_GAP_CODE)
        text = text.replace(WITNESS_GAP_LO_BLOCK, "")
        text = text.replace(INIT_CLEAR_COUNT, INIT_CLEAR_COUNT_WITNESS)
        return text.replace(WITNESS_FINISH_LO, WITNESS_FINISH_CODE)
    begin = text.index(WITNESS_BEGIN)
    end = text.index(WITNESS_END) + len(WITNESS_END)
    return text[:begin] + text[end:]


def build_image(witness=False, rom_path=None):
    """Assemble and patch.  Returns (rom_bytes, symbols, original_bytes)."""
    orig = pathlib.Path(rom_path or DEFAULT_ROM).read_bytes()
    if len(orig) != 0x8000:
        raise SystemExit(f"expected a 32K image, got {len(orig)}")
    rom = bytearray(orig)

    base = REGIONS[0][1]
    code, sym = assemble(exerciser_source(witness), origin=base)

    entry = sym.get("start")
    if entry is None:
        raise SystemExit("no 'start' label")

    for name, lo, hi, endsym in REGIONS:
        end = sym.get(endsym)
        if end is None:
            raise SystemExit(f"no '{endsym}' label")
        used = end - lo
        if end > hi + 1:
            raise SystemExit(
                f"{name} section is {used} bytes, overruns {lo:04X}-{hi:04X} "
                f"by {end - hi - 1}")
        if name in WITNESS_ONLY_REGIONS and not witness:
            continue
        if name in RECLAIMED:
            if hashlib.sha256(orig[lo:hi + 1]).hexdigest() != RECLAIMED[name]:
                raise SystemExit(
                    f"{lo:04X}-{hi:04X} is not the expected stock code for "
                    f"reclaimed region '{name}' -- refusing to patch")
        elif any(orig[lo:hi + 1]):
            raise SystemExit(
                f"{lo:04X}-{hi:04X} is not empty in this image -- refusing "
                f"to patch")
        rom[lo:end] = code[lo - base:end - base]

    if bytes(orig[BOOT_ENTRY:BOOT_ENTRY + len(BOOT_ORIG)]) != BOOT_ORIG:
        raise SystemExit(
            f"{BOOT_ENTRY:04X} does not hold the expected cold-boot prologue "
            f"-- refusing")
    rom[BOOT_ENTRY:BOOT_ENTRY + 3] = bytes([0xC3]) + entry.to_bytes(2, "little")

    return bytes(rom), sym, orig


def main(argv=None):
    import argparse

    ap = argparse.ArgumentParser()
    ap.add_argument("-o", "--out", default=None)
    ap.add_argument("--rom", default=str(DEFAULT_ROM))
    ap.add_argument("--witness", action="store_true",
                    help="build the RX-witness variant")
    a = ap.parse_args(argv)
    if a.out is None:
        a.out = str(HERE / ("micron1_witness.bin" if a.witness
                            else "micron1_exerciser.bin"))

    rom, sym, orig = build_image(a.witness, a.rom)
    for name, lo, hi, endsym in REGIONS:
        end = sym[endsym]
        print(f"{name}  {end - lo:3d} bytes at {lo:04X}-{end-1:04X} "
              f"({hi - end + 1} free)")
    pathlib.Path(a.out).write_bytes(rom)
    print(f"boot entry {BOOT_ENTRY:04X}: JP {sym['start']:04X} "
          f"(was {BOOT_ORIG.hex(' ')})")
    print(f"wrote {a.out}")
    print(f"\nbytes changed vs the original: "
          f"{sum(1 for i in range(0x8000) if rom[i] != orig[i])}")
    # The chips are labelled with this number (DIP1 ACF8, DIP2 2E12) -- see
    # doc/re-notes/method.md.  Label the burned part with the one printed here
    # so it is never mistaken for a stock ROM.
    print(f"md5: {hashlib.md5(rom).hexdigest()}")
    print(f"sum16: {sum(rom) & 0xFFFF:04X}")
    print(f"sum24: {sum(rom) & 0xFFFFFF:06X}")
    print(f"sha256: {hashlib.sha256(rom).hexdigest()}")


if __name__ == "__main__":
    main()
