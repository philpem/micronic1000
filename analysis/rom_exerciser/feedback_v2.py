#!/usr/bin/env python3
"""Build the standalone combined IR feedback diagnostic for ROM00.

The cold-boot jump enters a private program in reclaimed session space.  It
does not alter either released connector-probe image and guards every input
ROM byte before assembling a burn image.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import sys
import tempfile

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))
from micronic.z80asm import assemble

DEFAULT_ROM = HERE.parent.parent / "micronic" / "micron1.bin"
SOURCE = HERE / "feedback_v2.asm"
ORIGIN, LIMIT = 0x6000, 0x6A00
# Cycle counts use documented Z80 timings for the assembled loop and byte-
# verified 34BD/34D2 helpers. The formulas and branch buckets are in the ASM.
FAST_SAMPLE_COUNT = 1000
FAST_K_SAMPLE_COUNT = 600
# Exact branch-bucket totals from the auditable ASM table below.
FAST_SAMPLE_AUDITED_TSTATES = 321_261
FAST_K_SAMPLE_AUDITED_TSTATES = 327_468
FAST_SAMPLE_MAX_TSTATES = 340_000
FAST_K_SAMPLE_MAX_TSTATES = 360_000
BOOT = 0x014B
BOOT_BYTES = bytes.fromhex("f3 2a d0 fb f9 ed 56")
STOCK_SHA256 = "6226dc1766933e193130112ee9a3304d916f503c57363cfcec00a4179aa66a6f"


def build_image(rom_path=DEFAULT_ROM):
    """Return a guarded feedback image, symbols, and untouched stock bytes."""
    original = Path(rom_path).read_bytes()
    if len(original) != 32768 or hashlib.sha256(original).hexdigest() != STOCK_SHA256:
        raise ValueError("input is not the verified stock 32K micron1.bin")
    if original[BOOT:BOOT + len(BOOT_BYTES)] != BOOT_BYTES:
        raise ValueError("cold-boot guard mismatch")
    code, symbols = assemble(SOURCE.read_text(), origin=ORIGIN)
    if symbols["start"] != ORIGIN or symbols["end"] > LIMIT:
        raise ValueError("feedback program exceeds reclaimed session region")
    image = bytearray(original)
    image[ORIGIN:ORIGIN + len(code)] = code
    image[BOOT:BOOT + 3] = b"\xC3" + symbols["start"].to_bytes(2, "little")
    return bytes(image), symbols, original


def fingerprint(image):
    return {
        "size_bytes": len(image),
        "md5": hashlib.md5(image).hexdigest(),
        "sum16": f"{sum(image) & 0xffff:04X}",
        "sum24": f"{sum(image) & 0xffffff:06X}",
        "sha256": hashlib.sha256(image).hexdigest(),
    }


def manifest(image, symbols, original, image_name):
    return {
        "image": image_name,
        "purpose": "standalone combined IR feedback v2 diagnostic; ROM00 only",
        "record_version": 2,
        "fast_summary_record_bytes": "18..25: OR, AND, first bit-4 index LE, first bit-0 index LE, sample count LE",
        "capture_modes": {
            "H": {"mode": 5, "samples": FAST_SAMPLE_COUNT,
                  "audited_tstates": FAST_SAMPLE_AUDITED_TSTATES,
                  "max_tstates": FAST_SAMPLE_MAX_TSTATES,
                  "max_ms_at_3_6864_mhz": round(FAST_SAMPLE_MAX_TSTATES / 3686.4, 2),
                  "control": "LINK_CTRL bits 6/7 high via ROM00:34BD"},
            "J": {"mode": 6, "samples": FAST_SAMPLE_COUNT,
                  "audited_tstates": FAST_SAMPLE_AUDITED_TSTATES,
                  "max_tstates": FAST_SAMPLE_MAX_TSTATES,
                  "max_ms_at_3_6864_mhz": round(FAST_SAMPLE_MAX_TSTATES / 3686.4, 2),
                  "control": "LINK_CTRL bits 6/7 low via ROM00:34D2"},
            "K": {"mode": 7, "samples": FAST_K_SAMPLE_COUNT,
                  "audited_tstates": FAST_K_SAMPLE_AUDITED_TSTATES,
                  "max_tstates": FAST_K_SAMPLE_MAX_TSTATES,
                  "max_ms_at_3_6864_mhz": round(FAST_K_SAMPLE_MAX_TSTATES / 3686.4, 2),
                  "control": "repeated 34D2; one full LINK_STATUS read/test; 34BD if bit4 clear",
                  "limit": "no active stock TX/IRQ context; on pending this resumes sampling instead of dispatching RX"},
        },
        "checksums": fingerprint(image),
        "checksum_definition": "unsigned byte sum modulo 2^16 or 2^24; no complement",
        "stock_sha256": STOCK_SHA256,
        "assembly_sha256": hashlib.sha256(SOURCE.read_bytes()).hexdigest(),
        "changed_bytes": sum(a != b for a, b in zip(original, image)),
        "entry": f"ROM00:{symbols['start']:04X}",
        "end_exclusive": f"ROM00:{symbols['end']:04X}",
    }


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--rom", type=Path, default=DEFAULT_ROM)
    parser.add_argument("-o", "--out", required=True, type=Path)
    parser.add_argument("--manifest-out", type=Path)
    args = parser.parse_args(argv)
    image, symbols, original = build_image(args.rom)
    if args.manifest_out and args.manifest_out.resolve() == args.out.resolve():
        parser.error("--manifest-out must differ from the image path")
    args.out.parent.mkdir(parents=True, exist_ok=True)
    data = manifest(image, symbols, original, args.out.name)
    def publish(path, contents):
        with tempfile.NamedTemporaryFile(dir=path.parent, prefix=path.name + ".",
                                         delete=False) as staged:
            staged.write(contents)
            staged.flush()
            os.fsync(staged.fileno())
            temporary = Path(staged.name)
        if temporary.read_bytes() != contents:
            raise OSError("feedback image staging verification failed")
        os.replace(temporary, path)
    publish(args.out, image)
    if args.manifest_out:
        args.manifest_out.parent.mkdir(parents=True, exist_ok=True)
        publish(args.manifest_out, (json.dumps(data, indent=2) + "\n").encode())
    print(args.out.resolve())
    print(json.dumps(data, indent=2))


if __name__ == "__main__":
    main()
