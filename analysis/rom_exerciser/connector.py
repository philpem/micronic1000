#!/usr/bin/env python3
"""Build a dedicated, polled scanner-connector diagnostic ROM00.

Reclaims session code only because cold boot is redirected before any OS
initialisation. Never use this image for normal operation. The original
ROM and ROM01 are untouched. All original input bytes are SHA-256 guarded.
"""
from __future__ import annotations
import argparse
import hashlib
import json
import os
import tempfile
from pathlib import Path
import sys

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))
from micronic.z80asm import assemble

DEFAULT_ROM = HERE.parent.parent / 'micronic' / 'micron1.bin'
SOURCE = HERE / 'connector.asm'  # v1 compatibility alias
SOURCES = {1: SOURCE, 2: HERE / 'connector_v2.asm'}
ORIGIN, LIMIT = 0x6000, 0x6A00
STOCK_SHA256 = '6226dc1766933e193130112ee9a3304d916f503c57363cfcec00a4179aa66a6f'
BOOT = 0x014B
BOOT_BYTES = bytes.fromhex('f3 2a d0 fb f9 ed 56')
DEFAULT_OUT = HERE / 'releases' / 'connector-v1' / 'micron1_connector_v1.bin'
DEFAULT_OUT_V2 = HERE / 'releases' / 'connector-v2' / 'micron1_connector_v2.bin'


def _source_and_output(version):
    try:
        return SOURCES[version], (DEFAULT_OUT if version == 1 else DEFAULT_OUT_V2)
    except KeyError as exc:
        raise ValueError('connector version must be 1 or 2') from exc


def build_image(rom_path=DEFAULT_ROM, version=1):
    source, _ = _source_and_output(version)
    original = Path(rom_path).read_bytes()
    if len(original) != 32768 or hashlib.sha256(original).hexdigest() != STOCK_SHA256:
        raise ValueError('input is not the verified stock 32K micron1.bin')
    if original[BOOT:BOOT + len(BOOT_BYTES)] != BOOT_BYTES:
        raise ValueError('cold-boot guard mismatch')
    code, symbols = assemble(source.read_text(), origin=ORIGIN)
    if symbols['start'] != ORIGIN or symbols['end'] > LIMIT:
        raise ValueError('connector program exceeds reclaimed session region')
    image = bytearray(original)
    image[ORIGIN:ORIGIN + len(code)] = code
    image[BOOT:BOOT + 3] = b'\xC3' + symbols['start'].to_bytes(2, 'little')
    return bytes(image), symbols, original


def fingerprint(image):
    return {
        'size_bytes': len(image),
        'md5': hashlib.md5(image).hexdigest(),
        'sum16': f'{sum(image) & 0xFFFF:04X}',
        'sum24': f'{sum(image) & 0xFFFFFF:06X}',
        'sha256': hashlib.sha256(image).hexdigest(),
    }


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--rom', type=Path, default=DEFAULT_ROM)
    parser.add_argument('--version', type=int, choices=(1, 2), default=1)
    parser.add_argument('-o', '--out', type=Path)
    args = parser.parse_args(argv)
    source, default_out = _source_and_output(args.version)
    if args.out is None:
        args.out = default_out
    image, symbols, original = build_image(args.rom, version=args.version)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    manifest = {
        'image': args.out.name,
        'purpose': 'standalone connector output/input experiment; ROM00 only',
        'checksums': fingerprint(image),
        'checksum_definition': 'unsigned byte sum modulo 2^16 or 2^24; no complement',
        'stock_sha256': STOCK_SHA256,
        'assembly_sha256': hashlib.sha256(source.read_bytes()).hexdigest(),
        'changed_bytes': sum(a != b for a, b in zip(original, image)),
        'entry': f'ROM00:{symbols["start"]:04X}',
        'end_exclusive': f'ROM00:{symbols["end"]:04X}',
        'hardware_validation': 'not yet run on the physical handheld',
    }
    # Keep v1's published manifest byte-for-byte reproducible. v2 records the
    # explicit source/version needed to distinguish its added PORT2C bit-5 key.
    if args.version == 2:
        manifest['version'] = 2
        manifest['assembly_source'] = source.name
    # Stage on the same filesystem; never expose a partially written image.
    # Pair equality is additionally checked by the release regression test.
    def publish(path, data):
        with tempfile.NamedTemporaryFile(dir=path.parent, prefix=path.name + '.',
                                         delete=False) as staged:
            staged.write(data)
            staged.flush()
            os.fsync(staged.fileno())
            temporary = Path(staged.name)
        if temporary.read_bytes() != data:
            raise OSError('release staging verification failed')
        os.replace(temporary, path)
    publish(args.out, image)
    publish(args.out.with_suffix('.json'), (json.dumps(manifest, indent=2) + '\n').encode())
    print(args.out.resolve())
    print(json.dumps(manifest, indent=2))


if __name__ == '__main__':
    main()
