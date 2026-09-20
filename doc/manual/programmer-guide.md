# Programming for DIPOS-B — a guide for CP/M 2.2 programmers

*Micronic 1000 / PARCON 1000 (battery-powered, IR-linked handheld)*

This document is written to be read **alongside a CP/M 2.2
programmer's guide** (e.g. the Digital Research *CP/M 2.2 Alteration
Guide* or *CP/M Programmer's Guide*). It assumes you already know how
to write CP/M 2.2 programs and focuses on **what is different** when
programming for the Micronic's DIPOS-B operating system.

It describes DIPOS-B's CP/M-shaped entry convention and the supported subset.
Use it with the [supported profile](supported-profile.md) and
 [BDOS reference](../reference/bdos.md); it does not re-teach CP/M.

### CP/M reference manuals

For stock CP/M 2.2 behaviour, use these verified manuals — DIPOS-B's
documentation overrides them where they differ:

- [CP/M 2.2 Alteration Guide](https://bitsavers.org/pdf/digitalResearch/cpm/2.2/CPM_2.2_Alteration_Guide_1979.pdf)
- [CP/M Assembly Language Programming](https://bitsavers.org/pdf/digitalResearch/cpm/CPM_Assembly_Language_Programming_1983.pdf)
- [CP/M Operating System Manual](http://www.gaby.de/cpm/manuals/archive/cpm22htm/)

Where this guide, the [BDOS reference](../reference/bdos.md), or
[CP/M comparison](../re-notes/cp-m-comparison.md) states a DIPOS-B
deviation (version `0023h`, 16 drives, device-routed console, RAM
disks, wrapped `F3h-FFh` table, `F5h`/`FCh-FDh`/`FFh` extensions), that
DIPOS-B contract is authoritative.

---

## 1. What DIPOS-B is

DIPOS-B exposes a CP/M-2.2-shaped BDOS interface with a verified compatible
subset and proprietary extensions. It is entirely in ROM (there is **no CP/M
disk bootstrap** or CP/M
disk). The firmware is stored in ROM; the kernel and resident modules are copied
to battery-backed RAM at boot. The "disks" are
**RAM**.

The machine is a battery-powered handheld with an LCD, a keyboard,
an HD146818 real-time clock, and an **infrared link** (used for
program/data transfer to/from a PC via a Commstar-style session).

### Keyboard input pages

The keyboard scanner uses three 36-byte pages at `ROM00:1B58`. Ordinary
keys use page 0; Shift (MODE) selects page 1; tap/release Sun (2nd) selects
page 2 for one following key. These are distinct modifiers, not two names
for Shift. Held Sun is intercepted before keymap lookup for B/END/ENTER/MODE
direct chords; held Sun+X/Y/Z emits no key.

At the physical N/Z key position the pages return `0x4E` (N), `0xDB`, and
`0x5A` (Z), respectively. `0xDB` is a field-editor command, not text: in the
Load/Run `From` field it advances the enumerated source. Thus a program or
input emulator must emit `0xDB` for Shift+N and `0x5A` for Sun+N; emitting
ASCII Z for Shift+N is incorrect. See the [user guide](user-guide.md#the-keyboard)
for the complete physical-key grids.

The local terminal's `ESC A` and `ESC B` select page 0/cursor blink and page
1/character blink, respectively; `ESC R` also selects page 1 and `ESC S`
toggles page 0/1. `ESC U` alone consumes inherited `D/E` register values for
a private direct LCD write; no static firmware stream emits `ESC U`.

### Calling BDOS

The entry shape follows CP/M: put the function number in register **C**, any
documented pointer argument in **DE**, and call **address 0005h**:

```
    LD   C, FNC           ; function number
    LD   DE, FCB          ; (for FCB functions) FCB address
    CALL 0005h            ; enter BDOS
    ; result in A (and HL where CP/M returns a 16-bit value)
```

Entry 0005h (`JP F180h`, kernel in battery RAM) is present in both
memory banks. Register conventions match CP/M 2.2 (function number in
C, not E as in some other implementations).

### Memory organisation

The 64K address space is split:
- **0000-7FFFh** — a bank-switched window. Bank select is **port
  47h** (shadow `F791`). Bank 0 = kernel ROM, bank 1 = UI/Workstation
  ROM, banks 2+ = pages of the 256K static RAM.
- **8000-FFFFh** — fixed, **battery-backed** static RAM (32K of the
  256K total), used by the kernel and user program area.

A program normally lives in the RAM area. **RST 10h (restart vector 2) is a
banked-call dispatcher** — a DIPOS-B addition you will not find in
stock CP/M (see §6).

### Version

BDOS function **12 (return version number)** returns **HL = 0023h**
(CP/M "2.3"-style). Do not rely on it being 22h.

---

## 2. Files and drives (the RAM file system)

### No physical media

The local filesystem uses RAM. The drive table also has nonzero IDs that
enter session helpers; actual peer-dependent file operations and external
attachment need verification. A selectable letter is not proof of a
mounted device or an independent volume.

The canonical [drive table and operational limits](devices-and-storage.md#drives)
distinguish default IDs from demonstrated behavior. Do not infer a 32 KiB
A: volume and a 224 KiB B: volume from total SRAM capacity or menu names.

### Drive selection

- **Function 0Eh (select disk)**: register E = 0-15. Up to **16
  drives** are accepted (drive selection alone does not establish device availability). Values >= 16
  return 0xFF (error).
- **Function 19h (get current disk)**: returns the currently selected
  drive number in `A` (not `HL`) as the BDOS result; flags are not meaningful
  through `CALL 0005h` (see [BDOS reference](../reference/bdos.md)).
- **Function 18h (get login vector)**: **not really implemented** —
  returns a stub.

### FCB layout

The FCB is the standard CP/M 2.2 36-byte structure (drive byte,
8.3 filename, extent, S1/S2, record count, DM, CR, R0-R2). The drive
byte is interpreted by DIPOS-B as follows:

- **Drive byte 0** (default) → uses the currently selected drive
  (`fbc6`).
- **Drive byte 1..16** ('A'..'P') → selects the named storage/link
  device.

The 8.3 name path accepts uppercase characters and `?` wildcards for search.
See the [BDOS reference](../reference/bdos.md) for the verified normalization and
mutation behavior rather than assuming every stock CP/M edge case.

### File operations that work

The standard FCB/directory/record functions are implemented:

| fn | operation |
|----|-----------|
| 0Fh | open file |
| 10h | close file |
| 11h/12h | search first / search next |
| 13h | delete file |
| 14h | read sequential |
| 15h | write sequential |
| 16h | make file |
| 17h | rename file |
| 21h/22h | read / write random |
| 23h | compute file size |
| 24h | set random record (table end) |

Records are 128 bytes; a block is 32 records (4096 bytes), matching CP/M.
Use the [BDOS reference](../reference/bdos.md) for the verified field behavior:
in particular, random read/write interpret only offsets `+21h` and `+22h`,
not the high random-record byte at `+23h`.

### File operations that are stubs or restricted (do not use as general CP/M calls)

| fn | operation | what actually happens |
|----|-----------|-----------------------|
| 0Dh | reset disk system | unsafe shared diagnostic via `RST 28h` (`Bdos_SharedErrorStub`); behaviour conditional on `Bdos_SelectRst28Mode` — do not call |
| 1Bh / 1Dh | get allocation / read-only vector | returns `HL=0000h` (stub) |
| 1Ch | write protect disk | unsafe shared diagnostic via `RST 28h`; do not call |
| 1Eh | set file attributes | unsafe shared diagnostic via `RST 28h`; do not call |
| 1Fh | get DPB address | unsafe shared diagnostic via `RST 28h`; do not call |

**1Ah is not a stub:** `Bdos_SetDmaAddress` stores `DE` as the DMA pointer for
record I/O — it is a real state mutation, but downstream record-I/O ABI
remains incomplete (see [BDOS reference](../reference/bdos.md)). There is no
DPB/allocation-vector scheme to query because the "disks" are fixed-size RAM
partitions. **Do not rely on functions 0Dh, 1Bh-1Fh for portable behaviour.**
The high-level file calls (open, read, write, close, search, rename) plus
`1Ah` for DMA setup are what you use.

---

## 3. Console and device I/O (the big difference)

In CP/M, the console/reader/punch/list are mapped to physical I/O
through the IOBYTE. In DIPOS-B this is replaced by a **device
abstraction**: the console is a *virtual device* selected at
run-time, and the link can be redirected to the **IR (Commstar)
link** rather than the built-in LCD/keyboard.

### Console functions

| fn | operation |
|----|-----------|
| 01h | console input (waits) |
| 02h | console output |
| 06h | **direct console I/O** — with E=0xFF it is the *status/poll* primitive (no wait); this is what the session layer uses |
| 09h | print string at (DE) |
| 0Ah | read console buffer |
| 0Bh | get console status |
| 03h | reader in (RDR:) — implements the **external-device scan path** as a byte stream (see below) |
| 04h/05h | punch out / list out (device-routed; detailed behaviour varies by configured slot) |

### Reader input (fn 03h) — external-device capture

`fn 03h` = `Bdos_ReaderInChar` (ROM00:1080) reads the owner-adjudicated
**barcode-reader edge-capture pipeline**. Each scan is
delivered as: `1Bh` (scan-arrived), then `count`, then `count` data
bytes. The resident firmware default *discards* every capture (the
decode-hook default at ROM00:1567 zeroes the element count); a
program installs its own decoder at the hook socket **FBC2** (bank byte
FBC1, `D7` RST-10 stub at FBC0), which the capture tail (ROM00:1458)
calls after each capture with `FBB9`/`FBBB` = width-table ptr/count.
See [the barcode-reader guide](../reference/barcode.md) for the install recipe.

**Important:** `console output` (02h), `console input` (01h) and
`direct console I/O` (06h) **route through the active device**,
which can be the LCD/keyboard *or* the IR link. Output redirected to
the link appears at the *other end* (e.g. a PC). The active device is
selected by the **DIPOS-B extension** F7 (`SetActiveConsoleDevice`,
see §5).

### IOBYTE

Functions 07h (get IOBYTE) and 08h (set IOBYTE) exist but are
**read-only stubs** — setting the IOBYTE has no effect on routing.
Device selection is done with the extension functions, not the
IOBYTE.

### The shell's own screen UI

When no program is running (or between programs), the LCD shows the
DIPOS-B shell: a tree of **menus** (digit-keyed item lists) and **forms**
(field lists edited with YES/NO/ENTER). This is *not* a callable BDOS
library — the shell draws it on the same console device your program uses
(§3), and a loaded program's console I/O simply takes over the screen. The
**8000-series `*** ERROR ***` banner** (e.g. `8000` Plinth not connected)
is the shell/session layer's *own* error display and is unrelated to your
program's BDOS return codes. See the [user guide](user-guide.md) (operator
view) and [forms and UI](../re-notes/forms-ui.md) (internals).

---

## 4. Extended / system functions

Most of the useful non-file services are DIPOS-B **extensions**
(function numbers above the CP/M range). They group into:

1. **Device management** — select/read the active device
2. **Config-table access** — read/write the IR/link and storage
   configuration tables
3. **Real-time clock** — set/get the HD146818 time and alarm
4. **Timing** — a delay / period control

### The wrapped extension table

The kernel dispatches BDOS fn < 25h through the CP/M-shaped F1EB table
(`CP 0x25 / JR C`). Functions **0xF3 .. 0xFF** are the VALID wrapped
extension table: `CP 0xF3 / JR NC` takes the `DEC B` (B=FF) path, so
index C=F3..FF wraps onto the 13-entry table (ROM00:36EE, RAM copy at
`F1D1`) — correct by design. These entries are mechanically identified;
only calls allowed by the supported profile should be used by applications:

| fn | name | action |
|----|------|--------|
| 0xF5 | **set delay** | set a delay/period used by the event-wait loop |
| 0xF6 | **get active device** | returns the current active console/link device id |
| 0xF7 | **set active device** | select the active console/link device |
| 0xF8 | **read link config** | copy the 16-byte FE83 IR/link config (wire-ids) to your buffer |
| 0xF9 | **set device pair** | select a device pair for a link slot |
| 0xFA | **write link config** | write a 16-byte buffer into the FE83 IR/link config |
| 0xFB | **write storage config** | write a 16-byte buffer into the FE93 storage (drive) config |
| 0xFC | **set RTC time** ([8-byte record](../re-notes/rtc.md#bdos-eight-byte-rtc-record)) | write RTC regs `09/08/07/04/02/00/06` from `+1..+7`; `+0` metadata copied/RTC ignored (provisional: century `19`) |
| 0xFD | **get RTC time** ([8-byte record](../re-notes/rtc.md#bdos-eight-byte-rtc-record)) | read RTC into `+1..+7`; `+0` from `g_bRtcRecordMetadata` (`13h`, provisional `19`); polls `UIP` |
| 0xFE | **`Bdos_InternalTimedWait`** (`ROM00:1122`) internal timed wait | `E<<4` interval, low→`(IY+23h)` high→`word[FEFA]`, `FD4D` HALT wait; resident only |
| 0xFF | **RTC alarm control** ([8-byte record](../re-notes/rtc.md#bdos-eight-byte-rtc-record), `Bdos_FfAlarmControl`) | `DE=0` clears `AIE` else `+4..+6`→`05/03/01` + `AIE`; `+2/+3` date gate `RTC_AlarmDateMatches`; UIP blocks both |

(0xF3 = no-op; 0xF4 enters the mutable, unsafe RST-28 path.)

An **unmatched** fn in 25h-F2h falls through that same `DEC B` path
and dispatches through a **wild pointer** (its handler word is read
from the JP-vector run past the table, e.g. fn 40h → F26B). Nothing is
rejected. **HAZARD: calling an undefined BDOS function in 25h-F2h
jumps through garbage — do not probe for extensions by calling them.**

### Special non-sequential functions

| fn | action |
|----|--------|
| 2Dh | **`Bdos_SelectRst28Mode`** (`ram:F55A`) — mutable RST28 mode selector (`E=FFh` installs `F57B` no-op target, `FEh` default diagnostic `F57E`, `FDh` deferred `F59F` + `HL->FDBA`, `FCh` fatal `F5C0`); global unsafe state |
| 2Eh | **`Bdos_UpdateDriveDirectoryMetadata`** (`ROM00:0D79`) — drive metadata compute/stage/commit; `A=00h` local, nonzero entries load `A=2Ch` and enter session helpers; peer-dependent result remains unverified |
| 30h | shared diagnostic dispatch via `RST 28h` — behaviour conditional on current `2Dh` target |
| 62h | filesystem/directory integrity check |
| 68h/69h | no-op stubs |

### Real-time clock use

The clock is an **HD146818** accessed through ports (address latch
08h, data 28h). You do not need to touch the chip directly — use the
BDOS extension functions. Canonical 8-byte layout is
[BDOS eight-byte RTC record](../re-notes/rtc.md#bdos-eight-byte-rtc-record):
`+0` metadata (FC copied/RTC ignored, FD from `g_bRtcRecordMetadata`
`13h` provisional century `19`, FF copied unused), `+1` year→`09h`,
`+2` month→`08h`, `+3` day-of-month→`07h`, `+4` hour→`04h`,
`+5` minute→`02h`, `+6` second→`00h`, `+7` day-of-week→`06h`;
raw binary, 24-hour (Reg B `46h`), no firmware validation.

- **0xFC set RTC time** (`ROM00:1150`): pass `DE` → 8-byte block as
  above; writes `09/08/07/04/02/00/06` under SET/divider-stop; `A=00h`.
- **0xFD get RTC time** (`ROM00:113E`): reads clock into your 8-byte
  buffer as above; polls `UIP`, permanent `UIP` blocks return.
- **0xFE**: **`Bdos_InternalTimedWait`** (`ROM00:1122`) — not a general
  alarm setter; `E<<4` interval, low→`(IY+23h)` high→`word[FEFA]`,
  `FD4D` countdown/`HALT` wait; resident context required; `A=00h`
  completion.
- **0xFF**: **RTC alarm control** (`ROM00:112D`, `Bdos_FfAlarmControl`) —
  `DE=0000h` clears `AIE`, otherwise programs `+4..+6`→`05/03/01` and
  enables `AIE`; `+2/+3` date-gated by `RTC_AlarmDateMatches`
  (`g_bRtcAlarmDayOfMonth`/`g_bRtcAlarmMonth`); polls `UIP` before
  both — permanent `UIP` blocks; preamble `RegA|80h` likely ineffective
  then `RegA=2Ah`.

FC, FD, and FF provide the established clock/alarm operations. FE is an
internal resident-runtime wait and is not a general application service.

---

## 5. Cold and warm boot

- Reset with a clear boot-mode flag → **cold start** → self-tests →
  kernel copy → warm-restart tail into the restored program in top
  RAM.
- The machine **preserves the running program across a power-off**
  in battery-backed RAM; pressing power re-enters the program via the
  warm-restart path.
- A service-mode boot can be entered by holding the service key at
  reset.

The **warm-boot entry** is `024Dh`; BDOS function 0 (system reset)
takes the warm-restart path.

---

## 6. Banked calls (RST 10h) {#6-banked-calls-rst-2}

DIPOS-B programs and the system itself run from a bank-switched
window. The OS provides a **banked-call** mechanism so a program can
invoke a routine in another bank. It is not standard CP/M and is
normally only needed by the OS / drivers, but it is part of the
machine's programming model:

```
   RST 10h      ; restart vector 2, banked call (opcode D7h)
   DB bank      ; 1-byte bank number
   DW target    ; 2-byte target address in that bank
```

The RST 10h dispatcher re-selects the bank via port 47h and vectors to
the target. **A program only needs this if it is written to live in a
non-bank-0 page** and must call the kernel; ordinary CP/M-style
`CALL 5` entry from any bank is already handled by the page-zero
gate.

---

## 7. Practical summary of differences

| Area | CP/M 2.2 | DIPOS-B |
|------|----------|---------|
| Storage | floppy/disk BIOS | RAM filesystem plus session-backed paths; capacities/remote operation require verification |
| Drives | Drive selectors | A-P selectors; FE93 configuration and demonstrated operations are separate |
| Version (fn 0C) | 22h | **23h** |
| Allocation/read-only vectors (1B/1D) | implemented | **stubs (`HL=0000h`)**; `1Ah` is implemented set-DMA (stores `DE`) |
| Diagnostics (0Dh/1Ch/1Eh/1Fh/30h/F4h) | real | **unsafe shared `RST 28h` path; behaviour conditional on `Bdos_SelectRst28Mode` (`ram:F55A`)** |
| Console device | IOBYTE | **device abstraction** (select via fn 0xF7) |
| Clock/alarm | n/a | **fns 0xFC-0xFF** (HD146818) |
| Link/IR config | n/a | **fns 0xF8-0xFB** |
| Banked calls | n/a | **RST 10h** |

### Things to avoid

- Do **not** depend on allocation vector / DPB ( `1Bh`/`1Dh` stubs,
  `HL=0000h`) or on write-protect / set-attributes / DPB / disk-reset
  (`0Dh`/`1Ch`/`1Eh`/`1Fh`/`30h`/`F4h` are unsafe shared `RST 28h`
  diagnostic paths whose behaviour is conditional on the global
  `Bdos_SelectRst28Mode` (`ram:F55A`) — do not call).
- Do **not** try to select more than 16 drives, or assume drive `C:`+
  is always a file store — default `A:` has ID `00h`, while `B:`/`C:`/`D:` have nonzero
  IDs and enter session helpers. The mapping is configurable through `FE93` (see
  [devices and storage](devices-and-storage.md)).
- Do **not** assume console is always the LCD — it may be redirected
  to the IR link.

### Things to use

- The standard FCB file calls (0F-17, 21-24) for RAM-disk files.
- Fns **0xFC**, **0xFD**, and **0xFF** for the documented clock/alarm calls;
  do not call resident-only **0xFE** from an ordinary application.
- Read-only/query extensions only where the supported profile permits them;
  F7h/FAh/FBh and related calls mutate global configuration.
- fn **06h** (direct console I/O, =0xFF) for poll / session input.

---

## Program image formats: COM and DIP {#7b-program-image-formats-com-and-dip}

Apart from standard CP/M `.COM` files, DIPOS-B has its own
block-structured **DIP** program format ("DIP files"), plus a
`Fastcode:` transfer mode used over the link. The loader is the
**runtime Load/Run loader** in ROM01 (`ROM01:0A67-10CE` via
`ram:D081 -> ram:D0F0`); it is distinct from the ROM boot-load chain
(`ram:D6DB` / `ram:D6F4` `fn=0/1/2/FFFF`), which is boot-only.

### Packaging a program

Use a COM for a single flat image loaded at `0100h`; use DIP when the
loader must place blocks in different banks or install banked-call stubs.
The canonical [program-format reference](../reference/program-formats.md)
defines headers, block fields, byte order, limits, and exact error messages.
The COM ceiling includes shared fixed RAM; it is not the size of one bank.

For producer helpers and executable validation examples, see
[building and validating images](../reference/program-formats.md#building-and-validating-images).
Validation checks image structure, not availability of a bank or physical
transfer compatibility. The loader's checksum detects changes to loaded
memory before execution; it is not a checksum stored in the file.

### Advantages of DIP over .COM

1. **Multi-segment + banked placement** — one image can target
   several 32K banks and battery RAM, beating the flat 64K limit.
2. **Banked-call initialisation** — type-1 blocks install RST 10h
   banked-call trampolines at selected destinations.
3. **Streamable** — the block stream loads in chunks via the provider
   (`0BAC`/`0CE7`/`D370`).
4. **Better diagnostics** — explicit "too big / too many blocks /
    not built for this system / `0x2332` (9010), "Program corrupt." stages
    vs a one-line
    ".COM too big". `0x232B` (9003), "Bad DIP file." means a truncated 8-byte
   block header or payload, not bad magic.

### Disadvantages vs .COM

- **Not standard** — a DIP must be built by a DIPOS-B-aware tool;
  you cannot just drop a stock CP/M .COM and rename it.
- **Overhead** — per-block headers and per-block trampoline expansion are
  heavier than a raw .COM.
- **More loader complexity** — the block-count/size/system/checksum
  checks are extra failure states.

---

## Evidence and scope {#8-where-this-comes-from}

This guide is based on static analysis of the `micron1.bin` ROM
(banks 0/1) in Ghidra:
- BDOS dispatch table at ROM00:3708 (RAM copy F1EB) — fn 00-24 map to
  CP/M 2.2 handlers.
- Wrapped extension table ROM00:36EE (RAM copy F1D1) — fn F3-FF.
- The device/link layer (drive letters → FE83/FE93 config, IR link,
  session ring) in [the Commstar protocol](../protocol/commstar.md).
- Memory map (battery RAM layout, system variables) in
  [the memory map](../reference/memory-map.md).

All `Bdos*` handlers are named and commented in the Ghidra program.

---

*Conservative compatibility:* a CP/M program that uses only the
FCB file calls (`0Fh-17h`, `14h`/`15h`, `21h`/`22h` with `+21h`/`+22h`
addressing), `1Ah` to set DMA, and the standard console functions,
and that avoids the unsafe dispatch range `25h-F2h` and the `F3h-FFh`
extensions (especially the unsafe global state in `F6h-FBh` and the
`Bdos_SelectRst28Mode` / `Bdos_UpdateDriveDirectoryMetadata` specials),
will run on DIPOS-B with the **caveats** that `19h` returns `A` not
`HL`, drive selection does not guarantee a usable device (see the
[drive table](devices-and-storage.md#drives)), and `FCh`/`FDh` use the
[8-byte RTC record](../re-notes/rtc.md#bdos-eight-byte-rtc-record)
(`+0` metadata provisional century `19`, exact value open). The remaining
differences (`FCh`/`FDh` clock, `FEh` `Bdos_InternalTimedWait`, `FFh`
`Bdos_FfAlarmControl` with `UIP` polling, IR-link and device selection)
are extra DIPOS-B extensions that a stock CP/M program would not have
used.
