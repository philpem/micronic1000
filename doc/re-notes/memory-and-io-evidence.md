# Memory and I/O — evidence and derivation

This page is the **evidence record** behind the address ranges, I/O ports,
RAM cells and other structural facts stated in
[Reference: Memory and I/O map](../reference/memory-map.md). The reference
page gives the programmer's contract; this page gives the byte-level proof,
the methodology, the false-positive analysis, and the dated traces that
established each fact.

## Evidence tags

Claims here carry the project's tags: **CONFIRMED** (read from the
bytes), **LIKELY** (firmware evidence plus a documented hardware fact),
**SUSPECTED** (plausible, unverified), **OPEN** (not established).

---

## How the I/O list was built

Two independent passes, because neither alone is sufficient:

1. **Ghidra instruction search** over all 21,113 disassembled
   instructions in `ROM00`, `ROM01` and the RAM-resident modules —
   169 `OUT` and 40 `IN`. Aligned and therefore trustworthy, but bounded
   by disassembly coverage (`ROM00` 61 %, `ROM01` 37 %).
2. **Raw opcode scan** of both full ROM images for `DB nn` / `D3 nn` and
   the `ED`-prefixed register-indirect forms
   (`ED 40/48/50/58/60/68/70/78` in, `ED 41/49/51/59/61/69/71/79` out),
   with every hit inspected in context.

### Why the raw scan produces many false positives

`DB` and `D3` turn up constantly as one byte of an address operand.
`CD DB 22` is `CALL 22DB` — `DB` is the low byte — not `IN A,(22h)`;
`2A 6E D3` is `LD HL,(D36E)`, with `D3` as the high byte, not an `OUT`.
Module A lives at `ram:D893`-`E0F3` and module B's workspace at
`ram:D2CB`-`D480`, so calls and variable references inside them generate
`DB xx` and `D3 xx` pairs by the hundred.

Two of Ghidra's own hits are exactly this: `ROM01:0D07` "`OUT (21h),A`"
and `ROM01:0F00` "`OUT (D1h),A`" are misaligned readings of
`22 6A D3` (`LD (D36A),HL`) and `2A 6E D3` (`LD HL,(D36E)`). Likewise
`ROM00:6FFD` "`IN A,(0Dh)`" and `ROM00:7021` "`IN A,(0Bh)`" fall inside
byte tables. **None of the four is real I/O.**

Net result: **`ROM01` performs essentially no port I/O at all.** Its one
genuine access is `ROM01:0042` `3E 00 / D3 47` (`LD A,0; OUT (47h),A`),
inside the page-zero image. Everything the Workstation and Commstar do to
hardware, they do by calling into bank 0 or the resident kernel.

---

## Register-indirect I/O accesses

Seven sites use `OUT (C),r` / `IN r,(C)`, where the port number is in
`C`. All are resolved:

| Site | `C` set at | Port | Note |
|---|---|---|---|
| `ROM00:1801` | `0E 08` | `08h` | RTC address latch, followed by `IN A,(28h)` |
| `ROM00:1A7E` | `0E 02` | `02h` | `Kbd_DriveSetAll`, `A = 3Fh`, shadow `F782` |
| `ROM00:1A88` | `0E 02` | `02h` | `Kbd_DriveClearAll`, `A = 00h` |
| `ROM00:1F76` | `0E 03` | `03h` | LCD data |
| `ROM00:1F7D` | `0E 23` | `23h` | LCD register select, `B = 0Ch` |
| `ROM00:1FD9` | `0E 46` | `46h` | LCD contrast, `A = (FC05)` |
| `ROM00:2104` | `0E 28` | `28h` | `RTC_ReadRegisterFile`, `IN B,(C)` |
| `ROM00:22DD`, `22E4` | `0E 08` | `08h` | `RTC_RegWrite` / `RTC_RegRead` |
| `ROM00:246E`, `2477` | `0E 28` | `28h` | `Link_StatusWatcher` reads RTC registers `07h`/`08h` |

CONFIRMED — the `LD C,nn` immediately precedes each in every case. The
remaining raw `ED 50` (`ROM00:7E1C`) and `ED 58` (`ROM01:59A0`) hits fall
inside data tables and are not instructions.

---

## Per-port evidence

### Port `00h` — `KBD_SENSE`

Keyboard matrix sense. Only the low 6 bits are used: `AND 3Fh` at
`ROM00:0181` and `ROM00:1A4F`. CONFIRMED.

### Port `02h` — `KBD_DRIVE`

Keyboard drive / configuration latch. `LD A,3Fh` drives all lines
(`ROM00:1A42`), `00h` clears them (`ROM00:1A83`); reset writes `FDh` at
`ROM00:017B` to select one column. Shadows at `F780` and `F782`. Also
written by the NMI and power-down paths. CONFIRMED as the keyboard drive;
the non-keyboard uses are **Provisional**.

### Port `04h` — `IRQ_MASK` / `OUT_LATCH`

Interrupt-enable mask, active low. `ROM00:22E9` does
`LD A,1Fh; DI; IM 1; CPL; LD (F784),A; OUT (04h),A` — the mask is
complemented before output, so a *set* bit in the argument enables a
source. A second entry at `ROM00:2306` passes `A = 2`. Also carries
power-latch bits (`Power_LatchSetBit0`/`ClrBit0`, `ROM00:1B36`/`1B41`).
Shadow `F784`. CONFIRMED.

### Port `05h` — `STATUS_IN`

Interrupt / status byte, active low. `ROM00:230A`
(`Kernel_WorkerPollPort5`) does `IN A,(05h); LD (F785),A; CPL; AND 8` —
snapshot to `F785`, complement, test bit 3. Also read at reset
(`ROM00:01B1`, `0238`, `17A5`) as a boot-condition byte. CONFIRMED that it
is polled and complemented; source assignments are byte-verified below.

### Port `07h` — `CTRL_07`

Control latch, shadow `F786`. Written at power-down (`ROM00:28F2`), by the
link watcher (`ROM00:24AD`, `24B8`) and at `ROM00:17A0`, `17B6`, `23CC`.
**Only bits 0 and 1 are ever manipulated** — a two-bit output, not an
eight-bit one. Function otherwise **unknown**.

### Port `2Ah` — `CTL_LATCH_2A`

Peripheral control latch, shadow `F78B`. Used by the barcode front end
(`ROM00:123B`, `124A`, `14F2`, `1541`, `1550`) and by `Link_PortSelect`
(`ROM00:345D`, which clears bit 1 on both paths). Bits 1, 4 and 5 are
individually managed. CONFIRMED as a shared latch; individual bit meanings
**Provisional**.

### Port `33h` — *unknown*

One access in the whole firmware: `ROM00:1ED9` `DB 33`
(`IN A,(33h); RET`), the tail of a four-instruction stub at `ROM00:1ED0`
that first does `LD A,0Dh; OUT (03h),A`. Alignment is sound (the stub
follows a `RET` at `1ECF`), but nothing references `1ED0` directly.
**Purpose unknown.** Candidates worth discriminating on hardware: an LCD
status/busy read (it sits inside the LCD driver block and follows an
`LCD_DATA` write), or an incompletely-decoded alias of `23h`/`03h`. Do not
assume it is either.

### Port `46h` — `LCD_CONTRAST`

Written only via `LD A,(FC05); LD C,46h; OUT (C),A` at `ROM00:1FD4`,
called from `Lcd_Init` (`ROM00:1F2B`) and from `Power_LatchIncr`/`Power_LatchDecr`
(`ROM00:1D73`/`1D57`). **LIKELY**, and stronger than it was. Observed: the
adjusters step `FC05` by **±2, not ±1** (`1D4A` does `DEC A` twice with a
floor at `00h`, `1D60` `INC A` twice with a ceiling at `FFh`), and
although `FC05` lives in battery RAM, cold boot overwrites it with `70h`
at `ROM00:0257`. Owner-supplied: the stock `70h` is almost black on this
unit, a Sun-modified key lightens it, and a cold boot puts it back — which
matches that overwrite exactly. Corroborating but **not** primary: MAME
maps it `lcd_contrast_w` (`micronic.cpp`), itself an inference from the
same ROM. *Confirmed by:* burning the exerciser with `CONTRAST` set and
seeing the screen legibility change. The Ghidra name
`Power_PowerLatchPort46` is a grandfathered misnomer.

### Port `47h` — `BANK_SEL`

32K bank select, shadow `F791`. 37 write sites in `ROM00`, 24 in the
resident kernel. CONFIRMED.

### Port `48h` — `IR_STROBE`

Two-bit output, driven `0`,`1`,`2`,`3` in sequence by
`Kernel_SenseDiagEcho` (`ROM00:24F7`-`252D`) and by `Link_SelftestRun`
(`ROM00:28AE`-`28E4`), also `Session_SystemInit` (`ROM00:0359`, value
`03h`) and power-down (`ROM00:178D`). CONFIRMED as a strobe/select output
paired with `49h`; the project's older `LCD_STROBE` label is **not
supported by the call sites**, which are all IR/link diagnostics.

### Port `49h` — `IR_SENSE` / `BOOTKEYS`

Low 2 bits read back after each `48h` write and compared against the value
written (`ROM00:24F2`-`251B`: `OUT (48h) 0/1/2` then `IN A,(49h); AND 3; CP …`)
— a loopback/presence test. Also read twice at reset: `IN A,(49h); AND 1;
JR Z` selects the cold path, `AND 2; JP NZ` selects a second boot mode
(`ROM00:0168`-`0172`). CONFIRMED.

### Port `4Ah` — `LINK_CTRL`

External-link control latch, shadow `F794`. 26 write sites. Bits 0, 1, 4,
5, 6 and 7 are all driven; **bits 2 and 3 are never written by any ROM
instruction** ([bit usage](../reference/memory-map.md#latch-bit-usage)).
Roles: bit 1 port select (CONFIRMED), bits 0/4/5 the transmit and receive
arm sequences, bits 6/7 the `34BD`/`34D2` pair. Electrical meanings
**Provisional**.

### Port `4Bh` — `LINK_STATUS`

Link status, polled in `Link_BlockTx`/`Link_BlockRx`/`Link_Probe`/`Link_WaitReady`.
Bit assignments **Provisional**.

### Port `4Ch` — `LINK_CMD`

Link command latch; the only write is `81h` in `Link_Present`
(`ROM00:34F5`). CONFIRMED.

### Port `4Dh` — `LINK_TXD`

Link TX data byte (`ROM00:32B6`, sole site). CONFIRMED.

### Port `4Eh` — `LINK_RXD`

Link RX data byte (`ROM00:338C`, sole site). CONFIRMED.

### Port `4Fh` — `LINK_PROBE`

Device probe/reset; the only write is `1Fh` in `Link_Probe` (`ROM00:3491`).
CONFIRMED.

**No other port is accessed anywhere in either ROM image or in any
RAM-resident module.** The untouched ranges are `01h`, `06h`,
`09h`-`22h`, `24h`-`27h`, `29h`, `2Eh`-`32h`, `34h`-`45h`, and everything
above `4Fh`. That is a statement about the firmware, not about the
hardware: a port this firmware never uses may still be decoded, and the
address decoding may well be partial — the `03h`/`23h`, `08h`/`28h` and
`2Ah`/`2Ch` pairings suggest only some address lines are compared.
**SUSPECTED** for the partial-decode inference; a hardware read of an
unused port would settle it.

---

## Interrupt source dispatcher trace

`Kernel_WorkerPollPort5` (`ROM00:230A`) reads `05h`, ORs it with the mask
from `F784`, complements the result to get *pending and enabled*, and walks
a table of `{bitmask, handler}` triples at `ram:FD84`, copied from
`ROM00:2352` at boot and terminated by `80h`:

| bit | mask | handler | source |
|---|---|---|---|
| 0 | `01h` | `ROM00:18F0` `Kbd_ScanMain` | **keyboard** |
| 1 | `02h` | `ROM00:2206` | **RTC** — reads HD146818 registers `0Ch` then `0Bh` via `22E2`, the standard acknowledge |
| 2 | `04h` | `ROM00:31B6` | **the link controller** |
| 3 | `08h` | `ROM00:2365` | snapshots `05h` to `FDA1` and schedules; shared with bit 4. **LIKELY** power/battery |
| 4 | `10h` | `ROM00:2365` | same handler as bit 3 |
| 5 | `00h` | none | **blank in ROM**, filled in at run time by `ROM00:2349` (`LD A,20h; LD (FD93),A; LD (FD94),HL`), whose sole caller is `ROM00:138F` in the barcode block |
| 6, 7 | — | — | no slot exists |

That is the answer to "why are so few mask bits enabled". `ROM00:22E9`
writes `CPL 1Fh` = `E0h`, enabling exactly bits 0-4, because those are
the five populated slots. Bit 5 is enabled only while the barcode front
end has installed its handler (`ROM00:139C` clears the mask bit, `149E`
sets it back), and bits 6 and 7 are masked permanently because nothing
dispatches them.

Reading `05h` appears to acknowledge: three sites (`ROM00:01B1`, `0238`,
`288A`) read it and discard the value, and at `288A` the very next action
is the HD146818's own acknowledge (`LD A,0Ch; OUT (08h); IN A,(28h)`).

---

## Latch-bit usage — how the table was built

Every output latch is read-modify-written through a RAM shadow, so a bit
is only touched by the routine that owns it, and the immediate mask names
the bit. The table on the reference page is the exhaustive result of
matching this idiom (`LD A,(shadow)` / `AND`-`OR`-`XOR n` / `LD (shadow),A`
/ `OUT (p),A`) across `ROM00`.

Caveats. A `.` means no *individual* manipulation; the whole-byte writers
can still set such a bit, and `04h`'s `2428` takes its mask from a
register rather than an immediate, so its bits are not enumerable this way.
`02h`'s bits 0-5 are the six keyboard columns, driven as whole-byte masks
by the scan loop (`ROM00:190D`-`191F`) rather than individually, which is
why they read `.` in the table — and bit 6 is a **mode flag**:
`ROM00:175E` tests it and drives `48h` instead of `3Fh` when set, a reduced
column pattern for the power-down wake scan.

Two negatives bound searches:

* **`LINK_CTRL` bits 2 and 3** are the only ones no ROM instruction ever
  writes. Bits 0, 1, 4, 5 are driven by the transmit and receive arms,
  and 6 and 7 by the pair at `ROM00:34BD` (sets both) and `34D2` (clears
  both, called from `Link_Probe` and from `Link_BlockTx`'s entry). So the
  untried space on that latch is exactly two bits, which is what
  `analysis/rom_exerciser`'s sweep phase exists to cover.
* **`CTRL_07` uses only bits 0 and 1.** Its purpose is still unknown, but
  it is a two-bit output, not an eight-bit one.

### Port `2Ch` bits — per-site evidence

Every write is a read-modify-write through the shadow at `F78D`, so a bit
is only ever touched by the routine that owns it. **No ROM instruction
ever sets bits 2, 3, 6 or 7** — every write masks them off or leaves them
at the zero `Link_Probe` establishes at `ROM00:34B5` (`XOR A`).

| bit | evidence in the ROM | reading |
|---|---|---|
| 0 | `1511` sets it, a `B=83h` `DJNZ` runs, `1520` clears it — a short output pulse of fixed width, inside the barcode block | **an output strobe on the external port.** Width and placement are CONFIRMED; what it strobes is **OPEN** |
| 1 | `128A` sets it, then `1299` immediately reads `IN A,(2Dh)` and tests bit 0. Cleared at `1283` and `14E6` | **an enable asserted around reads of `2Dh`.** The set-then-read ordering is CONFIRMED; whether it is a drive enable, a wand power line or a direction control is **OPEN** |
| 2, 3 | never written to 1 anywhere in the image | unused, or not brought out. **OPEN** |
| 4 | `1A0C` reads a flag, tests its bit 4, and sets (`1A11`) or clears (`1A1D`) `2Ch` bit 4 to match — a toggle in the keyboard handler. The power-down path clears it at `17E7` | **LIKELY the LCD backlight.** A user-toggleable output that is switched off on power-down fits nothing else here, and MAME's `port_2c_w` keeps exactly `BIT(data, 4)` as `m_lcd_backlight` — corroborating, but itself an inference from this same ROM, not independent measurement. *Confirmed by:* pressing the toggling key and watching the panel |
| 5 | `Link_PortSelect` sets it for id bit 5 clear (`3487`) and clears it for id bit 5 set; `Link_Probe` zeroes the whole latch (`34B5`); the barcode arm path clears it (`1231`); power-down preserves **only** this bit (`1786`, `AND 20h`) | **IR port select**, moving with `LINK_CTRL` bit 1. CONFIRMED — see [Commstar evidence](commstar-evidence.md#device-table-ports) |
| 6, 7 | never written to 1 anywhere in the image | unused, or not brought out. **OPEN** |

`CTL_LATCH_2C` bits 0 and 1 are initial output candidates for the scanner
connector, not an exhaustive physical pinout. Internal use of other bits
does not prove they are absent from the connector, and `CTL_LATCH_2A` has
additional candidate signals. The owner identifies eight contacts, with
power and ground known (2026-09-22). The earlier assertion that the current
exerciser already implements a pin walk was incorrect; that mode is absent.
See the [manual output-first experiment](../research/reviews/ir-protocol-audit-2026-09-22.md#manual-scanner-connector-experiment-outputs-first-then-inputs).

---

## Worked example: `ram:E5C2`

`ram:E5C2` is the body of the Commstar receive object. The emulator harness
writes serialised frames there (`analysis/boot_hw.py`: `harness_write` →
`analysis/commstar_peer.py`: `session_crlf_write` → `write_payload`), and
it works because `E5C2` is a precisely known address in *this* ROM image.

It is also exactly the kind of assumption that does not survive a ROM
change. `E5C2` is inside the block the bank-0 boot chain places with a
`memset E3C1..E704`; its position is determined by the cumulative size of
everything the chains copied before it. A different ROM build with a
different module A, or a different session-config block, puts the receive
object somewhere else — and the harness would then be writing 126 bytes
into whatever now occupies `E5C2`, with no error and no diagnostic.
The failure mode is silent and length-dependent: this project has already
had one such bug, in which an uncapped write from `E5C2` reached `E6C1`
and buried live session state, and it only reproduced at certain image
lengths.

The general rule that follows:

> An address in fixed RAM is only as stable as the module placement that
> produced it. Depend on the *structure* (a receive object with a header
> word and a payload) and derive the address; do not hard-code the
> address and assume the structure.

Where the firmware gives you a pointer to read — `ram:E3BD` for the load
ceiling, `ram:F791` for the current bank, `ram:FFA3` for the DMA address,
`ram:FBC2` for the decode hook — read it. Those indirections are the
version-independent part.

---

## Related

* [Reference: Memory and I/O map](../reference/memory-map.md) — the
  programmer-facing contract
* [RE notes: Interrupts](interrupts.md) — sleep-wake and link-interrupt
  evidence
* [RE notes: Barcode capture](barcode-capture.md) — the decode-hook
  dispatch and delivery path
* [RE notes: OS internals](os-diposb.md) — patching an OS function
