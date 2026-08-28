# Memory map

## Physical organisation

| Region | Size | Notes |
|--------|------|-------|
| 0000-7FFF | 32K | Bank-switched window |
| 8000-FFFF | 32K | Fixed, battery-backed static RAM (of 256K total) |

Banks of the lower window (CONFIRMED):

| Bank | Contents |
|------|----------|
| 0 | ROM image 0 (`micron1.bin`, Ghidra overlay `ROM00`) — kernel/diagnostics/self-test |
| 1 | ROM image 1 (`micron2.bin`, Ghidra overlay `ROM01`) — "Workstation" UI + Commstar comms app |
| 2+ | 32K pages of the 256K static RAM |

Bank select is **port 47h**, shadowed in RAM at `F791`. Selected by
writing the bank number; on reset bank 0 is active.

**Banked-window capacity (2026-08-25):** the firmware's bank sweeps
(Boot_BankWalkInit, Mem_BankSweepPutByte) walk banks **41h..1 = 64
banks × 32K = 2 MB** of addressable window space (6-bit bank latch,
LIKELY). These sweeps are **NOT RAM sizing** — they replicate page-zero
vectors (JP F238 @0000, JP F180 @0005) and the console/disk selection
cells (FBC5 @+3, FBC6 @+4) into every bank, so RSTs/IRQs and config
reads work no matter which bank is selected; they contain no read-back
and store no result. The actual RAM test is `ram_page_test_4banks`
(ROM00:2530, called from reset_entry @01BB, fail flag FDB0) plus
`contig_ram_map_test` (267A). Installed RAM (256K total) backs only a
fraction of the 2 MB window; the RAM-disk block I/O path is
`BdosReadRecordBlock` → `KernSwapCopySrc` (f49b: bank-select + LDIR
across the window). Ghidra overlay `RAM02` models bank 2 (uninitialised
until a page dump is loaded).

**Why the replication exists (owner-confirmed rationale 2026-08-25):**
code can be running from any bank — a COM program most likely won't be
bank-aware (a DIP program might be) — and Z80 interrupts + RST vectors
must work whichever bank is selected. Hence every bank carries the same
page-zero vectors and device cells.

**BDOS block-I/O staging cells (2026-08-26):** two distinct pairs —
`FF7F`/`FFA5` = read-path header staging (24h-byte copies,
BdosPrepReadFromBuf/BdosDoneReadFromBuf), `FEFF`/`FFA3` = write/sector
prep (BdosPrepWriteBuf/BdosDoneWriteBuf/SwpDirectory). The `F8B8`
directory buffer and the FS geometry cells (f820/f822/f828/f82a/f8af/
f8b0/f8b6) complete the picture; copies run bank-aware through the
FEFE bank operand via the f498 entry.

## Patch / hook surfaces (DIP-extensible RAM cells)

The kernel ships *consumers* in ROM and *contents* in battery RAM:
several RAM tables hold default no-op stubs that a soft-loaded DIP can
overwrite to patch ROM bugs or add functionality. Investigated
2026-08-25 (agent + main-agent byte review). Verdicts:

| Surface | Mechanism | Verdict |
|---|---|---|
| `tbl_FieldOpSlots` ram:ee00-ef37 (66×4B) | direct CALLs from ROM01 UI (`CD 00 EE` @11a4 …), content = `21 01 00 C9` no-op defaults; no ROM writer | CONFIRMED shape; patch purpose LIKELY |
| Stub farm B ram:f100-f17f (32×4B) | direct CALLs from ROM00 (e.g. `CD 38 F1` @41ba); 0/1-word stack args; same defaults | LIKELY |
| Pointer slots + F168 sentinel + `ram:d828` | UI cells (eb00/eb39/ec51/eb08…) hold callback ptrs; F168 = "unset"; guards skip extra work; d828 calls cell via JP (HL) for ≥ED00 targets or self-patching RST 10h stub (d834=target, d833=bank) | CONFIRMED |
| `g_apScreenHandlerTables` ram:D081 → `ram:D0F0` (entry 0) | five per-screen handler-table pointers indexed by active-screen selector at `ROM01:034B`; `Ui_FormExitDispatchNext` (ROM01:06D3) double-dereferences `word@(D081+2*i) → P → word@P` via `d828`; entry 0 = `g_apLoadRunHandlers` at `ram:D0F0` for the `ROM01:0A67-10CE` Load/Run loader | CONFIRMED |
| (was `g_tblFieldTypeRecPtrs` → cells `{D0F0,D13D,D121,D12F,D14B}` — superseded) | — | — | — |
| `fbc2` decode hook | ExtDecodeHookInstall/Discard; documented recipe ([barcode reader](../manual/barcode-reader.md)) | CONFIRMED |

The runtime DIP format provides equivalent patching power without using the
boot `fn` grammar: type-0 blocks copy payloads to a selected bank/address,
and type-1 blocks install `{D7,bank,target}` banked-call trampolines. The
runtime loader then transfers through `RunLoadedProgram` (`ram:d7f0`). The
`ram:d6fa`/`d713`/`d727` record handlers belong only to the ROM boot chain.

## Low memory (per-bank page zero)

Both banks carry an identical vector template except two entries
(byte-compared):

```
0000  JP <bank start>   ROM00: JP 0103    ROM01: JP F238 (kernel RAM)
0005  JP F180           BDOS/syscall gate -> kernel in battery RAM
0008  RST1 -> F5E1      kernel call
0010  RST2              banked-call dispatcher (see below)
0020  RST4 -> F5EA      kernel call
0028  RST5 -> F5ED      kernel call
0030  RST6 -> F5F0      kernel call
0038  RST7 -> F5F3      kernel call; doubles as IRQ entry under IM 1
0040  banked-call tail: OUT (47),0 ; JP <own bank target>
                        ROM00: JP 3BAA     ROM01: JP 3ADD
0066  NMI -> F5F6       kernel NMI handler (RAM)
```

### RST2 banked-call dispatcher (0010)

```
POP HL          ; return address = pointer to 2-byte operand table
LD E,(HL)       ; E = requested bank (first inline operand byte)
LD A,(f791)     ; current bank
CP E            ; E = requested bank from stack operand
JP NZ,d74b      ; wrong bank -> inter-bank path
INC HL / LD A,(HL) / INC HL / LD H,(HL) / LD L,A
JP (HL)         ; same bank: jump to target address stored after the call
```

Call sites embed `DB bank, DW target` after the `RST 10h`.
The mismatch path (d74b, mirrored per bank) re-selects the bank via
port 47h and vectors through the kernel dispatch block.

## ROM01 descriptor tables (7500-79C3)

The top of ROM01 below the string area is a table complex, not code.
Structures confirmed so far:

### Link/device name pointer tables

| Address | Type | Contents |
|---------|------|----------|
| 757F | ushort[5], null-terminated | WORKSTATION MEMORY, WORKSTATION RAMDISK, PLINTH, V24 ADAPTOR, EXT STORAGE ADAPTOR. Index = link/device id |
| 7663 | ushort[2], null-terminated | **PLINTH, V24 ADAPTOR only** — an IR-only filtered view; consumers of this list drive the infrared hardware |

Both lists are embedded in descriptor blocks with back-pointers and
6-byte device records of the form `{01h, id, attr_mask, 01h, ptr}` —
e.g. `01 08 20 01 63 76` at 7671 points at the IR-only list, a sibling
points at 757F.

### Menu structures (Ghidra struct: dipos_menu_item_t)

5-byte records `{marker(01h), hotkey char or 00, text_ptr word,
line_no}`, applied as an array at 772B:

```
{01, 00, 7AC4} Main Menu
{01, '1', 7ACE} Load/Run Program   line 4
{01, '2', 7ADF} Set Clock          line 5
{01, '3', 7AE9} Display Status     line 6
{01, '4', 7AF8} Diagnostics        line 1
```

Similar runs with marker 00h near 776B/77AB point at sub-menu strings
(7B04+). Menu-block headers around them (e.g. `02 04 | word | word`
at 7745) cross-link item lists — layout unconfirmed pending decoding
of the template builder ROM01:0271, which instantiates UI objects as
`builder(dest in EC page, src D0CF/D0DA, template 75EB/760D)`.

### Consumers

* UI init at ROM01:0640 builds menus via kernel service E02B.
* Comms session support lives in **ROM00 bank-0 code** (~43xx-45xx):
  compiled routines that enter via the dispatcher coroutine stub
  (`CALL d837`) and emit status strings ("Plinth not connected" etc.)
  through SessionShowMessage (ROM00:443C).

## Battery-backed RAM layout (8000-FFFF)

Contents below are initialised by cold boot; parts of the kernel are
copied from ROM (see [the operating-system overview](os-diposb.md)). The ROM dumps contain no RAM bytes
— values shown are post-boot state for a healthy machine, seeded by the
`FillBatteryRam` Ghidra script.

| Address | Name | Size | Function |
|---------|------|------|----------|
| D081 | `g_apScreenHandlerTables` / `g_pProgramLoadCeiling` value | — | First byte of resident module B (`ROM01:7BCB → ram:D081`, 0x24A bytes). Kernel startup writes D081 to `g_pProgramLoadCeiling`; this is the exclusive upper bound for COM loading. Thus COM occupies 0100-D080 and is limited to CF81h bytes |
| D681 | `bdos_dispatcher` / kernel dispatch & **boot-loader** block | 212h | Copied from `ROM00:7030` by `ROM00:3BAA`. Implements CALL-5 syscalls and the **boot-load chain** (`ram:D6DB` / `ram:D6F4` `fn=0/1/2/FFFF` + `ram:D7D1` checksum) that installs ROM banks at cold boot. **Not** the runtime COM/DIP loader — the runtime Load/Run loader is separate in `ROM01:0A67-10CE` via `ram:D081 → ram:D0F0` (`Program_LoadDipOrCom`, `Program_Generate/VerifyBlockChecksums`, `ram:D7F0` `RunLoadedProgram`) |
| D79C..D86x | — | — | Dispatcher subroutines: self-modifying trampolines, coroutine-style SP/IX/IY context switch (d837/d850/d858) |
| ED1C-ED480 | kernel data area | 464h | Initialised by d6C0 LDIR chain at dispatcher init |
| EF88 | kernel routine | — | Called once during dispatcher start-up |
| ED1C | deferred_call_queue | 0x364 | Growable list of 4-byte RST10 banked-call stubs {D7h, bank, target}, written by syscall fn=2 (SyscallQueueBankedBlock) via queue_write_cursor (d684). Arena pre-filled with no-op stub "LD HL,1 / RET" (template at d6d7) so executing unfilled slots returns harmlessly. Executed in place as a straight-line program of banked calls; entry point computed dynamically (suspected: chain-loaded module code). |
| F180 | syscall entry | — | Target of the 0005h BDOS gate in both banks |
| F2xx-F4xx | kernel routines | — | Targets of the per-bank API jump tables (ROM00:0106-0148) |
| F5E1/F5EA/F5ED/F5F0/F5F3/F5F6 | kernel stubs | — | RST1/RST4/RST5/RST6/RST7(IRQ)/NMI handlers |

### System variables

| Address | Name | Type | Function | Post-boot value |
|---------|------|------|----------|-----------------|
| F791 | g_bBankShadowP47 | byte | Current bank, mirror of port 47h; indexes RST2 dispatch | 00 |
| F780 | p02_shadow | byte | Shadow of I/O port 02h | runtime |
| F782 | p02_cfg_shadow | byte | Config/shadow for port 02h (written masked 3Fh) | runtime |
| F784 | p04_shadow | byte | Shadow of port 04h (written masked E7h) | FF |
| F786 | p07_shadow | byte | Shadow of port 07h (bit1 = comms control) | runtime |
| F78B | p2a_shadow | byte | Shadow of port 2Ah (bit5 = beep/control) | 20 |
| F78D | p2c_shadow | byte | Shadow of port 2Ch (written masked EFh) | runtime |
| F81A | sys_stack_top | — | Initial system stack pointer | — |
| F81C | g_bWarmbootSig | byte | 55h ⇒ warm restart at 024Dh instead of cold init | 00 |
| F81D | g_bBootmodeFlag | byte | 00 normal boot, FF service/special boot (key combo at reset, sense==1Ch) | 00 |
| FBD0 | g_wSysSavedSp | word | Saved Z80 SP; loaded into SP as first reset action. Copy at FBD2, in-restart flag at FBD5 | runtime |
| FC03/FC04 | — | bytes | IR/comms link state flags (used by lcd_sync_status path) | runtime |
| FC05 | — | byte | Value written to port 46h by WritePowerLatchPort46 (ROM00:1FD4) | 70 |
| FC06 | g_abLcdFramebuffer | 160 bytes | LCD framebuffer, 20 chars × 8 lines, sent by LcdRefreshScreen | spaces/text |
| FD50 | g_abRtcFileBuf | 16 bytes | RTC register-file read buffer filled by RtcReadRegisterFile (ROM00:20F0, ex-"CommsRxBurst16") reading indices 00-0F | — |
| F9AA | g_bExtBusRoute | byte | External-bus route/wire byte (= active wire-id fdca). 0x2A variant uses CTL_2A trigger; default 0x2B uses CTL_2C/2D front-end. Set by ExtBusArm (1221) | 00 |
| F9AB | g_bExtBusStatus | byte | Ext-bus result status: 0=error/absent, 1=2A-route retry, 2=ok. Written 12AF, read by ExtBusComplete (14A3) | 00 |
| F9AC | g_wExtBusRetry | word | Ext-bus arm-window timeout counter (decremented at 1340) | — |
| F9B4 | g_bExtBusEdgeCnt | byte | Edge/pulse count from ExtBusAcquireEdge (13B8); <9 → invalid | — |
| F9B5 | g_abExtBusEdgeWid | 64 | Edge/width timing table; reversed into FBB3 on completion (1415–1443) | — |
| FBB6 | g_bExtBusActive | byte | Ext-bus route active flag (set by ExtBusArm, cleared on disarm) | 00 |
| FBB7 | g_pExtBusResultBuf | word | Caller buffer pointer for the acquired edge/width result | — |
| FBBF | g_bExtBusBeepFlag | byte | Completion beep flag (checked by ExtBusPoll/ExtBusRoute2ARet) | — |
| FBC4 | g_bExtBusLevel | byte | Last sampled EXTBUS_EDGE bit0 level (data/signal) | — |
| FBCB | g_bExtBusStatus2 | byte | Ext-bus present/route latch (written 12B6; also linked to LinkResetSession 30C9) | — |
| FBCE | g_wExtBusWindow | word | Ext-bus arm-window base/counter (ExtBusAdvanceTimer 14B0) | — |
| FD84 | g_abCommsCfgTable | 19 bytes | Comms controller config, copied from ROM00:2352 | copied |
| FDAB/FDAD/FDB3/FDB4 | — | bytes | Link status query results (QueryLinkStatusKernel, ROM00:280F) | runtime |
| FDB0 | g_bRamTestFailFlag | byte | FF = bad page found by ram_page_test_4banks → error beep | 00 |
| FDB5/FDB6/FDB7 | — | bytes | Power-down / self-test result latches (set with port 04h writes) | runtime |
| F954/F956 | g_pLinkRxRingHead/Tail | 4 B | Receive ring pointers (head/tail) for the link console-in ring at F95E; init 0DDB, frame ingest 0E70-0E95, read by BDOS fn01/06. Frame length at F95C | runtime |
| F95E | g_abLinkRxRing | ~12+ B | Ring buffer receiving validated Commstar link frames (bytes from port 4Eh). Consumers: BDOS console-in. | runtime |
| E69F | g_abSessionRxBuf | ~10 B | **Session RX frame buffer** — received link bytes as the session layer reads them (SessionRxByteGet indexes E69F by remaining-count E6A9). Consumed by the session RX loops (59FB) | runtime |
| E6AD/E6B1 | g_bSessionRxByte / g_bSessionRxChar | 1 B | RX byte latch + current char (overflow/next-byte queue in the byte getter) | runtime |
| E69D | g_wSessionRxReady | word | Frame-ready latch for the session "wait for frame" (656D polls it; 666D sets it via fn6). | runtime |
| E6A9 | g_wSessionRxRemaining | word | Remaining bytes of the received frame still unread (decremented by the byte getter). | runtime |
| E5BC/E5BE/E5C0 | g_sessionParamBlock | 4 B | Session connection params (link addr, sizes); copied into the record header state E644..E649 by the session-setup path | runtime |
| E644/E646/E648/E649 | g_sessionRecHeader | 5 B | **Record header state** set per received/transmitted record (E646 = record type/status: 4=abort, 8/9=data/complete). Written/read by the RECORD state machine (5A81) before InlineTableDispatch | runtime |
| FDAF | — | byte | IrSenseDiagEcho result flag | runtime |
| FE83 | g_abDeviceCfgSlots | 16 B | 16 independent one-byte wire ids indexed numerically 1-16 (low branch of DeviceTableIndex 31FF), defaults 80 AB 63 43 \| 80 2B 63 43 \| 80 67 63 43 \| 80 67 63 43 (source ROM00:3267); read through fbc5 selector windows (console entries 1-4, reader-channel 5-8, punch 1-16 direct, list per BdosListOutChar). 0x63/0x43 are wire ids, NOT 'c'/'C', and there is no 4-byte "record" structure | copied |
| FE93 | g_abDeviceCfgMain | 16 B | Letter-indexed (SUB 0x41 branch) device-pair table from ROM00:3257; non-RAM defaults are wire ids 0x73 / 0x72 (not ASCII 's'/'r' records) | copied |
| FEA4 | — | byte | Cleared early in cold start | 00 |
| FEAF | g_bRamBankBitmap | byte | Bitmap of passing RAM pages built by ram_page_test_4banks | FF |

## Cold-start flow (reset with bank 0)

```
0000 -> 0103 -> reset_entry @ 014B
  DI, IM 1, SP <- (FBD0)
  port 2Ah <- 20h ; ~4000-iteration delay
  clear f81d/f791
  IN 49h bit0 clear? -> cold start (step below)
    else bit1 -> alternate boot @17A5
    else scan keyboard (02h/00h) for service key (sense==1Ch),
         set f81d=FF
  restore port 02h from f780
  f81c == 55h ? -> warm restart @024D
COLD:
  SP=f81a; clear fbd5/f81c; IN 05h; OUT 04h=FFh; OUT 2Bh=0
  -> 2530 ram_page_test_4banks (55AA/AA55 + address + inverted fills,
     bitmap -> feaf, fail -> fdb0=FF + beep via 01BE)
  -> beep/self-test: fea4=0, fc05=70h, display "TESTING..."
  -> link diagnostics, contig_ram_map_test (kernel probe FUN_ram_f180)
  -> CopyCfgTablesToRam, QueryLinkStatusKernel, RTC read (08/28)...
  -> kernel copies into battery RAM (e.g. 3BAA), then warm-restart tail:
     restore latch shadows to ports 02h/04h/2Ah/2Ch, full register
     context, IM 1, CALL F54E into restored program in top RAM
```
