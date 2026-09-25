#!/usr/bin/env python3
"""Guarded active-buffer and terminal-byte diagnostic, with stock reset routes.

All receive code and timing through the yellow marker match v7. After
return, with interrupts disabled, snapshot the first two bytes of the
active descriptor buffer into the former saved-BC display slot. These
are RAM reads only; validity depends on the captured pointer advancement.
The separate terminal byte is still captured immediately after its INI.
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
import stock_context_v7 as v7

v5 = v6.v5
v3 = v5.v4.v3
STATUS_HOOK_SITE = v6.STATUS_HOOK_SITE
STATUS_HOOK_BYTES = v6.STATUS_HOOK_BYTES

# E0-E3 retain entry-HL and return-AF. C7EE-EF temporarily holds saved BC
# at the terminal hook; after return it is replaced by two buffer bytes.
# All other record fields retain v7 meaning.
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
                ; Snapshot active-buffer bytes only after cleanup/marker.
                ; Slot validity is decoded from length and next-write pointer.
                ld hl,(SCR_BUFFER)
                ld de,SCR_SAVED_BC
                ld bc,2
                ldir
                ; Row 1: R8IaaFF:ssvvLLLLPPPP (exactly 20 characters).
                ld a,':'
                call lcd_putc
                ld hl,SCR_STATUS
                ld b,6
                call lcd_dump
                ; Row 2: XDDDDWWWWbbccTTTTRR and one clearing space.
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
HOOK_SOURCE = PREFIX + _base.replace("ld a,'4'", "ld a,'8'").replace(
    v6._DISPLAY_OLD, DISPLAY)


def build_image(rom_path=v3.DEFAULT_ROM):
    prior, _, stock = v5.build_image(rom_path)
    if stock[STATUS_HOOK_SITE:STATUS_HOOK_SITE + 4] != STATUS_HOOK_BYTES:
        raise ValueError("stock terminal-status hook guard mismatch")
    code, symbols = assemble(f"org 0x{v3.CODE_ORG:04X}\n" + HOOK_SOURCE,
                             origin=v3.CODE_ORG)
    if symbols["end"] > v3.CODE_END + 1:
        raise ValueError("v8 hooks exceed the guarded zero cave")
    image = bytearray(prior)
    image[v3.CODE_ORG:v3.CODE_END + 1] = bytes(v3.CODE_END - v3.CODE_ORG + 1)
    image[v3.CODE_ORG:v3.CODE_ORG + len(code)] = code
    image[STATUS_HOOK_SITE:STATUS_HOOK_SITE + 4] = (
        b"\xC3" + symbols["terminal_hook"].to_bytes(2, "little") + b"\x00")
    return bytes(image), symbols, stock


def decode_readout(text):
    """Decode v8; stale sample slots never become reported received bytes.

    Buffer length/content is a post-return snapshot. Counts describe the
    active descriptor only; earlier descriptors are not retained here.
    """
    compact = re.sub(r"\s+", "", text).upper()
    if not compact.startswith("R8I"):
        raise ValueError("expected v8 readout")
    result = v7.decode_readout("R7I" + compact[3:])
    record = result["terminal_record"]
    if record is None:
        return result
    sample = int(record.pop("saved_bc"), 16).to_bytes(2, "little")
    advance = record["active_descriptor_pointer_advance_mod65536"]
    length = record["descriptor_length"]
    terminal = int(record["terminal_byte_valid"])
    consistent = (0 < length and terminal <= advance <= length
                  and ((length - advance) & 255) == int(record["residual_b"], 16))
    valid_count = min(2, advance) if consistent else 0
    record.update({
        "buffer_snapshot_consistent": consistent,
        "buffer_sample_raw": sample.hex().upper(),
        "buffer_sample_bytes": [f"{value:02X}" if i < valid_count else None
                                for i, value in enumerate(sample)],
        "active_descriptor_ordinary_reads": advance - terminal if consistent else None,
        "active_descriptor_bytes_not_shown": max(0, advance - 2) if consistent else None,
        "sample_scope": "first two active-buffer bytes, copied after return; descriptor stability assumed",
    })
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
        "basis": "v7 receive/return/marker timing unchanged; post-return two-byte RAM snapshot",
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
        "scratch_ram": "C7E0-C7F2 (upper TPA diagnostic scratch; only assessed for the controlled FOO trial)",
        "display_rows": ["R8IaaFF:ssvvLLLLPPPP", "XDDDDWWWWbbccTTTTRR "],
        "word_encoding": "raw little-endian byte order; use --decode",
        "terminal_byte_validity": "vv is valid only when ss bit 2 is set; otherwise slot is 00",
        "non_ec_display": "R8IaaFF only; ignore stale LCD suffix/second row",
        "buffer_sample_validity": "bb/cc only valid when pointer advancement and descriptor length/residual agree; use --decode",
        "buffer_sample_scope": "First two active-buffer bytes; saved BC display removed; not earlier descriptors",
        "snapshot_limits": "Controlled FOO trial; buffers/descriptors must not overlap scratch C7E0-C7F2; no concurrent writers",
        "timing_vs_v7": {"receive_and_yellow_tstates": 0,
                         "post_marker_snapshot_extra_tstates": 73},
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
