# Program file formats — COM and DIP

This page states the **image contract** for programs that DIPOS-B loads
at runtime via the Load/Run Program menu. It describes the bytes a tool
must produce; the loader mechanics and Ghidra evidence live in
[RE notes: OS internals](../re-notes/os-diposb.md) and
[RE notes: Commstar evidence](../re-notes/commstar-evidence.md).

## Stability

| Format | Stability |
|---|---|
| **COM** — flat image at `0100h`, limit `0xCF81` (53,121 bytes) | **Stable** |
| **DIP** — 14-byte header + typed blocks (types 0 and 1) | **Stable** for types 0/1; higher types are **Not implementable** (no error, next-block path) |
| Block checksum at runtime | **Stable** — mismatch reports “Program corrupt.” on the error screen |

## COM

A COM file has **no header**. It is loaded contiguously starting at
`0100h`. The last permitted byte is at `D080h`; exceeding `0xCF81` bytes
reports `COM file too big` on the error screen.

Fallback: if the first input chunk is shorter than 14 bytes or its first
word is not `0xC8C9` (`C9 C8` on disk), the loader treats the input as raw
COM and uses run-bank `0`, entry `0x0100`.

## DIP

### Header — 14 bytes, little-endian

| Offset | Field | Accepted values |
|---:|---|---|
| +0 | magic `0xC8C9` (bytes `C9 C8`) | distinguishes DIP from COM |
| +2 | system ID | `0` wildcard or `0x00E5` (Micronic 1000) |
| +4 | entry-bank offset | relative to selected program-bank base |
| +6 | image size | clamped to `0x8000` |
| +8 | run-bank offset | bank active at entry |
| +10 | entry address | Z80 address jumped to in that bank |
| +12 | block count | `0..5`; `>5` reports `DIP file has too many blocks.` |

Bank offsets are relative, not absolute port values. The entry-bank offset
defines the load range; the run-bank offset selects the bank at transfer.

### Blocks

`blockCount` repetitions of:

| Field | Type | Meaning |
|---|---|---|
| type | `u16` | `0` direct copy, `1` trampoline expansion |
| dest bank offset | `u16` | relative to bank base |
| dest address | `u16` | destination address |
| payload byte count | `u16` | length of following payload |
| payload | `u8[count]` | bytes |

* **Type 0:** payload is copied directly to the destination bank/address.
* **Type 1:** payload is a sequence of 4-byte items `{bank offset, target
  address}`; each installs a banked-call trampoline (`RST 10h` opcode
  `0xD7` plus resolved bank and target) at the destination.

Only types `0` and `1` have defined handlers. Higher type values take the
loader’s default next-block path without an explicit error.

### In-memory checking

Each block header is expanded with an additive checksum over its payload;
a mismatch before execution reports `Program corrupt.` — meaning resident
memory changed, not “file header checksum failed”.

> The D081 load ceiling derivation, the RAM-placement mechanism (the single
> most useful DIP feature for resident hooks), the COM alternative, and the
> trade-offs are covered in
> [RE notes: OS internals](../re-notes/os-diposb.md#runtime-program-loading-loadrun-loader-confirmed).

## Error catalogue

The loader shows decimal IDs; hexadecimal IDs are included for tooling:

| Error (hex + decimal, quoted text) | Condition |
|---|---|
| `0x232B` (9003), "Bad DIP file." | truncated header or payload |
| `0x2331` (9009), "Program not built for this system." | system ID not `0` or `0x00E5` |
| `0x2334` (9012), "DIP file has too many blocks." | block count `>5` |
| `0x232A` (9002), "DIP file too big." | `destAddr + count` exceeds the load ceiling `ram:E3BD` = `D081h` (`ROM01:0E9E`) |
| `0x232C` (9004), "COM file too big." | raw COM exceeds `0xCF81`, which is `D081h - 0100h` |
| `0x2332` (9010), "Program corrupt." | post-load checksum mismatch |

No executable-extension comparison beyond the fallback rule is part of the
contract.

### Why the ceiling is D081h

`D081h` is the first byte of resident Workstation module B in these ROM
images. Startup sets the loader's exclusive ceiling to that address, so
`D080h` is the last byte available to a loaded image. This is a firmware
layout boundary, not a RAM-page size or a universal COM-format limit.

The Z80 sees a selected 32 KiB bank at `0000h-7FFFh` and fixed RAM at
`8000h-FFFFh` simultaneously. A COM image can span that boundary:

| Part of the image | Mapping | Capacity |
|---|---|---:|
| `0100h-7FFFh` | Selected program RAM bank, excluding page zero | `7F00h` = 32,512 bytes |
| `8000h-D080h` | Fixed RAM below resident module B | `5081h` = 20,609 bytes |
| Total | One contiguous CPU address range | `CF81h` = 53,121 bytes |

Thus `D081h - 0100h = CF81h` is correct even though each bank is only
32 KiB. The upper portion is shared fixed RAM; each bank does not get its
own additional 20,609 bytes. This is image capacity, not a guarantee of
spare space for application buffers or resident hooks.

For the byte-verified initialization, boot record and loader calculation,
see [COM capacity evidence](../re-notes/os-diposb.md#com-capacity-and-the-fixed-ram-boundary).

## Building and validating images

The existing `analysis/micronic/program.py` module provides
`build_dip_file`, `build_dip_header`, `build_dip_block`, and `validate`.
Run this from the repository root after assembling a COM image:

```python
import sys
from pathlib import Path

sys.path.insert(0, "analysis")
from micronic.program import build_dip_file, validate

payload = Path("/tmp/hello.com").read_bytes()
result = validate(payload)
assert result.kind == "COM" and result.valid, result.errors
image = build_dip_file(
    header_kwargs={"image_size": len(payload), "entry_address": 0x0100},
    blocks=[(0, 0, 0x0100, payload)],
)
assert validate(image).valid
Path("/tmp/hello.dip").write_bytes(image)
```

The host validator checks syntax, supported system IDs, block count,
truncation, COM length, and type-1 four-byte alignment. Alignment is a
host-tool safeguard, not a dedicated ROM error. It does **not** check
destination-plus-length against the runtime load ceiling, available banks,
overlapping blocks, runtime memory ownership, or execution safety. A
producer must check these separately and use only block types 0/1; an
unknown type is not a supported extension merely because validation passes.
The `D081h` boundary check must use non-wrapping arithmetic in producer tools.

Run the existing format tests with `python3 analysis/test_program.py`.
These are host-side tests, not a physical transfer test.

## Related

* [Programmer guide](../manual/programmer-guide.md) — usage
* [Supported profile](../manual/supported-profile.md) — packaging guidance
* [RE notes: OS internals](../re-notes/os-diposb.md)
* [Reference: Memory and I/O map](memory-map.md) — resident module layout
