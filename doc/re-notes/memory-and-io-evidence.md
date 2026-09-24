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
source. A second entry at `ROM00:2306` passes `A = 2`. Also carries the
per-source enable bits touched by `Kernel_IrqMaskBit0Set`/`Clr`
(`ROM00:1B2E`/`1B39`). Shadow `F784`. CONFIRMED.

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

Written only via `LD A,(FC05); LD C,46h; OUT (C),A` at `ROM00:1FD4`
(`Lcd_ContrastWrite`), called from `Lcd_Init` (`ROM00:1F2B`) and from
`Lcd_ContrastUp`/`Lcd_ContrastDown` (`ROM00:1D73`/`1D57`). **CONFIRMED**. Observed: the
adjusters step `FC05` by **±2, not ±1** (`1D4A` does `DEC A` twice with a
floor at `00h`, `1D60` `INC A` twice with a ceiling at `FFh`), and
although `FC05` lives in battery RAM, cold boot overwrites it with `70h`
at `ROM00:0257`. Owner-supplied: the stock `70h` is almost black on this
unit, a Sun-modified key lightens it, and a cold boot puts it back — which
matches that overwrite exactly. Corroborating but **not** primary: MAME
maps it `lcd_contrast_w` (`micronic.cpp`), itself an inference from the
same ROM. *Confirmed by:* burning the exerciser with `CONTRAST` set and
seeing the screen legibility change. (The old Ghidra names
`Power_PowerLatchPort46`/`Lcd_ContrastUp`/`Lcd_ContrastDown` were
grandfathered misnomers; renamed to `Lcd_ContrastWrite`/`Up`/`Down`.)

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
| 0 | `1511` sets it, a `B=83h` `DJNZ` runs, `1520` clears it — a short output pulse of fixed width, inside the barcode block | **a programmed output pulse.** Pulse sequence and placement are CONFIRMED; physical routing and electrical function are **OPEN** |
| 1 | `128A` sets it, then `1299` immediately reads `IN A,(2Dh)` and tests bit 0. Cleared at `1283` and `14E6` | **a control switched before reads of `2Dh`.** The set-then-read ordering is CONFIRMED; whether it is an internal enable or an external signal is **OPEN** |
| 2, 3 | never written to 1 anywhere in the image | unused, or not brought out. **OPEN** |
| 4 | `1A0C` reads a flag, tests its bit 4, and sets (`1A11`) or clears (`1A1D`) `2Ch` bit 4 to match — a toggle in the keyboard handler. The power-down path clears it at `17E7` | **CONFIRMED the EL-backlight enable.** Owner hardware fact: holding the red Sun key and pressing **`LIGHT` (letter B)** toggles the backlight, and the firmware toggles `2Ch` bit 4 in the keyboard handler (`1A0A`-`1A25`, set `1A14`/`1A19`, clear `1A20`/`1A25`). The unit's HD61830 LCD has an EL backlight (owner spec). MAME's `port_2c_w` `m_lcd_backlight` is corroborating, not the source. |
| 5 | `Link_PortSelect` sets it for id bit 5 clear (`3487`) and clears it for id bit 5 set; `Link_Probe` zeroes the whole latch (`34B5`); the barcode arm path clears it (`1231`); power-down preserves **only** this bit (`1786`, `AND 20h`) | **IR port select**, moving with `LINK_CTRL` bit 1. CONFIRMED — see [Commstar evidence](commstar-evidence.md#device-table-ports) |
| 6, 7 | never written to 1 anywhere in the image | unused, or not brought out. **OPEN** |

`CTL_LATCH_2C` bits 0 and 1 are initial output candidates for the scanner
connector, not an exhaustive physical pinout. Internal use of other bits
does not prove they are absent from the connector, and `CTL_LATCH_2A` has
additional candidate signals. The owner identifies eight contacts, with
power and ground known (2026-09-22). The earlier assertion that the current
exerciser already implements a pin walk was incorrect; that mode is absent.
See the [manual output-first experiment](../research/reviews/ir-protocol-audit-2026-09-22.md#manual-scanner-connector-experiment-outputs-first-then-inputs).

## Power-down / standby path (consolidated)

`Power_DownSuspend` (ROM00:1721) groups the port writes below into one
suspend sequence; the per-site evidence for each is above.

* **`KBD_DRIVE` bit 6** is the wake-scan mode: released to `00h`, then
  driven `48h` when set / `3Fh` when clear (ROM00:1759-176B). It keeps
  the keyboard matrix scan live during the low-power spin.
* **`OUT_LATCH`** receives the power state `FAh`/`F8h`/`D8h`
  (ROM00:177F) — `F8h`/`FAh` chosen on `bit 6`, else `D8h`/`F8h` on
  `FBCB`.
* **`CTL_LATCH_2C`** is masked to `AND 20h` (ROM00:1786) so only bit 5
  (IR port select) survives, dropping bit 4 (LIKELY LCD backlight); the
  dedicated power-down path then clears bit 4 again (`AND EFh`,
  ROM00:17E7).
* **`LCD_STROBE`** bits 0-1 are forced to `11` (ROM00:1788-178D).
* **Spin loop** (ROM00:1795-17A3) refreshes `CTL_LATCH_2A` (bit 5
  clear) and `CTRL_07` (=3) and reads `STATUS_IN` bit 1 (ROM00:17A5).
  The loop is a **busy-spin, not a CPU halt**; the JR at ROM00:17A3
  targets the middle byte of a preceding `LD (db00),HL`, so `0xDB`
  executes as `IN A,(05h)` — an overlapping self-modifying read. This is
  the reason standby consumes power despite the LCD being off.
* **State save:** the 8-byte console context `g_abConsoleContext`
  (FBF3) is copied to `g_abConsoleContextSaved` (FBFB), gated on
  `g_bConsoleStateSavedFlag` (FC03). `g_eRestartFlag` (FBD5) drives the
  NMI restart/wake decision.

## Standby / low-power (2026-09-24)

**CORRECTION (2026-09-24):** the earlier framing of a clean three-path
"standby hierarchy" was overstated. The two `HALT` sites are in
specific wait contexts, not a general idle loop, and the autonomous
"idle → LCD/backlight off → wake on key" trigger is **not yet pinned
down**. What is confirmed:

* **`Link_WaitForLink`** (ROM00:168F-1707) holds the CPU in a **`HALT`**
  (ROM00:16C9) while waiting for link/session events: it `EI`s, re-arms
  the IRQ gate (`ffa8`), `HALT`s, then tests the `fbc9`/`fbca` event
  flags; `fbf2==0` re-arms and HALTs again. It also schedules
  `Power_DownSuspend` (ROM00:1711 → 1721) via the deferred-call queue
  (ROM00:16BA: `HL=1711`, `DE=FBEC`).
* **`Power_DownSuspend`** (ROM00:1721) clears the backlight (port `2C`
  bit 4, ROM00:1786), sets port `04h` to the wake-source interrupt-enable
  mask (`F8h`/`FAh`/`D8h` = only kbd/RTC/link stay armed), then
  **busy-spins** (ROM00:1793-17A3, no `HALT`) refreshing `CTL_LATCH_2A`/
  `CTRL_07` while keeping the keyboard wake-scan (`KBD_DRIVE` bit 6)
  live. Reached from the NMI handler, a key dispatch, `Link_WaitForLink`,
  and the barcode capture-timer underflow. The CPU keeps running.
  **Owner fact (2026-09-24): there is no power key**, so the NMI is not
  a power-button line; its physical source is unknown (the owner guide's
  "Sun+MODE enters power-down" is a key-combo route).
* **`RTC_AlarmSleep`** (ROM00:21EC, `BDOS FEh` timed wait) sets a
  countdown (`FD4D`) and **HALTs** until the RTC alarm wakes it; used by
  `Bdos_InternalTimedWait` (ROM00:1129).

So the Z80 clock is stopped only by the `HALT` instruction (link-wait /
timed-wait); `Power_DownSuspend` keeps the CPU busy-spinning. Whether
there is a distinct autonomous idle-countdown that drives the
LCD/backlight off is **OPEN** — not established.
CONFIRMED: the two HALT sites, the deferred-call to 1711, and the
Power_DownSuspend teardown at the cited addresses.

## Shared control latches and device multiplexing (2026-09-24)

The three external devices (V24 IR, PLINTH IR, barcode side port) do
**not** contend for data pins — link/storage I/O runs the 4× byte
transport (4A–4F), the barcode runs the 2D edge front end — but they
**do** share control-latch bits on ports 2A/2C. Every write to these is a
read-modify-write through the shadow (`F78B`/`F78D`), so each bit is
owned by one routine.

### Port `2Ch` (`CTL_LATCH_2C`, shadow `F78D`) bit ownership

| bit | set at | clear at | meaning |
|---|---|---|---|
| 0 | `150F`/`1519` | `1520`/`1528` | barcode attention-strobe pulse |
| 1 | `128A`/`1292` | `1280`/`1283`, `14E1`/`14E6` | enable asserted around `2Dh` reads (barcode capture enable) |
| 4 | `1A14`/`1A19` | `1A20`/`1A25`, `17E7` | LIKELY LCD backlight |
| 5 | `3482`/`3487` | `346F`/`3487`, `34B5`, `122C`/`1231` | **IR port select** / shared device select |
| 2,3,6,7 | — | — | never written; not brought out |

### Port `2Ah` (`CTL_LATCH_2A`, shadow `F78B`) bit ownership

| bit | set at | clear at | meaning |
|---|---|---|---|
| 0 | — | `14EB`/`14F2` (`AND FEh`) | barcode output (owner: yellow/pin6 sink/release) |
| 1 | `1245`/`124A` (armed dev==2Ah), `1541`/`1550` | `3458`/`345D` (both IR branches), `1236`/`123B` | attention/trigger, **shared** IR+barcode |
| 4 | `14EB`/`14F2` (`OR 10h`) | — | barcode output (owner: red/pin1) |
| 5 | `17FB` (Boot_entry `OR 20h`) | `179B`/`179D` (standby refresh `AND DFh`) | boot/standby line |

### Port `48h` / `49h` — strobe + echo pair

`Kernel_SenseDiagEcho` (ROM00:24F7-252D) drives `48h` bits 0-1 with
`00,01,02,03` and reads back `49h` low 2 bits, requiring each to match
(result `FD AF`). **The result is diagnostic only:** `fdaf` is read by
`Diag_SelfTestScreen` (03D3), which prints it as the self-test
"Status flags" line (string at ROM00:29D1) then enters a key-wait loop.
**Nothing downstream is functionally gated on the outcome** — it is not
a presence check that enables/disables a device. `48h` is an OUTPUT
(`F792` shadow) and `49h` an INPUT on the same 2-bit line set (`49h` is
also read at reset as a boot-mode selector, ROM00:0168-0172); whether
those lines reach an external device (IR transceiver) or are merely an
internal loopback is **not determinable from the ROM**. `Link_SelftestRun`
(28AE-28E4) additionally powers port `04h` to `FFh` as part of its run.

### Multiplexing conclusions

* **Q1 (why two select bits):** `Link_PortSelect` (ROM00:3454) drives
  `LINK_CTRL` bit 1 and port `2C` bit 5 as a strict mirror pair — both
  set on the wire-ID-bit-5-clear branch (`old|02h` vs `(old&FCh)|20h`)
  and both cleared on the bit-5-set branch. No site sets one without the
  other, so it is one select signal fanned to two latch outputs.
* **Q3 (device selection) — CORRECTED (2026-09-24): there IS a genuine
  device selector, and it includes the barcode.** `g_bActiveDevice`
  (FBC5) is mapped through `Device_LookupConfigEntry` (ROM00:31FF) into
  the `FE83`/`FE93` config tables to produce a **wire-id** (reader-channel
  selection at ROM00:110C: `((FBC5>>2)+5)&1Fh` → FE83+idx−1 → wire-id in
  `f999`). That wire-id is then dispatched by `Link_CommandLookup`
  (ROM00:31C6) through a wire→handler table (base `IX=0x31F5`, wire list
  at ROM00:31F2 = `2B,2A,23,03,…`) to a per-device handler: **`2Bh` and
  `2Ah` → `0x1221` (`ExtBus_BusArm`, the barcode)**; **`23h` and `03h` →
  `0x1893` (`Bdos_SharedErrorStub`)**, which issues syscall `FEh`
  (`LD C,FEh; RST 28h`) — an error/support route, so `23h`/`03h` are not
  real devices. Measured `FBC5=04` → FE83+5 = **wire `2Bh`**, which is
  the barcode. So the device index **does** select the barcode,
  alongside the IR and storage devices — this supersedes the earlier
  "link-only" reading.
* **Q2 / Q5 (barcode vs back-IR; both IR on one cluster):** the "device"
  tables select the logical device by wire-id (above), and the barcode
  and IR link DO share actively-configured control-latch bits — this is
  *not* a case of "neutral" values. The owner's bench gate (black/pin5 =
  `2Dh` bit 0 timing input) requires **`2A` bit 1 HIGH and `2C` bit 5
  LOW** (owner-measured hardware requirement), and the firmware configures
  exactly that on barcode arm: `ExtBus_BusArm` clears `2C` bit 5
  (ROM00:122C) and sets `2A` bit 1 (ROM00:1245, for device id `2Ah`).
  Since IR operation clears `2A` bit 1 (`Link_PortSelect` ROM00:3458,
  both branches), the two bits form a plausible 2-bit device decode:
  `2A` bit 1 HIGH = barcode, LOW + `2C` bit 5 HIGH = V24 IR, LOW + `2C`
  bit 5 LOW = PLINTH IR. Whether this is one hardware router or two
  independent enables, and whether the two IR ports share one
  transceiver cluster, remain **OPEN** (hardware).

## Remaining port-bit refinements (2026-09-24)

### Port `07h` — `CTRL_07`

Write-only two-bit output (shadow `F786`); only bits 0-1 are ever
written. Six write sites, no reads. Observed contexts:
* **bit 0** (`01h`): set on entering power-down (`Power_SaveState`
  ROM00:28F0-28F2 writes `01h`, just before port `04h`=FFh) and cleared
  on the wake path (Boot_entry ROM00:17B1-17B6, `AND FEh`) — consistent
  with a power-down indicator/output.
* **bit 1** (`02h`): cleared by the RTC-alarm status watcher
  (`Link_StatusWatcher` ROM00:24A5-24AD), set by a companion
  (ROM00:24B3-24B8) and in the restart flow (ROM00:23C7-23CC) — toggles
  around a periodic RTC/link event.
**Physical role OPEN** — candidates: alarm/status output, peripheral
power/control. No read site to corroborate.

### Port `04h` — interrupt-ENABLE + capture-window gate (mixed register)

**Reframed (2026-09-24):** port `04h` is a **mixed-purpose register**.
Bits 0-4 are the **interrupt-enable mask**; bit 5 is a peripheral
capture-window gate. `Kernel_CfgEnableIrq` (ROM00:22E9) loads `1Fh`,
`CPL`s it, stores `F784`, and `OUT (04h)` — so **a bit set in the
argument enables that source** (active-low stored mask). The interrupt
dispatch gates `STATUS_IN` by this mask (`B = NOT(F784 OR status)`; a
source fires iff its mask bit is 0 and its `STATUS_IN` bit is 0).
* **bits 0-4** = enables for the five polled sources (kbd / RTC-wake /
  link / main-battery / backup-battery).
* **bit 5** = barcode **capture-window gate** (peripheral output, not an
  interrupt-enable): cleared at capture entry (ROM00:1397 `AND DFh`),
  set at capture completion (ROM00:1499 `OR 20h`) — it brackets the
  barcode edge-capture window. There is no `fd84` source-5 entry; it is
  a separate output bit, so the whole register is **not** purely an
  interrupt controller.
* **FFh** = all sources masked (ROM00:28DA/28FB before power-down).

The legacy `OUT_LATCH`/`Kernel_IrqMask*`/`Lcd_Contrast*` names describe the
interrupt-enable bits loosely.

### Port `33h` — orphan

Single access in the firmware: `IN A,(33h)` at the tail of an
LCD-stub at ROM00:1ED0 (`LD A,0Dh; OUT (03h); …; IN A,(33h); RET`) with
**no xref to 1ED0** (unreachable by static refs). Candidates: LCD
status/busy read or an alias of `23h`/`03h`. **OPEN**; not fruitful.

### Port `05h` — `STATUS_IN` = interrupt STATUS register

**Reframed (2026-09-24):** port `05h` is the **interrupt status/pending
register** (read-only — there is no `OUT` to it anywhere in the image).
Each IRQ `Kernel_WorkerPollPort5` (ROM00:230A) snapshots it to `F785`,
gates it by the interrupt-enable mask (`OUT_LATCH`/`04h` shadow `F784`),
and dispatches via the `fd84` `{mask,handler}` table (template
ROM00:2352):
* bit 0 (`01h`) → `18F0` `Kbd_ScanMain` (keyboard event)
* bit 1 (`02h`) → `2206` `RTC_WakeReasonFetch` (RTC alarm/wake)
* bit 2 (`04h`) → `31B6` `Link_IrqPollArmOrService` (link event)
* bit 3 (`08h`) / bit 4 (`10h`) → `2365` (latches inverted status to
  `FDA1`, then sets `OUT_LATCH` bits 3-4 via `Kernel_IrqMaskBitsSet`)
bit 1 is also probed directly in the standby wake path (ROM00:17A5).
The two reset reads (ROM00:01B1/0238) read-and-discard the value, so
port `05h` is **not** the reset boot-key test (that is port `49h`).

### Battery-low monitor (main / backup)

The low-battery warnings trace to active-low flag lines on `STATUS_IN`
bits 3/4:
* **MAIN BATTERY LOW** (string ROM00:24CA) — printed when
  `STATUS_IN` **bit 3 is low**.
* **BACKUP BATTERY LOW** (string ROM00:24DD) — printed when
  `STATUS_IN` **bit 4 is low**.
* **Chain:** the IRQ dispatch's handler `2365` (which fires on status
  bits 3/4) latches the inverted status into `FDA1` and schedules a
  deferred call to the battery check at ROM00:2387; that routine tests
  `FDA1` bits 3/4 (`AND 18h`), prints the MAIN and/or BACKUP message
  (via the string printer ROM00:240C), and sets `CTRL_07` bit 1 on
  backup-low (ROM00:23C7-23CC). If neither flag is set it clears
  `OUT_LATCH` bits 3-4 and continues.
* **Confirms the owner-surmised low-battery detection** (micronic_notes):
  the unit reads active-low battery-flag lines on port `05h` bits 3/4,
  not a sampled analog ADC.
* The related link-layer text "Link inhibited -   battery low"
  (ROM00:2D59) is the session consequence when a link transfer is
  inhibited on low battery; its exact reference is not yet located.

## Barcode front-end I/O set (2026-09-24)

The side-port barcode reader front end uses these ports, sequenced
around the edge-timing capture:
* **Port `2Dh`** (read-only edge input): bit 0 = photocell/timing input
  (owner: black/pin5); **bit 1** = second input, tested with bit 0 at
  `ExtBus_BusArm` (ROM00:1299 `AND 1` / `12A3` `AND 2`) to select the
  attached barcode device type `E = 0/1/2` (stored in `f9ab`).
* **Port `2Ah`** (shadow `F78B`): bit 0 = output (owner: yellow/pin6
  sink/release), bit 1 = attention/trigger, bit 4 = output (owner:
  red/pin1), bit 5 = boot/standby line.
* **Port `2Ch`** (shadow `F78D`): bit 0 = attention-strobe pulse, bit 1 =
  capture enable around `2Dh` reads, bit 5 = IR port select / barcode
  gate.
* **Port `04h` bit 5** = **capture-window gate**: cleared at capture
  entry (ROM00:1397) and set at capture completion (ROM00:1499),
  bracketing the capture; a peripheral output, not an interrupt-enable.
* **Port `2Bh`** = sounder: the attention beep is emitted through the
  standard `Sound_2bWrite`/`Sound_Off` path (not a new barcode pin).

The capture sequencing (ROM00:1317-14A3): sample `2Dh` → `04h` bit 5
clear (capture entry) → poll/acquire `2Dh` edges (`ExtBus_BusAcquireEdge`)
→ `04h` bit 5 set (capture completion) → arm/re-arm. The `2A`/`2C`
attention lines are set around each capture window.

### Barcode device-type probe (ROM00:1221 `ExtBus_BusArm`)

At arm time the barcode front end identifies the attached device by a
2-bit probe on `2Dh` after a control-line pulse (byte-verified):
1. Clear port `2C` bit 1 (`F78D &= FD`), delay (~0xDE-loop, ROM00:35CE),
   then set port `2C` bit 1 (`F78D |= 02`) — a control-line pulse.
2. Short delay (ROM00:1563, A=2).
3. Read port `2Dh` → 3-state code `E`:
   * bit 0 **set** → `E = 0` → invalid/error (JP 13A3)
   * bit 0 clear, bit 1 **set** → `E = 1` (route 12DD)
   * bits 0 and 1 **clear** → `E = 2` (default)
4. `E` stored in `f9ab` **and** `fbcb`; `fbcb` later selects the
   power-down latch value (`F8h` vs `D8h`, ROM00:1772).
5. Route on `E`: `E=1` gates the attention beep on `fbbf` (work item
   `DE=1`); `E=2` calls the attention strobe directly.
The physical device mapping of the `E` codes and the electrical role of
`2Dh` bit 1 are **OPEN** — see GitHub issue #29.

### Wire-`0x2B` identity ambiguity (OPEN)

Wire-id `0x2B` appears in two contexts that must be reconciled:
* **Reader channel** — `Device_SlotSelectPair` (ROM00:110C-1119) computes
  `((FBC5>>2)+5)&1Fh` → `FE83+idx-1` → wire-id stored in `f999`, which is
  read by **`Bdos_ReaderInChar`** (ROM00:1083, the `RDR:` reader = the
  barcode). Measured `FBC5=04` → wire `2Bh`.
* **Disk probe** — `Disk_SelectWireId2b` (ROM00:0D6B) loads `A=0x2Bh`
  and probes it (`Fs_SelectProbeResult`). Its plate (prior analysis)
  labels it "EXT STORAGE default".

So `0x2Bh` is the `RDR:` barcode channel *and* is probed by a disk
function labeled "ext storage". Resolution is **OPEN** — either the
barcode reader and the ext-storage device are the same/related device,
share the wire-id value in different lookup contexts, or the disk
function is mislabeled. Do not resolve by fiat.

### Storage adapter (EXT STORAGE) — IR/link device (2026-09-24)

Confirmed as an **IR/link device**: it is probed and accessed over the
4× byte transport (`4A-4F`), consistent with AGENTS §3.
* **Probe** — `Disk_SelectProbe` (ROM00:0ABC): `HL=0x839` (callback);
  `CALL 2F1A` (`LinkTransportCall`); `C=0x0B`, `HL=0x40`;
  `CALL 168F` (`EventWaitForLink`); checks result bit 0 (0xEE = none)
  and drive type from `f93e` (>=0xDF valid). `Disk_SelectWireId2b`
  (0D6B) drives the probe with wire `0x2Bh`.
* **Keyed-record access** — `Disk_KeyedWriteCmd` (ROM00:081B) writes a
  4-byte keyed-read command header `{C,B,E,D}` at `(HL)` (length + key);
  `DiskKeyedRead0` (0AA5) reads a 0x24-byte record, `DiskKeyedRead128`
  (0AB0) a 0x80-byte block; `DiskKeyedSearch` (0A6D) searches by key;
  `Disk_KeyedClearPair` (0A0D) clears a keyed record.
* **Validate** — `Disk_DriveValidate` (ROM00:3205) reads the `FE93`
  storage config (wires `73h`/`72h`).
So the drive is a keyed-record peripheral on the IR link, probed by
wire-id and read through 4-byte keyed-read commands over the transport.

### Storage vs barcode front end (adversarial check, 2026-09-24)

**Storage does NOT use the barcode scanner side port.** All eight
`2Dh` (edge input) reads are inside the barcode front-end code
(ROM00:1200-1570); the storage/drive path uses `Link_TransportCall`
(ROM00:2F1A) via `Disk_SelectProbe` and the `Device_*` service-33
open/message functions. So the storage data flows over the **4× byte
transport** (`4A-4F`), never the 2D edge front end. The only overlap
with the barcode is the shared control-latch bit (port `2C` bit 5 = IR
port select), not the data path.

**Port: BACK PLINTH (LIKELY).** The storage wires `73h`/`72h` (`FE93`)
both have wire-ID **bit 5 = 1** (`73h & 20h`, `72h & 20h`). Bit-5=1 is
the state complementary to the owner-confirmed top **V24** port
(bit-5=0 → `LINK_CTRL` bit1 set, port `2C` bit5 set). By two-port
elimination the storage adapter is on the **back PLINTH** port (LIKELY;
not yet observed there).
---

## Keyboard: Sun (☼) modifier (2026-09-24)

The Sun key (keycap ☼) is keycode `D0h` (`tbl_kbd_map` page 0/1 index
27). Two distinct mechanisms:
* **One-shot Sun (tap Sun, then a key)** selects page 2 of `tbl_kbd_map`
  (ROM00:1B58, 3 × 36-byte pages) for the next key. Page 2 (ROM00:1BA0)
  maps F/J/N to `X`/`Y`/`Z` (`58h`/`59h`/`5Ah`) and supplies function
  codes `1Ah`, `0Ch`, `12h`, `0Bh`, `11h` at other positions; the rest
  are `00`.
* **Held Sun + key (direct chord)** bypasses the table: the dispatch at
  ROM00:19C0 matches the raw matrix pattern (A = `KBD_DRIVE` byte, B =
  expected `KBD_SENSE` rows) against the 4-entry table at ROM00:19E0 and
  tail-jumps to the handler:

  | pattern (drive, sense) | handler | operation |
  |---|---|---|
  | `04h,01h` | `1A0A` | backlight toggle (Sun+`LIGHT`/B) |
  | `10h,08h` | `1D60` `Lcd_ContrastUp` | LCD contrast up |
  | `08h,21h` | `1D4A` `Lcd_ContrastDown` | LCD contrast down |
  | `01h,01h` | `19FB` → `1721` | power-down (Sun+MODE) |

**Contrast:** `Lcd_ContrastUp`/`Lcd_ContrastDown` step `FC05` by ±2
(floor `00`, ceiling `FF`) and apply it to port `46h` (LCD contrast DAC)
via `Lcd_ContrastWrite` (ROM00:1FD4). **CONFIRMED** — the legacy
`Power_Latch*` names were misnomers (contrast adjusters).

**Wake from deep standby:** pressing a key during `Power_DownSuspend`
wakes the unit, but the *keypress itself is not decoded* in the standby
spin (it only drives the wake event); what, if anything, the waking key
then triggers is **OPEN** (the NMI/restart path restores the saved
session state).

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
