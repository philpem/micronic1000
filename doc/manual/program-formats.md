# Program formats: COM and DIP

This is the byte-level specification of the program-image formats DIPOS-B
loads. The record grammar and checksum are **CONFIRMED** from the resident
loader; the DIP file **header** is documented as a set of verified
requirements with its exact layout still open (see the note at the end).

Everything is little-endian unless stated otherwise.

## COM

A COM image is the ordinary CP/M single-image file with **no header**: it
is loaded contiguously starting at **0100h**. The loader only validates its
size (`COM file too big`) and integrity (`Program corrupt`).

## The kernel loader — record grammar (CONFIRMED)

Both the ROM's own boot-load chain and the runtime program loader funnel
into the resident kernel's **record dispatcher** at `ram:d6db`:

```
d6de:  read fn (word)                     ; record type
       index handler table at ram:d6f4     ; entry = word @ (d6f4 + 2*fn)
       tail-jump to handler                ; handler re-enters d6de
```

Handler table at `ram:d6f4` (byte-verified):

| `fn`   | handler        | record                                     | action |
|--------|----------------|--------------------------------------------|--------|
| 0x0000 | `ram:d6fa`     | `{fn, addr, count}`                        | memset(addr, 0, count) |
| 0x0001 | `ram:d713`     | `{fn, src, dst, count}`                    | memcpy(dst ← src, count) |
| 0x0002 | `ram:d727`     | `{fn, N, addr[N]}`                         | enqueue N deferred calls |
| 0xFFFF | `ram:d6ee`     | *(none)*                                   | terminate stream |

The `0xFFFF` terminator works by wrap-around: `d6f4 + 2*0xFFFF ≡ d6f2`
(mod 64K), and the word at `ram:d6f2` is `d6ee`, which pops the saved
registers and returns.

### Record layouts

**`fn = 0x0000` — zero-fill (6 bytes):**

| offset | field  | meaning |
|--------|--------|---------|
| +0     | word   | `0000` |
| +2     | word   | destination address (current bank) |
| +4     | word   | byte count |

**`fn = 0x0001` — copy (8 bytes):**

| offset | field  | meaning |
|--------|--------|---------|
| +0     | word   | `0001` |
| +2     | word   | source address |
| +4     | word   | destination address |
| +6     | word   | byte count |

**`fn = 0x0002` — enqueue deferred calls (4 + 2N bytes):**

| offset | field  | meaning |
|--------|--------|---------|
| +0     | word   | `0002` |
| +2     | word   | N (number of targets) |
| +4     | word[N]| target addresses |

Each target is emitted as a 4-byte deferred-call stub appended to the queue
at `ram:d684`:

```
{ 0xD7, bank, addr_lo, addr_hi }
```

`0xD7` is the `RST 10h` (banked-call) opcode; `bank` is the current bank
shadow (`ram:f791`, selected by port 47h); `addr` is a 16-bit target in
that bank. On load, these stubs run as on-load initialisation.

**`fn = 0xFFFF` — terminate.** Ends the record stream.

## Checksum (CONFIRMED)

`ram:d7d1` (`ChecksumBytes`) computes a **16-bit additive byte-sum** — not
a CRC:

```
sum = 0; carry = 0
for each byte b: sum += b; if overflow then carry++
result = (carry << 8) | sum
```

This is almost certainly the integrity check behind the `Program corrupt`
error.

## Boot-load chain and ROM footer (CONFIRMED)

Each ROM bank ends with a 16-byte footer at `7FF0h`:

| offset | bank 0 | bank 1 | meaning |
|--------|--------|--------|---------|
| 7FFA-7FFB | `58 7D` | `15 7E` | boot-chain pointer (word) |
| 7FFC-7FFD | `7D 58` | `15 7E` | duplicate chain pointer |
| 7FFE-7FFF | `F8 AC` | `12 2E` | candidate system ID / ROM tag |

The boot chain lives at `(7FFC)` (bank 0: `7D58`, bank 1: `7E15`) and is a
**bare record stream with no header** — the same `fn` grammar above,
terminated by `fn=FFFF`. It is the *mechanism*, not the *file container*.

## The DIP file (header requirements known, layout open)

A **DIP file** (as it exists on the RAM disk or arrives over the link) has
a header that the receiving parser validates. The error strings in ROM01
(`7d3c`–`7d9d`, reached through a runtime-built error-code table, so no
direct xrefs) prove the parser checks, at minimum:

| error string | ROM01 addr | required header field |
|--------------|------------|-----------------------|
| `Bad DIP file` | 7d4d | format magic / type marker |
| `Program not built for this system` | 7d6b | system compatibility ID |
| `DIP file too big` | 7d3c | total size |
| `DIP file has too many blocks` | 7d9d | block count |
| `Program corrupt` | 7d8d | checksum (see above) |

So a DIP file almost certainly begins with a fixed header carrying (at
least) a magic, a system ID, a size, a block count, and a checksum,
followed by one or more blocks of `fn` records.

> **OPEN — do not implement against this yet.** The parser that reads this
> header lives in **module A** (loaded to `ram:D893` from `ROM00:73CE`,
> 2145 bytes), which has not been disassembled. The *exact* header offset,
> field width and value of each of the five fields above is therefore
> **unknown**. Until module A is disassembled (or a DIP file is captured
> from a running link session), treat the header as five verified
> *requirements* but unconfirmed *layout*.

The **record grammar above is complete and safe to implement** — a DIP
*decoder* for the record stream, and a *linker* that emits `fn` records,
can be built on it today; only the surrounding file header remains
unresolved.

## Where the parser lives (next trace)

Module A: `ROM00:73CE` → `ram:D893` (2145 bytes, boot-chain `memcpy` at
`ROM00:7D74`). Disassembling it and locating the compare against the magic /
system-ID / size / block-count / checksum will pin the header. The checksum
call site is not yet found (no direct xref to `ram:d7d1`; it is reached by
computed dispatch, or the parser uses its own sum loop).

## Related

- [Loader internals](../internals/os-diposb.md) — boot-chain context.
- [Programmer guide](programmer-guide.md) — application-level constraints.
- `analysis/decode_chains.py` — the boot-chain decoder (same grammar).