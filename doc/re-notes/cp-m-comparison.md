# Micronic 1000 — CP/M implementation comparison

Status: 2026-09-20 (storage claims corrected; other findings retain their cited evidence). Source: Ghidra analysis of `micron1.bin` (ROM00
kernel + ROM01 UI), plus the drive/device and operating-system analysis
in this directory.

## Compatibility scope

The Micronic 1000 runs a **CP/M-2.2-shaped BDOS with a verified compatible
subset**, implemented
in ROM00 (bank 0) and shadowed into battery RAM at `ram:F180`+
(`Kernel_KernelToRam`, ROM00:02FE). The dispatch table lives at
**ROM00:3708 → ram:F1EB** (byte-identical copy). Function numbers
0-36 (00-24h) include both compatible calls and verified deviations; above
that are proprietary extensions. **There is no conventional BIOS on disk** —
the firmware is supplied in ROM and the local filesystem uses RAM.
Do not infer drive capacities from the 256 KiB SRAM total; see
[drive configuration and limits](../manual/devices-and-storage.md#drives).

## BDOS entry and dispatch

- Entry: `ROM00:0005` is `C3 80 F1` = `JP F180`
  (CONFIRMED, byte-verified); `F180` lies outside
  `ROM00`'s `0000h..7FFFh` bank window, so it
  targets the RAM-resident kernel at `ram:F180`,
  whose existing label is `Bdos_DispatchFn`
  (CONFIRMED). The phantom `ROM00:bdos_entry_impl`
  at `F180` was a wrong-space invention and is
  **REJECTED** — the Ghidra comment now reads
  `JP Bdos_DispatchFn (ram:F180) vectors into the
  DIPOS kernel (battery RAM)`; no new label needed
  (Ghidra saved).
- `Kernel_Image_BdosMain` (ROM00:36A0, RAM image F183) is the
  dispatcher:
  - fn 0-24h: `handler = word[F1EB + fn*2]` (the 3708 table).
  - fn 2Dh → ram:F55A; 2Eh → 0D79; 30h → 1893; 62h → 0742;
    68h/69h → 115E (DIPOS specials).
  - fn 25h-F2h: **no valid handlers** — an unmatched fn here falls
    through the DEC B path and dispatches through a WILD POINTER (its
    handler word is read from the JP-vector run past the table, e.g.
    fn 40h reads F26B = bytes of the F2xx jump stubs). Nothing is
    rejected; never call undefined fns in this range (hazard
    documented in [the operating-system overview](os-diposb.md)).
  - fn >= F3h: the VALID wrapped extension view — DEC B (B=FF)
    wraps index C=F3..FF onto F1D1..F1E9 (the 13 words immediately
    before the F1EB base; full table below).

## Function map (verified from table ROM00:3708)

| fn | CP/M 2.2 name | handler | notes |
|----|---------------|---------|-------|
| 00 | System reset / warm boot | 024D | warm-restart path |
| 01 | Console input | 0DE9 | via session ring @f95e |
| 02 | Console output | 0F36 | **Bdos_ConsoleOutChar** - routes through Link_SelectActiveDevice (fbc5/f97c) => virtual device |
| 03 | Reader input | 1080 | Bdos_ReaderInChar |
| 04 | Punch output | 10D2 | Bdos_PunchOutChar |
| 05 | List output | 1015 | Bdos_ListOutChar |
| 06 | Direct console I/O | 0FD6 | `Bdos_DirectConsoleIo`; `E=FFh` => status/poll (session uses this) |
| 07 | Get IOBYTE | 10FD | Bdos_GetSetIoByte |
| 08 | Set IOBYTE | 10FD | same handler (read-only stub) |
| 09 | Print string (DE) | 11FB | Bdos_PrintString |
| 0A | Read console buffer | 117B | Bdos_ReadConsoleBuffer (128-byte) |
| 0B | Get console status | 0FC5 | Bdos_GetConsoleStatus |
| 0C | Return version | 15C7 | **returns HL=0x23 (2.3)** - deviates from stock 0x22 |
| 0D | Reset disk system | 1893 | unsafe mutable RST-28 path; behavior depends on fn 2Dh target |
| 0E | Select disk | 15B3 | Bdos_SelectDisk; validates <0x10 (16 drives); sets fbc6 |
| 0F | Open file | 0877 | Bdos_OpenFile |
| 10 | Close file | 089D | Bdos_CloseFile |
| 11 | Search first | 096C | Bdos_SearchFirst |
| 12 | Search next | 09A3 | Bdos_SearchNext |
| 13 | Delete file | 08C0 | Bdos_DeleteFile |
| 14 | Read sequential | 0B8F | Bdos_ReadSequential |
| 15 | Write sequential | 0B09 | Bdos_WriteSequential |
| 16 | Make file | 0843 | Bdos_MakeFile |
| 17 | Rename file | 0910 | Bdos_RenameFile |
| 18 | Get login vector | 1888 | Bdos_GetLoginVector (HL=FFFFh) |
| 19 | Get current disk | 15AF | `Bdos_GetCurrentDisk` (returns current drive in `A`; `fbc6`) |
| 1A | Set DMA address | 0CEC | `Bdos_SetDmaAddress` (implemented; stores `DE` as DMA pointer) |
| 1B | Get allocation vector | 188C | `Bdos_GetAllocationVector` (**`HL=0000h` stub**) |
| 1C | Write protect disk | 1893 | `Bdos_SharedErrorStub` via `RST 28h` — unsafe mutable diagnostic (conditional on `Bdos_SelectRst28Mode` `ram:F55A`) |
| 1D | Get read-only vector | 188C | same `HL=0000h` stub |
| 1E | Set file attributes | 1893 | `Bdos_SharedErrorStub` via `RST 28h` — unsafe mutable diagnostic |
| 1F | Get DPB address | 1893 | `Bdos_SharedErrorStub` via `RST 28h` — unsafe mutable diagnostic |
| 20 | Get/set user code | 1890 | returns A=00h (stub) |
| 21 | Read random | 0C50 | handler entry corrected from 0C80 |
| 22 | Write random | 0BF3 | |
| 23 | Compute file size | 0CF1 | writes record count to FCB random-record field |
| 24 | Set random record | 0CB4 | |

## Shared FCB machinery (annotated)

- `BdosFcbPrepareDrive` (0824): FCB drive byte; 0 => default fbc6+1.
- `BdosValidateFcbName` (068D): 11-char name, upper-case, `?` wildcard
  -> f93d.
- `BdosCopyFcb` (06C1): copies 32-byte FCB between buffers.
- `BdosFcbCommonHandle` (`ROM00:09CA`) handles shared FCB paths;
  `Bdos_UpdateDriveDirectoryMetadata` (`ROM00:0D79`) updates drive metadata
  and is not an FCB filename-search helper.
- Block I/O through `FUN_ram_f4c6/f543/f510/f523` (kernel RAM image);
  records 128 B, 32 records/block (0x1F check at FCB+0x0C).

## Deviations from stock CP/M 2.2

1. **No disk BIOS** — everything is ROM; file storage is RAM.
   FE93 distinguishes a zero local ID from nonzero IDs that enter session
   helpers. Menu names do not prove capacities or operational remote drives;
   see [drive configuration](../manual/devices-and-storage.md#drives).
2. **Version number returns 0x23** (CP/M 2.3 style), not stock 0x22.
3. **Several CP/M functions are stubs or unsafe diagnostics:**
    `1Bh`/`1Dh` get allocation/read-only vector return `HL=0000h` stubs;
    `0Dh` reset-disk, `1Ch` write-protect, `1Eh` set-attributes, `1Fh`
    get-DPB, `30h` and `F4h` are unsafe shared `RST 28h` diagnostic paths
    via `Bdos_SharedErrorStub` (`ROM00:1893`) conditional on the mutable
    `Bdos_SelectRst28Mode` (`ram:F55A`); `18h` login vector returns
    `HL=FFFFh`, `20h` returns `A=00h`; `1Ah` set-DMA is implemented
    (stores `DE`). Only the FCB/directory/record functions are fully
    implemented for file storage, which matches the "RAM disk, no real
    media" design.
4. **Console I/O is device-routed**: fn01/02/06 go through
   `Link_SelectActiveDevice` (fbc5/f97c) — output can be re-targeted
   to the IR link (Commstar), not just the LCD. fn06 (direct console
   I/O) is the session layer's poll/read primitive.
5. **Sixteen drive selectors** are accepted (select < 0x10); this does
   not establish sixteen independent or present storage devices.
6. **DIPOS extensions**: fn 2D/2E/30/62/68/69 and the wrapped
   F3+ table (see next section) — these are how the Commstar session
   layer calls into BDOS. The session uses fns 06, 0D, 10, 12, 13,
   1A, 22, 2D, F6, F7, FC, FD.

## DIPOS-B extension functions (documented)

### Special dispatch (fn < 0xF3, hard-wired in Kernel_Image_BdosMain)

| fn | handler | purpose |
|----|---------|---------|
| 2D | `ram:F55A` (`Bdos_SelectRst28Mode`) | **mutable RST28 mode selector** — `E=FFh` installs no-op target `F57B`, `FEh` default diagnostic `F57E`, `FDh` deferred `F59F` (`HL->FDBA`), `FCh` fatal `F5C0`; other `E` leaves target unchanged; `A` preserved; global unsafe state |
| 2E | `ROM00:0D79` (`Bdos_UpdateDriveDirectoryMetadata`) | drive metadata compute/stage/commit; `E=00h` current drive else `FE93` entry; local `00h` → `A=00h`, nonzero loads `A=2Ch` and enters session setup/transfer helpers; successful remote operation is not established |
| 30 | `ROM00:1893` (`Bdos_SharedErrorStub` via `RST 28h`) | shared diagnostic — behaviour conditional on `2Dh` target |
| 62 | `ROM00:0742` (`Bdos_ExtFn62`) | directory/filesystem integrity check (scans 16-byte dir entries @`f8b8` via `0746`) |
| 68/69 | `ROM00:115E` (`Bdos_ExtFn68`) | no-op stubs |

### Wrapped table (fn 0xF3-0xFF) — ROM00:36EE → ram:F1D1

The kernel copies a 50-word handler array (source ROM00:36EE, dest
ram:F1D1-F234) at boot — ONE array whose dispatcher-visible base is
F1EB (fn 00h-24h). The 13 words before F1EB (F1D1-F1E9) are the
wrapped view for fn 0xF3-0xFF (byte-verified 2026-08-25). Each word
is the handler for fn 0xF3+n. All handlers identified and annotated
in Ghidra:

| fn | handler (ROM00) | name | purpose |
|----|-----------------|------|---------|
| F3 | 1FDF | Bdos_F3NoOp | no-op (`RET`) |
| F4 | 1893 | Bdos_SharedErrorStub | caller-A-selected diagnostic path; unsafe |
| F5 | `ROM00:1877` | `Bdos_F5SetDelay` | set delay/period (`fbd6`, values ` <04h` become `0Fh`) used by event-wait loop |
| F6 | `ROM00:15A0` | `Bdos_F6ActiveDev` | get active console/link device (returns `fbc5`) |
| F7 | `ROM00:15A4` | `SetActiveConsoleDevice` | set active device (`fbc5`) + kernel notify |
| F8 | `ROM00:3237` | `Bdos_F8Fe83Read` | read 16-byte `FE83` IR/link config (wire-ids) out to caller |
| F9 | `ROM00:15CB` | `Bdos_F9DevPair` | set device pair `{fbc8,fbc7}` from 5-entry table @`15E0` |
| FA | `ROM00:3241` | `Bdos_FAFe83Write` | write caller's 16 bytes into `FE83` link-id config |
| FB | `ROM00:3248` | `Bdos_FBFe93Write` | write caller's 16 bytes into `FE93` storage config (MEMORY/RAMDISK) |
| FC | `ROM00:1150` | `Bdos_SetRtcTime` | **set real-time clock** — copy [8-byte record](rtc.md#bdos-eight-byte-rtc-record) (`+1..+7`→`09/08/07/04/02/00/06`, `+0` metadata LIKELY `19`) to `f9a2`, `RtcSetTime` (`20AF`); raw binary 24h, no validation |
| FD | `ROM00:113E` | `Bdos_GetRtcTime` | **get real-time clock** — `RTC_ReadRegisterFile` (`20EF`) → [8-byte record](rtc.md#bdos-eight-byte-rtc-record) (`+0` from `g_bRtcRecordMetadata` `13h`, `+1..+7`←`09/08/07/04/02/00/06`); UIP-polled |
| FE | `ROM00:1122` | `Bdos_InternalTimedWait` | **internal timed wait** — `E<<4` interval, low→`(IY+23h)` high→`word[FEFA]`, `FD4D` countdown/`HALT`; `A=00h` completion, nonzero = full queue; resident context required |
| FF | `ROM00:112D` | `Bdos_FfAlarmControl` | RTC alarm control — `DE=0000h` clears `AIE` else [8-byte record](rtc.md#bdos-eight-byte-rtc-record) `+4..+6`→`05/03/01` + `AIE`; `+2/+3` date gate `RTC_AlarmDateMatches`; `UIP` blocks both; preamble `RegA|80h` likely ineffective then `2Ah` |

So the DIPOS-B extensions are: **device-management** (F6/F7 get/set
active device, F9 device pair), **config-table access** (F8/FA/FB
read/write the FE83 link-id and FE93 storage configs), **RTC services**
(FC/FD time and FF alarm), **internal timed wait** (FE), and **timing** (F5),
plus the F3 no-op and F4 unsafe mutable diagnostic path. These extend the
verified CP/M-compatible subset.

## Where the annotated code lives

All the `Bdos*` named functions are in ROM00 (handlers at 024D,
0DE9, 0F36, 1080, 10D2, 1015, 0FD6, 10FD, 11FB, 117B, 0FC5, 15C7,
1893, 15B3, 0877, 089D, 096C, 09A3, 08C0, 0B8F, 0B09, 0843, 0910,
1888, 15AF, 0CEC, 188C, 1890, 0C50, 0BF3, 0CF1, 0CB4) plus the
shared helpers (0824, 068D, 06C1, 09CA, 0D79) and extension
handlers (`ROM00:0742`, `ROM00:115E`, and the wrapped-table set
`Bdos_F3NoOp`, `Bdos_F5SetDelay`, `Bdos_F6ActiveDev`, `Bdos_F8Fe83Read`,
`Bdos_F9DevPair`, `Bdos_FAFe83Write`, `Bdos_FBFe93Write`, `Bdos_SetRtcTime`,
`Bdos_GetRtcTime`, `Bdos_InternalTimedWait`, `Bdos_FfAlarmControl`). The
dispatch table `ROM00:3708`
(RAM F1EB) and the wrapped table ROM00:36EE (RAM F1D1) are commented.

See also: [BDOS reference](../reference/bdos.md),
[Extensions reference](../reference/extensions.md),
[Supported profile](../manual/supported-profile.md).
