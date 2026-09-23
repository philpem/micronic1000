#!/usr/bin/env python3
"""Build a guarded stock-ROM diagnostic for live V24 receive context.

One guarded patch wraps LinkRxDispatcher's call to Link_BlockRx. It calls
the stock reader once, preserves its return registers, and emits a bounded
yellow/pin-6 pulse after receive returns. Another guarded patch adds a
distinct logger witness to the shared cold/warm restart latch initialization.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import pathlib
import sys
import tempfile

HERE = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))
from micronic.z80asm import assemble

DEFAULT_ROM = HERE.parent.parent / "micronic" / "micron1.bin"
STOCK_SHA256 = "6226dc1766933e193130112ee9a3304d916f503c57363cfcec00a4179aa66a6f"
CODE_ORG = 0x7E96
CODE_END = 0x7FF9
RX_CALL_SITE = 0x2FC1
RX_CALL_BYTES = bytes.fromhex("cd 78 33")
INIT_SITE = 0x0252
INIT_BYTES = bytes.fromhex("32 8b f7 d3 2a")
LINK_BLOCK_RX = 0x3378
PORT_2A = 0x2A
SHADOW_2A = 0xF78B

HOOK_SOURCE = r"""
PORT_2A         equ 0x2A
SHADOW_2A       equ 0xF78B
LINK_BLOCK_RX   equ 0x3378

; Call stock Link_BlockRx once and preserve return AF/BC/DE/HL on the stack.
; Pin 6 sinks when port-2A bit 0 is set. Only after RX returns, emit about
; 0.9 ms on carry-set error or 1.8 ms on carry-clear success. Release first
; so the pulse has an edge even if the incoming shadow was already set.
; Hold each release for about 450 us: a shorter transition can be missed
; by the Uno pin-change interrupt before the sink or shadow restore.
rx_wrapper:     call LINK_BLOCK_RX
                push af
                push bc
                push de
                push hl
                jr c,rx_error
rx_success:     ld a,(SHADOW_2A)
                push af
                and 0xFE
                out (PORT_2A),a
                call delay_450us
                pop af
                push af
                or 0x01
                out (PORT_2A),a
                call delay_1ms
                call delay_1ms
                jr rx_pulse_end
rx_error:       ld a,(SHADOW_2A)
                push af
                and 0xFE
                out (PORT_2A),a
                call delay_450us
                pop af
                push af
                or 0x01
                out (PORT_2A),a
                call delay_1ms
rx_pulse_end:   pop af
                push af
                and 0xFE
                out (PORT_2A),a
                call delay_450us
                pop af
                out (PORT_2A),a
                pop hl
                pop de
                pop bc
                pop af
                ret

; The loop is 3327 T-states (~0.9 ms at 3.6864 MHz), plus wrapper overhead.
delay_1ms:      ld b,0xFF
delay_loop:     djnz delay_loop
                ret
; 1663 T-states (451.1 us at 3.6864 MHz), including RET but excluding CALL.
delay_450us:    ld b,0x7F
guard_loop:     djnz guard_loop
                ret

; Common cold/warm restart at 0252. Reproduce the overwritten shadow store
; and latch write before emitting a distinct ~3.6 ms boot/logger witness.
; At the call site A=20h and SP has just been set to F81Ah.
init_wrapper:   ld (SHADOW_2A),a
                out (PORT_2A),a
                push af
                push bc
                push de
                push hl
                and 0xFE
                out (PORT_2A),a
                call delay_450us
                ld a,(SHADOW_2A)
                or 0x01
                out (PORT_2A),a
                call delay_1ms
                call delay_1ms
                call delay_1ms
                call delay_1ms
                ld a,(SHADOW_2A)
                and 0xFE
                out (PORT_2A),a
                call delay_450us
                ld a,(SHADOW_2A)
                out (PORT_2A),a
                pop hl
                pop de
                pop bc
                pop af
                ret
end:
"""


def build_image(rom_path: pathlib.Path | str = DEFAULT_ROM):
    """Return (image, symbols, original) after strict stock-byte guards."""
    original = pathlib.Path(rom_path).read_bytes()
    if len(original) != 0x8000 or hashlib.sha256(original).hexdigest() != STOCK_SHA256:
        raise ValueError("input is not the verified stock 32K micron1.bin")
    if original[CODE_ORG:CODE_END + 1] != bytes(CODE_END - CODE_ORG + 1):
        raise ValueError("stock hook cave is not all zero")
    if original[RX_CALL_SITE:RX_CALL_SITE + len(RX_CALL_BYTES)] != RX_CALL_BYTES:
        raise ValueError("Link_BlockRx call guard mismatch at ROM00:2FC1")
    if original[INIT_SITE:INIT_SITE + len(INIT_BYTES)] != INIT_BYTES:
        raise ValueError("restart latch guard mismatch at ROM00:0252")

    code, symbols = assemble(
        f"org 0x{CODE_ORG:04X}\n" + HOOK_SOURCE, origin=CODE_ORG)
    if symbols["rx_wrapper"] != CODE_ORG or symbols["end"] > CODE_END + 1:
        raise ValueError("stock context hooks exceed the verified ROM cave")

    image = bytearray(original)
    rx_patch = bytes([0xCD]) + symbols["rx_wrapper"].to_bytes(2, "little")
    init_patch = (bytes([0xCD]) + symbols["init_wrapper"].to_bytes(2, "little")
                  + bytes([0x00, 0x00]))
    image[RX_CALL_SITE:RX_CALL_SITE + len(rx_patch)] = rx_patch
    image[INIT_SITE:INIT_SITE + len(init_patch)] = init_patch
    image[CODE_ORG:CODE_ORG + len(code)] = code
    return bytes(image), symbols, original


def fingerprint(image: bytes):
    return {
        "size_bytes": len(image),
        "md5": hashlib.md5(image).hexdigest(),
        "sum16": f"{sum(image) & 0xFFFF:04X}",
        "sum24": f"{sum(image) & 0xFFFFFF:06X}",
        "sha256": hashlib.sha256(image).hexdigest(),
    }


def manifest(image: bytes, symbols: dict, original: bytes, image_name: str):
    return {
        "image": image_name,
        "revision": 2,
        "purpose": "stock-context receive diagnostic; guarded ROM00 wrapper",
        "patch": {
            "address": f"ROM00:{RX_CALL_SITE:04X}",
            "original_bytes": RX_CALL_BYTES.hex(" "),
            "replacement": f"CALL ROM00:{symbols['rx_wrapper']:04X}",
        },
        "init_patch": {
            "address": f"ROM00:{INIT_SITE:04X}",
            "original_bytes": INIT_BYTES.hex(" "),
            "replacement": f"CALL ROM00:{symbols['init_wrapper']:04X}; NOP; NOP",
            "scope": "common cold/warm restart after LD SP,F81Ah",
        },
        "stock_sha256": STOCK_SHA256,
        "assembly_sha256": hashlib.sha256(HOOK_SOURCE.encode("ascii")).hexdigest(),
        "changed_bytes": sum(a != b for a, b in zip(original, image)),
        "entry": f"ROM00:{symbols['rx_wrapper']:04X}",
        "end_exclusive": f"ROM00:{symbols['end']:04X}",
        "checksums": fingerprint(image),
        "checksum_definition": "unsigned byte sum modulo 2^16 or 2^24; no complement",
        "marker": {
            "pin": "yellow/pin 6",
            "port": "2Ah bit 0",
            "sink_value": 1,
            "error_dwell_tstates": 3327,
            "success_dwell_tstates": 6654,
            "release_guard_tstates": 1663,
            "release_guards": 2,
            "clock_hz": 3686400,
            "timing_note": "subroutine times include RET; CALL and wrapper instructions add time",
            "tested_out_intervals_tstates": {"carry_set": [1719, 3383, 1701], "carry_clear": [1719, 6739, 1701]},
            "order": "after stock Link_BlockRx returns: release, guard, sink, dwell, release, guard, restore shadow",
        },
        "init_marker": {
            "pin": "yellow/pin 6",
            "sink_value": 1,
            "dwell_tstates": 13308,
            "release_guard_tstates": 1663,
            "release_guards": 2,
            "clock_hz": 3686400,
            "timing_note": "four dwell subroutines including RET; CALL and wrapper add time",
            "tested_low_tstates": 13407,
            "scope": "common cold/warm restart, distinct from RX result marker",
        },
    }


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--rom", type=pathlib.Path, default=DEFAULT_ROM)
    parser.add_argument("-o", "--out", required=True, type=pathlib.Path)
    parser.add_argument("--manifest-out", type=pathlib.Path)
    args = parser.parse_args(argv)
    source = args.rom.resolve()
    if args.out.resolve() == source or (args.manifest_out and
                                        args.manifest_out.resolve() == source):
        parser.error("output paths must differ from the source ROM")
    image, symbols, original = build_image(args.rom)

    if args.manifest_out and args.manifest_out.resolve() == args.out.resolve():
        parser.error("--manifest-out must differ from the image path")

    def publish(path, contents):
        path.parent.mkdir(parents=True, exist_ok=True)
        with tempfile.NamedTemporaryFile(dir=path.parent, prefix=path.name + ".",
                                         delete=False) as staged:
            staged.write(contents)
            staged.flush()
            os.fsync(staged.fileno())
            temporary = pathlib.Path(staged.name)
        if temporary.read_bytes() != contents:
            raise OSError("staged image verification failed")
        os.replace(temporary, path)

    publish(args.out, image)
    data = manifest(image, symbols, original, args.out.name)
    if args.manifest_out:
        publish(args.manifest_out, (json.dumps(data, indent=2) + "\n").encode())
    print(args.out.resolve())
    print(f"wrapper ROM00:{symbols['rx_wrapper']:04X}; "
          f"changed bytes {sum(a != b for a, b in zip(original, image))}")


if __name__ == "__main__":
    main()
