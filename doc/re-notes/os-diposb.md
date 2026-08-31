# Operating system: DIPOSB

## Identification

* String `DIPOSB Ver 228` @ ROM00:041E — the OS is **DIPOS** ("DIPOSB"),
  Micronic's proprietary system. **Not** CP/M.
* Machine branded **PARCON 1000** in ROM strings (both banks).
* ROM bank 0: kernel, diagnostics, self-test, fatal-error handler.
  ROM bank 1: "Workstation" application + **Commstar** comms program
  (`in Commstar` / `in Workstation` error-context strings).
* Feature strings: `WORKSTATION MEMORY`, `WORKSTATION RAMDISK`,
  `Load/Run Program`, `Set Debug mode`, `Diagnostics`, `Main Menu`.
* Fatal-error handler offers **"M key for monitor"** (ROM00:2CF2) —
  a built-in machine-code monitor exists.

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
6. **Coroutine/thread machinery in the dispatcher**: SP/IX/IY context
   switch blocks at ram:D837/D850/D858 — no CP/M analogue.
7. **Syscall dispatch is table-driven in RAM**: the caller passes HL
   pointing at a parameter block whose first WORD is the function
   number; handler = word[d6f4 + fn×2], tail-jumped via
   `EX (SP),HL / RET`. The copied block's table holds exactly three
   loader primitives:
    * 0 = D6FA `SyscallMemset` — zero-fill a block (fn=0x0000,
      `{fn, addr, count}`); was mis-named SyscallLoadBlockToMem
    * 1 = D713 `SyscallMoveBlockAlt` — block move, swapped operands
      (fn=0x0001, `{fn, src, dst, count}`)
    * 2 = D727 `SyscallQueueBankedBlock` — append deferred-call records
      `{D7h, bank, addrL, addrH}` to a queue at (d684); each record is
      itself an RST10 banked-call stub ("call address X in bank Y later")
      (fn=0x0002, `{fn, N, addr[N]}`); `fn=FFFF` terminates the stream.
   The general BDOS surface lives at F180 (battery RAM, not in dump).
8. **Idle loop calls BDOS function 0** (`BC=0 ; CALL 5 ; loop` at
   ram:D6AC) — resident scheduler/command loop rather than a CCP that
   exits to BIOS.

## ABI layers (complete picture)

```
User (.COM) programs      : CALL 0005h          -> kernel F180
ROM01/ROM00 app code      : RST 08h/20h/28h/30h -> kernel F5Ex/F5Fx
Inter-bank calls          : RST 10h + embedded DB bank, DW target
Fixed ROM-side API        : JP table at ROM00:0106-0148 (and per-bank)
                            -> kernel routines F2xx-F4xx
Hardware IRQ (IM 1)       : 0038 -> F5F3        NMI: 0066 -> F5F6
```

## BDOS function set (CONFIRMED — from the ROM-resident kernel image)

`InstallKernelToRam` copies the kernel from **ROM00:369D → F180**
(0x50D bytes), so the entire kernel is statically analysable in ROM00.
The image begins with 3 NOPs; the dispatcher proper is at F183
(ROM00:36A0, function `KernelImage_BdosMain`).

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

Note on addressing: handlers below 8000 live in the banked window
and require ROM bank 0 mapped during service — which is exactly what
`BankedCallBankZeroWrapper` (ROM00:3ADD) arranges before work happens.

## Workstation object system (decoded)

UI objects are built from chained descriptor blocks in ROM01
(first at 75EB, `ui_object_descriptor_1`; see also the descriptor
tables section in [Memory and I/O map](../reference/memory-io.md)):

* header: two name-string pointers + word
* 4-word **vtable of kernel-side methods** (e.g. EFEC/F0F8/EF98/EFD8)
* config/type bytes (`01 08 20 01` vs `…00`), prev/next links
* arrays of item-name pointers (menu/submenu titles)

`TemplateBuilder` (ROM01:0271) processes a block:

1. `CoroutineTaskSwitch(0)` — yield to the scheduler first
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

`SessionBdosCall`/`Kernel_DeferStagedCall` (module helpers): for functions
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

`0008 -> F180` (BDOS dispatch) is separate; `RST 20h`/`28h`/`30h`/`38h` →
`F5EA`/`F5ED`/`F5F0`/`F5F3` share the common IRQ/event handler path
(see [interrupts](interrupts.md)). `0010 -> F5E1` is the banked-call
dispatcher; `0066 -> F5F6` is NMI.

## Kernel installation (CONFIRMED)

**The whole kernel is installed from ROM on every cold boot.**
A factory-fresh unit reaches the menu on new batteries because
`InstallKernelToRam` (ROM00:02FE) copies the resident kernel into
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
  1. **Task list**: `CoroutineTaskSwitch` (ram:D837) runs entries
     cooperatively (emulation-confirmed; tasks observed at the
     enqueued targets)
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
* ROM00:3ADD `BankedCallBankZeroWrapper`: reached from both banks'
  RST2 tails; saves current bank, switches to bank 0, calls kernel
  (F54E) then bank-0 worker (2C00), restores bank, re-notifies kernel.

## Runtime program loading — Load/Run loader (CONFIRMED)

* Loader: **ROM01:0A67-10CE** via `ram:D081` (`g_apScreenHandlerTables`) →
  `ram:D0F0` (`g_apLoadRunHandlers`), entered through
  `Ui_FormExitDispatchNext` (ROM01:06D3). Key routines:
  `Program_PrepareLoadGeometry` (`0A67`), `Program_NormalizeLoadRange`
  (`0AE3`), `Program_GenerateBlockChecksums` (`0957`),
  `Program_VerifyBlockChecksums` (`09C2`), `Program_LoadByName` (`0B82`),
  `Program_ConsumeInputChunk` (`0BAC`), `Program_LoadDipOrCom` (`0CE7`),
  `Program_ReportLoadError` (`0CCB`), `Program_FinalizeInput`
  (`ROM01:1002`) — zero completion finalizes state, generates DIP block
  checksums when needed, and sets loader state `3` (nonzero status follows
  `0x2330` error path), `Program_RunByName` (`106F`),
  final transfer `10C6 → ram:D7F0` (`RunLoadedProgram`).
* **DIP vs COM**: magic `0xC8C9` (`C9 C8`) at `+0`, system ID `0`/`0x00E5`,
  14-byte header, max 5 blocks, type `0`=direct copy / `1`=RST 10h
  trampoline expansion, 8-byte serialized prefix in a 10-byte descriptor
  slot with additive checksum at `+8`
  (`0957`/`09C2`, `0x2332` (9010), "Program corrupt." = mismatch). COM fallback when
  first chunk `<14` bytes or first word `!=0xC8C9` → load at `0x0100`,
  run-bank `0`, entry `0x0100`. See [Program file formats](../reference/program-formats.md).
* **No BDOS execute function** — BDOS `open`/`read`/`search` are generic FCB
  services. `ram:D370` is `g_pProgramLoaderContinuation`, a coroutine
  continuation exchanged by `Coroutine_SwapContinuation` (`ram:D9F9`), not
  an input-provider pointer; the upstream physical/session provider remains
  **OPEN** (not identified).
* **Service-33 identities (CONFIRMED):** actual service-33 entry is
  `ROM00:2E02` (`DeviceSelectOpen`, retained name); `ROM00:2E72` is
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
* Transports named in UI strings: PLINTH (IR, back connector),
  V24 ADAPTOR (IR strap, top), EXT STORAGE ADAPTOR, LOCAL LINK,
  modem (auto-answer / dial / manual).
* Menu: `Load/Run Program`. Reception messages: `Receiving prog`,
  `Program received`, `Invalid data stream`.

### Code-loading paths (from strings; static evidence) — legacy strings

## Debug facilities

* **Monitor located**: `MonitorEnter` (ROM00:3513). Reached two ways:
  * fatal-error handler `FatalErrorHandler` (ROM00:2C00, entered from
    the banked-call wrapper after a kernel-notified fault): prompts
    "R key for retry / M key for monitor / Any key for return";
    M (4Dh) or Z (5Ah) saves HL → FEFA and DE:BC → FEF8 then enters
    the monitor with the crashed context
  * cold boot with the service-key combo: reset sets the
    bootmode flag (f81d=FF) when it detects the combo; the banner
    flow then calls 3513 directly (ROM00:0291-0296, when f81d == FF)
    *instead of continuing to the normal card screen / menu*. So
    holding H+L+P at power-on drops straight into the machine-code
    monitor - the same monitor reached via "M key for monitor".
* **Service key combination = H + L + P ("HELP")**, held at power-on.
  Verified end-to-end: reset probes matrix row-drive 02h and expects
  sense pattern 1Ch (columns 2/3/4 of row 1); the runtime translation
  table at ROM00:1B58 maps those three positions to 'H', 'L', 'P'
  (indices col×6+row = 13/19/25 in the unshifted plane). The mnemonic
  independently validates the whole matrix decode chain.
  Additional gate: port 49h must read bit0=1 / bit1=0 at reset
  (checked twice before the matrix probes).
  **Effect:** f81d=FF -> at the banner's key-read point (ROM00:0291)
  the firmware CALLs MonitorEnter (3513) instead of waiting for
  ENTER/keys, i.e. the service combo bypasses normal boot into the
  monitor.
* `Set Debug Mode` menu option in ROM01 (string @ ROM01:7B52).
* Full PARCON-style self-test on cold boot: status flags, bank select,
  ROM checksums (`ROM 0 CS:`), clock test, powerdown test, RAM tests.

## Power on/off (partially decoded)

* **PowerDownSuspend** (ROM00:1721) is the suspend routine, reached
  from the NMI handler — strong evidence the power button is wired
  to NMI:
  * saves SP and 8 bytes of state (fbf3 → fbfb)
  * sets restart flag fbd5 = 2
  * shuts down latches: port 02 reconfigured, port 04 ← FAh/F8h,
    port 2C masked, port 48 bits 0-1 set
  * spins refreshing port 2A / port 07 until the wake NMI
* Wake: NMI with fbd5 == 2 takes the handler's restart path → warm
  boot; session state survives in battery RAM.
* First press during operation therefore suspends; second press
  reboots into the restored session.

## Remaining internal questions

* Which link-id bit-5 state selects PLINTH versus V24 ADAPTOR.
* Physical interrupt source(s) behind IM1 IRQ and NMI.
* Runtime session data structures and Commstar file-transfer payloads.

The RTC and resident BDOS image are no longer open: ports 08h/28h are the
HD146818 interface, and the RAM kernel is copied from ROM at cold boot.

## Interrupt architecture (fully mapped)

- Mode-1 IRQ vector 0038h in BOTH ROMs = `JP F5F3` — dispatch goes
  through battery RAM, so the handler is field-replaceable.
- Battery-RAM vector block: `F5F0 JP 3513` (break/monitor entry),
  `F5F3 JP F64D` (tick/IRQ handler), `F5F6+` inline prologue gating
  on restart flag fbd5.
- ram:F64D = `IrqCommonHandlerImage` ≡ ROM00:3B6A: ffa8 semaphore
  (0 = drop IRQ silently; re-armed to 1 after service), bank switch
  to 0, CALL 230A, restore.
- ram:230A `IrqWorkerPollPort5`: IN(05) snapshot -> f785; walks
  event table fd84 {mask,handler} records (template ROM00:2352:
  01→18F0, 02→2206, 04→31B6, 08→2365, 10→2365, term ≥80h). Status
  lines are POLLED per IRQ, not vectored.

## Clock self-test decoded

ROM00:2828 `ClockSelftestTickWindow` -> result fdb5 ("Clock test"
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
