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

## Error catalogue

The loader shows decimal IDs; hexadecimal IDs are included for tooling:

| Shown | Condition |
|---|---|
| `0x232B` (9003) Bad DIP file | truncated header or payload |
| `0x2331` (9009) Program not built for this system | system ID not `0` or `0x00E5` |
| `0x2334` (9012) DIP file has too many blocks | block count `>5` |
| `0x232A` (9002) DIP file too big | block destination + payload exceeds boundary |
| `0x232C` (9004) COM file too big | raw COM exceeds `0xCF81` |
| `0x2332` (9010) Program corrupt | post-load checksum mismatch |

No executable-extension comparison beyond the fallback rule is part of the
contract.

## Related

* [Programmer guide](../manual/programmer-guide.md) — usage
* [Supported profile](../manual/supported-profile.md) — packaging guidance
* [RE notes: OS internals](../re-notes/os-diposb.md)
* [Reference: Memory and I/O map](memory-map.md) — resident module layout
