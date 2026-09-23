#!/usr/bin/env python3
"""One-shot stock receive result diagnostic, with forced cold boot.

No LCD or yellow writes precede the stock receive call. A RAM snapshot
records dispatch entry; the first return prints R4I + raw A/F and stops.
The six-dwell boot pulse (~5.46 ms) identifies this image to the logger.
"""
import argparse
import hashlib
import os
import tempfile
import json
import pathlib
import sys

HERE = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import stock_context_v3 as v3
import stock_instrument as si
from micronic.z80asm import assemble

# Use the v3 post-return marker and register preservation without changing
# receive I/O. Snapshot HL costs 16 T-states before the stock CALL.
HOOK_SOURCE = v3.HOOK_SOURCE.replace(
    "rx_wrapper:     call LINK_BLOCK_RX",
    "rx_wrapper:     ld (0xC7E0),hl\n                call LINK_BLOCK_RX")
HOOK_SOURCE = HOOK_SOURCE.replace(
    "                pop af\n                ret\n\n; The loop",
    "                pop af\n                jp show_result\n\n; The loop", 1)
HOOK_SOURCE = HOOK_SOURCE.replace(
    "                call delay_1ms\n                ld a,(SHADOW_2A)\n                and 0xFE",
    "                call delay_1ms\n                call delay_1ms\n                call delay_1ms\n                ld a,(SHADOW_2A)\n                and 0xFE")
HOOK_SOURCE = HOOK_SOURCE.replace("\nend:\n", "\n") + si.COMMON + r"""
; AF is the exact stock receive return, restored by the v3 marker wrapper.
; This is deliberately one-shot: no header/session acceptance is claimed.
show_result:    push af
                pop de
                ld (0xC7E2),de
                di
                call lcd_home
                ld a,'R'
                call lcd_putc
                ld a,'4'
                call lcd_putc
                ld a,'I'
                call lcd_putc
                ld a,d
                call lcd_hex
                ld a,e
                call lcd_hex
stopped:        jr stopped
end:
"""


def build_image(rom_path=v3.DEFAULT_ROM):
    # v3 validates the complete source hash, patch sites and zero cave.
    _, _, original = v3.build_image(rom_path)
    code, symbols = assemble(f"org 0x{v3.CODE_ORG:04X}\n" + HOOK_SOURCE,
                             origin=v3.CODE_ORG)
    if symbols["end"] > v3.CODE_END + 1:
        raise ValueError("v4 hooks exceed the guarded zero cave")
    image = bytearray(original)
    si.apply_coldstart_patches(image, original)
    image[v3.CODE_ORG:v3.CODE_ORG + len(code)] = code
    image[v3.RX_CALL_SITE:v3.RX_CALL_SITE + 3] = b"\xcd" + symbols["rx_wrapper"].to_bytes(2, "little")
    image[v3.INIT_SITE:v3.INIT_SITE + 5] = b"\xcd" + symbols["init_wrapper"].to_bytes(2, "little") + bytes(2)
    return bytes(image), symbols, original


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--rom", type=pathlib.Path, default=v3.DEFAULT_ROM)
    ap.add_argument("-o", "--out", type=pathlib.Path, required=True)
    args = ap.parse_args(argv)
    manifest_path = args.out.with_suffix(".json")
    if args.rom.resolve() in (args.out.resolve(), manifest_path.resolve()):
        ap.error("outputs must differ from source ROM")
    image, symbols, original = build_image(args.rom)
    patches = []
    for addr, expected in [*si.WARMSTART_JUMPS,
                           (0x3708, original[0x3708:0x370A]),
                           (v3.RX_CALL_SITE, v3.RX_CALL_BYTES),
                           (v3.INIT_SITE, v3.INIT_BYTES)]:
        patches.append({"address": f"ROM00:{addr:04X}",
                        "original": expected.hex(),
                        "replacement": image[addr:addr + len(expected)].hex()})
    data = {"image": args.out.name, "checksums": v3.fingerprint(image),
            "stock_sha256": v3.STOCK_SHA256, "patches": patches,
            "assembly_sha256": hashlib.sha256(HOOK_SOURCE.encode("ascii")).hexdigest(),
            "symbols": symbols, "boot_low_dwell_calls": 6,
            "display": "R4I followed by two hex digits A and two hex digits F",
            "one_shot": True, "hardware_validated": False}
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
