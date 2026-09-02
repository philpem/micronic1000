# Barcode reader — scanning and decode hooks

This page is the **programmer's contract** for the barcode input path: how
to read scans, how to install your own decoder, where that decoder has to
live, and how long it survives. The sampling mechanics, timing derivations
and the evidence behind each claim are in
[RE notes: barcode capture](../re-notes/barcode-capture.md).

Everything here has been executed in the emulator, not only read out of the
ROM — see `analysis/test_barcode.py`.

!!! note "What the device is"
    The 5-pin side port is the barcode pen, on the project owner's knowledge
    of the hardware. **The firmware does not corroborate this**: no string
    names a barcode, pen or symbology, and the default `FE83` wire table
    makes wire `2Bh` the EXT STORAGE ADAPTER. The Ghidra names use a neutral
    `Ext*` prefix for that reason. The mechanism below is exactly as
    described whatever is plugged in.

## Stability

| Use | Stability |
|---|---|
| Read scans via BDOS `RDR:` (function `03h`) | **Stable** |
| Decode-hook socket, entry and return contract | **Stable** — measured, not inferred |
| Installing via BIOS entry 24 | **Stable** |
| Element timing constants | **Provisional** — correct for this ROM |

## Reading scans — BDOS function `03h`

`CALL 0005h` with `C=03h`, repeatedly. The stream is:

```text
1Bh          scan-arrived marker
count        number of decoded bytes
count bytes  the decoded data
```

**CONFIRMED by execution.** A driven scan of Code 39 `A1` returns
`1B 02 41 31` over four calls.

That is all a portable application needs. Everything below is for programs
that want to supply their own decoder.

## The decode hook

### The socket

`ram:FBC0` is a complete **four-byte `RST 10h` banked-call thunk**, not a
pointer:

| Cell | Contents |
|---|---|
| `FBC0` | `D7` — the `RST 10h` opcode |
| `FBC1` | the hook's **bank** |
| `FBC2`-`FBC3` | the hook's **address** |

All four cells matter. An earlier version of this page showed
`LD (hook_ptr),HL` against a placeholder; there is no single pointer cell.

### Installing it

**The supported route is BIOS jump-table entry 24**, reachable portably as
`(0001h)+45h`. It takes **two** arguments:

```text
    LD   HL,(0001h)      ; CP/M BIOS jump-table base + 3
    LD   DE,0045h
    ADD  HL,DE           ; entry 24 = install decode hook
    LD   (patch+1),HL
    LD   DE,0C000h       ; DE = hook address
    LD   HL,<window>     ; HL = re-arm window; stored as HL x 64 at ram:F9B0
patch:
    CALL 0000h           ; patched above
```

`HL` is easy to miss and is **not optional** — `ROM00:1596` shifts it left
six times into `ram:F9B0`, the scan re-arm window. A caller that sets only
`DE` writes whatever `HL` happened to hold.

The installer takes the hook's bank from `ram:FEFE`, the caller's bank as
saved by the syscall envelope, so a hook in your own bank is called
correctly.

**Or write the socket directly**, which avoids disturbing `F9B0`:

```text
    LD   HL,0C000h
    LD   (0FBC2h),HL     ; address
    XOR  A
    LD   (0FBC1h),A      ; bank 0 -- see below
    LD   A,0D7h
    LD   (0FBC0h),A      ; make it a thunk
```

Bank 0 is right for an unbanked hook because the capture code always runs
with bank 0 paged, so the `RST 10h` takes its same-bank fast path and the
call becomes a plain tail-jump.

### Entry contract — measured

The hook is entered with **one stack argument and nothing in registers**:

```text
[SP+0]  return address
[SP+2]  0FBB9h  -- the parameter block
```

Identical in the same-bank and cross-bank cases; only the return address
differs (`ROM00:1468` versus the kernel's bank-restore trampoline). A hook
that simply `RET`s works either way.

* **Interrupts are off.** The capture parks the real `SP` in `ram:FBBD` and
  uses `SP` itself as the table pointer, so the callers `DI` first.
* **The bank in `FBC1` is paged in** before entry and restored on return.
* **Every register except `SP` is free to clobber** — the caller reloads
  everything from memory afterwards.

### The parameter block at `ram:FBB9`

| Offset | Size | Contents |
|---|---|---|
| `FBB9`-`FBBA` | word | pointer to the width table (`F9B5` on entry) |
| `FBBB`-`FBBC` | word | **16-bit element count**, little-endian |

`FBBC` is the count's **high byte**. An earlier version of this page called
it a status byte; `ROM00:147E` reads the pair with `LD BC,(FBBB)` and uses
it as an `LDIR` length, so a nonzero "status" there would copy 256 extra
bytes per unit.

### Returning

Put your decoded bytes somewhere readable, set `FBB9` to point at them and
`FBBB`/`FBBC` to the byte count, then `RET`.

* **Count 0 means reject and re-arm.** That is the entire body of the ROM's
  default hook: `LD HL,0 / LD (0FBBBh),HL / RET`.
* **Do not write `ram:FBB5`.** It is the delivery record's status byte. A
  nonzero value there gets written into the record and then suppresses the
  completion event, so a blocked `BDOS 03h` hangs until the timer re-arms.

### Two hazards worth designing around

**Clamp the element count yourself.** `ROM00:1409` stores the *uncapped*
count in `ram:F9B4`; the 128 cap at `ROM00:140F` applies only to the
reverse-copy loop; then `ROM00:1446` reads the uncapped value back and hands
it to your hook. Feed 140 elements and the hook is told 140 while only 128
table entries exist. **This is a firmware bug** — a decoder must reject or
clamp counts above 128.

**Keep output to 26 bytes.** The delivery buffer's descriptor gives it
length `20h` from `ram:F958`, of which the first six bytes are the record
header, leaving `F95E`-`F977`. The copy at `ROM00:148B` is an unbounded
`LDIR`, so a longer result overruns into the device-table pointer at
`F978`.

## Where the decoder lives, and how long it lasts

**It must be reachable when the hook fires.** Unbanked RAM (`8000`-`D080`)
is the safe home; `C000`-`D080` is the recommended sub-range. A hook in a
banked page *is* called correctly — the thunk pages it back in — but nothing
marks that bank in use and every program load reuses it, so the decoder is
gone the moment anything else runs.

Two ways to get code there, covered in
[Program file formats](program-formats.md#placing-code-in-unbanked-ram):

* **A DIP** with a type-0 block whose destination is `C000` — the loader
  places it before entry. Verified by experiment.
* **A COM** that copies its payload up with an `LDIR` when it runs. Unbanked
  RAM is mapped throughout, so this is just as effective and needs only a
  flat binary.

Neither can write the socket at `FBC0`-`FBC3` from a block, because that is
above the loader's `D081` ceiling. Running code must install it.

**Lifetime: the hook survives program exit, warm boot and power cycling.**
`FBC1`/`FBC2` have exactly two writers in the whole firmware, both
installers. Only a cold start reinstalls the default — and a cold start also
pattern-tests all of `8000`-`FFFF`, so it would have destroyed the decoder
anyway. There is no separate terminate-and-stay-resident call; installing
the hook *is* the residency mechanism.

## Worked example — a Code 39 decoder

`analysis/micronic/barcode.py` carries a complete Code 39 decode hook in
Z80 source (`decoder_source()`), 494 bytes assembled including its pattern
table and output buffer. It:

* takes the min and max of each character's own nine widths and thresholds
  at the midpoint, so it needs no absolute width calibration;
* shifts each wide/narrow decision into a 9-bit key and looks it up;
* validates `count = 10k − 1`, requires `*` delimiters at both ends and
  rejects `*` inside the data;
* **clamps the element count at 128**, per the firmware bug above;
* returns count 0 on any failure, which re-arms the scanner.

Driven end to end — wand model, firmware capture, hook, then `BDOS 03h`:

```text
--barcode-scan A1 --barcode-decode --barcode-bdos --barcode-expect A1
[barcode] fn 03h returned 1b024131  b'\x1b\x02A1'
[barcode] PASS
```

Code 39 suits this hook well: it is discrete and self-checking, so an
invalid pattern rejects itself, and it decodes straight from a width table.

**UPC/EAN is feasible but more work.** 59 elements fits the 128 cap
comfortably, both symbologies start and end with a bar so the arm and
terminator behave, and 13 digits fits the 26-byte envelope. What it costs is
decoder complexity: delta decoding against a module width re-estimated from
the guard bars, four-way element classification, and parity tables for the
number system — plus, for EAN-13, the thirteenth digit encoded only in the
left-half parity pattern. It also loses Code 39's self-checking property, so
a misread is caught only by the check digit.

## Driving a scan in the emulator

`analysis/boot_hw.py` models the wand on port `2Dh`:

```text
--barcode-scan TEXT      encode TEXT as Code 39 and scan it
--barcode-widths W,...   feed raw element widths
--barcode-decode         install the Code 39 hook first
--barcode-bdos           read the result back through BDOS 03h
```

Widths are in **polls of port `2Dh`**, not time — nominally 15.4 µs each.
See the RE notes for the timing derivation and the element limits.

## Related

* [Program file formats](program-formats.md) — getting a decoder into unbanked RAM
* [Memory and I/O map](memory-map.md) — where resident code may live
* [BDOS calls](bdos.md) — function `03h` and the BIOS jump table
* [DIPOS-B extensions](extensions.md) — device-selector mutation (F7h)
* [RE notes: barcode capture](../re-notes/barcode-capture.md) — evidence and mechanics
