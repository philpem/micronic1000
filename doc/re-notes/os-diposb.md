# Operating system: DIPOSB

**On this page:** The DIPOS-B operating system internals — kernel
installation, BDOS dispatch, boot chains, module copying, the Load/Run
loader, interrupt architecture, the diagnostic entry stub, and the patching
interface. Intended for kernel analysts, patch authors, and anyone
tracing the boot chain. Companion: the programmer-facing
[BDOS reference](../reference/bdos.md) and
[Memory and I/O map](../reference/memory-map.md).

* [Identification](#identification)
* [CP/M compatibility layer](#cpm-compatibility-layer)
* [ABI layers](#abi-layers-complete-picture)
* [BDOS function set](#bdos-function-set-confirmed-from-the-rom-resident-kernel-image)
* [Local terminal escape protocol](#local-terminal-escape-protocol)
* [Workstation object system](#workstation-object-system-decoded)
* [Kernel call mechanisms](#kernel-call-mechanisms-two-paths-decoded)
* [Kernel installation](#kernel-installation-confirmed)
* [Boot load scripts](#boot-load-scripts-module-copying-how-to-find-srcdstlen)
* [Runtime program loading](#runtime-program-loading-loadrun-loader-confirmed)
* [Debug facilities](#debug-facilities)
* [Power on/off](#power-onoff-partially-decoded)
* [Interrupt architecture](#interrupt-architecture-fully-mapped)
* [Clock self-test](#clock-self-test-decoded)
* [Patching an OS function](#patching-an-os-function-full-evidence)

## Identification

* String `DIPOSB Ver 228` @ ROM00:041E — the OS is **DIPOS** ("DIPOSB"),
  Micronic's proprietary system. **Not** CP/M.
* Machine branded **PARCON 1000** in ROM strings (both banks).
* ROM bank 0: kernel, diagnostics, self-test, fatal-error handler.
  ROM bank 1: "Workstation" application + **Commstar** comms program
  (`in Commstar` / `in Workstation` error-context strings).
* Feature strings: `WORKSTATION MEMORY`, `WORKSTATION RAMDISK`,
  `Load/Run Program`, `Set Debug mode`, `Diagnostics`, `Main Menu`.
* The fatal-error handler offers **"M key for monitor"** (`ROM00:2CF2`),
  but the selected entry is a returning stub in these dumps, not a
  built-in machine-code monitor. See [Debug facilities](#debug-facilities).

## CP/M compatibility layer

DIPOSB borrows the CP/M transient-program interface. Standard CP/M
references:

* CP/M 2.2 manuals and docs archive — <http://www.cpm.z80.de/manuals/cpm22-cpm.pdf>,
  <http://www.cpm.z80.de/docs.html>
* John Elliott's CP/M pages (BDOS function reference) —
  <https://www.seasip.demon.co.uk/Cpm/bdos.html>
* Wikipedia, *CP/M* § page zero / memory layout —
  <https://en.wikipedia.org/wiki/CP/M>

### What matches CP/M convention (CONFIRMED)

| Convention | DIPOSB evidence |
|------------|-----------------|
| TPA programs enter via `CALL 0005h` | Address 0005 in **both** ROM banks contains `JP F180` → kernel in battery RAM |
| Location 6 = BDOS entry base | Dispatcher installs itself: `LD HL,d681 ; LD (0006),HL` (ram:D7BE) |
| Location 1 area (IOBYTE) read by OS | dispatcher reads `(0001)` and self-patches trampoline (+3Ch) |
| `.COM`-style loaded images | strings: `COM file too big`, `Bad DIP file`, `DIP file too big`, `Program not built for this system`, `Program corrupt` |
| Warm boot / persistent command level | battery-RAM persistence; warm restart preserves full register context |

### What is NOT standard CP/M

1. **No CCP/BIOS split visible at page zero as in CP/M.** Reset vector
   0000 is real reset code; the kernel lives in battery-backed RAM at
   F180+ rather than being reloaded from track 0 at each warm boot.
   Persistence comes from the battery, not disk.
2. **RST vectors are syscalls.** Standard CP/M leaves RST slots to the
   user; DIPOSB uses RST 08h/20h/28h/30h as direct kernel entries and
   RST 10h as an inter-bank call instruction with embedded operands:
   `RST 10h / DB bank / DW target`. Under IM 1 the 0038 slot doubles as
   the hardware IRQ entry.
3. **Bank-switched memory model.** Programs/data load into 32K pages of
   the 0000-7FFF window; load records are tagged with the current bank
   number taken from the port-47h shadow (F791). CP/M 2.2 has no banking.
4. **RAMdisk instead of disk drives.** File storage targets are
   `WORKSTATION MEMORY` and `WORKSTATION RAMDISK`; device names include
   PLINTH, V24 ADAPTOR, EXT STORAGE ADAPTOR, LOCAL LINK, MODEM A/ANS,
   MODEM A/DIAL, MODEM MAN/D (ROM01 descriptor table ~7500-76A0).
5. **Custom file formats beside .COM**: DIP files (block-structured,
   `DIP file has too many blocks`) and Fastcode (`Fastcode:` string).
6. **Coroutine frame-entry helper**: `Coroutine_Enter`
   (`ram:D837`, `CONFIRMED ram:D837-D857`) pops the
   continuation, switches `SP` by `DE`, saves
   `BC`/`IX`/`IY`, calls via `ram:D836` (`JP (HL)`);
   returns `HL` with `Z` iff `HL==0` — no CP/M
   analogue. Companion `Coroutine_SwapContinuation`
   at `ram:D9F9` and context blocks at `ram:D850`/`D858`
   remain.
7. **Syscall dispatch is table-driven in RAM**: the caller passes HL
   pointing at a parameter block whose first WORD is the function
   number; handler = word[d6f4 + fn×2], tail-jumped via
   `EX (SP),HL / RET`. The copied block's table holds exactly three
   loader primitives:
    * 0 = D6FA `Syscall_Memset` — zero-fill a block (fn=0x0000,
      `{fn, addr, count}`); was mis-named SyscallLoadBlockToMem
    * 1 = D713 `Syscall_MoveBlockAlt` — block move, swapped operands
      (fn=0x0001, `{fn, src, dst, count}`)
    * 2 = D727 `Syscall_QueueBankedBlock` — append deferred-call records
      `{D7h, bank, addrL, addrH}` to a queue at (d684); each record is
      itself an RST10 banked-call stub ("call address X in bank Y later")
      (fn=0x0002, `{fn, N, addr[N]}`); `fn=FFFF` terminates the stream.
   The general BDOS surface lives at F180 (battery RAM, not in dump).
8. **Idle loop calls BDOS function 0** (`BC=0 ; CALL 5 ; loop` at
   ram:D6AC) — resident scheduler/command loop rather than a CCP that
   exits to BIOS.

## ABI layers {#abi-layers-complete-picture}

```
User (.COM) programs      : CALL 0005h          -> kernel F180
ROM01/ROM00 app code      : RST 08h/20h/28h/30h -> kernel F5Ex/F5Fx
Inter-bank calls          : RST 10h + embedded DB bank, DW target
Fixed ROM-side API        : JP table at ROM00:0106-0148 (and per-bank)
                            -> kernel routines F2xx-F4xx
Hardware IRQ (IM 1)       : 0038 -> F5F3        NMI: 0066 -> F5F6
```

## BDOS function set (CONFIRMED — from the ROM-resident kernel image)

`Kernel_KernelToRam` copies the kernel from **ROM00:369D → F180**
(0x50D bytes), so the entire kernel is statically analysable in ROM00.
The image begins with 3 NOPs; the dispatcher proper is at F183
(ROM00:36A0, function `Kernel_Image_BdosMain`).

Dispatch: function number in `C`.
* `00h-24h`: handler = `word[F1EB + fn*2]` — table source at `ROM00:3708`
* Special-cased first: `2Dh`→`ram:F55A` (`Bdos_SelectRst28Mode`),
  `2Eh`→`ROM00:0D79` (`Bdos_UpdateDriveDirectoryMetadata`), `30h`→`ROM00:1893`,
  `62h`→`ROM00:0742`, `68h`/`69h`→`ROM00:115E`
* `F3h-FFh`: the VALID wrapped extension table — the dispatcher does
  `CP 0x25 / JR C` (`F1EB` table) / `CP 0xF3 / JR NC` (`DEC B`, `B=FFh`),
  so index `C=F3h..FFh` wraps onto the 13-entry table at `F1D1` (source
  `ROM00:36EE`) — correct by design (see detailed mapping in §Kernel call
  mechanisms)
* `25h-F2h` unmatched: falls through that same `DEC B` path and
  dispatches through a wild pointer (its handler word is read from
  the `JP`-vector run past the table, e.g. fn `40h` → `F26B`). Nothing is
  rejected. HAZARD: calling an undefined BDOS function in `25h-F2h` jumps
  through garbage — do not probe for extensions by calling them.

Call state saved to kernel vars: `fef9`=DE low, `fefc`=function
number, `fefd`=FFh (in-BDOS-call flag).

The table maps 1:1 onto CP/M 2.2 BDOS numbering:

| Fn | CP/M meaning | Handler | Note |
|----|--------------|---------|------|
| 00 | System reset | `ROM00:024D` | warm-restart entry |
| 01/02 | Console in/out | `ROM00:0DE9` / `ROM00:0F36` | `02h` returns `A=00h`/`08h`/`FFh` per mode/routed result |
| 03/04/05 | Reader/Punch/List | `ROM00:1080` / `ROM00:10D2` / `ROM00:1015` | `04h` via `Device_LookupConfigEntry` `ROM00:31FF`, descriptor `80h` local else routed; `A=00h` normal |
| 06 | Direct console I/O | `ROM00:0FD6` | `E=FFh` poll |
| 07/08 | Get/Set IOBYTE | `ROM00:10FD` | shared handler — CP/M fingerprint |
| 09/0A | Print string / Read buffered | `ROM00:11FB` / `ROM00:117B` | `0Ah` `1Bh` counted literal block |
| 0B/0C | Console status / Version | `ROM00:0FC5` / `ROM00:15C7` | `0Ch` `HL=0023h` |
| 0D/0E | Disk reset / Select disk | `ROM00:1893` / `ROM00:15B3` | `0Dh` unsafe shared `RST 28h` diagnostic (conditional on `2Dh`); `0Eh` validates `<10h` |
| 0F-17 | File ops (open…rename) | `ROM00:0877-0910` | real implementations; rename expects second FCB at `DE+10h` |
| 18-20 | Login vector…User code | `ROM00:1888-1890` | `18h` `HL=FFFFh`, `19h` returns `A`, `1Ah` stores `DE` (implemented), `1Bh`/`1Dh` `HL=0000h`, `20h` `A=00h` |
| 21-24 | Random read/write/size/record | `ROM00:0C50` / `ROM00:0BF3` / `ROM00:0CF1` / `ROM00:0CB4` | `21h`/`22h` use `+21h`/`+22h` only, `+23h` not read |

Shared and stubbed handlers confirm the numbering: fn 7=8 share,
fn 1B=1D share (static vector returns), and the disk-oriented stubs
(1C, 1E, 1F) are no-ops — this machine has a RAMdisk, not disks.

## Local terminal escape protocol

`Tty_out_char` (`ROM00:1BEB`) interprets `ESC` followed by a byte from the
computed table at `ROM00:2050`. Its parallel handler-word table starts at
`ROM00:2062`: the dispatcher pre-increments its handler pointer twice, so
the apparent `2060` base is two bytes early.

| Sequence | Confirmed action |
|----------|------------------|
| `ESC X p` | consume one 1-based column parameter (1..20) |
| `ESC Y p` | consume one 1-based row parameter (1..8) |
| `ESC A` | select page 0 and cursor-blink state |
| `ESC B` | select page 1 and character-blink state |
| `ESC U` | direct LCD write: inherited D is temporary attribute, E is byte |
| `ESC I`, `ESC W` | bare no-op return |
| `ESC C` | toggle LCD mode state and reprogram Mode Control |
| `ESC K` | clear the 160-character LCD buffer |
| `ESC R` | enable LCD mode bit 0 and select keyboard page 1 |
| `ESC S` | toggle keyboard page 0/1 |
| `ESC +` | decrement contrast code by two and write `LCD_CONTRAST` |
| `ESC -` | increment contrast code by two and write `LCD_CONTRAST` |
| `ESC H` | call the display-reset helper |
| `ESC V`, `ESC (`, `ESC )` | complete escape parsing with no additional state change |

There are no terminators or decimal strings: only X/Y consume one following
byte. The meanings of the display-reset helper remain open. The table above
records mechanics only; it does not imply an ANSI or VT-family protocol.

Note on addressing: handlers below 8000 live in the banked window
and require ROM bank 0 mapped during service — which is exactly what
`Kernel_CallBankZeroWrapper` (ROM00:3ADD) arranges before work happens.

## Workstation object system (decoded)

UI objects are built from chained descriptor blocks in ROM01
(first at 75EB, `ui_object_descriptor_1`; see also the descriptor
tables section in [Memory and I/O map](../reference/memory-map.md)):

* header: two name-string pointers + word
* 4-word **vtable of kernel-side methods** (e.g. EFEC/F0F8/EF98/EFD8)
* config/type bytes (`01 08 20 01` vs `…00`), prev/next links
* arrays of item-name pointers (menu/submenu titles)

`Form_Builder` (ROM01:0271) processes a block:

1. `Coroutine_Enter(0)` — frame-entry helper
   (`ram:D837`; `DE`=0 frame size; `CONFIRMED
   ram:D837-D857`)
2. `dbee` (=ROM00:759D, inside chain-loaded module A) — text-format
   interpreter: decimal accumulation (×10+digit), space/tab/slash
   dispatch — parses the runtime text associated with the block,
   e.g. the Commstar state-name table at D0CF ("SHUT-DOWN",
   "C-RX-REC", "C-BEGIN-FILE"…) delivered by the bank-0 boot-script
   blob
3. `d828` (=ROM00:71D7) — **location-aware call router**: targets
   ≥ ED00h jump directly into always-resident RAM; lower targets
   route through block-load machinery so the owning module is
   guaranteed present before the call
4. optional post-create hook FUN_ROM01__170A when flags bit6 set

So menus/dialogs = vtables + name-pointer lists + parsed runtime
text: a small object system riding on the cooperative scheduler.

## Kernel call mechanisms (two paths, decoded)

The resident kernel in battery RAM (F180-F68D) is reached three ways,
all now decoded:

### 1. CP/M BDOS gate (`CALL 0005`)

`0005: JP F180` (both banks). `F180-F1CE` is the normal envelope joining
the common continuation at `F382`; `F376` (`Kernel_BankedCallEnvelope`) is the
alternate entry. The dispatcher saves the function to `fefc`, sets
`fefd=FF`, then dispatches:
- fn 00h-24h: handler = `word[F1EB + fn*2]` (CP/M-compatible table; source at
  `ROM00:3708`)
- fn `2Dh`/`2Eh`/`30h`/`62h`/`68h`/`69h`: special-cased to `ram:F55A`
  (`Bdos_SelectRst28Mode`)/`ROM00:0D79`
  (`Bdos_UpdateDriveDirectoryMetadata`)/`ROM00:1893`/`ROM00:0742`/`ROM00:115E`
- fn `>=F3h` (not special): `CP 0xF3 / JR NC` takes the `DEC B` (`B=FFh`)
  path, so the wrapped RAM index `F1EB-0x200 + 2*fn` wraps `C=F3h..FFh`
  onto the 13-entry extension table at `F1D1` (source `ROM00:36EE`; entries
  `F3h` `1FDF`, `F4h` `1893`, `F5h` `1877`, `F6h` `15A0`, `F7h` `15A4`,
  `F8h` `3237`, `F9h` `15CB`, `FAh` `3241`, `FBh` `3248`, `FCh` `1150`,
  `FDh` `113E`, `FEh` `1122`, `FFh` `112D`) — VALID by design.
- fn `25h-F2h` unmatched: falls through that same `DEC B` path and
  dispatches through a wild pointer (handler word read from the `JP`-vector
  run past the table, e.g. fn `40h` → `F26B`). Nothing is rejected.
  HAZARD: calling an undefined BDOS function in `25h-F2h` jumps through
  garbage — do not probe for extensions by calling them.

### 2. Fast kernel jump table (fn 1-18)

`Session_BdosCall`/`Kernel_DeferStagedCall` (module helpers): for functions
1-18 the payload jumps to **`(word@0002) + (fn-1)*3`** — a 3-byte
`JP handler` table in the kernel at the reset-vector page (JP F238
target: table at ram:F238, source ROM00:3755). Decoded entries:

| fn | JP | fn | JP |
|----|----|----|----|
| 01 | F2DE | 0A | F299 |
| 02 | F2F8 | 0B | F29E |
| 03 | F303 | 0C | F319 |
| 04 | F30E | 0D | F2A3 |
| 05 | F280 | 0E | F2A8 |
| 06 | F285 | 0F | F2AD |
| 07 | F28A | 10 | F2B2 |
| 08 | F28F | 11 | F34A |
| 09 | F294 | 12 | F355 |

Each entry stores the function number to `fefc` then `RST 28h` (or
the cold-restart path JP 01A6). So the session/Workstation layer
calls kernel services 1-18 (IO, state, clock...) via this table.

### 3. RST trampolines

**CONFIRMED, byte-verified 2026-09-20:** `0005 -> F180` is the BDOS
gate; `0008 -> F5E1` is a separate restart entry. The `0010` banked-call
dispatcher is inline code, not a jump to `F5E1`. `0066 -> F5F6` is NMI.

The initial kernel image gives `RST 20h -> F5EA -> F64D` and
`RST 38h -> F5F3 -> F64D`, but `RST 28h -> F5ED -> F57E` and
`RST 30h -> F5F0 -> 3513`. These four restarts therefore do not all
share the IRQ handler. RAM vectors can subsequently be patched; these
are the initial targets from `ROM00:3B07-3B12`, not a claim about every
runtime state. See [interrupts](interrupts.md).

## Kernel installation (CONFIRMED)

**The whole kernel is installed from ROM on every cold boot.**
A factory-fresh unit reaches the menu on new batteries because
`Kernel_KernelToRam` (ROM00:02FE) copies the resident kernel into
battery RAM before anything calls it:

* Source ROM00:369D → destination ram:F180, length 0x50D bytes
  (F180-F68C). Byte-by-byte loop — no LDIR.
* Covers: F180 BDOS gate, F2xx-F4xx API targets, F54E resume hook,
  F57E error-handler pointer, F5E1-F5F6 RST/NMI stubs, F64D.
* Called from the reset flow at 023E; first direct kernel call
  (CALL F425) follows at 0244.
* Battery backup therefore only preserves *state* (warm restart,
  RAMdisk contents) across power-off; no factory programming needed.

## Boot load scripts (module copying) — how to find src/dst/len

On **every** boot the firmware materialises the Workstation/session
modules and dispatch state into battery RAM from tables at the tail
of each ROM bank. Nothing in the ROM hard-codes where these modules
live: a **boot-load chain** (a table of loader records) says where.
This is how you find those addresses mechanically.

### Finding the chain

Each ROM bank's chain start is the word at **address `7FFC`** of that
bank (the last word of the 32K window, before the RAM above):

| Bank | `(7FFC)` | chain start |
|------|----------|-------------|
| 0 (`micron1.bin`, overlay ROM00) | `7D58` | ROM00:7D58 |
| 1 (`micron2.bin`, overlay ROM01) | `7E15` | ROM01:7E15 |

*(Verified by reading the raw bytes: ROM00:7FFC = 7D58h, ROM01:7FFC =
7E15h.)*

The dispatcher startup (ram:D681, source ROM00:7030) reads `(7FFC)`
of the active bank and walks its chain; both banks' chains run so both
banks' modules install.

### The record grammar — boot chain only (CONFIRMED)

Records are little-endian words. The first word selects the type;
the handlers are the three loader syscalls in `ram:D681-D7C8`. Each
record handler tail-jumps (`JP d6de`) to run the next record, and a
hidden table terminator (`d6f2 → d6ee`) ends the walk. **This grammar
is the ROM boot-load chain only — it is NOT the runtime DIP file
format** (see [Program file formats](../reference/program-formats.md)).
The runtime Load/Run loader (`ROM01:0A67-10CE` via `ram:D081 → ram:D0F0`)
has its own 14-byte header + 8-byte block grammar with type 0/1 and
8→10-byte checksum expansion.

| fn | Fields | Action |
|----|--------|--------|
| `0000` | `addr`, `count` | `memset(addr, 0, count)` |
| `0001` | `src`, `dst`, `count` | `memcpy(dst ← src, count)` |
| `0002` | `N`, `word[N]` | enqueue `N` far-call stubs `{D7h, bank, target}` at the deferred-call cursor `*(d684)` |
| `FFFF` | — | terminate |

### The verified chains (from `analysis/decode_chains.py`)

**Bank 0 (micron1.bin), chain at 7D58:**

| Off | Record | Effect |
|-----|--------|--------|
| 7D58 | memcpy | `7242 → E0F4` (16 B) — BDOS-call param page |
| 7D60 | memset | `E36F..E3C0` zeroed (82) |
| 7D66 | memcpy | `7301 → E22D` (205) — misc config |
| 7D6E | memset | `E3C1..E704` zeroed (836) |
| 7D74 | memcpy | **`73CE → D893` (2145) — session module A** |
| 7D7C | memcpy | `7C2F → E104` (297) — module A auxiliary block |
| 7D84 | enqueue | 134 × far-call target words |
| 7E94 | `FFFF` | terminate |

**Bank 1 (micron2.bin), chain at 7E15:**

| Off chain | Record | Effect |
|-----------|--------|--------|
| 7E15 | memcpy | `0080 → E2FA` (117) — page-zero copy |
| 7E1D | memset | `E705..EC6C` (1384) |
| 7E23 | memcpy | **`7BCB → D081` (586 B, 0x24A) — module B** |
| 7E2B | memset | `D2CB..D480` (438) |
| 7E31 | enqueue | 147 × target words |
| 7F5B | term | |

Combined coverage: bank-0 writes **D893-E704**, bank-1 writes
**D081-D480**, so D081-D480 and D893-EC6C are contiguous after boot.
(the E0F4/E22D/E104 aux blocks sit within those spans.)

> Character of `src` and `dst`: sources are *ROM addresses within the
> bank whose chain is running* (addresses < 0x8000 — so bank-0 for
> the bank-0 table, bank-1 for the bank-1 table). Destinations are
> battery-RAM addresses >= 0x8000. So "`73CE → D893` (2145)" means
> "copy 2145 bytes from ROM offset 73CE of bank 0 to battery RAM
> D893". To see the loaded code in Ghidra, copy those ROM bytes to
> the RAM address (see `FillBatteryRam.java`), then disassemble.

> These tables are regenerated by `analysis/decode_chains.py` (reads
> each bank's `(7FFC)` pointer, walks the records, prints src/dst/len
> for every copy/memset and the enqueued target words).

### Queue purpose (the fn=2 records)

The fn=2 records build a 1124-byte table at ED1C-F17F of executable
{RST10h, bank, target} far-call stubs — and this table serves
TWO roles:
  1. **Deferred-call queue** (cooperative; tasks observed
     at the enqueued targets) — **not** driven by
     `Coroutine_Enter` (`ram:D837`), which is a frame-entry
     helper (`CONFIRMED ram:D837-D857`), not a scheduler
  2. **Transfer vector table**: Workstation UI object vtables
     (e.g. EFEC/F0F8/EF98/EFD8 in `ui_object_descriptor_1`) point
     DIRECTLY into this arena — calling a vtable slot executes the
     stub = far-call to the real handler wherever it resides. This
     decouples ROM-resident objects from handler location, and is
     why no static reference to ED1C exists anywhere in either ROM.
  The two banks' chains interlock: bank-0 entries first (targets
  incl. 3BAA inside the kernel image), then bank-1 entries
  (Workstation functions), exactly filling the arena.
* Queue consumer mechanism still open: no static reference to the
  arena base (ED1C) or cursor (d684) exists outside fn=2 itself,
  including inside the chain-loaded modules. Module A contains four
  `JP (HL)` trampolines (ram:DA4B/DB68/DB73/E0D8) that are candidate
  dispatch sites. Next tool up: read-watchpoint on ED1C via the
  z80 emulator's mark_addrs/set_read_callback.
* Remaining unwritten by the chains: tail **EC6D-ED1B** and gap
  **D481-D892** (may be pure workspace, or populated later).
* Page-zero installer (ram:F425 ≡ ROM00:3942): stamps every bank's
  page zero with reset vector JP F238 and BDOS gate JP F180, so
  vectors reach the resident kernel from any bank.
* The warm-restart tail ends with `CALL F54E` — resuming whatever sits
  in top RAM, which only works because of the battery backup.
* ROM00:3ADD `Kernel_CallBankZeroWrapper`: reached from both banks'
  RST2 tails; saves current bank, switches to bank 0, calls kernel
  (F54E) then bank-0 worker (2C00), restores bank, re-notifies kernel.

## Runtime program loading — Load/Run loader (CONFIRMED)

* Loader: **ROM01:0A67-10CE** via `ram:D081` (`g_apScreenHandlerTables`) →
  `ram:D0F0` (`g_apLoadRunHandlers`), entered through
  `UI_FormExitDispatchNext` (ROM01:06D3). Key routines:
  `Program_PrepareLoadGeometry` (`0A67`), `Program_NormalizeLoadRange`
  (`0AE3`), `Program_GenerateBlockChecksums` (`0957`),
  `Program_VerifyBlockChecksums` (`09C2`), `Program_LoadByName` (`0B82`),
  `Program_ConsumeInputChunk` (`0BAC`), `Program_LoadDipOrCom` (`0CE7`),
  `Program_ReportLoadError` (`0CCB`), `Program_FinalizeInput`
  (`ROM01:1002`) — zero completion finalizes state, generates DIP block
  checksums when needed, and sets loader state `3` (nonzero status follows
  `0x2330` error path), `Program_RunByName` (`106F`),
  final transfer `10C6 → ram:D7F0` (`Program_LoadedProgram`).
* **DIP vs COM**: magic `0xC8C9` (`C9 C8`) at `+0`, system ID `0`/`0x00E5`,
  14-byte header, max 5 blocks, type `0`=direct copy / `1`=RST 10h
  trampoline expansion, 8-byte serialized prefix in a 10-byte descriptor
  slot with additive checksum at `+8`
  (`0957`/`09C2`, `0x2332` (9010), "Program corrupt." = mismatch). COM fallback when
  first chunk `<14` bytes or first word `!=0xC8C9` → load at `0x0100`,
  run-bank `0`, entry `0x0100`. See [Program file formats](../reference/program-formats.md).
* **No BDOS execute function** — BDOS `open`/`read`/`search` are generic FCB
   services. **Loader coroutine rendezvous (CONFIRMED):** the runtime
   Load/Run loader (`ROM01:0A67`-`ROM01:10CE`) is coroutine-driven — its
   routines enter via `LD DE,0; CALL ROM01:D837` (`Coroutine_Enter`,
   `ram:D837`, `CONFIRMED ram:D837-D857`: `DE`=frame
   size, `HL`=body result with `Z` iff `0`) and yield
   to a peer with `LD HL,D370; CALL ROM01:D9F9`
   (`Coroutine_SwapContinuation`, `ram:D9F9`) (CONFIRMED). `Coroutine_SwapContinuation`
   (`ram:D9F9`-`ram:DA0A`) swaps the current continuation with the 16-bit
   word at the address in `HL`, then returns: `Z` when the peer slot was
   empty (the caller continues), `NZ` when it yielded to the peer
   (`EX SP,HL; LD HL,1; RET`) (CONFIRMED). `ram:D370` is the loader's
   peer/rendezvous slot — a byte search for the address (`70 D3`) finds it
   ONLY inside the loader region at `ROM01:0BA3`, `ROM01:0CEE`,
   `ROM01:0D15`, `ROM01:0DB5`, `ROM01:0E69`, `ROM01:0EE9`, `ROM01:0F6C`;
   no code outside the loader writes or reads `D370`, so the peer is
   resumed by the coroutine scheduler rather than registered by a distinct
   ROM routine (CONFIRMED). **Loader staging cell RESOLVED 2026-09-19
   (CONFIRMED, byte-verified): the `ram:D36A` pointer protocol;
   five targets.** The "staging cell" is the `ram:D36A`
   pointer protocol: the loader sets `D36A` (pointer),
   `D36C` (count), `D368` (dest offset) and `D393`
   (limit), yields via `ram:D370`, and
   `Program_ConsumeInputChunk` (`ROM01:0BAC-0C9A`)
   copies `min(D36C,D393)` bytes FROM `D36A` TO
   `ECD8+D368` and advances `D36A`/`D36E` (e.g.
   `ROM01:0C2B`-`ROM01:0C9A`) (CONFIRMED,
   byte-verified). Five staging targets:
   `ram:ECDC` (14 B, initial DIP/COM header —
   primary; set at `ROM01:0D05`, yield `0xD18`,
   read `0xD2F`); `ram:D39B` (8 B, DIP block
   descriptor prefix — `0xE59`, yield `0xE6C`);
   descriptor[+4] (variable, Type-0 DIP payload —
   yield `0xEEC`); `ram:D372` (4 B, Type-1 DIP
   `RST 10h` expansion — yield `0xF6F`, read
   `0xF94`); `0x0100+D399` (variable, COM body in
   TPA — yield `0xDB8`) (CONFIRMED). Labels
   `g_abLoadStagingHeader` (`ram:ECDC`),
   `g_abDipBlockDescriptor` (`ram:D39B`),
   `g_abType1ExpandBuf` (`ram:D372`),
   `g_pLoadStaging` (`ram:D36A`),
   `g_wLoadStagingCount` (`ram:D36C`),
   `g_wLoadDestOffset` (`ram:D368`), each with a
   one-line repeatable comment; function list
   unchanged, saved. Feeder is the session
   program-data receive (state-44 →
   `Session_ReadStreamChunk` `ROM00:3E6A` →
   `Program_ConsumeInputChunk`) (CONFIRMED);
   **residual sub-question (OPEN, does not affect
   the WHAT):** no ROM00 code reads
   `D36A`/`D36C`/`ECDC`/`D372`/`D39B`; how the
   session peer learns these addresses (presumably
   via the RAM coroutine scheduler `ram:D820`-
   `D85F` feeding the `ROM00:7E00` dispatch table)
   remains untraced.
* **Service-33 identities (CONFIRMED):** actual service-33 entry is
  `ROM00:2E02` (`Device_SelectOpen`, retained name); `ROM00:2E72` is
  `Device_Service33Timeout`, not the entry; `ROM00:2E85` is
  `Device_Service33Complete`, the completion callback registered through
  `ram:FDD2` (`g_pSvc33Callback`). Successful type-4 processing falls
  through at `30BC` into shared completion `30BD`; the callback discards
  the synthetic return address `30DB` and returns to `31C1` in the IRQ path.
  `59D0` is the initial async-launch return before completion.
* **Provider bridge mechanics (CONFIRMED, mechanics-only):**
  `Program_StreamChunkCallbacks` (`ROM01:0741`, was `UiDialogCommitPair`) is
  a 128-byte callback-driven copy using `D2E2` state; `Program_BridgeHandlerTables`
  (`ROM01:07EE`, was `UiDialogDrawBlock`) is a seven-slot handler-table
  bridge into `D0F0` (`g_apLoadRunHandlers`). Do not assert a service-33
  provider link. `Lib_MinS16` (`ROM00:5944`, was `Lib_MaxS16`) is
  mechanics-only. `Session_RxStateMachineThunk` (`ROM00:5A63`) is the thunk
  into `SessionRxStateMachine` (`ROM00:5A81`, plate corrected); the
  zero-payload object there retains length `0` and numeric value `2`, then
  takes `5B07 -> 5A13` to resume internal receive polling — it does not
  return a final numeric result and does not relaunch service 33.
* `ram:ECDA` as maximum available entry-bank offset from selected-storage
  geometry is **LIKELY** only.
* Session states (separate transport layer): `NOT-STARTED / DISCONNECTED /
  CONNECTED / READY-RX-DATA / READY-RX-PROG / READY-TX-* / RECORD-*
  / BLOCK-* …`
* Transports named in UI strings: PLINTH (IR port, back of the unit),
  V24 ADAPTOR (IR port, top of the unit where the strap attaches),
  EXT STORAGE ADAPTOR, LOCAL LINK,
  modem (auto-answer / dial / manual).
* Menu: `Load/Run Program`. Reception messages: `Receiving prog`,
  `Program received`, `Invalid data stream`.

### COM capacity and the fixed-RAM boundary

**CONFIRMED, byte-verified 2026-09-20:** startup at `ROM00:7052`
contains `21 81 D0 22 BD E3` (`LD HL,D081h; LD (E3BDh),HL`), setting
`g_pProgramLoadCeiling` to `D081h`. The bank-1 boot record at
`ROM01:7E23` is `01 00 CB 7B 81 D0 4A 02`: copy `024Ah` bytes from
`ROM01:7BCB` to `ram:D081`, the resident Workstation module B.

The raw-COM path at `ROM01:0D9B-0DAB` computes remaining capacity as
`g_pProgramLoadCeiling - (0100h + firstReadCount)`. The subtraction
helper at `ram:E0A9` begins with `EX DE,HL`, then subtracts; this
operand order matters. `Program_ConsumeInputChunk` (`ROM01:0BAC`)
limits copies to the remaining capacity and reports
`0x232C` (9004), "COM file too big." for further raw-COM input after
completion (`ROM01:0BCA`).

The resulting image capacity is `D081h - 0100h = CF81h` (53,121 bytes).
It comprises `7F00h` bytes in the selected lower RAM bank plus `5081h`
bytes in shared fixed RAM. It does not require a bank larger than 32 KiB.
`D081h` is exclusive; an image ending there occupies through `D080h`.
See the [program-format explanation](../reference/program-formats.md#why-the-ceiling-is-d081h).

### Unbanked RAM placement (CONFIRMED)

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

#### A COM can do the same thing

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
[Barcode reader](../reference/barcode.md).

## Debug facilities

See the dedicated [Monitor / ICE hook](monitor-and-debug.md) page for
the full topology (the `3513` stub, the `RST 30h` → `F5F0` hook, the
error-handler break, and the separate monitor ROM).

**CONFIRMED, byte-verified 2026-09-20:** the function now named
`Debug_MonitorHookStub` (formerly `Monitor_Enter`) at `ROM00:3513` contains only `AF C9` (`XOR A; RET`).
The name and the menu string do not establish a monitor implementation.
The previous claims of a built-in monitor and a service-key boot into
that monitor are withdrawn.

* **Error-screen path:** `Diag_ErrorHandler` (`ROM00:2C00`) prints the
  retry/monitor/return prompts. M (`4Dh`) or Z (`5Ah`) selects
  `ROM00:2C3F-2C55`: restore the stacked registers, save restored HL
  to `ram:FEFA`, pop the saved AF word into HL and save it to
  `ram:FEF8`, then call the stub at `ROM00:3513`. It returns, and the
  handler executes `SCF; CCF; EX AF,AF'; RET`. The saved word is AF,
  not DE:BC; the handler began with `EX AF,AF'`, so it must not be
  described as the original incoming main AF without tracing the caller.
  HL now contains that saved AF word rather than its original value.
* **Cold-boot path:** `ROM00:0291-0296` tests `ram:F81D` against `FFh`
  and conditionally calls the same stub. Execution resumes at
  `ROM00:0299` and continues the boot/banner flow. This call does not
  bypass the menu into a monitor.
* **Service key combination = H + L + P ("HELP")**, held at power-on.
  Verified end-to-end: reset probes matrix row-drive 02h and expects
  sense pattern 1Ch (columns 2/3/4 of row 1); the runtime translation
  table at ROM00:1B58 maps those three positions to 'H', 'L', 'P'
  (indices col×6+row = 13/19/25 in the unshifted plane). The mnemonic
  independently validates the whole matrix decode chain.
  Additional gate: port 49h must read bit0=1 / bit1=0 at reset
  (checked twice before the matrix probes).
  **Effect at this call site:** `ram:F81D=FFh` causes the conditional
  stub call described above; it supplies no interactive monitor.
* `Set Debug Mode` menu option in ROM01 (string @ ROM01:7B52).
* Full PARCON-style self-test on cold boot: status flags, bank select,
  ROM checksums (`ROM 0 CS:`), clock test, powerdown test, RAM tests.

**SUSPECTED historical purpose:** an alternate/patched ROM monitor or an
ICE could intercept the entry and use the saved state, returning to the
caller's continuation when finished. These dumps do not show such an
installation, an external-monitor exit, or an ICE handshake. Establishing
one requires an alternate ROM, debugger documentation, or a hardware trace
showing interception. The concrete behavior in these images is a stub
call followed by normal return, not a transfer to another monitor ROM.

## Power on/off (partially decoded)

* **Power_DownSuspend** (ROM00:1721) is the suspend routine, reached
  from the NMI handler and also from the capture-timer underflow at
  `ExtBus_BusAdvanceTimer` (ROM00:14C3). That underflow is the
  **barcode-capture window timeout**, not an autonomous idle/standby
  timer; an idle-countdown that drives the owner-observed
  LCD/backlight-off has **not** been located in the ROM (2026-09-24).
  **Owner fact (2026-09-24): there is no power key**, so the NMI is
  *not* a power-button line and its physical source is still unknown
  (owner-guide "Sun+MODE enters power-down" is the key-combo route):
  * saves SP to `g_wSysSavedSp` (FBD0) and the 8-byte console context
    `g_abConsoleContext` (FBF3) → `g_abConsoleContextSaved` (FBFB);
    the copy is gated on `g_bConsoleStateSavedFlag` (FC03)
  * sets restart flag `g_eRestartFlag` (FBD5, enum `RestartFlag`) = 2
    (SUSPENDED); 1 = SUSPEND_ENTRY set first so an NMI during setup is
    ignored
  * shuts down latches: `KBD_DRIVE` released then driven `48h` (bit 6
    wake-scan) vs `3Fh`, `04h` (`IRQ_MASK`) ← `FAh/F8h/D8h`, `CTL_LATCH_2C`
    masked to keep only bit 5 (IR port select) so bit 4 (LIKELY LCD
    backlight) drops, `48h` (`STATUS_DRIVE`) bits 0-1 set
  * **busy-spins** refreshing `CTL_LATCH_2A` (bit 5 clear) and
    `CTRL_07` (=3) while polling `STATUS_IN` bit 1 — standby is a spin,
    **not a CPU halt**; low-power means LCD+backlight off. The loop's
    JR at ROM00:17A3 lands on the middle byte of a preceding
    `LD (db00),HL`, executing `IN A,(05h)` as an overlapping
    self-modifying read of `STATUS_IN`.
* Wake: NMI with `g_eRestartFlag` == 2 takes `Kernel_HandlerImage`'s
  restart path (force `KBD_DRIVE` bit 6, JP 1758) → warm boot; session
  state survives in battery RAM.
* First press during operation therefore suspends; second press
  reboots into the restored session. The owner-observed wake on an
  ordinary keypress (not a second power press) is **OPEN** — the wake
  key-generation path is not yet byte-verified.

## Remaining internal questions

* Which link-id bit-5 state selects PLINTH versus V24 ADAPTOR.
* Physical interrupt source(s) behind IM1 IRQ and NMI.
* Runtime session data structures and Commstar file-transfer payloads.

The RTC and resident BDOS image are no longer open: ports 08h/28h are the
HD146818 interface, and the RAM kernel is copied from ROM at cold boot.

## Interrupt architecture {#interrupt-architecture-fully-mapped}

- Mode-1 IRQ vector 0038h in BOTH ROMs = `JP F5F3` — dispatch goes
  through battery RAM, so the handler is field-replaceable.
- Battery-RAM vector block: `F5F0 JP 3513` (break/monitor entry),
  `F5F3 JP F64D` (tick/IRQ handler), `F5F6+` inline prologue gating
  on restart flag fbd5.
- ram:F64D = `Kernel_CommonHandlerImage` ≡ ROM00:3B6A: ffa8 semaphore
  (0 = drop IRQ silently; re-armed to 1 after service), bank switch
  to 0, CALL 230A, restore.
- ram:230A `Kernel_WorkerPollPort5`: IN(05) snapshot -> f785; walks
  event table fd84 {mask,handler} records (template ROM00:2352:
  01→18F0, 02→2206, 04→31B6, 08→2365, 10→2365, term ≥80h). Status
  lines are POLLED per IRQ, not vectored.

## Clock self-test decoded

ROM00:2828 `Clock_SelftestTickWindow` -> result fdb5 ("Clock test"
banner line). Hijacks F5F3 with handler 2877, countdown fda8=130
ticks; each tick pokes peripheral reg C (IN(05)/OUT(08)=0C/IN(28));
on expiry POP-IX-unwinds into evaluation: elapsed busy-loop count
must land in 4502..4C46 => CPU-vs-tick-source ratio check, i.e.
oscillator verification. Configures controller idx 40h/26h first
(FUN_20d9). Port 04h = write-only control/mask reg written at every
power-state transition (reset/suspend/selftest/link-test/shutdown).

## RTC status — RESOLVED

The HD146818 is at ports 08h (register select) / 28h (data) — the
"indexed peripheral" previously mislabelled as comms. See
[the RTC reference](rtc.md) for the register map and the traced Set Clock /
clock-test write/read paths. The 4x latch cluster (4A-4F) is NOT the
RTC. The PLINTH/V24 IR and side-port data paths are the remaining
open question — whether they share the 08/28 bus at higher indices
or live on separate ports.

## Patching an OS function — full evidence

The resident kernel dispatches BDOS calls through a **word table in
unbanked RAM**, which makes it a real hook point rather than a
theoretical one:

```
ram:f18f  06 00         LD   B,0          ; BC = C = function number
ram:f191  79 FE 25      LD A,C; CP 25h
ram:f194  38 2F         JR   C,F1C5       ; fn < 25h  -> CP/M table
ram:f196  FE F3         CP   F3h
ram:f198  30 2A         JR   NC,F1C4      ; fn >= F3h -> extension table
…                                         ; 25h..F2h: special-case chain
ram:f1c4  05            DEC  B            ; B=FFh: biases the index by -200h
ram:f1c5  21 EB F1      LD   HL,F1EB      ; table base
ram:f1c8  09 09         ADD HL,BC; ADD HL,BC
ram:f1ca  7E 23 66 6F   LD A,(HL); INC HL; LD H,(HL); LD L,A
ram:f1ce  C3 82 F3      JP   F382         ; common banked-call envelope
```

CONFIRMED, byte-verified `ram:F18F`-`F1D0`. Cross-checked against the
table's own contents: entry 0 is `024D` (`ROM00:024D` = the system-reset
handler, which is one of the four `LD SP,F81A` sites), and entry 3 is
`1080` — `Bdos_ReaderInChar`, exactly as documented.

There is one table base and two windows onto it, which is why the two
tables sit `0x200` apart:

| Table | Address | Index | Covers |
|---|---|---|---|
| Extension | `ram:F1D1`-`F1EA` | `F1EB + 2×fn − 200h` (via `B = FFh`) | DIPOS-B functions `F3h`-`FFh`, 13 words |
| CP/M range | `ram:F1EB`+ | `F1EB + 2×fn` | BDOS functions from `00h` |

CONFIRMED: for `fn = F3h`, `F1EB + 0x1E6 − 0x200 = F1D1` exactly.

Both are inside the resident kernel image, so:

* **A patch is a 16-bit store**: write your handler's address into
  `F1EB + 2 × fn` for a CP/M-range function, or into
  `F1D1 + 2 × (fn − F3h)` for an extension function. The dispatcher will
  route the call through the same `F382` envelope it uses for a ROM
  handler.
* **Your handler is entered with bank 0 selected.** The envelope saves
  the caller's bank and then switches unconditionally:

  ```
  ram:f382  22 F6 FE      LD   (FEF6),HL   ; handler address
  ram:f385  2A FA FE      LD   HL,(FEFA)   ; restore the caller's argument
  ram:f388  3A 91 F7      LD   A,(F791)
  ram:f38b  32 FE FE      LD   (FEFE),A    ; caller's bank -> FEFE
  ram:f38e  F3            DI
  ram:f38f  F5 3E 00      PUSH AF; LD A,0
  ram:f392  32 91 F7      LD   (F791),A
  ram:f395  D3 47         OUT  (47h),A     ; bank 0, always
  ```

  CONFIRMED, byte-verified `ram:F382`-`F396`. So a handler in the banked
  window must be in **bank 0**, and a handler at `C000`+ works
  unconditionally, which is the reason to put it there.
* **The patch survives a warm boot, and dies on a cold one.**
  `ROM00:02FE` copies the kernel image `ROM00:369D` → `ram:F180` up to end
  address `F68D`, and `F1D1`/`F1EB` are inside that range — but it runs
  **only on a cold start**. `CALL 02FE` has exactly one call site in the
  whole ROM, `ROM00:023E`, which sits inside `ColdStartSelfTestBanner`
  *after* the warm-boot entry point:

  ```text
  ROM00:019E  LD   A,(0F81Ch)
  ROM00:01A1  CP   55h
  ROM00:01A3  JP   Z,024Dh      ; warm -> skips 01A6..024C entirely
  ROM00:0232  LD   A,55h / LD (0F81Ch),A   ; cold start stamps the flag
  ```

  So a `F1EB`/`F1D1` patch persists across a warm boot and a power cycle,
  and is undone only by a cold start — which also RAM-tests all of
  `8000`-`FFFF` and would have destroyed your patch anyway.
* **Special-cased functions bypass the table.** Functions `2Dh`, `2Eh`,
  `30h`, `62h`, `68h` and `69h` are dispatched by an explicit compare
  chain at `ram:F19A`-`F1C2` *before* the table lookup is reached
  (`CP 30h / LD HL,1893 / JR Z`, and so on), so patching their table
  slots has no effect. CONFIRMED.
* **Do not call an unassigned function in `25h`-`F2h`.** Anything in that
  range that is not one of the six special cases falls through to the
  `DEC B` at `ram:F1C4` and is indexed with the `−200h` bias, so
  `fn = 25h` fetches its handler from `ram:F035` — inside the far-call
  stub arena. There is no range check. CONFIRMED (arithmetic over the
  byte-verified dispatch above).

Beyond this table and the barcode socket, **no general hooking API has
been shown to exist.** The far-call stub arena at `ram:ED1C`-`F17F` is
281 repointable four-byte stubs and UI vtables target it directly, so it
is mechanically patchable — but which stub serves which purpose is
established for only a fraction of them, and there is no published index.
Treat repointing an arena stub as reverse engineering, not as an
interface.

See also: [BDOS reference](../reference/bdos.md),
[Extensions reference](../reference/extensions.md),
[Programmer guide](../manual/programmer-guide.md).
