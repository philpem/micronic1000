#!/usr/bin/env python3
"""Stock-context receive diagnostic with the original reset routes restored.

This is a single-variable comparison against v4 for physical boot. It keeps
the v4 receive wrapper, display and yellow markers byte-for-byte, while
restoring all five reset-route changes made by v4.
"""
import argparse
import hashlib
import json
import os
import pathlib
import tempfile

import stock_context_v4 as v4
from micronic.z80asm import assemble


RESET_SITES = (*v4.si.WARMSTART_JUMPS, (0x3708, bytes.fromhex("4d 02")))


def build_image(rom_path=v4.v3.DEFAULT_ROM):
    # V3 validates the stock ROM, every changed call site and the zero cave.
    _, _, stock = v4.v3.build_image(rom_path)
    code, symbols = assemble(f"org 0x{v4.v3.CODE_ORG:04X}\n" + v4.HOOK_SOURCE,
                             origin=v4.v3.CODE_ORG)
    if symbols["end"] > v4.v3.CODE_END + 1:
        raise ValueError("v5 hooks exceed the guarded zero cave")
    image = bytearray(stock)
    image[v4.v3.CODE_ORG:v4.v3.CODE_ORG + len(code)] = code
    image[v4.v3.RX_CALL_SITE:v4.v3.RX_CALL_SITE + 3] = (
        b"\xcd" + symbols["rx_wrapper"].to_bytes(2, "little"))
    image[v4.v3.INIT_SITE:v4.v3.INIT_SITE + 5] = (
        b"\xcd" + symbols["init_wrapper"].to_bytes(2, "little") + bytes(2))
    for address, expected in RESET_SITES:
        if stock[address:address + len(expected)] != expected:
            raise ValueError(f"stock reset-route guard mismatch at {address:04X}")
    return bytes(image), symbols, stock


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--rom", type=pathlib.Path, default=v4.v3.DEFAULT_ROM)
    parser.add_argument("-o", "--out", type=pathlib.Path, required=True)
    args = parser.parse_args(argv)
    manifest_path = args.out.with_suffix(".json")
    if args.rom.resolve() in (args.out.resolve(), manifest_path.resolve()):
        parser.error("outputs must differ from source ROM")
    image, symbols, stock = build_image(args.rom)
    patch_sites = (
        (v4.v3.RX_CALL_SITE, v4.v3.RX_CALL_BYTES),
        (v4.v3.INIT_SITE, v4.v3.INIT_BYTES),
    )
    data = {
        "image": args.out.name,
        "checksums": v4.v3.fingerprint(image),
        "stock_sha256": v4.v3.STOCK_SHA256,
        "basis": "v4 receive/display/marker code; original reset routes",
        "patches": [
            {"address": f"ROM00:{address:04X}", "original": expected.hex(),
             "replacement": image[address:address + len(expected)].hex()}
            for address, expected in patch_sites
        ],
        "restored_stock_reset_routes": [f"ROM00:{address:04X}"
                                        for address, _ in RESET_SITES],
        "assembly_sha256": hashlib.sha256(v4.HOOK_SOURCE.encode("ascii")).hexdigest(),
        "symbols": symbols,
        "boot_low_dwell_calls": 6,
        "display": "R4I followed by two hex digits A and two hex digits F",
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
