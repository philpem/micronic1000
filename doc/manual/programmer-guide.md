# Programming for DIPOS-B — a guide for CP/M 2.2 programmers

*Micronic 1000 / PARCON 1000 (battery-powered, IR-linked handheld)*

This document is written to be read **alongside a CP/M 2.2
programmer's guide** (e.g. the Digital Research *CP/M 2.2 Alteration
Guide* or *CP/M Programmer's Guide*). It assumes you already know how
to write CP/M 2.2 programs and focuses on **what is different** when
programming for the Micronic's DIPOS-B operating system.

It is self-contained: everything you need about DIPOS-B's BDOS call
interface is here. It does not re-teach CP/M.

---

## 1. What DIPOS-B is

DIPOS-B is a CP/M-2.2-compatible BDOS with a set of proprietary
extensions, entirely in ROM (there is **no disk BIOS**, no bootstrap
loader, no CP/M disk). The whole OS runs from the Micronic 1000's ROM,
with the kernel copied to battery-backed RAM at boot. The "disks" are
**RAM**.

The machine is a battery-powered handheld with an LCD, a keyboard,
an HD146818 real-time clock, and an **infrared link** (used for
program/data transfer to/from a PC via a Commstar-style session).

### Calling BDOS

Exactly like CP/M: put the function number in register **C**, any
data address in **DE**, call **address 0005h**:

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

A program normally lives in the RAM area. **RST 2 (0010h) is a
banked-call dispatcher** — a DIPOS-B addition you will not find in
stock CP/M (see §6).

### Version

BDOS function **12 (return version number)** returns **HL = 0023h**
(CP/M "2.3"-style). Do not rely on it being 22h.

---

## 2. Files and drives (the RAM file system)

### No physical media

There is no floppy, hard, or ROM disk. Files live in **RAM** on two
logical storage devices:

| Drive letter | Device | Type | Persistence |
|--------------|--------|------|-------------|
| **A:** | **WORKSTATION MEMORY** | fixed RAM area | configuration-dependent |
| **B:** | **WORKSTATION RAMDISK** | banked RAM area | configuration-dependent |

The firmware accepts sixteen drive selectors, but their runtime mapping is
configuration-dependent. The default FE93 table includes external-link
entries; do not assume that every unit maps C: through P: identically, or
that a banked RAM area is not retained by the backup battery. The drive
letter is a **user-visible selector**, not a hardware-unit number. See
[devices and storage](devices-and-storage.md).

### Drive selection

- **Function 0Eh (select disk)**: register E = 0-15. Up to **16
  drives** are accepted (stock CP/M 2.2 allows 8, A-H). Values >= 16
  return 0xFF (error).
- **Function 19h (get current disk)**: returns the currently selected
  drive number in the HL register as usual.
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

The 8.3 name is validated exactly as CP/M (uppercase, `?` wildcards
allowed in search).

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

Records are 128 bytes; a block is 32 records (4096 bytes), matching
CP/M. The FCB record count / random-record fields behave as in CP/M
2.2.

### File operations that are stubs (do not work)

These CP/M 2.2 functions are **not implemented** — they return a
no-op / HL=0:

| fn | operation | what actually happens |
|----|-----------|-----------------------|
| 0Dh | reset disk system | far-call stub |
| 1Ah | set DMA address | returns without effect |
| 1Bh / 1Dh | get allocation / read-only vector | returns HL=0 |
| 1Ch | write protect disk | far-call stub |
| 1Eh | set file attributes | far-call stub |
| 1Fh | get DPB address | returns HL=0 |

There is no DPB/allocation-vector scheme to query because the
"disks" are fixed-size RAM partitions. **Do not rely on functions
0D, 1A-1F for real behaviour.** The high-level file calls (open,
read, write, close, search, rename) are what you use.

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

`fn 03h` = `BdosReaderInChar` (ROM00:1080) reads the owner-adjudicated
**barcode-reader edge-capture pipeline**. Each scan is
delivered as: `1Bh` (scan-arrived), then `count`, then `count` data
bytes. The resident firmware default *discards* every capture (the
decode-hook default at ROM00:1567 zeroes the element count); a
program installs its own decoder at the hook socket **FBC2** (bank byte
FBC1, `D7` RST-10 stub at FBC0), which the capture tail (ROM00:1458)
calls after each capture with `FBB9`/`FBBB` = width-table ptr/count.
See [the barcode-reader guide](barcode-reader.md) for the install recipe.

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
view) and [forms and UI](../internals/forms-ui.md) (internals).

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

The kernel dispatches BDOS fn < 25h through the CP/M F1EB table
(`CP 0x25 / JR C`). Functions **0xF3 .. 0xFF** are the VALID wrapped
extension table: `CP 0xF3 / JR NC` takes the `DEC B` (B=FF) path, so
index C=F3..FF wraps onto the 13-entry table (ROM00:36EE, RAM copy at
`F1D1`) — correct by design. The usable ones for a programmer are:

| fn | name | action |
|----|------|--------|
| 0xF5 | **set delay** | set a delay/period used by the event-wait loop |
| 0xF6 | **get active device** | returns the current active console/link device id |
| 0xF7 | **set active device** | select the active console/link device |
| 0xF8 | **read link config** | copy the 16-byte FE83 IR/link config (wire-ids) to your buffer |
| 0xF9 | **set device pair** | select a device pair for a link slot |
| 0xFA | **write link config** | write a 16-byte buffer into the FE83 IR/link config |
| 0xFB | **write storage config** | write a 16-byte buffer into the FE93 storage (drive) config |
| 0xFC | **set RTC time** | write the real-time clock (HD146818) from an 8-byte time block |
| 0xFD | **get RTC time** | read the real-time clock into a buffer |
| 0xFE | **set RTC alarm** | set the HD146818 alarm |
| 0xFF | **RTC alarm control** | arm/clear the RTC alarm |

(0xF3 = no-op; 0xF4 = far-call stub.)

An **unmatched** fn in 25h-F2h falls through that same `DEC B` path
and dispatches through a **wild pointer** (its handler word is read
from the JP-vector run past the table, e.g. fn 40h → F26B). Nothing is
rejected. **HAZARD: calling an undefined BDOS function in 25h-F2h
jumps through garbage — do not probe for extensions by calling them.**

### Special non-sequential functions

| fn | action |
|----|--------|
| 2Dh | **banked call** — invoke a bank-0 worker from any bank (RST2 helper) |
| 2Eh | directory-search helper (advanced) |
| 30h | far-call stub |
| 62h | filesystem/directory integrity check |
| 68h/69h | no-op stubs |

### Real-time clock use

The clock is an **HD146818** accessed through ports (address latch
08h, data 28h). You do not need to touch the chip directly — use the
BDOS extension functions:

- **0xFC set RTC time**: pass a pointer to an 8-byte time block in
  DE. The block is the standard packed time fields in the order the
  HD146818 file uses.
- **0xFD get RTC time**: reads the clock into your buffer.
- **0xFE / 0xFF**: set / arm the alarm.

These are the clean way for a program to set/read the clock and
alarm, which a stock CP/M program has no equivalent for.

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

## 6. Banked calls (RST 2)

DIPOS-B programs and the system itself run from a bank-switched
window. The OS provides a **banked-call** mechanism so a program can
invoke a routine in another bank. It is not standard CP/M and is
normally only needed by the OS / drivers, but it is part of the
machine's programming model:

```
   RST 2        ; 'banked call'  (opcode DF at 0010h)
   DB bank      ; 1-byte bank number
   DW target    ; 2-byte target address in that bank
```

The RST2 dispatcher re-selects the bank via port 47h and vectors to
the target. **A program only needs this if it is written to live in a
non-bank-0 page** and must call the kernel; ordinary CP/M-style
`CALL 5` entry from any bank is already handled by the page-zero
gate.

---

## 7. Practical summary of differences

| Area | CP/M 2.2 | DIPOS-B |
|------|----------|---------|
| Storage | floppy/disk BIOS | RAM "disks": A: MEMORY (32K), B: RAMDISK (224K) |
| Drives | A-H (8) | A-P (16, only A/B are file storage) |
| Version (fn 0C) | 22h | **23h** |
| Allocation/DPB (1B-1F,0D) | real | **stubs (return 0)** |
| Console device | IOBYTE | **device abstraction** (select via fn 0xF7) |
| Clock/alarm | n/a | **fns 0xFC-0xFF** (HD146818) |
| Link/IR config | n/a | **fns 0xF8-0xFB** |
| Banked calls | n/a | **RST 2h** |

### Things to avoid

- Do **not** depend on allocation vector / DPB / write-protect /
  set-attributes (they are stubs).
- Do **not** try to select more than 16 drives, or use drive C:+
  for file storage (they are IR/link devices).
- Do **not** assume console is always the LCD — it may be redirected
  to the IR link.

### Things to use

- The standard FCB file calls (0F-17, 21-24) for RAM-disk files.
- Fns **0xFC-0xFF** for clock and alarm.
- Fns **0xF5-0xFB** for device and config management.
- fn **06h** (direct console I/O, =0xFF) for poll / session input.

---

## 7b. Program image formats: .COM and DIP

Apart from standard CP/M `.COM` files, DIPOS-B has its own
block-structured **DIP** program format ("DIP files"), plus a
`Fastcode:` transfer mode used over the link. The loader's error
strings are visible in ROM1 (`DIP file too big`, `Bad DIP file`,
`COM file too big`, `Program not built for this system`,
`Program corrupt`, `DIP file has too many blocks`) — these prove the
format parser enforces a size cap, a block-count cap, a
system-compatibility marker and an integrity check.

### DIP is a loader-record stream (verified mechanism)

The DIP and COM loaders both funnel into the **kernel loader
primitives** (resident in battery RAM at `d6f4`+), which consume a stream
of records:

```
d6fa = memset  (fn=0x0000)  zero-fill addr..addr+count
d713 = memcpy  (fn=0x0001)  copy src -> dst, count bytes
d727 = enqueue (fn=0x0002)  append N {RST10h, bank, addr} deferred
                             banked-call stubs to the queue at d684
d6de = record dispatcher    (reads fn, indexes d6f4+2*fn)
```

A **DIP file is a sequence of these loader records**, terminated by
`fn=FFFF` — the same grammar the ROM's own *boot-load chain* uses (the
reset code reads `(7FFC)` and feeds it to the record dispatcher; see
`analysis/decode_chains.py`). Each `fn=2` stub tags the current bank
(`port 47` shadow, `f791`), so a single DIP can place code/data into the
banked 0000-7FFF window *and* the fixed battery RAM, and enqueue
"constructor" calls that run on load.

> The full byte-level spec — record layouts, the 16-bit byte-sum checksum,
> the ROM footer, and the (still-open) DIP file header — is in
> [Program formats: COM and DIP](program-formats.md). The record grammar
> and checksum there are CONFIRMED; the external DIP *file header* layout
> (magic / system ID / size / block count) has not yet been pinned from
> the parser, so do not build a DIP file encoder until it is.

A stored `.COM`, in contrast, is the ordinary CP/M single-image file
loaded at 0100h; the loader validates it (`COM file too big`,
`Program corrupt`) but has no multi-block structure.

### Advantages of DIP over .COM

1. **Multi-segment + banked placement** — one image can target
   several 32K banks and battery RAM, beating the flat 64K limit.
2. **On-load initialisation** — the deferred banked-call records let
   a DIP bundle setup calls that run after transfer.
3. **Incremental / streamable** — the record stream loads in
   fixed-size chunks, which is exactly what the Commstar link
   RECORD/BLOCK transfer delivers as it arrives.
4. **Better diagnostics** — explicit "too big / too many blocks /
   not built for this system / corrupt" stages vs a one-line ".COM
   too big".

### Disadvantages vs .COM

- **Not standard** — a DIP must be built by a DIPOS-B-aware tool;
  you cannot just drop a stock CP/M .COM and rename it.
- **Overhead** — per-block headers and per-record metadata are heavier
  than a raw .COM, especially over a slow IR link.
- **More loader complexity** — the block-count/size/system/checksum
  checks are extra failure states.

> Note: the exact on-disk DIP **header** layout (where the block count /
> system ID / size live) is still open — the parser is in module A
> (ROM00:73CE → ram:D893), not yet disassembled. The record *grammar*,
> the checksum, and the ROM footer are CONFIRMED; the full spec and the
> open item are in [Program formats: COM and DIP](program-formats.md).
> Until the header is pinned, treat it as a live-session/capture item.

---

## 8. Where this comes from

This guide is based on static analysis of the `micron1.bin` ROM
(banks 0/1) in Ghidra:
- BDOS dispatch table at ROM00:3708 (RAM copy F1EB) — fn 00-24 map to
  CP/M 2.2 handlers.
- Wrapped extension table ROM00:36EE (RAM copy F1D1) — fn F3-FF.
- The device/link layer (drive letters → FE83/FE93 config, IR link,
  session ring) in [the Commstar protocol](../protocol/commstar.md).
- Memory map (battery RAM layout, system variables) in
  [the memory map](../internals/memory-map.md).

All `Bdos*` handlers are named and commented in the Ghidra program.

---

*If a CP/M program uses only the FCB file calls and the standard
console functions, it will run on DIPOS-B essentially unchanged —
the interesting differences (clock, alarm, IR-link, device and
config selection) are all *extra* DIPOS-B extensions that a
CP/M program simply would not have used.*
