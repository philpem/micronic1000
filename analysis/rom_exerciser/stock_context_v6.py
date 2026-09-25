#!/usr/bin/env python3
"""One-shot terminal receive status/derived-read diagnostic on v5 boot route.

The extra hook runs only after Link_BlockRx has sampled LINK_STATUS and
rotated through bit 3. It records the sampled byte and count operands,
then executes the four overwritten bytes' control flow. No port access or
delay is added before the terminal status sample.

The N field derives an INI-read count from IX, the active descriptor and B.
It excludes the setup LINK_RXD read and is ambiguous at a 256-byte block
boundary, where B=00h can mean 256 remain.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import pathlib
import tempfile

import stock_context_v5 as v5
from micronic.z80asm import assemble


STATUS_HOOK_SITE = 0x33F8
STATUS_HOOK_BYTES = bytes.fromhex("e1 d1 38 20")  # POP HL; POP DE; JR C,341C

# v5's scratch ends at C7E3. This extension uses the adjacent six bytes.
_DISPLAY_OLD = """                ld a,e
                call lcd_hex
stopped:        jr stopped
end:
"""
_DISPLAY_NEW = """                ld a,e
                call lcd_hex
                ld a,d
                cp 0xEC
                jr nz,stopped            ; no terminal snapshot on ED/EE
                ld a,'S'
                call lcd_putc
                ld a,(SCR_STATUS_ROT)
                rrca
                rrca
                rrca
                rrca
                call lcd_hex
                ld a,'N'
                call lcd_putc
                ; Derived INI count. B=00h at a 256-byte block start
                ; represents 256 remaining, so this case overcounts.
                ld hl,(SCR_TOTAL_REQ)
                ld de,(SCR_SAVED_BC)
                xor a
                sbc hl,de
                ld a,(SCR_REMAINING)
                ld e,a
                ld d,0
                xor a
                sbc hl,de
                ld a,h
                call lcd_hex
                ld a,l
                call lcd_hex
stopped:        jr stopped

; Enter after the fourth RRCA of the one terminal LINK_STATUS sample.
; A is that byte rotated right by four, F contains bit 3 in carry, and
; B is the current INI residual. Save without touching F; replay the two
; POPs and the original status branch before resuming stock code.
terminal_hook:  ld (SCR_STATUS_ROT),a
                ld a,b
                ld (SCR_REMAINING),a
                ld a,(SCR_STATUS_ROT)
                pop hl
                ld (SCR_SAVED_BC),hl
                pop de
                ld (SCR_TOTAL_REQ),ix
                jp c,0x341C
                jp 0x33FC
end:
"""

_base_source = v5.v4.HOOK_SOURCE
if _base_source.count(_DISPLAY_OLD) != 1 or _base_source.count("ld a,'4'") != 1:
    raise ValueError("v5 diagnostic source layout changed")
HOOK_SOURCE = (
    "SCR_STATUS_ROT equ 0xC7E4\n"
    "SCR_REMAINING  equ 0xC7E5\n"
    "SCR_SAVED_BC   equ 0xC7E6\n"
    "SCR_TOTAL_REQ  equ 0xC7E8\n"
    + _base_source.replace("ld a,'4'", "ld a,'6'").replace(_DISPLAY_OLD, _DISPLAY_NEW)
)


def build_image(rom_path=v5.v4.v3.DEFAULT_ROM):
    prior, _, stock = v5.build_image(rom_path)
    if stock[STATUS_HOOK_SITE:STATUS_HOOK_SITE + len(STATUS_HOOK_BYTES)] != STATUS_HOOK_BYTES:
        raise ValueError("stock terminal-status hook guard mismatch")
    code, symbols = assemble(
        f"org 0x{v5.v4.v3.CODE_ORG:04X}\n" + HOOK_SOURCE,
        origin=v5.v4.v3.CODE_ORG,
    )
    if symbols["end"] > v5.v4.v3.CODE_END + 1:
        raise ValueError("v6 hooks exceed the guarded zero cave")
    image = bytearray(prior)
    image[v5.v4.v3.CODE_ORG:v5.v4.v3.CODE_ORG + len(code)] = code
    image[STATUS_HOOK_SITE:STATUS_HOOK_SITE + 4] = (
        b"\xc3" + symbols["terminal_hook"].to_bytes(2, "little") + b"\x00"
    )
    return bytes(image), symbols, stock


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--rom", type=pathlib.Path, default=v5.v4.v3.DEFAULT_ROM)
    parser.add_argument("-o", "--out", type=pathlib.Path, required=True)
    args = parser.parse_args(argv)
    manifest_path = args.out.with_suffix(".json")
    if args.rom.resolve() in (args.out.resolve(), manifest_path.resolve()):
        parser.error("outputs must differ from source ROM")
    image, symbols, stock = build_image(args.rom)
    data = {
        "image": args.out.name,
        "checksums": v5.v4.v3.fingerprint(image),
        "stock_sha256": v5.v4.v3.STOCK_SHA256,
        "basis": "v5 stock-reset diagnostic; terminal-status snapshot after fourth RRCA",
        "patches": [
            {"address": f"ROM00:{address:04X}", "original": original.hex(),
             "replacement": image[address:address + len(original)].hex()}
            for address, original in (
                (v5.v4.v3.RX_CALL_SITE, v5.v4.v3.RX_CALL_BYTES),
                (v5.v4.v3.INIT_SITE, v5.v4.v3.INIT_BYTES),
                (STATUS_HOOK_SITE, STATUS_HOOK_BYTES),
            )
        ],
        "stock_reset_routes": [f"ROM00:{address:04X}" for address, _ in v5.RESET_SITES],
        "assembly_sha256": hashlib.sha256(HOOK_SOURCE.encode("ascii")).hexdigest(),
        "symbols": symbols,
        "display": "R6IaaFF; on EC append SssNnnnn (raw terminal status and derived INI count)",
        "one_shot": True,
        "hardware_validated": False,
    }
    args.out.parent.mkdir(parents=True, exist_ok=True)

    def publish(path, contents):
        with tempfile.NamedTemporaryFile(dir=path.parent, delete=False) as staged:
            staged.write(contents)
            staged.flush()
            os.fsync(staged.fileno())
            temporary = pathlib.Path(staged.name)
        os.replace(temporary, path)

    publish(args.out, image)
    publish(manifest_path, (json.dumps(data, indent=2) + "\n").encode())
    print(json.dumps(data["checksums"], indent=2))


if __name__ == "__main__":
    main()
