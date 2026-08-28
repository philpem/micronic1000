# Micronic 1000 — CP/M implementation comparison

Status: 2026-08-24. Source: Ghidra analysis of `micron1.bin` (ROM00
kernel + ROM01 UI), plus the drive/device and operating-system analysis
in this directory.

## Bottom line

The Micronic 1000 runs a **CP/M 2.2-compatible BDOS**, implemented
in ROM00 (bank 0) and shadowed into battery RAM at `ram:F180`+
(`InstallKernelToRam`, ROM00:02FE). The dispatch table lives at
**ROM00:3708 → ram:F1EB** (byte-identical copy). Function numbers
0-36 (00-24h) follow CP/M 2.2 semantics closely; above that are
proprietary extensions. **There is no conventional BIOS on disk** —
the whole OS is in ROM, and the "disks" are RAM (Workstation MEMORY
= 32K battery RAM, Workstation RAMDISK = 224K banked RAM).

## BDOS entry and dispatch

- Entry: `bdos_entry_call5` (ROM00:0005) → `FUN_ram_f180` (kernel
  RAM image).
- `KernelImage_BdosMain` (ROM00:36A0, RAM image F183) is the
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
| 02 | Console output | 0F36 | **BdosConsoleOutChar** - routes through LinkSelectActiveDevice (fbc5/f97c) => virtual device |
| 03 | Reader input | 1080 | BdosReaderInChar |
| 04 | Punch output | 10D2 | BdosPunchOutChar |
| 05 | List output | 1015 | BdosListOutChar |
| 06 | Direct console I/O | 0FD6 | BdosDirectConsoleIo; fn=0xFF => status/poll (session uses this) |
| 07 | Get IOBYTE | 10FD | BdosGetSetIoByte |
| 08 | Set IOBYTE | 10FD | same handler (read-only stub) |
| 09 | Print string (DE) | 11FB | BdosPrintString |
| 0A | Read console buffer | 117B | BdosReadConsoleBuffer (128-byte) |
| 0B | Get console status | 0FC5 | BdosGetConsoleStatus |
| 0C | Return version | 15C7 | **returns HL=0x23 (2.3)** - deviates from stock 0x22 |
| 0D | Reset disk system | 1893 | RST28 far-call stub |
| 0E | Select disk | 15B3 | BdosSelectDisk; validates <0x10 (16 drives); sets fbc6 |
| 0F | Open file | 0877 | BdosOpenFile |
| 10 | Close file | 089D | BdosCloseFile |
| 11 | Search first | 096C | BdosSearchFirst |
| 12 | Search next | 09A3 | BdosSearchNext |
| 13 | Delete file | 08C0 | BdosDeleteFile |
| 14 | Read sequential | 0B8F | BdosReadSequential |
| 15 | Write sequential | 0B09 | BdosWriteSequential |
| 16 | Make file | 0843 | BdosMakeFile |
| 17 | Rename file | 0910 | BdosRenameFile |
| 18 | Get login vector | 1888 | BdosGetLoginVector (HL=FFFFh) |
| 19 | Get current disk | 15AF | BdosGetCurrentDisk (returns fbc6) |
| 1A | Set DMA address | 0CEC | BdosSetDmaAddress (5-byte stub) |
| 1B | Get allocation vector | 188C | BdosGetAllocationVector (**HL=0 stub**) |
| 1C | Write protect disk | 1893 | RST28 stub (unimplemented) |
| 1D | Get read-only vector | 188C | same HL=0 stub |
| 1E | Set file attributes | 1893 | RST28 stub (unimplemented) |
| 1F | Get DPB address | 1893 | RST-28 path; application ABI unsafe |
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
- `BdosFcbCommonHandle` (09CA), `BdosDirSearchHelper` (0D79):
  directory search / FCB helpers.
- Block I/O through `FUN_ram_f4c6/f543/f510/f523` (kernel RAM image);
  records 128 B, 32 records/block (0x1F check at FCB+0x0C).

## Deviations from stock CP/M 2.2

1. **No disk BIOS** — everything is ROM; file storage is RAM.
   Drives A/B are WORKSTATION MEMORY / WORKSTATION RAMDISK (FE93
   table); C/D+ map to IR/link devices (FE83 wire-ids AB/2B/67/67).
2. **Version number returns 0x23** (CP/M 2.3 style), not stock 0x22.
3. **Several CP/M functions are stubs** returning HL=0 or a no-op:
   get allocation vector (1B/1D), get DPB (1F), write-protect (1C),
   set-attributes (1E), reset-disk (0D), login vector (18), set-DMA
   (1A). Only the FCB/directory/record functions are truly
   implemented, which matches the "RAM disk, no real media" design.
4. **Console I/O is device-routed**: fn01/02/06 go through
   `LinkSelectActiveDevice` (fbc5/f97c) — output can be re-targeted
   to the IR link (Commstar), not just the LCD. fn06 (direct console
   I/O) is the session layer's poll/read primitive.
5. **Up to 16 drives** (select < 0x10) vs stock 8 (A-P vs A-H).
6. **DIPOS extensions**: fn 2D/2E/30/62/68/69 and the wrapped
   F3+ table (see next section) — these are how the Commstar session
   layer calls into BDOS. The session uses fns 06, 0D, 10, 12, 13,
   1A, 22, 2D, F6, F7, FC, FD.

## DIPOS-B extension functions (documented)

### Special dispatch (fn < 0xF3, hard-wired in KernelImage_BdosMain)

| fn | handler | purpose |
|----|---------|---------|
| 2D | ram:F55A | **banked-call wrapper** — switches to bank 0, calls ROM00:2B18 worker, restores bank (the "call across bank" helper) |
| 2E | 0D79 (BdosDirSearchHelper) | directory-search helper: computes dir slot f823/f82c, writes f94e, calls 0DBF + f523 (rename/dir op) |
| 30 | 1893 | RST28 far-call stub |
| 62 | 0742 (BdosExtFn62) | directory/filesystem integrity check (scans 16-byte dir entries @f8b8 via 0746) |
| 68/69 | 115E (BdosExtFn68) | no-op stubs |

### Wrapped table (fn 0xF3-0xFF) — ROM00:36EE → ram:F1D1

The kernel copies a 50-word handler array (source ROM00:36EE, dest
ram:F1D1-F234) at boot — ONE array whose dispatcher-visible base is
F1EB (fn 00h-24h). The 13 words before F1EB (F1D1-F1E9) are the
wrapped view for fn 0xF3-0xFF (byte-verified 2026-08-25). Each word
is the handler for fn 0xF3+n. All handlers identified and annotated
in Ghidra:

| fn | handler (ROM00) | name | purpose |
|----|-----------------|------|---------|
| F3 | 1FDF | BdosF3NoOp | no-op (`RET`) |
| F4 | 1893 | (RST28 stub) | far-call stub |
| F5 | 1877 | BdosF5SetDelay | set delay/period (fbd6, clamped >=0xF) used by event-wait loop |
| F6 | 15A0 | BdosF6ActiveDev | get active console/link device (returns fbc5) |
| F7 | 15A4 | SetActiveConsoleDevice | set active device (fbc5) + kernel notify |
| F8 | 3237 | BdosF8Fe83Read | read 16-byte FE83 IR/link config (wire-ids) out to caller |
| F9 | 15CB | BdosF9DevPair | set device pair {fbc8,fbc7} from 5-entry table @15E0 |
| FA | 3241 | BdosFAFe83Write | write caller's 16 bytes into FE83 link-id config |
| FB | 3248 | BdosFBFe93Write | write caller's 16 bytes into FE93 storage config (MEMORY/RAMDISK) |
| FC | 1150 | BdosSetRtcTime | **set real-time clock** — copy time block to f9a2, RtcSetTime (20AF) |
| FD | 113E | BdosGetRtcTime | **get real-time clock** — RtcReadRegisterFile (20E8) into caller buffer |
| FE | 1122 | BdosFcSetAlarm | set RTC alarm — build index block @fd4d, register work item (2189) |
| FF | 112D | BdosFcAlarmControl | RTC alarm control — program/clear HD146818 alarm via 2131 |

So the DIPOS-B extensions are: **device-management** (F6/F7 get/set
active device, F9 device pair), **config-table access** (F8/FA/FB
read/write the FE83 link-id and FE93 storage configs), **RTC
services** (FC/FD get/set time, FE/FF alarm), **timing** (F5 delay),
plus the F3/F4 no-op/far-call stubs. These are the session/UI-facing
BDOS additions on top of the CP/M-2.2-compatible core.

## Where the annotated code lives

All the `Bdos*` named functions are in ROM00 (handlers at 024D,
0DE9, 0F36, 1080, 10D2, 1015, 0FD6, 10FD, 11FB, 117B, 0FC5, 15C7,
1893, 15B3, 0877, 089D, 096C, 09A3, 08C0, 0B8F, 0B09, 0843, 0910,
1888, 15AF, 0CEC, 188C, 1890, 0C96, 0BF3, 0CF1, 0CB4) plus the
shared helpers (0824, 068D, 06C1, 09CA, 0D79) and extension
handlers (0742, 115E, and the wrapped-table set BdosF3NoOp,
BdosF5SetDelay, BdosF6ActiveDev, BdosF8Fe83Read, BdosF9DevPair,
BdosFAFe83Write, BdosFBFe93Write, BdosSetRtcTime, BdosGetRtcTime,
BdosFcSetAlarm, BdosFcAlarmControl). The dispatch table ROM00:3708
(RAM F1EB) and the wrapped table ROM00:36EE (RAM F1D1) are commented.
