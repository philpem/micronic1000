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

## Placing code in unbanked RAM

**This is how a program leaves resident code behind**, and it is the single
most useful thing about the DIP format for anyone writing a decode hook or a
patch that has to outlive the program that installed it.

The loader's block-acceptance test compares the block's **end address**
against the program load ceiling:

```text
ROM01:0E9C  ADD  HL,DE          ; dest + payload count
ROM01:0E9E  LD   HL,(0E3BDh)    ; g_pProgramLoadCeiling = D081h
ROM01:0EA1  CALL 0E0E8h         ; Z iff ceiling >= end
ROM01:0EA4  JP   Z,0EB0h        ; accept
ROM01:0EA7  LD   HL,232Ah       ; else error 9002, "DIP file too big."
```

so the rule is **`destAddr + count <= 0xD081`**. Because `D081` is far above
`8000`, **a type-0 block may name a destination anywhere in `8000`-`D080`,
which is fixed battery-backed RAM outside the bank window.**

**CONFIRMED by experiment**, not just by reading the check. A two-block DIP
whose second block targets `C000` places its payload exactly there:

```text
--fill-mem c000:c03f --dump-mem c000:64

[mem] final C000:64  44 49 50 44 45 53 54 2D 4C 41 4E 44 45 44 2D 41 54 2D 43 30 30 30 ...
                     D  I  P  D  E  S  T  -  L  A  N  D  E  D  -  A  T  -  C  0  0  0
```

The marker pattern seeded across `C000`-`C03F` beforehand is overwritten for
exactly the 32 payload bytes and survives untouched from `C020` on, so the
copy is precisely placed and does not overrun.

### A COM can do the same thing

A DIP is not the only route, and often not the simplest. A COM is a flat
image loaded at `0100h` in a bank, but **unbanked RAM is mapped the whole
time**, so a COM can simply copy its payload up when it runs:

```text
        LD   HL,payload      ; in the COM's own image
        LD   DE,0C000h       ; unbanked, bank-independent
        LD   BC,payload_len
        LDIR
        ; ... then install the hook
```

The trade-off is only in tooling and timing:

| | DIP | COM |
|---|---|---|
| Placement | done by the loader, before entry | done by your own copy loop |
| Toolchain | needs a DIP header and block table | a flat binary |
| Size limit | `destAddr + count <= D081` per block, 5 blocks | image `<= 0xCF81`, which is exactly `D081 - 0100` |
| Payload cost | payload only | payload is carried inside the image as well |

Either way the code ends up in the same place and behaves identically once
there. Use a DIP when you want the loader to do the placement or need several
scattered destinations; use a COM when a copy loop is easier than building a
header.

**What neither can do:** write the decode-hook socket at `ram:FBC0`-`FBC3`
directly from a DIP block, because `FBC0` is above the `D081` ceiling and the
loader would reject it. The socket must be written by running code — see
[Barcode reader](barcode.md).

## Error catalogue

The loader shows decimal IDs; hexadecimal IDs are included for tooling:

| Shown | Condition |
|---|---|
| `0x232B` (9003) Bad DIP file | truncated header or payload |
| `0x2331` (9009) Program not built for this system | system ID not `0` or `0x00E5` |
| `0x2334` (9012) DIP file has too many blocks | block count `>5` |
| `0x232A` (9002) DIP file too big | `destAddr + count` exceeds the load ceiling `ram:E3BD` = `D081h` (`ROM01:0E9E`) |
| `0x232C` (9004) COM file too big | raw COM exceeds `0xCF81`, which is `D081h - 0100h` |
| `0x2332` (9010) Program corrupt | post-load checksum mismatch |

No executable-extension comparison beyond the fallback rule is part of the
contract.

## Related

* [Programmer guide](../manual/programmer-guide.md) — usage
* [Supported profile](../manual/supported-profile.md) — packaging guidance
* [RE notes: OS internals](../re-notes/os-diposb.md)
* [Reference: Memory and I/O map](memory-map.md) — resident module layout
