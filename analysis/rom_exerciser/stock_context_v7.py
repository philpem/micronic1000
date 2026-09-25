#!/usr/bin/env python3
"""Guarded terminal-byte/active-descriptor diagnostic, with stock reset routes.

The receive wrapper and all receive I/O through the terminal status sample
are unchanged from v6. Only after that sample, capture the optional terminal
INI's destination byte from RAM (never re-read LINK_RXD), then replay stock
control flow. After cleanup and the yellow marker, display two 20-column
rows. Multi-byte fields are raw little-endian bytes; decode_readout names them.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import pathlib
import re
import tempfile

import stock_context_v6 as v6
from micronic.z80asm import assemble

v5 = v6.v5
v3 = v5.v4.v3
STATUS_HOOK_SITE = v6.STATUS_HOOK_SITE
STATUS_HOOK_BYTES = v6.STATUS_HOOK_BYTES

# E0-E3 retain v4/v6 entry-HL and return-AF snapshots. The remaining record
# is contiguous so two short hex-dump loops fit the existing guarded cave.
PREFIX = r"""
SCR_STATUS      equ 0xC7E4
SCR_BYTE        equ 0xC7E5
SCR_LENGTH      equ 0xC7E6
SCR_BUFFER      equ 0xC7E8
SCR_DESCRIPTOR  equ 0xC7EA
SCR_WRITE       equ 0xC7EC
SCR_SAVED_BC    equ 0xC7EE
SCR_TOTAL       equ 0xC7F0
SCR_REMAINING   equ 0xC7F2
"""

DISPLAY = r"""                ld a,e
                call lcd_hex
                ld a,d
                cp 0xEC
                jr nz,stopped
                ; The saved cursor is immediately past the active descriptor.
                ; Copy its length/pointer only after the receive has returned.
                ld hl,(SCR_DESCRIPTOR)
                dec hl
                dec hl
                dec hl
                dec hl
                ld (SCR_DESCRIPTOR),hl
                ld de,SCR_LENGTH
                ld bc,4
                ldir
                ; Row 1: R7IaaFF:ssvvLLLLPPPP (exactly 20 characters).
                ld a,':'
                call lcd_putc
                ld hl,SCR_STATUS
                ld b,6
                call lcd_dump
                ; Row 2: XDDDDWWWWCCCCTTTTRR and one clearing space.
                ld a,'X'
                call lcd_putc
                ld hl,SCR_DESCRIPTOR
                ld b,9
                call lcd_dump
                ld a,' '
                call lcd_putc
stopped:        jr stopped

lcd_dump:       ld a,(hl)
                call lcd_hex
                inc hl
                djnz lcd_dump
                ret

; Enter after the fourth RRCA of the terminal LINK_STATUS sample.
; Preserve its AF, BC, HL and IX, and the original two-POP continuation.
; A raw-status bit-2 set proves INI just wrote (HL-1). Read RAM only.
terminal_hook:  push af
                rrca
                rrca
                rrca
                rrca
                ld (SCR_STATUS),a
                ld (SCR_WRITE),hl
                ld (SCR_TOTAL),ix
                ld a,b
                ld (SCR_REMAINING),a
                xor a
                ld (SCR_BYTE),a
                ld a,(SCR_STATUS)
                and 0x04
                jr z,no_terminal_byte
                dec hl
                ld a,(hl)
                ld (SCR_BYTE),a
                inc hl
no_terminal_byte:
                pop af
                pop hl
                ld (SCR_SAVED_BC),hl
                pop de
                ld (SCR_DESCRIPTOR),de
                jp c,0x341C
                jp 0x33FC
end:
"""

_base = v5.v4.HOOK_SOURCE
if _base.count(v6._DISPLAY_OLD) != 1 or _base.count("ld a,'4'") != 1:
    raise ValueError("base diagnostic source layout changed")
HOOK_SOURCE = PREFIX + _base.replace("ld a,'4'", "ld a,'7'").replace(
    v6._DISPLAY_OLD, DISPLAY)


def build_image(rom_path=v3.DEFAULT_ROM):
    prior, _, stock = v5.build_image(rom_path)
    if stock[STATUS_HOOK_SITE:STATUS_HOOK_SITE + 4] != STATUS_HOOK_BYTES:
        raise ValueError("stock terminal-status hook guard mismatch")
    code, symbols = assemble(f"org 0x{v3.CODE_ORG:04X}\n" + HOOK_SOURCE,
                             origin=v3.CODE_ORG)
    if symbols["end"] > v3.CODE_END + 1:
        raise ValueError("v7 hooks exceed the guarded zero cave")
    image = bytearray(prior)
    image[v3.CODE_ORG:v3.CODE_END + 1] = bytes(v3.CODE_END - v3.CODE_ORG + 1)
    image[v3.CODE_ORG:v3.CODE_ORG + len(code)] = code
    image[STATUS_HOOK_SITE:STATUS_HOOK_SITE + 4] = (
        b"\xC3" + symbols["terminal_hook"].to_bytes(2, "little") + b"\x00")
    return bytes(image), symbols, stock


def decode_readout(text):
    """Decode complete printed rows; never interpret an invalid byte slot.

    Only whitespace is ignored. For EE/ED/success the ROM prints seven
    characters and stops; any old LCD suffix is not a terminal record.
    """
    compact = re.sub(r"\s+", "", text).upper()
    match = re.fullmatch(r"R7I([0-9A-F]{2})([0-9A-F]{2})(?::([0-9A-F]{12})X([0-9A-F]{18}))?", compact)
    if not match:
        raise ValueError("expected R7IaaFF or both complete v7 EC rows")
    a, f = int(match[1], 16), int(match[2], 16)
    result = {"a": f"{a:02X}", "f": f"{f:02X}", "carry": bool(f & 1)}
    if match[3] is None:
        if a == 0xEC:
            raise ValueError("EC readout requires both terminal-record rows")
        result["terminal_record"] = None
        return result
    if a != 0xEC:
        raise ValueError("only EC returns display a terminal record")
    record = bytes.fromhex(match[3] + match[4])
    word = lambda offset: int.from_bytes(record[offset:offset + 2], "little")
    status, value = record[:2]
    length, buffer, descriptor, write, saved_bc, total = [word(i) for i in (2, 4, 6, 8, 10, 12)]
    result["terminal_record"] = {
        "link_status": f"{status:02X}",
        "terminal_byte_valid": bool(status & 4),
        "terminal_byte": f"{value:02X}" if status & 4 else None,
        "descriptor_address": f"{descriptor:04X}",
        "descriptor_length": length,
        "buffer_address": f"{buffer:04X}",
        "next_write_address": f"{write:04X}",
        "saved_bc": f"{saved_bc:04X}",
        "total_requested_through_active_descriptor": total,
        "residual_b": f"{record[14]:02X}",
        "active_descriptor_pointer_advance_mod65536": (write - buffer) & 0xFFFF,
    }
    return result


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--rom", type=pathlib.Path, default=v3.DEFAULT_ROM)
    parser.add_argument("-o", "--out", type=pathlib.Path)
    parser.add_argument("--decode", help="quoted readout; whitespace between rows allowed")
    args = parser.parse_args(argv)
    if args.decode is not None:
        if args.out is not None:
            parser.error("--decode and --out are mutually exclusive")
        try:
            decoded = decode_readout(args.decode)
        except ValueError as error:
            parser.error(str(error))
        print(json.dumps(decoded, indent=2))
        return
    if args.out is None:
        parser.error("--out is required when building")
    manifest_path = args.out.with_suffix(".json")
    if args.out.resolve() == manifest_path.resolve():
        parser.error("image and manifest outputs must differ (use a .bin image)")
    if args.rom.resolve() in (args.out.resolve(), manifest_path.resolve()):
        parser.error("outputs must differ from source ROM")
    image, symbols, stock = build_image(args.rom)
    data = {
        "image": args.out.name,
        "checksums": v3.fingerprint(image),
        "stock_sha256": v3.STOCK_SHA256,
        "basis": "v6 receive timing through terminal sample; stock reset routes",
        "patches": [
            {"address": f"ROM00:{address:04X}", "original": original.hex(),
             "replacement": image[address:address + len(original)].hex()}
            for address, original in ((v3.RX_CALL_SITE, v3.RX_CALL_BYTES),
                                      (v3.INIT_SITE, v3.INIT_BYTES),
                                      (STATUS_HOOK_SITE, STATUS_HOOK_BYTES))
        ],
        "stock_reset_routes": [f"ROM00:{a:04X}" for a, _ in v5.RESET_SITES],
        "assembly_sha256": hashlib.sha256(HOOK_SOURCE.encode("ascii")).hexdigest(),
        "symbols": symbols,
        "scratch_ram": "C7E0-C7F2 (upper TPA; no loaded application)",
        "display_rows": ["R7IaaFF:ssvvLLLLPPPP", "XDDDDWWWWCCCCTTTTRR "],
        "word_encoding": "raw little-endian byte order; use --decode",
        "terminal_byte_validity": "vv is valid only when ss bit 2 is set; otherwise slot is 00",
        "non_ec_display": "R7IaaFF only; ignore stale LCD suffix/second row",
        "timing_vs_v6": {
            "through_terminal_sample_tstates": 0,
            "post_sample_extra_tstates_no_terminal_ini": 109,
            "post_sample_extra_tstates_with_terminal_ini": 136,
            "timeout_or_exhaustion_extra_tstates": 0,
            "yellow_error_intervals_tstates": [1719, 3383, 1701],
            "yellow_success_intervals_tstates": [1719, 6739, 1701],
            "clock_hz": 3686400,
            "note": "Only marker onset/stock cleanup after the terminal sample are delayed; pulse widths unchanged",
        },
        "one_shot": True,
        "hardware_validated": False,
    }
    args.out.parent.mkdir(parents=True, exist_ok=True)
    for path, contents in ((args.out, image), (manifest_path, (json.dumps(data, indent=2) + "\n").encode())):
        with tempfile.NamedTemporaryFile(dir=path.parent, delete=False) as staged:
            staged.write(contents)
            staged.flush()
            os.fsync(staged.fileno())
            temporary = pathlib.Path(staged.name)
        os.replace(temporary, path)
    print(json.dumps(data["checksums"], indent=2))


if __name__ == "__main__":
    main()
