# Task list — Micronic 1000 reverse-engineering

State: continuously updated as work progresses.

## Done (verified vs docs + Ghidra + byte-level traces)

1. Map syscall table at ram:d6f4 (3 loader primitives + hidden terminator)
2. Kernel installers -> InstallKernelToRam (ROM00:02FE),
   CopyKernelDispatchBlock (ROM00:3BAA)
3. ROM00 gap analysis; ROM01 gap pass 1
4. Boot load scripts CLOSED (decode_chains.py; grammar fn=0/1/2/FFFF)
5. Deferred-call queue / transfer-vector table SOLVED
   (queue ED1C-F17F doubles as task list AND UI vtable targets)
6. Template builder / object system decoded (ROM01:0271)
7. Warm restart path decoded
8. Monitor located (MonitorEnter ROM00:3513)
9. Keyboard matrix fully decoded (H+L+P = HELP service key;
   drive(02)=col bit, sense(00)=row bit, index=row*6+col)
10. Interrupt architecture fully decoded (IM1 -> 0038 -> F5F3 -> F64D ->
    polled fd84 event table; NMI -> 0066 -> F5F6)
11. Clock self-test decoded (ClockSelftestTickWindow ROM00:2828)
12. Session/Commstar reference data located (ROM00:6A50-6E90)
13. **RTC RESOLVED: 08h/28h indexed pair IS the HD146818** (address
    latch / data). Register map proven from firmware sequences:
    regs 00,02,04,06,07,08,09 = time file; 0A/0B = status/ctrl;
    0C = interrupt flags. See internals/rtc.md. The 4x
    latch cluster (4A/4B/4D/4F) is NOT the RTC (owner-confirmed).
14. **ROM documentation-coverage baseline** (doc/research/gap-analysis.md):
    of 480 functions, only 88 (18 %) carry meaningful names; 392 are
    still auto `FUN_*` (ROM00 237, ROM01 91, RAM modules ~40). The
    named set is the boot/RTC/link/LCD/clock/diagnostic subsystems.
    In-progress tracked there.
15. **CP/M implementation comparison** (doc/internals/cp-m-comparison.md):
    BDOS dispatch table ROM00:3708→ram:F1EB; fns 00-24h = CP/M 2.2
    semantics, with DIPOS extensions & stubs. Annotated ~30 `Bdos*`
    functions (dispatch handlers + FCB machine 0824/068D/06C1/09CA/
    0D79) and the extension stubs (0742/115E). Deviations documented:
    no disk BIOS (RAM storage), version=0x23, stub'd allocation/DPB/
    write-protect fns, device-routed console I/O, 16 drives.
16. **DIPOS-B extension fns IDENTIFIED + DOCUMENTED**: special fns
    2D(banked-call wrapper F55A)/2E(dir-search 0D79)/30(1893)/
    62(dir-integrity 0742)/68-69(no-op 115E), and the 13-word wrapped
    table ROM00:36EE→ram:F1D1 (fn F3-FF): F3 no-op, F4 RST28, F5 delay,
    F6 get-device, F7 SetActiveConsoleDevice, F8/F9/FA/FB FE83/FE93
    config read/write + device-pair, FC/FD set/get RTC time,
    FE/FF RTC alarm. All renamed+plate-commented in Ghidra.
17. **DIPOSB programmer's guide** (doc/manual/programmer-guide.md):
     self-contained doc to read alongside a CP/M 2.2 guide. Covers the
     BDOS call interface, RAM file system (A/B drives, 16-drive select,
     stubbed alloc/DPB fns), device-routed console I/O, the F3-FF
     extension fns (device/config/RTC/alarm/delay), banked calls (RST2),
     and a practical differences/avoid table.
18. **Runtime DIP/COM Load/Run loader — file format CLOSED (2026-08-28)**:
     `ROM01:0A67-10CE` via `ram:D081` (`g_apScreenHandlerTables`, was
     `g_tblFieldTypeRecPtrs`) → `ram:D0F0` (`g_apLoadRunHandlers`),
     `Ui_FormExitDispatchNext` (ROM01:06D3) double-dereference. Ghidra
     names: `Program_PrepareLoadGeometry` 0A67, `Program_LoadByName` 0B82,
     `Program_ConsumeInputChunk` 0BAC, `Program_LoadDipOrCom` 0CE7,
     `Program_RunByName` 106F, `Program_GenerateBlockChecksums` 0957,
     `Program_VerifyBlockChecksums` 09C2, `Program_NormalizeLoadRange`
     0AE3, `Program_ReportLoadError` 0CCB, `RunLoadedProgram` ram:D7F0
     (final transfer at 10C6). **No BDOS execute function** — BDOS
     open/read/search are generic FCB services; source bytes via
     coroutine/provider around `0C12`/`0CE7`/`ram:D370`, exact physical
     source-reader remains open — do not claim identified. DIP is
     **distinct from boot record dispatcher `ram:D6DB`** (`fn=0/1/2/FFFF`
     grammar is boot-only, not DIP). DIP grammar (LE, CONFIRMED): 14-byte
     header `{magic 0xC8C9 (C9 C8), system ID 0/0x00E5, entry-bank, image
     size clamped 0x8000, run-bank, entry addr, blockCount max 5}` then
     blocks `{u16 type, u16 dest bank off, u16 dest addr, u16 payload
     count}+payload`; type 0 direct copy, type 1 = 4-byte `{bank off,
     addr}` → `{0xD7, resolved bank, addr LE}` RST10 trampolines; only
     types 0/1 accepted (other type → default/next logic only if
     applicable, phrased explicitly). 8→10-byte
     `DIP_LoadedBlockDescriptor` expansion — `0957` writes additive
     checksum at `+8`, `09C2` recomputes, mismatch `0x2332` (9010),
     "Program corrupt." = **loaded memory changed** (not file checksum). COM
     fallback if first chunk `<14` or first word `!=0xC8C9` → copy to
     `0x0100`, run-bank `0`, entry `0x0100`. Errors: `0x232B` (9003),
     "Bad DIP file." = short/truncated 8-byte header or payload (not bad
     magic); `0x2331` (9009), "Program not built for this system." = ID
     mismatch; `0x2334` (9012), "DIP file has too many blocks." = count>5;
     `0x232A` (9002), "DIP file too big." = dest+payload over boundary;
     `0x232C` (9004), "COM file too big." = raw COM over capacity.
     `ram:ECDA` max entry-bank offset is **LIKELY** only. `ram:D681` is
     the kernel dispatch/boot-loader block, **not** the runtime loader
     (ROM01 separate). Supersedes old header-open / funnel-into-D6DB
     / `g_tblFieldTypeRecPtrs` device-mapping claims.
     Docs updated: program-formats.md (rewritten), programmer-guide.md
     §7b, forms-ui.md, memory-map.md, os-diposb.md, user-guide.md.

## In progress

- **Session modules loaded into Ghidra** (MCP inline script; also in
  FillBatteryRam.java). Module A (D893-E0F3), Module B (D081-D2CA),
  A2 (E104-E233), params (E0F4), misc (E22D), page-zero (E2FA),
  disassembled.
  * `ram:da13` = BDOS-call wrapper (CALL 0005, fn from E0FE)
  * `ram:e0b2` = command dispatcher (walks inline {cmd->handler})
  * `ram:d86e` = stack-param->E0FE copy then jump
  * `e06a/e085` = 16-bit comparison helpers
  * session RX loop `FUN_ROM00_59fb`, TX loop `FUN_ROM00_5f58`
- **Full emulator boot to a live link I/O** (updated 2026-08-28):
  * The 16C9 HALT-wait is the **keyboard event wait**, not just the
    tick: kernel EI/LD A,1/LD (FFA8),A/HALT at 16C3-16C9, wake checks
    fbc9&fbca; measured fbca=07 → caller 1105 = keyboard read waiting
    for fbc9 bit2. tick => fd4f/fbca recompute, but exit needs an
    event bit that no emulated source ever posts.
  * **Timebase fixed:** `boot_hw.py` uses 3400-tick slices and derives RTC
    phase from the measured `SLICE_TICKS - ticks_to_stop` execution budget.
    It calls `rtc.push_tick()` for each elapsed RTC period, then offers INT
    only when `FFA8 != 0`; thus breakpoints/watchpoints cannot make the RTC
    run faster than the emulated CPU.
  * **Events verified:** when PC parks in 16C9-16D2 with `FFA8=1`, the harness
    writes one queued byte through the FBF0 keyboard ring and sets FBC9 bit2.
    The serial-driven boot enters the Main Menu. Matrix injection via ports
    00/02 is not viable because firmware does not scan them during this wait.
  * Remaining: model a live link peer and capture a complete send/receive
    transaction; the current I/O stubs still cannot establish that exchange.

## In progress

- **Decode Commstar session/frame layer** — DONE only for the ROM-visible
  transport and partial validated envelope: LinkTransferService (2F86),
  LinkTransportCall (2F1A), RX dispatcher (2FBD),
  LinkValidateFrameHeader (30DC), frame builders (3106/3130), session
  bootstrap (0F40-10FB), and the 4Ah-4Fh byte-latch path. Numeric types,
  reply words, and inline-dispatch cases are confirmed observations, not a
  command-name or payload grammar. Remaining: trace RECORD/BLOCK/C-COMMAND
  payload construction and consumption, resolve the complete reply envelope
  and session transitions, and capture a complete software/live exchange.

## Next (priority order)

### No-hardware priorities

1. **Characterise the Commstar builder preflight at `5C1F`/`5D05`.** Every
   current Load/Run builder trace forces its return to success; establish the
   condition a real peer would have to satisfy, if any.
2. **Cycle-account link timeout loops and retry scheduling.** Convert the
   `02DA`/`026C`/`06F9` polls to bounded CPU time and establish the units of
   `fdd6`/`fdd8`; do not infer connector deadlines without this.
3. **Determine whether the fresh program-receive arm is externally visible.**
   Current synthetic Load/Run waits for RAM/PC state (`FDDC=FE0E` etc.); find a
   controller/wire event that replaces it, or record that real peers retry.
4. **Bisect the state-44 payload maximum at 127 bytes.** A 126-byte synthetic
   payload succeeds and 128 bytes reaches `0x1FAE` (8110), "Line failure";
   establish whether 127 succeeds and preserve the result as a regression.
5. **Continue static session-module and UI analysis.** Resolve RECORD/BLOCK/
   C-COMMAND payload construction and consumption, the `e701/e6ff` RCV1/RCV2
   fields, and remaining runtime result/state writers in the loaded modules.
6. **Run a complete software-only Commstar session.** Extend the existing
   byte-level `LinkPeer` duplex regression through the real session state
   machine under bounded emulation. This may establish software framing and
   sequencing, but not connector-level electrical meanings.
7. **Resolve the runtime loader input-provider path.** Trace the coroutine/
   provider behind `ram:D370` and its callers around `ROM01:0C12/0CE7`; the
   COM/DIP file grammar and host-side validator are already complete.
8. **Finish guarded structural repairs before semantic naming.** Repair the
   `ROM01:6E77-6EEE` inline-data body with the required function-list diff
   guard, then address the pending compiler-runtime page and unresolved
   `d2dc/d2de` / `EA14/EA1C` writers.
9. **Final annotation and typing sweep (deferred).** Name/plate remaining
   `FUN_*` functions, repair data/table types, and refresh the canonical
   `research/gap-analysis.md` inventory only after semantic work stabilises.

### Hardware-dependent priorities

1. **Capture a physical IR byte exchange.** Establish modulation, bitrate,
   byte framing, timing, and whether the controller-queue sync/trailer bytes
   exist at the connector boundary.
2. **Capture RECORD/BLOCK payload bytes live** (hardware bus capture on
   4Dh/4Eh, or full UI/Commstar emulation to a live transfer) — the
   one remaining runtime item for the file-transfer tool.
3. **Capture the electrical timing and meanings of the link status/control
   bits.** The ROM branch mapping and 4Ah strobe ordering are now CONFIRMED;
   a hardware trace is still required to map 4Bh/4Ah bits to electrical
   functions and to measure connector-facing timing.
4. **Resolve physical port selection.** Hardware-test which wire-id bit5 value
   selects the top V24 ADAPTOR versus back PLINTH port, and confirm where the
   EXT STORAGE ADAPTER attaches. ROM evidence proves only the shared 4x byte
   transport and the bit5 selector.
5. **Acquire a representative banked-RAM dump** for `RAM02` so runtime-only
   modules/state can be compared with the static overlays.

### Detailed and historical backlog

The items below retain evidence and completion history. They are not the
current priority order; the concise lists above are authoritative.
5. **Examine the queued work-item system** — **DONE (2026-08-25,
   delegated analysis, applied + saved).** The FD5C queue is a 10-slot
   countdown-timer/callback table serviced from the RTC wake path, not
   an IRQ dispatcher: RTC_WakeReasonFetch (2206) → Comms_WorkItemSweep
   (224C) → Comms_WorkItemDispatch (2275); register/cancel =
   CommsWorkItemRegister (2189, CY=full) / CommsWorkItemCancel (21BA;
   listing shows 3 INC IX but bytes are 4 — stride is 4, do not
   "fix"). ExtBusQueueWorkItem (135C, re-arming poll timer f9ae → 5
   ticks) / ExtBusPoll (12EC; no-edge path has an OPEN weird DI
   fallthrough at 1328). RtcAlarmRegWorkItem → RTC_AlarmSleep (21EC,
    pure-timer + HALT-poll on FD4D, caller Bdos_InternalTimedWait 1129).
   FUN_ROM00__35c9 → Sound_Off (2Bh write; quiet-bus before 2Dh
   timing, LIKELY). Plus created RTC_AlarmDateMatches (223E, formerly
  `Link_StatusCompare_FD4B`) and
   Update remaining OPEN bits: meaning of fd84/RegB runtime bits;
   fbc9 bit0 → fn03 staging link; whether the alarm handler also
   writes FD4D directly.
   Also named from the repair batch + loaded-symbol recovery: the ROM01
   UI survivors (see item 6) and Ui_PostDescriptor (6633, posts
   descriptor's first byte as command id into ram:e0b2).
6. **Define the orphaned ROM01 code gaps as functions** — **DONE
   (2026-08-25, all three ranges, diff-guarded).** 03C3-0740: bogus
   0465/052f/05dc removed, 06d3 discovered. 1D79-2115: two
   no-return-continuation guards (inline cmd tables after `CALL
   ram:e0b2` SessionCommandDispatch at 1F96/6B40/6E64) cleared via a
   listing script before the repair; discovered 1E0A, 1FB5 (+thunks
   1E9E/1ECB), 2047; one named loss (UiOpenSaveDialog 1ADD) restored
   with a recovery plate; noise "SessionCommandDispatch" function
   auto-created at 1F96 deleted. 67CA-6F28: bogus 67ca removed;
   discovered 6B53, 6B9B, 6CB2, 6E77; ram losses da4c/dc69 restored.
   NEXT: name the survivors (research/gap-analysis.md lists them).
7. **ROM01 / UI survey for `fbc5` and `fbc2` writers** (review §6.3) and
   **`fbc7/fbc8` consumers** (§6.4, BDOS fn F9 presets) — likely a
   "device" settings screen in ROM01. **CLOSED 2026-08-24 (§6.2)**: the
   reader-completion event bit is `fbc9` bit0, posted by
   `ExtBusComplete`(14A3)→`LinkResetSession`(30BD); that wakes the
   fn-03 `EventWaitForLink` HALT (see manual/barcode-reader.md).
8. **Residual inverted-dispatcher doc claims — CLOSED 2026-08-28.** Active
   documentation now uses the corrected model: fn <25h -> F1EB; F3h-FFh ->
   F1D1 wrap via DEC B; unmatched 25h-F2h -> wild pointer, nothing rejected.
8a. **6e77 guarded repair needed**: its function body contains inline
    data (FF FF FF FF at 6EA5-6EA8, 7F at 6ED1) misdisassembled as
    RST 38h / LD A,A — run the diff-guarded clear-flow repair on
    6E77-6EEE before attempting a name (plate marked PROVISIONAL).
8b. **ram:pending compiler-runtime page**: e020-e0aa helpers
    (AND16/NOT16/OR16/XOR16/cmp at e04b/e05a, neg at e0a0, e0e7/e0e8,
    memmove at ram:d9a0) and thunks — label + plate them from the
    2026-08-25 analysis notes; then da13 semantics (constructor vs
    stream-read) decides the 6A36/6AA9 interpretation.
8c. **Static writers of d2dc/d2de (06d3 globals)** and of the EA14/
    EA1C chunk-state blocks — not in defined code post-repair;
    re-check after the thunk-sweep and get_callers pass.
9. **Stale manual/barcode-reader.md leftovers** — **DONE (verified 2026-08-27):**
   manual/barcode-reader.md H1 and the "What a symbology decoder does" section
   no longer carry the stale "(was ...)" / "(if this is a light-pen)"
   wording. NOTE: protocol/commstar.md §400 still titles the external-device
   bus "(was "barcode/light-pen")" and §434 asserts "no barcode strings" —
   that predates the owner adjudication and needs a separate review pass.
10. **Name `FUN_ROM00__35c9`** (the quiet-bus helper in the capture
     path, review §2.3) during the work-item-queue analysis (item 5).
11. **Decode the error-screen format** — **DONE (2026-08-27, see
     protocol/commstar.md "Error / status screen format").** Owner observed
     "Error 8000 (238/001) Plinth not connected". CONFIRMED: 8000 = major
     error qualifier (literal 0x1F40, or 0x1F41=8001 for the 0x0009 case),
     NOT the e488 code (6); the "(238/001)" pair = RCV1/RCV2 session
     status fields from e701/e6ff (3-digit zero-padded), template at
     ROM00:7310 (tbl_sess_status_fmt) with field names RCV1/RCV2/SEND/
      LOAD/PROG/TIME/ENDC. Open: runtime meaning of RCV1/RCV2 (SUSPECTED
      receive counters; writer trace agent looped - still open) +
      FileSearchNextCb renamed FormatDecU16 (2026-08-27, below).

### 12. FINAL PASS — complete annotation + naming cleanup (defer until the
    reverse-engineering is done; owner-decision 2026-08-27)

    One coordinated sweep at the end, not piecemeal ad-hoc patches. Scope
    (baseline 2026-08-27: 935 functions, 131 still `FUN_*`, 27 dispatch
    tables):

    1. **Name + plate every `FUN_*`** (131 today, mostly the new
       InlineTableDispatch handlers) — proper Module_VerbNoun name + plate
       per §8 (brief purpose / mechanics / In-Out-Clobbers / evidence tag).
    2. **Rename wrong or grandfathered names** — the concatenated legacy
       names (LinkBlockTx, BdosReaderInChar, ...) to `Module_Name` style,
       plus outright-wrong names (e.g. the former FileSearchNextCb ->
       FormatDecU16 pattern). Do as one repo-wide pass, then grep doc/ to
       sync every mention (rename hygiene §7).
    3. **Plate-quality pass** — every named function gets a real plate;
       fix the SHORT-form ones that don't actually fit one sentence, fix
       plates that contradict their own names, re-flow to ~70 cols.
    4. **Comment-style pass** — migrate raw-address cites to labels,
       decode remaining magic numbers/masks in place, drop comments that
       restate the opcode (§8 anti-patterns).
    5. **Data-typing backlog** — apply the still-open proposals: ROM00 7d80
       + 7e50 fn-ptr tables, 7c50/7c30 font metrics, ROM01 7545-7fff
       config-descriptor table, ram:e105 font copy, ram:d0e0 error-string
       table, and the 27 dispatch tables' `tbl_` labels + index->handler
       plate comments.
    6. **Refresh research/gap-analysis.md** (the single coverage tracker) after the
       sweep; do not keep competing %-named claims elsewhere.

    Sequencing: one Ghidra-writing agent at a time, `save_program` between,
    and diff-guard the function list each batch (§11). Hold until the
    remaining open items (field-cycle key, "No program in memory"
    qualifier, emulator navigation) are resolved, so we annotate the
    final picture rather than a moving target.

## Owner corrections to honor

- 4x ports (4A/4B/4C/4D/4F cluster) are NOT the RTC (twice-confirmed)
- No serial EEPROM; serial number is user-entered at banner after
  battery removal, stored at FEAB
- Hardware only has 08/28 as an obvious address+data latch pair.

## Do not regress

- 08/28 device is the RTC: keep Rtc* names (RtcRegWrite/RtcRegRead/
  RtcInit/RtcWriteTime/RtcSetTimeFromBuffer/RtcReadRegisterFile).
- 4x cluster is the external data link: keep Link* names
  (LinkBlockTx/LinkBlockRx/LinkTransferService/Link*). No RTC or
  "comms" naming there.
- RST vector 0010 = Rst2Dispatch (banked dispatch), 0020/0038 =
  Rst4IrqPoll/Rst7IrqPoll, 0028 = Rst5FatalScreen, 0030 = Rst6ZeroRet.
  ROM01 0008/0020/0028 = BankedRst08/BankedRst20/BankedRst28.
  Cold start 01BE = ColdStartSelfTestBanner; 2FBD = LinkRxDispatcher.
- RAM 32-bit session math opcodes keep Session* names (SessionAdd32/
  SessionNeg32/SessionTestCarry/...); empty dispatch slots keep
  SessionOpStub_<addr>.
- External-device bus naming (2026-08-24): port 2Dh = `EXTBUS_EDGE`;
  the 120F-14EE handlers stay `ExtBus*` (ExtBusArm/ExtBusAcquireEdge/
  ExtBusComplete/...). The user **decode-hook socket** keeps neutral
  labels: `fbc0` = RST10 stub, `fbc1` = bank byte, `fbc2` = hook ptr;
  `ExtDecodeHookInstall` (156E) / `ExtDecodeHookDiscard` (1567)
  default it. **SUPERSEDED by owner adjudication (2026-08-24, AGENTS.md
  §3): the side port was used with a barcode pen; the 2D edge-capture
  subsystem IS the barcode reader front end, and `Barcode_` is the
  module prefix for NEW names there.** Existing `ExtBus*` names are
  grandfathered until a deliberate rename pass; do NOT flip back to
  `Reader*`, and do NOT reassign the disproven "EXT STORAGE ADAPTER"
  identity. `BdosReaderInChar` (1080) is genuinely the CP/M fn-03 RDR
  path either way.
18. **Annotation coverage tracker**: **593/593 (100%) named** (Pass A
    complete as of this session). All ROM00 + ROM01 + RAM kernel stubs
    carry meaningful names. Highlights of the closing batch:
    RST vectors ROM00 0010/0020/0028/0030/0038 = Rst2Dispatch/
    Rst4IrqPoll/Rst5FatalScreen/Rst6ZeroRet/Rst7IrqPoll; ROM01 banked
    thunks BankedRst08/20/28; cold start ROM00:01BE =
    ColdStartSelfTestBanner; link RX ROM00:2FBD = LinkRxDispatcher;
    ROM01 field/dialog layer = FieldSelectWalk/FieldConfigLoad/
    SessionFieldEditLoop/StrToNumberParse/NumberAccumulate/
    StrTableLookup/TextOut*; RAM dispatch slots SessionOpStub_*.
    The only auto created `FUN_ram_8c0c` was a false positive over a
    zero buffer (spurious CALL from a jump-table byte) — deleted.
19. **DIP program format documented** (manual/programmer-guide.md §7b +
    internals/os-diposb.md): DIP = block-structured loader-record stream, same
    grammar as the boot chain (fn 0 copy / 1 move / 2 queue-banked-call
    / FFFF term, bank-tagged); COM = plain single image. Advantages
    (multi-bank, init calls, streamable, diagnostics) vs. .COM; exact
    DIP on-disk header left as live-capture item. Loader primitives
    (D6FA/D713/D727/D7F0/D800) annotated to Pass A+B incl. record-walk
    inline comments + KernelDispatchEntry plate.
20. **Pass A COMPLETE (100%)**: all 593 functions named. Pass B
    (inline comments) started: io:00xx ports labelled + repeatable
    comments; RTC/LCD/link hardware EOL+pre comments use datasheet
    names (Reg B PIE/SET/24h, Reg A DV/RS, LINK_CTRL/LINK_STATUS bits).
    **Comment style rules (audited + enforced)**:
      * Short single-fact notes stay EOL.
      * Multi-clause/register-list/para explanations go in **Pre**
        comments, width-wrapped (~70 cols), one bit/field per line.
      * All long EOL comments converted to Pre (82 -> 0): HELP-key
        decode (018E), reset vector block 0000-0044, cold/warm restart
        entries, RTC Reg A/B bit-breakdowns, delay/monitor/TTY routing,
        link frame-validate/command-lookup/slot/descriptor functions.
    Further Pass B coverage this session (Pre comments, datasheet
    names): BDOS entry dispatcher (36A0 + specials 2D/2E/30/62/68/69),
    console device I/O (0DE9/0E00/0F37/1166/1170), CP/M line editor
    (117B), tty_out_char control dispatch (1BEB), select-disk (15B3),
    DMA set (0CEC), RTC get-time (113E), alarm work-item queue
    (2189/21BA), date-rollover (222E/223B), drive valid (0824).

## Session log

- 2026-08-24 (AGENTS.md maintenance): reconciled the rules file with
  owner adjudication + repo facts. IR-port positions settled by owner:
  **V24 ADAPTOR = top, PLINTH = back** (corrected micronic_notes.md,
  internals/os-diposb.md, AGENTS.md §3 — an earlier "bottom/front" reading was
  discarded); tagged bit5 port-select as byte-verified (LinkBlockTx
  3278 `AND 0x20` → LinkPortSelect 3454); made `Barcode_` the declared
  module prefix for the port-2D capture front end everywhere (§3/§7/
  §13, port 2Dh row); corrected tool prefix to `ghidra-mcp_*`; added
  micronic_notes.md + annotate-subagent pointers. SUPERSEDED the old
  "do not rename back to barcode" do-not-regress entry (above)
  accordingly.
- 2026-08-24 (annotation batch 1 — delegated; verified by spot-check):
  plates set for ExtDecodeHookDiscard (1567), ExtBusComplete (14A3),
  KeyboardReadChar (18C0, +3 EOLs on fbc9 bits/0xCD hotkey),
  LinkPortSelect (3454); 2 PRE + 5 EOL inline comments in
  ExtBusAcquireEdge (13B8, SP-repurposing, retries, timeout, overflow,
  noise filter, <9 reject, hook dispatch); plate comments on fbc0/fbc1/
  fbc2; io:2d repeatable replaced (EXT STORAGE claim removed → barcode
  front end); stale "ReaderArmRoute/"ReaderEdgeDecode" plate first
  lines of 1221/13B8 fixed. All byte-verified at write time; program
  saved.
- 2026-08-24 (annotation batch 2 — delegated; verified by spot-check):
  KernelImage_BdosMain (36A0) plate: inverted dispatcher description
  replaced with the corrected model + HAZARD (verified CP 25/JR C,
  CP F3/JR NC, DEC B, F1EB/2*BC, fn 40h→F06B, F3→F1D1); LinkBlockTx
  (3277) plate tail copy-paste artifact ("Micronic 4x link
  transceiver datasheet") removed; RtcRegWrite (22DB) indirect OUT
  (C),B @22DD got EOL "C=8: RTC_ADDR port". FUN_ram_8c0c (false
  positive over a zero buffer) deleted again — watch for re-creation
  after any run_analysis (research/gap-analysis.md records it). Program saved.
- 2026-08-24 (docs batch — delegated; site rebuilt): internals/os-diposb.md +
  manual/programmer-guide.md dispatcher claims corrected (+HAZARD);
  internals/memory-map.md FE83/FE93 rows fixed (16 one-byte wire ids; letter
  indexing is FE93's); RST2 listings got the missing `LD E,(HL)` in
  internals/memory-map.md + internals/interrupts.md (stray "0186C" fixed); barcode-reader
  fbb7 typo + header re-stated with the owner adjudication.
- 2026-08-24 (emulator research — delegated): stall at 16C9 is the
  keyboard-event wait (fbca=07, caller 1105); INT injection coarse and
  push_tick() never called; Fix A (timebase) + Fix B (fbc9|=4 + FBF0
  ring ENTER, VERIFIED to leave the wait) — details above in the
  emulator in-progress entry; scratch /tmp/opencode/boot_diag.py,
  boot_timeline.py, fixB_regen.py.
- 2026-08-24 (coverage audit #2): 668 functions, 610 (91 %) named, 58
  FUN_* remaining (ROM00 1, ROM01 14, ram 43) — doc/research/gap-analysis.md
  refreshed and is the single canonical tracker.
- 2026-08-24 (tooling): opencode.json now points the annotate + docs
  subagents at the cheap model opencode/x-preview-f-free — takes
  effect after an opencode restart; this session they ran on the
  primary model via the `general` agent (the old `opencode/deepseek-
  v4-pro` alias in the loaded config no longer resolves).
- 2026-08-24 (CRASH / recovery notes): system has 1.9 GiB RAM. The
  emulator research agent applied Fix A+B to analysis/boot_hw.py
  (SLICE=3400, unconditional timebase accrual + rtc.push_tick(),
  --drive-kbd opt-in cheat, MAX_SLICES + stall-exit) — but an
  unbounded `log` list with gc disabled ballooned a long run and the
  tmux scope hosting opencode was OOM-killed at 23:47 (1.5 G peak).
  Hardening applied afterwards: log capped at 200 k entries, manual
  gc.collect() each 4096 slices, --max-slices argv. Emulator runs:
  always `timeout 300`, never in parallel, only when memory is free.
- 2026-08-25 (guarded repair, ROUND 2 — DONE): Ghidra was restarted
  (close crashed; no save) so the program landed on the clean
  pre-repair disk state. The clear-flow repair of ROM01 03C3-0740 was
  re-run under a strict diff guard (baseline list vs post-repair list
  via list_functions_enhanced dumps). Beyond-seed damage again
  deleted 14 functions (incl. NAMED UiDialogOpen3F 0907,
  UiDialogShowMenu 0A42, SessionHelperRouter6621 6621, TextScreenInit
  6F61, plus ram session stubs EF08/EF0C/EF1C/EF20 and FUN_1803/659F/
  DFE4). All 14 re-created from surviving symbols and the 8 improved
  ones got honest recovery plates ("original plate lost... recovered
  from surviving symbol"). Net: bogus FUN_0465/052f/05dc DELETED,
  real FUN_ROM01__06d3 added (table-walk over the ram:D081 pointer
  table — Module B head; still needs a name + analysis). SAVED.
  Lesson: never run clear-flow repairs without a before/after
  function-table diff; save promptly — deferred auto-analysis
  pollutes otherwise. Remaining ranges (1D79-2115, 67CA-6F28) to be
  done the same guarded way.
- 2026-08-25 (guarded repairs ROUND 3 — DONE): ranges 1D79-2115 and
  67CA-6F28 completed with the same diff guard. Discovery on the way:
  the repair refuses to delete a DEFINED continuation after a
  `noreturn` call — three such sites here are inline `cmd->handler`
  tables after `CALL 0xe0b2` (SessionCommandDispatch, ram, noreturn,
  CONFIRMED pattern: TASKS "walks inline {cmd->handler}"). Cleared
  the continuation bytes with an inline GhidraScript
  (clearListing at ROM01::1f99-1fb4 / 6b43 / 6e67) before re-running.
  Losses restored via the guard: UiOpenSaveDialog (1ADD, + recovery
  plate), FUN_ram_da4c, FUN_ram_dc69; an auto-noise function named
  "SessionCommandDispatch" at ROM01::1f96 (a 3-byte CALL boxing)
  deleted. Intended deletions: bogus stubs 67ca (+ the earlier trio).
  Program saved.
- 2026-08-25 (delegated follow-up + ram sweep — 2 agents read-only;
  main agent applied + saved):
  * Follow-ups resolved: ROM01::0038 = BankedRst38 (JP F5F3, mirror of
    Rst7IrqPoll; renamed). d2dc/d2de writers = Ui_FormExitDispatchNext's
    own prologue (ROM01::06b9/06cd) - cell comments updated. RegB =
    0x46 at init -> PIE=1 AIE=0 CONFIRMED (RtcInit 2084; EnablePeriodicIrq
    OR 0x40; ClearAlarmInterrupt AND 0xDF; no RegA writes) - RTC_WakeReasonFetch
    plate upgraded. fbc9 full bit map CONFIRMED (bit0 session event @30C0,
    bit1 date-changed @2235, bit2 kbd @18E0/1968, bit3 date-wait-ack @170B
    via deferred callback; bits 4-7 unused) - manual/barcode-reader.md updated.
    Descriptor records 7715/7751 NOT yet repeatable-commentable (field
    layout inconsistent) - trace Ui_PostDescriptor instead.
  * ram sweep applied: runtime page Session_Not16 (was misnamed
    kernel_ui_service), Session_Or16/Xor16/Lnot16/UnsignedGe16/Sub16
    (bodies re-created), Session_UnsignedGt16 (WAS SessionUnsignedLe16,
    wrong polarity, 34 xrefs - verified at ram:d8f6); FCB family
    Session_FcbParseFilename/FcbCharTrans/IsDigitCy; Util_StrLen/
    StrCopy/ArgAddrSp5/ArgAddrSp5b; Session_CharTranslate,
    Session_StoreWordPair, Session_ShrFieldE3b4, Session_Cmp4Xor80 +
    CmpBranchGlue; mul family Mulu16Core/Mulu16/Mulu16Swap/MulS16/
    MulS16v2; shift family Shl16/ShrU16/Sra16; Session_EnvThunkD7d1
    (d7d1 = SUSPECTED checksum; test via ROM01::0a22 args).
  * Coverage: 680 fns / 653 named (96.0 %), 27 FUN_* left.
  * Still open (next sweep): e085 SessionSignedLe16 polarity vs
    Session_UnsignedGt16 (double-check one call site); e06a SessionGe16
    signedness; FUN_ram_df81 (abs helper); e0b2 multi-dim indexer;
    f46d; ee00-eef8 + f1a3-f8ef coroutine/record helpers; d88b terminal
    handler (decides 6a36/6aa9); 6e77 guarded repair.
- 2026-08-25 (tail wave — 2 agents read-only; main applied + saved):
  * Comparator page corrected AT CALL SITES (the Le/Ge swaps trace to
    the 1-byte EX DE,HL wrappers falling into the next routine):
    e06a SessionGe16 -> Session_SignedLe16; e085 SessionSignedLe16 ->
    Session_SignedGt16 (29 xrefs); e0d9 -> Session_UnsignedLe16,
    e0da -> Session_UnsignedGe16; e06b -> Session_SignedGe16.
    Session_AbsHlDe (df81), Session_Const1_eee4/eef8.
  * Kernel envelope family: Kernel_DeferStagedCall (d86e, was
    SessionBdosPrep), Kernel_RunStagedCall (d893, was SessionIdReturn;
    target = *(0001)+off = ram:F238 base), Kernel_BankedCallEnvelope
    (f376, epilogue f3c4 open), Kernel_DispatchCommand (f1a3, F1EB
    table B-1), Kernel_CallBank6_0E00 (f303), Syscall_InvokeServiceFB
    (f28f, RST 28h service FB/15h SUSPECTED), Boot_BankWalkInit (f425,
    installs JP F238 at 0000 in every bank; f483 helper OPEN),
    Mem_BankSweepPutByte (f46d, 64-bank write, no F791 shadow).
    DELETED data artifacts FUN_ram_f1ef/f206 (F1EB table words).
  * ROM01 record API: Ui_FindRecordByKey (6909), Ui_RecordBindAndExec
    (6a36), Ui_RecordMatchAndPost (6aa9; e986/e992 = last-match cache;
    error ids 0x1773/0x17D4/0x17D5), Ui_IdToRecOffset32 (0ad3),
    Ui_StateInit (1803), Ui_TableScanMatch (6027), Ui_DescChainInit
    (659f). Descriptor tables 7715/7751: repeatable comments now carry
    the CONFIRMED cross-links ('1'-'4'/'P'/'<' keys); full field map
    still open (handlers 6319/635e/645d/6464/6588 un-walked).
  * RtcSetAlarm (2141) verified: RegA=0x2A + RegB |= 0x20 (AIE) &
    0x7F (clear SET) - the FD4F bit5 wake path is LIVE when armed.
    LinkStatusWatcher (2468) corrected: polls RTC regs 07/08 (alarm
    sec/min) -> FD9B/FD9C, NOT Reg C.
  * Docs: internals/cp-m-comparison.md 25h-F2h wild-pointer claim fixed (item 8
    CLOSED); SessionBdosPrep renames propagated (internals/os-diposb.md,
    protocol/commstar.md).
  * Coverage: 686 fns / 672 named (98.0 %), 14 FUN_* left (9 ROM01
    incl. the five Ui_PostDescriptor case handlers + 6e77; 5 ram
    ee00-eedc/f8ef with empty listings - GUI pass needed).
- 2026-08-25 (descriptor-op wave — 2 agents read-only; main applied):
  * Five Ui_PostDescriptor case handlers named + plated:
    Ui_DescShowFieldChain (6319, key 03), Ui_DescFieldEditMenu (635e,
    3-byte-stride choice array at D+0Bh), Ui_DescOpNoop (645d),
    Ui_DescRecordScanLoop (6464, 4-byte-stride scan list at D+0Dh,
    deliberate SP-discard no-return continuation at 653b - PRE'd),
    Ui_DescChainNext (6588). Plus Ui_FieldEmptyCheck (62e5),
    Ui_FieldEditGetChoice (1d80), Ui_SvcCall2_07 (7279, DA13(2,7)
    fallback; identity SUSPECTED). Descriptor field map consolidated
    and written onto the 7715/7751 repeatables (key addresses
    corrected: '1'@7731...'4'@7740, 5-byte records @772F).
  * Kernel: Kernel_BankedCallReturn (f3c4, epilogue + deferred-chain
    fdb8/fdba cursor LIKELY); KernBankFnRet (f483) plated (bank-store
    helper); f54e plate CORRECTS the grandfathered name: it is the
    conditional-EI tail (FFA8 = irq-deferred flag LIKELY), NOT a bank
    restore. Syscall_InvokeServiceFB plate corrected: FEFC = syscall
    number global (not param-block ptr); RST 28h chain = 0028→F5ED→
    F57E (bank-0 trampoline) → CALL ram:2b55 (FB dispatch inside 2b55
    still OPEN - next decode). tbl_KernelJumps data label at f238
    (24 JP slots, no static xrefs).
  * f8ef deleted (zero padding; 5 phantom conditional-call xrefs from
    ROM01::7580-7670 removed; region bookmarked to define as data).
    ee00/ee14/ee2c/eedc = field-slot stub table cells renamed
    SessionOpStub_*; g_fieldSlotStubTable label + LIKELY plate.
  * NEW OPEN ITEMS: ram:2b55 FB-service dispatch decode; RAM backing
    gap (ram page-zero + 2d82 have no bytes in the program - bookmark
    set; needed for the FDBD hook and the RST-vector typing); ROM01::
    6431-6432 suspected NOP/ADD-HL,SP misdecode (EOL'd, candidate for
    guarded repair with 6e77); ROM01::7580-7670 data structure to
    define.
  * Coverage: 686 fns / 685 named (99.9 %). ONE FUN_* left:
    FUN_ROM01__6e77 (guarded repair then name).
- 2026-08-25 (6e77 repair + RST-family + error-screen verdict; agents
  + main applied, saved):
  * 6e77 REPAIRED (guarded: baseline diff, no noreturn flags on the 6
    callees, four inline coroutine-step data blocks pre-cleared and
    labelled tbl_corstep_* @6e81/6ea5/6eb4/6ed1) and NAMED
    Session_EvalRecordSteps: two symmetric halves evaluate ops and
    store results into the EA24 record; abort path zeroes +1/+3.
    100% of intended functions now named.
  * 2B55 VERDICT (strings decoded): error screen, not a service
    dispatcher. 7-code table {FE FD FC FB EA E9 E0} -> "*** FATAL
    ERROR *** Consult Dealer" + infinite keywait (FB lands HERE ->
    unsupported code is fatal); 4x4 table: EE/EC/EB -> "Peripheral
    Failure", FA -> "Link inhibited - battery low" + retry dialog
    (SCF on R/-). Plate updated.
  * RST trampoline family labelled in ram: BankedRst10Stub(F5E1),
    BankedRst20Stub(F5EA), BankedRst28Stub(F5ED), BankedRst30Stub
    (F5F0), BankedRst38Stub(F5F3), BankedCallCommonEntry(F64D),
    Kernel_NmiVectorStub(F5F6, function). AGENTS.md §5 corrected:
    0008 -> JP F180 (BDOS), not F5Ex (byte-verified).
  * FDBD/FDBE/FEA4 = kernel error-report state (SUSPECTED): FDBD bits
    1/2 gate the error-report display options; FDBE = failing fn#;
    FEA4 = "error screen active" latch read by MonitorGetChar. Open:
    hardware test with controlled D/E via RST 28h.
  * RAM02 overlay: Ghidra 12.2's public API cannot create overlay
    spaces (no addOverlay*/createOverlaySpace on AddressFactory or
    Memory - reflection-verified); create it via GUI: Memory Map
    window -> "+" (Add To Program) -> "Add Overlay Address Space"
    over 'ram', name RAM02, then Add Block covering 0x0000-0x7FFF.
    Owner-confirmed: banked zone can contain RAM (banks 2+ = 32K
    pages); load a hardware RAM dump of a bank there to visualise.
  * New auto-created noise: FUN_ram_ed51, FUN_ROM00__4e66 (AAM) -
    next sweep's tail.
- 2026-08-25 (service layer closed + RAM02; main agent, saved):
  * tbl_KernelJumps (F238) fully decoded - 24 slots, repeatable now
    carries the full map. STAGED-CALL SERVICES RESOLVED: off 2 =
    Kernel_CallBank6_0E00 (the service-2 entry of ServiceCall_Id2Byte
    6f29 -> bank-6:0E00 call), off 7 = Syscall_InvokeServiceFB (the
    service-7 entry of Ui_SvcCall2_07). d893 plate updated.
  * ROM00::2bee decoded + named Diag_FatalScreenDeferred: stores A
    (bank) -> FDB9, sets FDB8=FF (the deferred-chain marker
    Kernel_BankedCallReturn tests), joins the fatal screen inline.
    Its wrapper ram:f59f = BdosBankedCall3. ram:f5c0 =
    BdosBankedCall4 -> FatalErrorHandler (2C00). ROM00::2d83 =
    KernelErrorReport (FDBE!=0 -> FEA4=FF; fn prefix via 2C67;
    reg dump 2DD1; "Any key for entry" 2D17; bit2 gate @2DBA).
    The fdb8/fdb9/fdba deferred-chain cells now have a CONFIRMED
    writer - the diag screen scheduling path.
  * FUN_ROM00__4e66 + FUN_ram_ed51 deleted (1-byte AAM artifacts).
    ZERO FUN_* remain - every function in the DB is named.
  * RAM02 overlay verified (owner-created in GUI): block 0000-7FFF
    present, comment set. NOTE: MCP read_memory cannot read the
    uninitialised overlay block; load a hardware RAM dump in the GUI.
  * Agent providers were down this round (general spawn failed twice)
    - the above was done by the main agent directly.
- 2026-08-25 (RAM-page references round; owner: RAM02 uninitialised is
  CORRECT - no dump exists unless the emulator creates one; goal = set
  up references for the RAM-disk code and other RAM-page selectors):
  * RAM02::0000 plate written (bank-2 page; selectors + dump recipe).
  * Kernel-image sources named: Boot_BankWalkInitImage (ROM00::3942)
    and Mem_BankSweepPutByteImage (ROM00::398a) - the ROM00 templates
    of the RAM-resident sweepers; both sweep banks 41h..1 = every RAM
    page. KernSetBankNotify (ram:f41b, slot 20 of tbl_KernelJumps)
    = the generic arbitrary-bank selector (A >= 2 = RAM page). EOLs at
    the sweep sites cite the RAM02 overlay.
  * boot_hw.py gained --dump-bank N (writes analysis/ram_bank_NN.bin;
    RAM banks dump the emulated page, ROM banks echo the ROMs) - the
    emulator can now PRODUCE the RAM02 dump for Ghidra. Run when
    memory allows: `timeout 300 venv/bin/python3 boot_hw.py --drive-kbd
    --max-slices 300000 --dump-bank 2`.
  * Still open: RAM-disk driver itself (the Disk*/Fs code that maps
    drive A:/B: blocks to RAM banks) - not yet located; candidates:
    KernSwapCopySrc (f4a8) + the ROM00 3960/3983/398f region.
- 2026-08-25 (owner theory tested + refuted as stated; part survives):
  * THEORY: the RAM-resident sweepers size the RAM for a RAM disk,
    upper bound (41h-1) x 32K = 2 MB. RESULT: refuted - the sweeps
    contain NO read-back and store NO result, and their call sites
    prove the purpose: Mem_BankSweepPutByte is called by
    SetActiveConsoleDevice (15AB/15BE) with HL=3/HL=4 to broadcast the
    console-device (FBC5) and disk (FBC6) cells into every bank's page
    zero; Boot_BankWalkInit replicates the RST vectors (JP F238/F180)
    to all 64 banks so IRQs/RSTs work in any selected bank. Real RAM
    sizing = ram_page_test_4banks (2530, called from reset_entry 01BB,
    fail flag FDB0) + contig_ram_map_test (267A).
  * SURVIVES (documented in internals/memory-map.md + the four plates): the
    64-bank sweep implies 2 MB of addressable banked-window capacity
    (6-bit bank latch, LIKELY); installed 256K RAM backs part of it.
  * RAM-disk block I/O LOCATED: BdosReadRecordBlock (ram:f4e7) CALLs
    KernSwapCopySrc (f49b: select bank A + LDIR across the window) -
    the storage copy path for drives A:/B:. Write twin still to find.
- 2026-08-25 (RAM-disk block I/O layer CLOSED; main agent, saved):
  * Write twin FOUND (already named): BdosPrepWriteBuf (f510: 0x80B
    record FFA3 -> FEFF staging, banked via f498) + BdosDoneWriteBuf
    (f523: FEFF -> FFA3). BdosPrepReadFromBuf (f4eb: 0x24B header
    stage via FF7F) + BdosSwpDirectory (f535: F8B8 dir buffer ->
    [FFA3] DMA) complete the layer. All five plated; staging cells FF7F/
    FFA3/FFA5/FEFF/F8B8 commented; f498 entry EOL'd (bank arg comes
    from FEFE - the envelope's saved-bank cell is reused as the block
    I/O bank operand). BdosReadRecordBlock: C = bank, 0x80B read via
    KernSwapCopySrc. internals/memory-map.md: owner-confirmed rationale for the
    per-bank vector replication added (COM not bank-aware, DIP may be;
    IRQ/RST must work in any bank).
  * Open next: 049f/04c8 block-address helpers (f822/f8b0 math) -
    the record -> (bank, offset) geometry; FDBD/FDBE hardware test;
    emulator verification (memory-gated).
- 2026-08-25 (FS geometry layer decoded; main agent, saved):
  * The 04B8-052E cluster is the DIPOS filesystem geometry layer -
    already named Fs* by an earlier pass; plates + cell comments added
    and 4 auto-FUN helpers renamed (Util_HlPlus2Cy/HlMinus2Cy,
    FsHlSubF8b2/FsHlAddF8b2). FsVolumeInit (0509): A = log2 records
    per block -> f822; f820 = 1<<A, f828 = mask, f82a = A+3 (log2
    block bytes). FsInitAllocator (05a1): **f8b0 = 0x100 = 256
    records per 32K bank page** (32768/128), f8b6 = 0x8000 base -
    the RAM-disk geometry CONFIRMED. FsBitmapRolExt (049f): 16-bit
    rotate-left A, carry-out -> RST 28h error trap. DiskDirEntryWalk
    (04c8): 2-byte-stride dir search over the F8B2 table.
    BdosReadRecordBlock therefore: bank in C, record -> offset via
    FsBitmapRolExt(f822), 0x80-byte copy via KernSwapCopySrc.
  * RAM-disk geometry summary (CONFIRMED): 128-byte records, 256 per
    bank page, block size 128 * 2^f822; banks 2+ = data pages.
  * Provider still down (agent spawn failed again) - main agent again.
- 2026-08-25 (PASS B wave - 3 agents parallel + annotate apply; saved):
  * Pass B inline comments APPLIED: 124 comments (20 PRE + 104 EOL)
    across the 10 ROM01 UI survivors + descriptor handlers - all
    byte-verified at application time (incl. inline tables {0006,0001}
    @1f99, {03}@6b43, {05}@66ef, coroutine selectors @6e81/6ea5/6eb4/
    6ed1).
  * ABI corrections (byte-verified): e04b Z <=> DIFFERENT (unequal
    path zeroes via XOR A - branch on HL not Z); e05a Z <=> EQUAL.
    Plates updated.
  * Stub farms CLOSED: ee00-ef37 = 66 contiguous LD HL,1/RET cells
    (tbl_FieldOpSlots + repeatable; 32 SessionOpStub plates + 8 farm-B
    plates; ef88 body fixed). The earlier "ee78/ef24/eef0 are real
    helpers" reading REFUTED by bytes (decompiler-context error) -
    Ui_RecordEditModal and Ui_RedrawIfRequested plates corrected.
    No ROM writer found for the slot table (loaded software may patch:
    SUSPECTED).
  * BDOS dispatch arrays UNIFIED: F1D1-F234 = ONE 50-word handler
    array tbl_BdosFnHandlers (image of ROM00:36EE-3748); base F1EB =
    array+0x1A (fn 00-24h); F1D1-F1E9 = wrapped F3-FF view (1FDF/
    1893/1877/15A0/15A4/3237/15CB/3241/3248/1150/113E/1122/112D).
    ram:f180 rebuilt as BdosDispatchFn (f180-f1d0) with the full
    decode plate; Kernel_DispatchCommand (f1a3) retired - it was a
    fragment of the dispatcher. 12 auto labels deleted (table-word
    artifacts), f1c5/f1ce renamed BdosDispatch_TablePath/_GoHandler.
    Docs fixed: the stale "FD->0DE9, FC->024D, F6->1893, F7->2477"
    examples and the fn 40h -> ~F06B wild-pointer example (now F26B)
    in internals/cp-m-comparison.md / internals/os-diposb.md / manual/programmer-guide.md.
  * Syscall families named: the 11-entry FB family (ids 0C,0F,12,15,
    18,1B,1E,24,27,2A,2D -> Syscall_InvokeServiceFB_IdXX + Tail) and
    the second family (Syscall_RestartCold f2c4 -> JP 01A6,
    Syscall_RestartWarm f2de -> JP 024D, Syscall_InvokeService_Id03/
    06/09/21/3F/36/39/30/33/42 with targets byte-mapped).
- 2026-08-25 (patch/hook investigation - owner hypothesis; agent +
  main-agent review, applied, saved):
  * VERDICT: SessionOpStub farms ARE patch surfaces. Mechanism
    CONFIRMED (direct-CALL consumers in ROM + battery-RAM no-op
    defaults + zero ROM writers + loader fn 0/1 write-anywhere +
    d828 indirect caller with settable bank byte + F168 sentinel
    guards); design-intent (public patch sockets for DIP bug-patching/
    extensions) LIKELY. Full table in internals/memory-map.md "Patch/hook
    surfaces". Hardware test to settle LIKELY->CONFIRMED recorded.
  * Main-agent review caught + fixed: the e05a plate was WRONG (it is
    the NOT-EQUAL test: HL=1 iff !=; Z=1 <=> equal) - the third
    agent's flag reading reconciled the earlier two (e04b = equality
    test with Z=1 on unequal; e05a = not-equal with Z=1 on equal;
    names Eq16/Ne16 from wave 1 were right all along). Pass-B branch
    comments re-checked against the verified flags: all consistent.
  * Applied: tbl_FieldOpSlots repeatable extended (hook reading);
    d828 EOLs (JP (HL) >=ED00 / self-patched RST 10h stub);
    d6c0 plated (QueueArena_NoopFill - only covers ED1C arena, NOT
    the farms); d7f3 EOL (sets d828 bank byte).
  * OPEN: hardware DIP patch test (both farms + d081 level 1/2);
    factory provenance of farm contents unknowable from ROM.
- 2026-08-25 (owner comment-style correction + re-inventory round):
  * OWNER: long EOL/Repeatable comments violate AGENTS.md §8 - EOL
    and Repeatable must be ONE short sentence (<=~60C); detail goes
    in a PLATE at the same address. Rule amended in AGENTS.md §8.
    Audit found 29 offenders (long repeatables on io ports, RAM
    cells, 758b/7715/7751/ee00/f238; long EOLs at f498/f590/2468/
    6431/653b/31ca). Pattern fixed on ee00/f238/758b/7715/7751
    (short repeatable + full plate); the rest handed to agents.
  * OWNER: stub documentation upgrade - "Empty stub slot" alone is
    not enough; each stub plate should say what the hook enables
    (consumer, default behaviour, what a DIP patch would change).
  * OWNER: LAB_* auto labels inside functions (mostly ROM01) need a
    re-inventory: branch targets vs data artifacts, rename or
    delete, and comment.
  * NEXT: restructure remaining long comments (agents); LAB_
    inventory (agent); purpose-oriented stub plates (agent).
- 2026-08-25 (owner round 2 - more comment-style rules + F1EF task):
  * OWNER: comments must not restate the assembly ("PUSH AF; FEFA<-HL;
    A=06h ..." verbatim opcode lists are USELESS - remove). Caller
    lists in plates are also noise (Ghidra shows them via XREF) -
    remove from plates. Comments SHOULD be multi-line, wrapped ~70
    cols. This applies to many plates written in the 2026-08-25 waves
    (Kernel_CallBank6_0E00-style) - systematic cleanup needed.
  * OWNER TASK: check RAM:F1EF onwards is correctly initialised/copied
    - it is CALLed by ROM code and seems to contain invalid code.
    (F1EF sits in the tbl_BdosFnHandlers array region F1D1-F234; the
    array is data, so a CALLer means mis-disassembled flow somewhere
    in the ROM00 image (36EE+ region) - find the phantom xref, clear
    the flow, confirm the RAM image bytes match the ROM00 source.)
  * INFRA NOTE: Ghidra crashed twice on 2026-08-25 (17:1x and later);
    unsaved DB work from the style-fix round was lost and must be
    re-applied (e05a plate fix, tbl_FieldOpSlots hook repeatable,
    d828 EOLs, d6c0/d7f3 comments, short-rep+plate fixes on ee00/
    f238/758b/7715/7751). SAVE after every batch.
  * RULES TO ENFORCE going forward (AGENTS.md §8): EOL/Repeatable =
    one short sentence; plates = multi-line wrapped prose, no
    pseudo-asm, no caller lists.
- 2026-08-25 (F1EF check + stub plates + LAB batch 1; agents, saved):
  * F1EF ANSWER (owner task): RAM F1D1-F234 is CORRECTLY
    initialised - byte-identical to the ROM00 source (100/100 bytes
    compared). No bogus functions in the span; the region is typed
    as data (tbl_BdosFnHandlers word[50] + new tbl_BdosFnHandlers_Src
    word[50] at ROM00:36EE, whose 68 pseudo-instructions were cleared).
    The "invalid code" appearance = the handler-array data PLUS three
    GENUINE CALL instructions at ROM00:2767/2772/276f (inside
    CharOrBeep 275c-2796) targeting ram:f1ef/f1fb - addresses inside
    the array. OPEN: whether CharOrBeep really executes table bytes
    (the CALLs would enter data = garbage), or the name/analysis of
    CharOrBeep is wrong (275c region = post-RAM-test area), or the
    table is patched at runtime. Discriminating test: single-step
    CharOrBeep in the emulator/hardware, or re-derive 275c's role.
    EOLs at 2767/276f/2772 record the finding.
  * Stub purpose plates APPLIED: all 39 SessionOpStub_* now carry
    multi-line developer-facing plates (role + what the default means
    + what a DIP patch could enable; LIKELY/SUSPECTED tagged;
    ef08/ef0c/ef1c/ef20/f178 = SUSPECTED spares; ee88/ef2c/eec0/eee8
    = return-value-consumed slots; f118 doubly wired via ec69 seed).
  * LAB_ inventory: 1385 total (ROM00 616 / ROM01 538 / ram 231).
    BATCH 1 APPLIED: first 25 ROM01 labels - 23 renamed to branch-
    meaning names + comments; 2 write-xref aliases (020d/0390)
    commented only. QUEUED: 17 ROM01 outside-fn labels (1e8b,1f3b,
    1f90/93,2041,3b7a,5b57,620c,627c,6707/1f/25,6b90,6ca7,6f25,7564,
    79a6); 12 ROM00 +N mid-instruction labels (delete); remaining
    ROM01 (~513) and ram (109 outside-fn) batches.
  * NEXT: plate-refinement sweep - remove pseudo-asm restatement and
    caller lists from older wave plates (Kernel_CallBank6_0E00,
    Syscall_InvokeServiceFB family, BdosBankedCall3/4, envelope
    family, Boot_BankWalkInit, Mem_BankSweepPutByte, RTC/Link/Comms
    plates). Method: script-dump all plates, flag "<-"/opcode-list
    and "Callers:"/"CALLs" patterns, rewrite multi-line.
- 2026-08-25 (plan execution round; 3 agents + annotate, saved):
  * LAB inventory batches 2-4 APPLIED: 50 ROM01 labels renamed
    (branch-meaning names + comments) incl. pump-island, postdesc
    tails, evalrec tail; 5 ROM00 mid-operand labels deleted (via
    ref-removal - the removed refs may REGENERATE under auto-analysis,
    watch them); 2 contested jump-onto-operand sites (1793/7060)
    bookmarked for clear_flow; promotes: SessionOpStub_3b7a,
    SessionSub620C (island 620c-627f), UiChunkCopyEntry_A/B (SUSPECTED
    alternate entries). 456 in-fn LAB labels remain for the next
    tranches.
  * MYSTERIES RESOLVED/ADVANCED:
    - CharOrBeep -> SelfTest_PatternWalk275c: the 2740-2796 cluster is
      cold-start SELF-TEST (called from ColdStartSelfTestBanner via
      271F), not char output. Its CALLs into f1ef/f1fb/f206 land in
      BDOS-table data in the post-boot dump - SUSPECTED those
      addresses hold self-test stubs EARLY in boot, before the BDOS
      dispatcher+table are built over the same RAM (discriminating
      tests recorded). KeyCharStore -> SelfTest_NextPatternValue;
      CarryBitMacro (2740) bookmarked for rename.
    - F1D1 prefix: CONFIRMED nothing indexes F1D1 directly; F1EB is
      the only live base - consistent with the early-boot picture.
    - Flow gaps: 1d80 tail HEALTHY; 6292's skipped range = three real
      sibling thunks (62A9/62B6/62CA - promote next pass); 6431 =
      false alarm (decode was correct; note cleared).
    - d7d1 checksum CONFIRMED (16-bit byte-sum, D:A); ABI spot-checks
      all consistent with plates.
  * PLATE DEBT EXPOSED: of 730 functions, **498 named functions have
    NO plate** (mostly the Session 32-bit VM/arithmetic cluster -
    SessionAdd32/SessionNeg32/div/shift family and friends - whose
    names are self-describing but undocumented). This is the new
    dominant documentation gap; queue a plate-writing campaign
    (verify-then-plate per function).
  * Wrap batch: 71 more plates re-wrapped; SessionSub16 (e0a9) plate
    written from the REAL bytes (swap-then-subtract; Z = low byte
    only).
- 2026-08-25 (VM-cluster plates + small fixes; agents + annotate, saved):
  * 38 plates APPLIED for the plateless Session VM/arithmetic cluster
    (FillMemory/SaveArgs/LoadOp1-2/StoreOp1/DispatchThunk/SwapOps/
    Neg32/TestNonzero/CmpCarry32/Cmp4Xor80/Add32/And32/Shl32/Div*
    family/TestCarry/CmpThenDispatch/SetWord32/Mul16Mod16/And16/
    UnsignedCmp16/Neg16/CommandDispatch + SetBdosVectorD681/
    ChecksumBytes/BankedCallDispatch/JmpMemoryVector/SessionMemMove/
    SessionBdosCall/da27/da34/ShrFieldE3b4). 498-plateless debt now
    ~330 (next tranches continue the same pipeline).
  * Small fixes: 62A9/62B6/62CA promoted (Ui_Thunk* trio, vtable-
    reached); CarryBitMacro -> SelfTest_RamPatternWalk (the
    2740-2796 chain CONFIRMED cold-start RAM write-pattern walk);
    5B57 RESOLVED (legal dual entry / mid-instruction view fixed -
    function re-based at 5B57); 19E0-19F0 = keyboard probe table
    (typed byte[17] + records + JR trampolines + manual refs);
    tty_out_char NOT_CODE "phantoms" were real key handlers - 4
    functions created, keys/handlers tables labelled, anomalies
    recorded (key#0 FFxx slots SUSPECTED unreachable).
  * OPEN follow-ups: SessionShl32 cross-store + INC L fold does not
    reduce to a plain V<<n (emulator/fresh-eyes item); e0b2
    {stride,case,target} field order LIKELY until E104/E205 tables
    are dumped; SessionUnsignedCmp16 implements signed-less-than
    (name grandfathered, plate records the discrepancy);
    ram02:F1FB (self-test store helper) undefined in the dump.
- 2026-08-26 (plateless tranche 2 + LAB batch 5; agents + annotate, saved):
  * 40 more plates APPLIED (ram bank/syscall/banking layer - BdosBankedCall
    twins, KernSetBank/KernMemCopy/bank variants, NMI/common-entry, BDOS
    console handlers, ROM01 dialog helpers). Plateless debt ~458 ->
    ~418 substantive.
  * LAB batch 5: 40 ROM01 in-fn labels renamed + commented (list/walk/
    modal-loop internals). ~417 ROM01 in-fn LAB labels remain.
  * NAME-VS-BYTE MISMATCH FOUND: the Syscall_InvokeService_IdXX farm
    names were assigned on a wrong stride - the real entries are
    9-byte ({PUSH AF; LD (FEFA),HL; LD A,id; LD HL,tgt; JR tail});
    Id06's address actually holds id 09, Id42 holds id 45. NEXT:
    re-derive the whole second farm's boundaries and rename every
    entry by its true id.
  * NEW follow-ups: FF7F/FFA5 vs FEFF/FFA3 staging pairs -> add a
    internals/memory-map.md row; BankedCallCommonEntry's ROM00:230A call lands
    mid-ClockSelftestPeriphCfg - hand-check that boundary;
    ROM01::1b0a nested subroutine = split candidate; the 1fbe EOL
    ("id==13: fall through") may contradict the e04b convention -
    verify pass.
- 2026-08-26 (DB INCIDENT - in-memory wipe, disk safe):
  * During a three-agent parallel round, the in-memory function count
    dropped 746 -> 622. Selectively deleted: UiFieldListRender (198e),
    Ui_RecordEditModal (1b7d) functions, several xrefs (22c0/24fa/28ea
    lost their inbound refs), and the ram:ee00 data comments. Most
    functions + data plates intact. Root cause suspected: parallel
    MCP bursts from three agents with client-side timeouts that
    executed server-side, plus AAM churn on the results.
  * All three agents were READ-ONLY that round (their outputs are
    proposals in the session log below), so NOTHING valuable exists
    only in memory: the last disk save (746 functions incl. the
    deleted ones) is complete. RECOVERY: exit Ghidra WITHOUT saving
    (File -> Exit -> Don't Save) and reopen micron1.bin. Then verify
    count = 746ish and continue.
  * OPERATIONAL RULE (added to AGENTS.md): serialize Ghidra-writing
    agents - one at a time, save between; if the function count drops
    unexpectedly, STOP, do not save, revert to the disk state.
- 2026-08-26 (post-recovery: serial application resumed; saved):
  * REVERT VERIFIED: 746 functions restored, all wiped items back
    (UiFieldListRender, Ui_RecordEditModal, xrefs 22c0/24fa/28ea,
    ram:ee00 comments, f1d1/758b plates).
  * FARM-2 RENAMES APPLIED (descending order, no collisions): the
    InvokeService stubs now carry their TRUE ids - Id06 (was
    Kernel_CallBank6_0E00 at f303, target 0E00 - same bytes),
    Id09 (f30e, 0F37), Id21 (f319, 15EA), Id3F (f324, 15F0),
    Id36 (f32f, 16-byte variant, 3513), Id39 (f33f, 2D79),
    Id30 (f34a, 2ED3), Id33 (f355, 2E02), Id42 (f360, 1A8B),
    Id45 (f36b, 1587). Cross-ref plates updated (tbl_KernelJumps,
    Kernel_RunStagedCall). ROM01::0030 StrCopyPaste -> BankedRst30
    (misname fixed). 1fce/1fdb EOL polarity comments corrected;
    ROM00:2306 body-boundary note added (230A is IrqWorkerPollPort5).
  * QUEUED (next serial batches): LAB batch 6 (40 renames - Agent B
    manifest), tranche-3 plates (~31 + hazard resolutions: delete
    UiDialogDrawBlock2 0879, retype session_router_5994 as data,
    verify StrTrimDispatch 0303, Ui_LineWalkArgThunk promote).
- 2026-08-26 (serial application continued; saved):
  * LAB batch 6 APPLIED (40 renames: ModalRunLoop/SessionCoroAsync/
    StatusCursor/SleepDelay/PollTick/PollIntrq/RxProcessFrame/RxDispatch
    internals). ~393 ROM01 in-fn LAB labels remain.
  * TRANche-3 APPLIED: 31 plates (Text* cluster, Str* cluster,
    UiDialogDrawBlock/FieldTableBuild/FieldLineWalk, console wrappers,
    session validators); hazards resolved: UiDialogDrawBlock2 (0879)
    deleted (mid-body), session_router_5994 re-typed as data
    (tbl_sessionRouter5994), StrTrimDispatch (0303) byte-verified
    mid-operand artifact -> deleted + bookmark; UiOpenSaveDialog
    (1add) RENAMED to Ui_LineWalkArgThunk - fresh bytes proved it is
    the field-walk arg-marshalling trampoline, not a dialog routine
    (the old name was an unverified relic of the flow-repair
    recovery); TextHomeCursor (7121) + StateWordSet_E8D8 (6772)
    promoted. Count 745 = 746 -3 deleted +2 created, no losses.
  * Rename candidates queued: SessionNopWaiter (675A, actually a
    getter) -> StateWordGet_E8D6; ui_OpenSaveDialog doc-grep done
    (only historical TASKS logs).
- 2026-08-26 (recommended-order rounds; saved serially):
  * 675A renamed StateWordGet_E8D6 + plate. internals/memory-map.md gained the
    block-I/O staging-cells row (FF7F/FFA5 read pair, FEFF/FFA3 write
    pair, F8B8 dir buffer).
  * LAB batch 7 APPLIED (40 renames: RxIncr/DecrCounter, CountBytes,
    ParseField, ConnectCheck, CmdWalkTable, WaitCharCell,
    RxRecordStage, RxEditBuffer internals). ~352 ROM01 in-fn LAB
    labels remain.
  * TRANche-4 APPLIED: 39 plates (9 FB stub templates, 13 ROM01
    session/coro helpers incl. NumberAccumulate/NumValueTableFetch/
    CmdRetryCounter, 17 ROM00 BDOS fn handlers incl. the version
    deviation HL=23h, MonitorEnter/PutChar/GetChar routing, kbd row
    decode, decimal formatter). ROM00::2d82 DEFERRED (body
    mis-bounded - repair first). Plateless ~343 remain. Count 751.
  * NEXT (serial): LAB batch 8 (starts 2f2e; bonus context for
    2f2e-2fec already captured), plateless tranche 5 (unnamed helpers
    cited in tranche 4: ROM01::581F/5991/5E78, ROM00::F4EB/F501/
    F543/F46D + the duplicate-name collisions SessionCommandDispatch
    x4 / SessionCoroThunk x2 / BdosGetSetUserCode x2 need
    disambiguation), SessionShl32 anomaly, 2D82 bounds repair.
- 2026-08-26 (batch 8 + collision fixes; applied serially, saved):
  * LAB batch 8 APPLIED (40 renames: FieldEditLoop scanback +
    SessionRxProcessLine full editor internals - flags, trim, key
    dispatch stages DBh/1Ah/7Fh/20h, delete/insert paths, render
    loop, helper spacer). ~304 ROM01 in-fn LAB labels remain
    (next = 34FD).
  * Collision sweep: 5 SessionCommandDispatchStub_* thunks renamed
    (ROM00:5a66/604e, ROM01:3b53/5e2e/62d1 - all plain CALL ram:e0b2
    wrappers); BdosGetSetUserCodeRet0Stub_1890 renamed (dead
    constant-zero stub, behaviourally different from 0c96); the real
    SessionCommandDispatch (ram:e0b2) has 20 callers - name kept.
    ROM01::00ef SessionCoroThunk DELETED (pad-region artifact; callers
    759F/75B6 use CALL PO) + bookmark with the discriminating test.
  * Plates: BdosGetSetUserCode (0c96) plated. D660/D681/D686/D6C0
    already plated (skip verified). Entry-validity bookmarks set for
    59fb (RET PE opener), 6431 (leading NOP), 5b58 (name/entry
    off-by-one vs 5B57).
  * Tranche-4 helper citations double-checked: 581F/5991/5E78 are
    call sites INSIDE named functions (target ram:e0b2) - no new
    functions needed; the F4xx helpers are ram-space functions with
    correct names already.
  * Count 750. Plateless ~330. Remaining LAB ~304.
- 2026-08-26 (batch 9 + tranche 6; applied serially, saved):
  * LAB batch 9 APPLIED (39 rows: router exits, render loops, field
    load scan, pad-fill path, msg-table builder walks, validation
    chain; 34fd comment-only pending cross-space xref check; 3b7a
    kept as pooled RET epilogue with 7 sites). ~258 ROM01 in-fn LAB
    labels remain (re-enumerate before batch 10 - inventory drift).
  * Tranche 6: 6 new Fs* plates (FsRecCountIncr, FsBitmapRor,
    FsSetupGeometry, BlockAllocQueryFree, FsDirScanWildcard,
    FsDirBlockRead). The other proposals were already plated
    (skip-verified); ram space effectively saturated. ram:e04b check
    was a false alarm - util_CmpHLDE_Eq exists with plate.
  * Estimate: plateless ~300, concentrated in ROM00 (390 named) and
    the ram SessionOpStub_* farm (~35); a working enumeration script
    is needed next time (the inline script route flaked).
- 2026-08-26 (batch 10 + Fs-cluster tranche; applied serially, saved):
  * LAB batch 10 APPLIED (41 rows: msg-table builder tail, msg
    dispatcher/route, field-offset walk, helper-router case machine,
    key-process, wait-key-state). ~236 ROM01 in-fn LAB labels remain
    above 3da0 (next = 41c0).
  * TRANche-7 = the whole Fs layer completed: 26 plates -
    FsBlockMapRead, FsRecCountRead, FsBitmapShiftRight, alloc bitmap
    clear/claim/free, FsDirFormat, FsDirMakeEntry/FindMatch/
    ResetCursor/EntryAdvance/BlockRead, FsDirIntegrityCheck +
    BdosExtFn62 shim, FsSearchCommon ('?' extent wildcard), the three
    keyed-read variants. The filesystem/BDOS-disk layer is now fully
    documented end-to-end.
  * Plateless re-enumeration (script route repaired): 325 total -
    ROM00=264, ROM01=61, ram=0. Next tranches: ROM01's 61, then the
    ROM00 remainder.
  * Remaining: SessionShl32 anomaly, 2D82 bounds repair, LAB batch
    11+, emulator/hardware (gated).
- 2026-08-26 (tooling outage): the cheap subagent model
  (opencode/x-preview-f-free) is no longer supported by the provider
  - every agent spawn failed with 'Model x-preview-f-free is not
  supported'. opencode.json repointed (model/small_model/annotate/
  docs -> deepseek/deepseek-v4-pro); RESTART opencode for it to take
  effect. Queued work resumes after restart: LAB batch 11 (41c0+),
  ROM01 plateless tranche (61), ROM00 remainder (~240), SessionShl32
  anomaly, 2D82 bounds repair.
- 2026-08-26 (direct-tools round; owner re-configured agents -
  investigate/investigate_deep/annotate/docs with per-agent models;
  main agent did the work directly, serial, byte-verified, saved):
  * 2D82 BOUNDS REPAIR (last correctness item): the 1-byte shadow
    function at ROM00::2d82 deleted; the real KernelErrorReport body
    is 2d83-2dd0 (intact, fully plated with both entries: bit1 path
    msg@2D17, bit2 path msg@2D04); secondary entry labelled
    report_entry_bit1 at 2d82. SAVED.
  * LAB batch 11 APPLIED directly: 44 labels renamed + commented from
    a fresh script-dump (per-label evidence = containing function +
    first instruction + incoming branch sites): SessionWaitKeyState,
    FieldSelectWalk, SessionTableWalkNext, SessionRedrawField,
    SessionDrawFieldLine (incl. cross-fn entry from 75e3). Next batch
    starts at 4730 (~190 remaining).
  * NOTE: the main agent has direct ghidra-mcp tools again, so
    analysis and application run in-loop for accuracy; agents remain
    for routine work.
- 2026-08-25 (plate-refinement sweep EXECUTED; annotate, saved):
  * Enumerator found 40 pseudo-asm offenders, 26 caller-list
    offenders, 147 unwrapped single-liners (of 223 plates).
  * APPLIED: 40 exact multi-line rewrites (no asm restatement, no
    caller lists; reset_entry, PowerDownSuspend, RtcWriteTime/
    SetTimeFromBlock, IrqWorkerPollPort5, ClockSelftestTickWindow,
    FatalErrorHandler, LinkTransferService, LinkProcessCommandFrame,
    KernelImage_BdosMain, banked wrappers, NMI/IRQ images, session
    routines, dialog/set-clock entries, ExtBusPoll, EvalRecordSteps,
    dispatcher/loader plates, the runtime-page family, etc.);
    20 caller-list excisions; 60 mechanical re-wraps (~70 cols);
    SessionSub16 (e0a9) flagged as undocumented - plate needed.
  * CORRECTED: an enumeration space-typo (ROM01::12ec) caused a wrong
    function shell (Barcode_PollContinuation) in a legitimate ROM01
    gap - deleted; the rewrite went to the real ExtBusPoll at
    ROM00::12ec. Two leftover caller phrases excised (d8ce, e06b).
  * Remaining known debt: ~90 P3-only single-liners beyond the 60-cap
    (next wrap batch), SessionSub16 plate, and any plates still
    holding asm-style flow narration outside the P1 list (reviewed
    per-plate next sweep).
- 2026-08-25 (helper-cluster wave + memory-model resolution; 2 agents
  read-only, main applied + saved):
  * UI helper renames (stale names corrected): SessionLinkTx6292 ->
    Ui_PostKeyedEntry (6292; JP 62A6->62D1 gap flagged), StateVarDispatch
    -> Ui_RedrawIfRequested (6280, gate cell is eb18 not ebf7),
    UiHandler1B7D -> Ui_RecordEditModal (1b7d, six stack args, modal
    loop 1CD6-1D72), SessionCoroWaitByte -> Ui_GetStateWordEc41 (2116),
    TextOutChar -> ServiceCall_Id2Byte (6f29, DA13(2,arg) shim - the
    TextOut identity was unproven). 183c/198e kept (enriched plates:
    9B->10B field-table build; stride-4/5 item lists).
    DiagFatalErrorScreen (ROM00::2B55) plated with table contents.
  * FB-service path CLOSED mechanically: RST 28h -> F5ED -> F57E
    (bank-0 select + F54E) -> BdosBankedCall2 (F590): CALL 2B55;
    A=FB IS entry 3 of the 7-byte table @2CA8 (FE FD FC FB EA E9 E0).
    OPEN: whether that path means fatal or service-unavailable -
    decode msgs @2CBF/2CE2/2D04/2D17 next.
  * ROM01::7580-7670 decoded: variable-length UI form-template nodes,
    sig EC EF F8 F0 98 EF D8 EF at 758B/75EB/760D/764F/7669 (+08 config,
    +0C string-list ptr into 7A08-7A7F pool, +10 01 01 01 00, +14
    self-backlink). Labels tbl_UiFormTpl_* + repeatable at 758B.
  * MEMORY MODEL SETTLED: ram:0000-7FFF has NO memory block - the
    banked window is modelled ONLY by the ROM00/ROM01 overlays; ram
    byte reads below 8000 fail by design (documented at ram:0000).
    Page-zero runtime stamps (JP F238@0000, JP F180@0005 per bank)
    are installer-proven from Boot_BankWalkInit; ram:2d82 = bank-0
    ROM00 view, hook decoded (FDBD bits 1/2 -> msg@2D17/2D04, park
    3539). NO base-space block should be created - it would duplicate
    the overlay model.
- 2026-08-26 (agent config fixed + FUN_* re-triage; main agent, saved):
  * AGENT CONFIG: investigate/investigate_deep route through OpenRouter,
    which requires the vendor sub-path in the model id. The bare
    "deepseek-v4-flash" failed; "openrouter/deepseek-v4-flash" also
    failed ("Model not found ... Did you mean: deepseek/deepseek-v4-flash,
    deepseek/deepseek-v4-flash-0731, ~deepseek/deepseek-v4-flash-latest?").
    FIXED to "openrouter/deepseek/deepseek-v4-flash" (vendor-prefixed id).
    investigate_deep + top-level model = "openrouter/deepseek-v4-pro"
    (proven working). small_model = "opencode/nemotron-3.5-lightning-free"
    (was bare). general/annotate/docs = "opencode/muse-spark-1.2-free"
    (Opencode Zen). VERIFIED: investigate spawn succeeded after an
    opencode restart and returned a clean triage.
  * Enumerated 15 FUN_* (all real, none false-positive): ram:db89 ->
    Util_NulFillCopy (stack-arg dst/src/count NUL-fill copy, Z=dest==0);
    ram:dda4 -> Session_CondNeg32 (reads *(DE+3), falls into SessionNeg32
    if bit7 set); ram:ee0c/ee20/ee64/ee84 -> SessionOpStub_ee0c/20/64/84
    (tbl_FieldOpSlots patch sockets, each has a real CALLer);
    ROM01:0ae3 -> Session_DialogStateCheck; ROM01:254b ->
    Session_CondCommandDispatch (gate on (ec49)+0xC -> inline CALL e0b2
    dispatch at 257c); ROM01:40a2 -> Session_MsgTableBuildIfNeeded;
    ROM01:65f5 -> StateWordSet_E89A; ROM00:3cea -> Session_CoroInit;
    ROM00:3cf7 -> Session_InitAndRunTx; ROM00:54e5 -> StateWordSet_E519;
    ROM00:5834 -> Session_RunTx; ROM00:60d6 ->
    Session_TxFrame33Transaction. All named + plated.
  * Agent correction caught: 60d6 abort condition is e681 == 4 (via
    util_CmpHLDE_Eq inverted-Z semantics), NOT ">=4" as the subagent
    reported; 254b falls into e0b2 inline dispatch (verified); dda4
    tail-calls into SessionNeg32 (dc94), so mechanics name CondNeg32
    replaced the agent's interpretive "DescChainFollow".
  * Two more FUN_* appeared mid-session (deferred auto-analysis):
    ROM01:7288 -> Session_TableRender7288 and ROM01:73de ->
    Session_TableRender73de (both walk 20-byte records in the ea52 pool,
    TextPosCursor 70ae + char-emit ServiceCall_Id2Byte 6f29; 73de runs
    the record cursor one behind via -0x14). FUN_ram_9cf0 = 16 NOP bytes
    -> DELETED. FUN_* back to 0.
  * Coverage re-enumerated: 750 total (ROM00 394 / ROM01 164 / ram 192),
    FUN_*=0, thunk=13, plateless=299 (ROM00 238 / ROM01 61).
    research/gap-analysis.md refreshed (5th audit).
  * NEXT: plateless tranche 8 (ROM01's 61), then ROM00's 238; LAB batch
    12 (~160 in-fn labels above 4730, evidence dump in-hand).
- 2026-08-26 (ROM01 plateless CLOSED; 3 read-only investigate agents +
  main applied, saved):
  * ROM01 plateless tranche COMPLETE: 61 plates applied (3 RST thunks
    BankedRst08/20/28 done by main; 58 session/UI functions by three
    parallel investigate agents, byte-verified at application).
    Callee names cross-checked (UiFindKeyMatch/UiSetDialogId/
    UiSetAttrCells/UiRenderCharCell/BankedMonoCall/UiFieldLineWalk/
    CmdDispatchSub/CmdDispatchWrap + the Session 32-bit VM op cluster
    dc37/dc49/dce9/dca1/ddfa/dc30/e09f/df42/df5b) - all real, no
    hallucination. Coverage: 750 total / FUN=0 / thunk=13 / plateless
    238 (all ROM00; ROM01 now 0, ram saturated).
  * Boundary issue FOUND + bookmarked (not re-based): ROM01::2f74 holds
    an orphan 11 byte = first byte of LD DE,0x10; SessionFieldEditLoop
    entry is 2f75 (mid-instruction), yet the CALLer at 75df literally
    targets 0x2f75 (CD 75 2F). SUSPECTED dual entry (2f74 primary / 2f75
    DEC-B secondary). Discriminating test: single-step 75df. Guarded
    re-base candidate (bookmark at 2f74).
  * NEXT: plateless tranche 9 = ROM00's 238 (larger; dispatch investigate
    agents in ~6-8 batches); LAB batch 12 (~160 labels).
  * NOTE: agents are WORKING now (config fixed to
    "openrouter/deepseek/deepseek-v4-flash"); read-only investigate
     agents ran 3-wide in parallel without DB issue - the earlier wipe was
     write-agent concurrency. Keep annotate (write) serial.
- 2026-08-26 (ROM00 plateless COMPLETE + wipe/recovery; 9 read-only
  investigate agents in 3 waves, main applied, saved):
  * PLATE CAMPAIGN FINISHED: ROM00's 238 plateless functions plated in
    three waves (disk/Fs/BDOS + device/link/barcode + keyboard/LCD;
    RTC/periph + diag/LCD-print + link transport; TTY/coroutine +
    session screens + TX/RX protocol). Final coverage: 749 total /
    FUN_*=0 / thunk=13 / plateless=0 (ROM00, ROM01, ram all saturated).
    research/gap-analysis.md refreshed (6th audit). This closes the plate debt
    that started at 498-plateless on 2026-08-25.
  * AGENT QUALITY NOTE: investigate agents were reliable on callee
    NAMES and general mechanics but have a ~5-10% detail error rate
    (wrong registers/constants/addresses, esp. in "stub/no-op" guesses).
    Spot-checks caught + corrected: 1888/188c return 0xFFFF/0 (not
    identity no-ops); 1893 uses LD C,0xFE + RST 28h (not A/08h); KbdDrive
    shadow is f782 (not f784); 60d6 aborts on ==4 (not >=4). The applied
    ROM00 plates are FIRST-PASS - a systematic byte-verify refinement
    pass is queued (follow-up).
  * CORRECTNESS FIXES applied: TableIndexedRead (4f4f) = false positive
    over data (no xrefs) -> DELETED. SessionStartTransmit (52d7) is
    mid-function (real proem at 52a5) -> bookmarked, not re-based.
    SessionCompleteMsg/Silent (4a4b/4a67) = alternate entries of the 4a25
    coroutine (noted in plates).
  * WIPE + RECOVERY: during wave-3 application, deferred auto-analysis
    deleted ~125 functions in-memory (750 -> 625), concentrated in the
    ROM00 session/coroutine/TX-RX region. Followed AGENTS.md §11: did NOT
    save, owner exited Ghidra without saving, reopened the last disk state
    (751 functions), and wave-3's 63 plates were re-applied from the log.
    Root cause: sustained rapid set_plate_comment MCP load. NEW RULE for
    next time: save every ~30-40 plate writes (not per-wave).
  * NEXT: byte-verify refinement pass over the ROM00 first-pass plates;
    guarded re-bases of the 2f74/2f75 and 52a5/52d7 boundary issues; LAB
    batch 12 (~160 in-fn labels).
- 2026-08-26 (KbdDrive rename + LAB batch 12 complete; main agent, saved):
  * KbdDrive* grandfathered names fixed (owner-requested; byte-verified).
    KbdDriveAllOn(1a42)=2-byte LD A,0x3F entry that falls into the sense
    routine; KbdDriveWrite(1a44) drives a column AND senses; "ReleaseAll"
    wrote the SAME 0x3F as "AllOn" but without sensing - the real split is
    sense-vs-no-sense, not on-vs-release. Renamed: KbdSenseAllColumns(1a42),
    KbdSenseColumn(1a44), KbdDriveSetAll(1a77, 0x3F), KbdDriveClearAll
    (1a81, 0x00). Plates corrected; 2 first-pass byte-range errors fixed
    (KbdDriveWrite was 1a44-1a76 spanning KbdScanRowDecode; KbdDriveOff
    was 1a81-1a95).
  * LAB batch 12 COMPLETE: all 202 remaining ROM01 in-fn LAB_* labels
    renamed to branch-meaning names (function-prefix + suffix: load_cell/
    ret_imm/zero/one/back/join/exit/dispatch). ROM01 in-fn LAB = 0.
  * REMAINING LAB (enumerated): ROM00 505 in-fn + 88 out-fn; ROM01 60
    out-fn (data region 7715/7751 etc.); ram 128 in-fn + 126 out-fn.
    Next: ROM00 in-fn batch, then the out-fn labels (likely data - delete
    or comment), then ram.
- 2026-08-26 (LAB campaign continued; main agent, saved):
  * ROM00 in-fn LAB batch COMPLETE: 505 labels renamed to branch-meaning
    names (reset_/cold_/install_/diag_/Fs*/Disk*/Bdos*/devcon_/extarm_/
    extedge_/tty_/lcd*/rtc*/link*/ramtest_/contig_/session* prefixes).
  * ram in-fn LAB batch COMPLETE: 128 labels renamed (kernloop_/
    syscall_/loadblock_/fcb_/memmove_/shiftdiv_/mulu_/cmddisp_/bdos_/
    bankwalk_/bankcb_/nmi_ etc.).
  * Session total in-fn LAB renames: 202 ROM01 + 505 ROM00 + 128 ram =
    835. Only the out-fn data-region labels remain: ROM00 88, ROM01 60
    (7715/7751 descriptor tables), ram 126 - these are data labels, to
    type/comment/delete (next round), plus 2 mid-instruction artifacts
    (ROM00:200a, ram:f1b2) to delete.
  * OUT-FN LAB ASSESSED (not renamed - they are auto-generated dynamic
    labels, not deletable via removeSymbol; need the UNDERLYING fix):
    - 13 mid-instruction artifacts (ROM00:1793/200a/7060; ram:d0fe/d123/
      d159/d186/d207/d219/d27b/de6a/f1b2/f1fb) -> need clear-flow repair
      (misdisassembled flow), not label deletion.
    - Data tables (ROM00 7c52-7c70, 692a, 6a28-6a5d; ram e127-e145,
      f1f9/f1fb in the BdosFnHandlers array) -> need data-typing.
    - Code-gap branch targets (ROM00 199d-1a3f keyboard-scan region,
      ram page-zero 0100/01a6/024d etc.) -> need function creation
      (find_code_gaps), not rename.
    Verdict: in-fn LAB re-inventory is COMPLETE (835 renamed); the
    out-fn remainder is function-boundary/flow/data-typing debt, logged
    as its own follow-up.
- 2026-08-26 (terminology correction): "Session 32-bit VM" / "VM register
    file" was an OVER-CLAIM. There is no opcode-interpreter/dispatch loop;
    the E3B1-E3BF cells are a plain 32-bit arithmetic register file
    (accumulator/operand slots, little-endian) driven by direct-CALL
    routines, used by the session numeric formatter (SessionCmdHandler53C6).
    Historical TASKS entries above still say "VM" - treat as stale wording.
    The 16-bit helpers are genuinely generic (moved to Lib_*); the 32-bit
    cluster IS session-specific, so "Session*32" names stay.
- 2026-08-26 (byte-verify refinement wave 1; 4 read-only agents + main,
  saved):
  * RAM02 factored in: ram:0000-7FFF is the banked WINDOW, modelled by
    overlays ROM00/ROM01/RAM02 (RAM02 = RAM bank-2 page, owner-created).
    The ram:0100/01a6 "no-block" labels are banked-window page-zero
    targets (resolve to the selected bank); not a missing-block task.
  * MECHANICAL byte-range audit (script): 110 of 312 plates had a wrong
    "CONFIRMED: addr1-addr2" range (agents over-stated extent to the
    next function's address). ALL auto-corrected to actual body bounds.
  * FACTUAL verification (4 parallel investigate agents, ~295 plates):
    22 discrepancies found + corrected, all byte-verified before apply:
    - ROM01 (6): TemplateBuilder CALL-on-Z not NZ; UiDialogListItem JP
      09db not fall-through; UiDialogLayout does not return HL=1;
      SessionWaitCharCell returns HL=1 (not 0) on zero arg; SessionField
      EditLoop has NO 356e call; SessionFieldReady needs (eb53) non-zero
      too.
    - ROM00 (16): BdosDirSearchHelper extent = f823-f82c (reversed);
      LinkSelectActiveDevice AND 3 not 7; ExtBusAdvanceTimer fbce +=
      f9ac (not -=); CommsLineDeassertRd order (2349 first); KbdColumn
      Strobe branches on Z not carry; LcdCharWrapBound uses BC not HL;
      lcd_clear_spaces loops 0xA0 (160) not 0x60; RtcPeekDateByte CALL
      not tail-call; DiagPrintResult 0x80=TIMEOUT else FAIL (swapped);
      TtyPrintString/LcdPrintString NULL-terminated not $; LinkTransport
      Call CLEARS fbc9 bit0 while LinkResetSession SETS it (pair was
      SWAPPED); DescriptorCount16 reads 4 bytes not 16; RtcDateChanged
      Check sets fbc9 bit1 unconditionally; RtcAlarmWriteCtrl is a 15-byte
      fragment (real alarm logic in RtcSetAlarm).
    - Session cluster (ROM00 354c-6811) verified CLEAN (agent found 0).
  * BeepAndLatchWrite (14ff) renamed Barcode_AttentionStrobe (stale
    "ReaderBeepAttention"/"light-pen" plate fixed; drives 2A/2C route
    latches + arms fbbf). internals/io-map.md updated.
  * NEXT: byte-verify wave 2 (re-scan for remaining detail errors;
    data-typing + find_code_gaps for the out-fn tail); guarded re-bases
    (2f74/52a5/4a25); emulator run (memory-gated).
- 2026-08-26 (Comm Setup device-selection trace; 3 read-only agents +
  main, saved):
  * The 5 device names at ROM01:757F are COMM SETUP form labels, not
    drives. Form template at 758B (+0x0C -> 757F), built by
    Ui_CommSetupFormInit (060B) -> TemplateBuilder (0271).
  * Two wire-id tables, one accessor (~ROM00:31FF): FE93 = drive-letter
    -> wire-id (A=0x00 internal, B=0x7F, C=0x73, D=0x72, E-P=0x00);
    FE83 = 4 device slots [0x80,wire,0x63,0x43] = 0xAB/0x2B/0x67/0x67.
    BDOS std file ops (fn<0x25) reject non-zero wire-id -> external probe
    (DiskKeyedSearch -> LinkTransportOpen). Plates set on FE93/FE83.
  * `ram:D081` = `g_apScreenHandlerTables` (was `g_tblFieldTypeRecPtrs`): **five
    per-screen handler-table pointers indexed by active-screen selector at
    `ROM01:034B`** (CONFIRMED). Entry 0 = `g_apLoadRunHandlers` at `ram:D0F0`
    for the `ROM01:0A67-10CE` Load/Run loader (`Program_LoadByName`,
    `Program_LoadDipOrCom`, `Program_RunByName`, `Program_GenerateBlockChecksums`
    etc.); supersedes the earlier device-callback mapping
    `{D0F0,D13D,D121,D12F,D14B}`. Plate corrected on `ram:D081`.
  * VERDICT: WORKSTATION MEMORY/RAMDISK are config FLOWS, not hardcoded
    wire-ids; the wire-id values are RUNTIME (dialog result / banked-call
    param), so static analysis cannot read them. NEXT: hardware/emulator
    step the Comm Setup wizard and observe FE93/FE83/FBC5.
- 2026-08-27 (3 agents: emulator + code-gaps + acronym/EOL; main applied):
  * EMULATOR (general agent): booted but STALLED in the bank-walk loop
    (never reached BannerKeyRead/menu). Still produced a full 64K dump.
    FINDING: runtime D660-D680 holds CODE (not the zeros in our static
    dump) and D681 self-patches to JP F180 - so the static dump's D660
    zeros are pre-boot state, overwritten by the boot/dispatch code.
    FE83/FE93/F180/F820 match ROM defaults. To reach menu: higher
    --max-slices (~2e6) + fix the ram-page-test skip.
  * CODE GAPS: created functions Kbd_ScanMain (ROM00:18f0, the keyboard
    scan loop) + 4 session helpers (7be0 Session_IncHLOrRet, 7bed
    Session_LoadDecCmp, 7c14 Session_Cmp16Bit, 7c22 Session_Cmp16BitB).
    Data tables identified (not yet typed): ROM00 7c30 lookup, 7c50
    bitmap, 7d80/7e50 fn-ptr tables, ROM01 7545-7fff descriptor table,
    ram:e105 lookup+bitmap, ram:d0e0 string table. 2 mid-instruction
    labels to delete (ram:f1b2, ram:de6a - auto-symbols, need clear-flow).
  * ACRONYM: 14 32-bit-arithmetic plates corrected - dropped the "VM
    register file" over-claim, now name the concrete E3Bx cells.
  * EOL: 41 EOL comments on SessionCommandDispatch (e0b2), FsInitAllocator
    (05a1), Kernel_BankedCallEnvelope (f376), SessionCoroStartTask (3d3c).
  * CHURN: 7 FUN_* re-triaged + named: Fs_DirBlockMap (042d),
    Session_DialogIdGet (1548), Kbd_SetKeyState2 (1aec), Kbd_ClearAndPower
    Bit0 (1b1a), PowerLatchClrBit0 (1b39), SessionDivS32 (ddb0),
    SessionModS32 (ddcb). FUN_* = 0.
  * NEXT: data-type the identified tables; guarded re-bases (2f74/52a5/
    4a25); emulator menu reach (higher slices); apply remaining EOL
    (SessionCoroJumpTable 3c06).
  * COMMENT-STYLE GUIDE added to AGENTS.md §8 (owner-requested): plate
    template (brief/longer/In/Out/Clobbers, MUST be multi-line ASCII -
    never squashed); SHORT form allowed for trivial fns (Lib_SignedLe16);
    LABELS-not-addresses rule (cite g_/named labels, not raw cell/port
    addresses). MIGRATION follow-up: many existing comments still cite raw
    addresses (fbc9 bit0, e681, ec49, f794, ...) - a labelling pass should
    create descriptive labels for the hot session/link cells and rewrite
    those comments to reference them.
- 2026-08-27 (3 agents: stdlib inventory + serial flow + emulator; applied):
  * STDLIB RECATEGORISATION continued (byte-verified by agent): the
    string/memory/char helpers are generic and moved to Lib_*. Two were
    MIS-NAMED and corrected: Util_ArgAddrSp5 = bounded STRNCMP ->
    Lib_StrCmp (db35); Util_ArgAddrSp5b = STRCAT -> Lib_StrCat (dbb1).
    Also: Util_StrLen -> Lib_StrLen, Util_StrCopy -> Lib_StrCopy,
    Util_NulFillCopy -> Lib_StrCopyN, SessionMemMove -> Lib_MemMove,
    SessionFillMemory -> Lib_MemFill, Session_IsDigitCy -> Lib_IsDigit.
    NO pure strcmp/strncmp-with-caller-bound exists. Kept Session_ for
    the FCB/session-specific (Session_CharTranslate, Session_FcbCharTrans,
    Session_FcbParseFilename) and the VM register-file ops. (Nugget:
    the underlying 32-bit divide engine might be general-purpose - open.)
  * RAM SIZE vs SERIAL (CORRECTION, owner-flagged): ram:FEAB is WRITTEN by
    DelayCountUp (ROM00:271F) at cold start as FEAB = FEA9*0x20 (FEA9 =
    count of 0xFF bytes from the RAM scan) - this is the RAM SIZE code,
    DISPLAYED on the banner as "Ram: NN K.B." - I mistook it for the
    serial number; BOTH are shown on the boot screen. The banner waits
    only for ENTER (0x0D) at 02D8. The "Enter the Workstation serial
    number shown on the back" dialog (strings 7A8E-7AB2, template 76E4)
    is ROM01 app UI, post-boot - that is where the user-entered serial
    (in the FEAB AREA, owner-confirmed) is written; the exact serial CELL
    has not been pinned yet.
  * EMULATOR STALL SOLVED: root cause was NOT a bank-walk bug - it was the
    genuine banner HALT-wait (16CA, ffa8=1, fbc9=0); the --drive-kbd cheat
    spammed ENTER faster than the ring was consumed. Fix (in /tmp/
    boot_hw_serial.py, NOT yet merged): pace one char per consume (inject
    only when fbc9 bit2 clear), add --drive-serial/--serial to inject
    banner-ENTER + "12345678" + ENTER. Result: reaches the MAIN MENU
    (~173k slices; framebuffer shows Main Menu / Load/Run Program / Set
    Clock / Display Status / Diagnostics). Speed: SLICE=5-10k halves the
    slice count at the same wall time; MAX_SLICES 300k sufficient.
    NEXT: merge the paced-injection + --drive-serial flags into
    analysis/boot_hw.py.
- 2026-08-27 (emulator visibility + naming convention; agents + main):
  * EMULATOR UPGRADE: analysis/boot_hw_visible.py adds (1) LCD render of
    FC06-FCA5 (20x8) to the terminal, (2) an expect-DSL (--expect
    "text:keys" / --expect-file JSON / --expect-timeout) so scripts can
    wait-for-text-then-type, (3) multi-bank RAM (--ram 256|512; ports 47h
    bank select banks 0=ROM0/1=ROM1/2..N=RAM pages; --dump-bank N). Boots
    to the Main Menu with the LCD animated. Boot reached via expect:
    "To Continue Press>>:\r" + "serial number:\r12345678\r" + "Main Menu:".
    (Keeps boot_hw_serial.py working variant; not yet merged into boot_hw.py.)
  * NAMING CONVENTION (per owner): RAM stdlib -> Lib_; ROM utilities ->
    omit prefix or _rom0/_rom1 suffix; Session_ only for real session
    handling. APPLIED: 25 renames - 21 Session*32 -> RegFile_* (the
    E3B1-E3BF register-file arithmetic: RegFile_Add32/And32/Shl32/Neg32/
    CmpCarry32/CmpSigned32/TestNonzero/DivResult/ShiftSubDiv/LoadOp1/2/
    StoreOp1/2/SetWord32/SaveArgs2/Shr32/CondNeg32/DivS32/ModS32/DivShl/
    CmpGtDispatch); SessionAnd16 -> Lib_And16; SessionNeg16 -> Lib_Neg16;
    Session_SyscallFromGlobals -> Bdos_CallFromGlobals;
    session_bdos_prep_call -> Bdos_PreparedCall. Plus Fcb_CharTrans/
    Fcb_ParseFilename (earlier). FUN_*=0.
  * DEFERRED naming proposals (agent audit, NOT applied - await owner
    preference): 30+ SessionOpStub_ee* -> OpStub_ee*; Session_CmpBranchGlue
    /DispatchThunk -> Vm_*; SessionDialogRenderer/DialogIdGet/DialogState
    Check -> Dialog_*; Session_TableRender7288/73de + SessionDrawFieldLine
    -> Ui_*; Util_HlPlus2Cy/HlMinus2Cy/Shr16A -> *_rom0; Str*/Text* ->
    *_rom1; Session_CharTranslate -> Lib_ (conflicting evidence, keep
    Session_ for now); Session_EnvThunkD7d1 -> Util_ChecksumThunk.
- 2026-08-27 (emulator RAM/FF + --help; error-path q's; labels; churn):
  * EMULATOR FIX (general agent): not-present banked pages now READ 0xFF
    (and discard writes), so --ram 256 reports "Ram: 256 K.B." not 2016K;
    --ram 512 -> 512K. boot_hw_visible.py gained full --help docstring +
    an analysis/README.md "Emulator" section (options, expect DSL grammar,
    RAM model). Not merged into boot_hw.py yet.
  * ERROR-PATH Q's (investigate): "Plinth not connected" (ROM00:6d6f) =
    LinkProbe (348a) hardware probe failure - 0x1F->port 4F, LINK_CTRL(4A)
    bit5/0/6/7 toggles, read LINK_STATUS(4B); error code 6 in e488; NO
    data packets (4Dh/4Ch) in the probe stage (0xE0/0xEE frames come later
    in the connect handshake). "No program in memory" (ROM01:7d07) and
    "Can't open or create file" (ROM01:7cdb) are behind a RUNTIME
    error-code->string table (ram:d0e0 / ROM01 7c80) - exact condition
    needs emulator/RAM trace (LOW confidence).
  * LABELS: applied g_ labels to 9 hot RAM cells (g_bEventFlags fbc9,
    g_bActiveDevice fbc5, g_bActiveDrive fbc6, g_pScreenDesc ec49,
    g_wEventWord ec41, g_wTxResult e681, g_bLinkCtrlShadow f794,
    g_bLinkState fdd5, g_bWireId fdca) with repeatables. The comment-
    rewrite pass (cite labels, not raw addrs) is still open.
  * DATA-TYPING proposals (investigate, not yet applied): ROM00 7d80 word
    [104] + 7e50 word[~27] fn-ptr tables, 7c50/7c30 font-metric data,
    ROM01 7545-7fff config-descriptor table, ram:e105 font copy, ram:d0e0
    error-string table, ram:f1f9 (already typed as BdosFnHandlers).
  * CHURN: 15 FUN_* re-triaged (all real session coroutines, LD DE,0/d837
    proem, in the ROM00 session TX/RX code gaps) -> named SessionSub<addr>;
    their proper plates are queued. FUN_* = 0.
  * NEXT: proper plates for the 15 SessionSub* + data-typing apply +
    comment-rewrite labels migration; guarded re-bases (2f74/52a5/4a25);
    merge boot_hw_visible.py into boot_hw.py.
- 2026-08-27 (LinkProbe question + emulator-chase note; documented):
  * Owner-flagged: LinkProbe (348a) is called ONLY by ColdStartSelftest
    Banner (self-test), so the session-connect "Plinth not connected" must
    use a DIFFERENT probe. OPEN: which fn probes the link during connect
    (LinkPresent 34ec / LinkWaitReady 34f8 / SessionConnectCheck 2b43?).
    Documented in protocol/commstar.md "Error-path triggers".
   * EMULATOR NOTE: chase "No program in memory" by driving Load/Run
     Program in boot_hw_visible.py and tracing which BDOS/session error
     code populates d0e0 and e48d/e488. (Error-code->string table is
     runtime-built; not statically visible.)
- 2026-08-27 (byte-verify wave-2 fix + boot_hw merge verified; main):
  * BdosSwpDirectory (ram:f535) plate CORRECTED: copies 0x80 bytes FROM
    the F8B8 directory buffer TO [FFA3] (the BDOS DMA address) - the
    earlier plate had the direction reversed. Byte-verified: HL=[FFA3],
    EX DE,HL -> HL=F8B8 src, DE=[FFA3] dst, KernMemCopy(HL=src,DE=dst).
  * Two data-cell plates corrected in the same pass: FFA3 is a 2-byte
    DMA POINTER (set by BDOS fn 1A at BdosSetDmaAddress), not a
    "128-byte record cell"; F8B8 = directory buffer that SwpDirectory
    copies OUT of (not into). FEFF staging-buffer plate was already
    correct. TASKS.md 2026-08-25 block-I/O-layer entry updated to match.
  * boot_hw.py MERGE VERIFIED: it is the canonical single harness
    (LCD+expect+banking+snapshot+--help), --help smoke-tested clean;
    usage examples now cite analysis/boot_hw.py (was boot_hw_visible.py).
    boot_hw_visible.py and boot_hw_serial.py both DELETED (fully
    superseded). boot_hw.py header docstring + analysis/README.md emulator
    section rewritten for the single canonical harness.
  * Added TASKS item 11: decode the error-screen format (owner observed
    "Error 8000 (238/001) Plinth not connected") - identify the three
    numeric fields, byte-verify, document as an "error screen format"
    section.
- 2026-08-27 (documentation Mermaid rendering + validation):
  * Fixed the HTML builder's module import to load Mermaid's ESM bundle;
    the previous import treated the non-ESM bundle as a default-exporting
    module, so diagrams did not render.
  * Fixed a sequence-diagram note whose semicolon Mermaid parsed as a
    statement separator. All three diagrams now parse successfully.
  * Added `build.py --validate-mermaid` and `make validate`; these run
    every Mermaid fence through `mmdc` and identify the source file and
    diagram number on failure.
- 2026-08-27 (WaveDrom documentation integration):
  * Added client-side rendering for `wavedrom` WaveJSON fences and a
    matching `--validate-wavedrom` build option using WaveDrom CLI.
  * Added a representative, explicitly not-to-scale timing diagram for
    the barcode edge-capture loop. Its store-on-edge behavior was
    byte-verified at ROM00:13E5-1402; WaveDrom 3.6.2 parsed both current
    WaveDrom examples successfully.
  * Browser integration corrected after review: WaveDrom 3.6.2's engine
    expects `window.WaveSkin`, so the pinned default-skin bundle now loads
    before `wavedrom.min.js`. A DOM smoke test rendered the example SVG.
  * Validation no longer uses `mmdc`: Mermaid CLI pulled Puppeteer plus
    Chrome/`chrome-headless-shell` merely to check syntax. The builder now
    calls pinned Mermaid 11.17.2's `parse()` API under jsdom and WaveDrom's
    browser-free CLI; all five current examples validate without Puppeteer.
- 2026-08-27 (keyboard keymap + UI field-edit keys; main):
  * KEYMAP TABLE LOCATED: ROM00:1b58 (labelled tbl_kbd_map) is a three
    36-byte-page keymap (base in ram:fbda, set at ColdStartSelfTestBanner
    / KbdScanRowDecode). Page 0 unshifted (ASCII letters; 'N'=0x4E idx21,
    ENTER=0x0D idx22), page 1 shifted (+0x24), page 2 special (+0x48,
    fbdd==2; 'Z'=0x5A idx21). Function keys use codes 0x01/0x06/0x0b/
    0x0c/0x11/0x12/0x14/0x1a/0xd0. Kbd_ScanMain (18f0) produces the code
    into fbe7 -> key ring -> ec41.
  * FIELD-EDIT KEY DISPATCH: Ui_FieldEditPumpLoop (1e0a) reads ec41 and
    tail-jumps to CALL ram:e0b2 with inline dispatch table at ROM01:1f99
    (labelled tbl_fieldkey_dispatch): 0x06/0x0b->1e61, 0x01/0x0c->1ea1,
    0x11->1ece, 0x12->1eed, default->1f23. SessionKeyProcess (40c4)
    branches on 0x01/0x06/0x11/0x12.
  * OWNER KEY MAPPING (hardware, for emulator input): N/Z key edits the
    active field value; YES/NO keys move between fields. Codes: N=0x4E,
    Z=0x5A, YES/NO=0x11/0x12 (which-is-which direction TBD), ENTER=0x0D.
    Recorded in the two Ghidra plates; emulator chase to use these.
- 2026-08-27 (error-screen format CLOSED; investigate + main, applied):
  * TASKS #11 answered (investigate agent, byte-verified by main): the
    "Error 8000 (238/001) Plinth not connected" screen is rendered by
    SessionStateBuild (4351) via SessionMessageBox (4296). CONFIRMED:
    8000 = major error qualifier literal 0x1F40 (8001 = 0x1F41 for the
    0x0009 connect-check case), 11-digit space-padded; NOT e488 (code 6).
    "(238/001)" = RCV1/RCV2 session status from e701/e6ff (3-digit
    zero-padded), template at ROM00:7310 (now tbl_sess_status_fmt) with
    field names RCV1/RCV2/SEND/LOAD/PROG/TIME/ENDC. Annotated: plates on
    7310/e488/e701(g_wSessRcv1)/e6ff(g_wSessRcv2)/SessionStateBuild; EOLs
    at 47ca/47b7/47d0/4380/4399. protocol/commstar.md gained "Error/status
    screen format (CONFIRMED)".
  * MISNOMER FLAGGED: ROM00:403b (named FileSearchNextCb) is actually a
    decimal-to-ASCII formatter (div-10 digit loop + 0x30); used by
    SessionStateBuild. Rename queued (needs rename-hygiene pass).
  * "No program in memory" emulator chase: partial. General agent booted
    to Load/Run Program (From defaults to PLINTH; ENTER there goes to
    "Log-on information / Mode LOCAL_LINK"). The field-move keys (0x11/
    0x12) injected via the ring do NOT change the From selection in this
    harness build, so the agent forced the branch with a RAM patch
    (0xE00E=0) and reached the error screen:
    "PARCON 1000 / *** Error *** / <major> / No program in memory",
    with major qualifier shown as 9000 (SUSPECTED - patch-induced, the
    pushed constant is not cleanly byte-verified; agent muddled 0x1F40).
    e488/e48d/e681 stayed zero (patch bypassed the setter). d0e0 dump
    starts ".Consult Dealer." (runtime error-string table). OPEN: map
    the physical key matrix / ring bytes to the field-move so the UI can
    be driven without a RAM patch, then re-trace the real qualifier.
- 2026-08-27 (tie-up: formatter + SessionSub* + dispatcher format; main):
  * FileSearchNextCb -> FormatDecU16 (ROM00:403b). CONFIRMED decimal
    formatter (div-10 + 0x30, two-pass leading-zero->pad, null-term at
    [width]); stack args value/dest/width/pad at SP+0x0C/0x0E/0x10/0x12.
    Callers: SessionStateBuild (error-screen), FileSearchFindNum.
  * SessionSub* naming applied:
    - SessionSub16 -> Lib_Sub16 (ram:e0a9); plate CORRECTED: Z flags the
      FULL 16-bit result (OR L), not just the low byte.
    - SessionSub612A -> Session_FieldParseValidate (ROM01:612a).
    - SessionSub620C -> plate updated: field loop, SUSPECTED dead code
      (init block 61d0-620b unreachable).
    - DELETED SessionSub5DFD (mis-bounded fragment; real entry 5df2) and
      SessionSub6431 (basic block inside Ui_DescFieldEditMenu, entry is a
      NOP). Function count 779 -> 777, saved.
  * SessionCommandDispatch (ram:e0b2) inline-table format CONFIRMED from
    two dumps: {count:word}{case_lo,case_hi,handler_lo,handler_hi}xN
    {default:word}. Documented in the plate; 5e2e dispatch (CmdRetryCounter
    retry index) case 0/1/2 -> 5df2/5e04/5e17, default 5e41.
  * "No program in memory" qualifier agent LOOPED (repeated itself) and was
    cancelled - still OPEN.
  * Emulator field-navigation: PROGRESS. YES/NO are 0x06/0x01 (not
    0x11/0x12) - byte-confirmed in the keymap + dispatch table; they move
    DOWN/UP a field. N/Z (0x4E/0x5A) are plain letters and TYPE into a
    text field (the "From" field is free-text, default "PLINTH"); no CP
    0x4E/0x5A exists in the field-edit path, so the owner "N/Z cycles the
    value" is NOT how this firmware build behaves - OPEN to reconcile
    (documented in micronic_notes.md). keymap/dispatch tables annotated.
- 2026-08-27 (InlineTableDispatch: rename + struct + typed all 26 tables):
  * ram:e0b2 renamed SessionCommandDispatch -> InlineTableDispatch; plate
    and EOL comments thrown out and redone from the code. Format byte-
    verified (NOT the earlier "sentinel" guess): {count: u16le}
    {case: u16le, handler: u16le} x count {default_handler: u16le}. The
    leading count is loaded once and DEC'd per probe; underflow (D<0)
    enters the trailing default. No per-entry sentinel.
  * Defined struct DispatchTableEntry {caseValue: word, handler: word}
    and typed ALL 26 inline tables after CALL InlineTableDispatch via a
    Ghidra script (clearListing + createWord/array/word), with
    COMPUTED_CALL references added to every handler + default target.
    Function count unchanged (777). Saved. protocol document updated.
- 2026-08-27 (dispatch handlers -> functions; handler field -> pointer):
  * handler field of DispatchTableEntry retyped word -> pointer (the 'p'
    key equivalent). Iterated to fixpoint: 27 inline tables (the 27th at
    ROM00:4cc8 is nested inside handler FUN_ROM00__4c2c), every handler +
    default target now has a FUNCTION starting at its address (144
    targets, verified ok=144 bad=0). Function count 777 -> 935 (all
    additive - new handler functions; no losses). Saved.
  * Field-edit dispatch semantics decoded (1f96 table): 0x06/0x0b -> 1e61
    (next field), 0x01/0x0c -> 1ea1 (prev field), 0x11 -> 1ece (first
    choice), 0x12 -> 1eed (last choice), default 1f23 (choice-table
    letter-match). So 0x11/0x12 are first/last, NOT cycle - the "N/Z
    cycles the From value" key is STILL unresolved.
  * NEXT (large): annotate the ~96 new handler functions (name + plate +
    labels) - dispatch via annotate agent, serialized. Continue the
    choice-cycle trace (d8ce transform + the From field's choice table).
- 2026-08-27 (MkDocs diagram rendering):
  * Added MkDocs custom fences and ordered client-side Mermaid/WaveDrom
    assets. Mermaid fences now become Mermaid containers; WaveDrom fences
    are converted from escaped code to the `script[type=WaveDrom]` format
    required by WaveDrom after the document loads.
  * Restored a non-session Mermaid sequence diagram for the CONFIRMED
    controller-facing transmit ordering in protocol/commstar.md. The former
    host/peer and state diagrams remain intentionally absent: the current
    protocol evidence does not establish normative session transitions.
- 2026-08-27 (cycle key pinned; form/template functions named; docs mkdocs):
  * CYCLE KEY PINNED: the next/prev value cycle is YES/NO (0x06/0x01),
    and their Sun variants Sun+YES=0x0B / Sun+NO=0x0C - NOT N/Z. The 1f96
    dispatch handlers increment/decrement the choice index e739 and the
    5-byte-stride cursor e734 (byte-verified: 1e8b INC e739 / e734+=5;
    1eb8 DEC / e734-=5). 0x11 -> first-choice (1ece), Sun+ENTER=0x12 ->
    last-choice (1eed), default 1f23 = letter-match. So the owner "N/Z
    cycles the value" is NOT what this firmware does - N/Z (0x4E/0x5A)
    type letters and fall to the letter-match default. OPEN: reconcile
    with owner on hardware.
  * KEYMAP CORRECTION: Sun+YES = 0x0B (idx23 page2), NOT 0x11 (earlier
    mis-read). Full Sun page: Sun+NO=0x0C, Sun+ENTER=0x12, Sun+YES=0x0B,
    Sun+N=Z=0x5A, Sun+J=Y=0x59, Sun+F=X=0x58, Sun+backspace=0x1A, and
    0x11 at idx34 (col5 row4 = no physical key). tbl_kbd_map + 1f99 plates
    corrected.
  * RENAMED: Ui_CommSetupFormInit (060b) -> Form_InitFromTemplates (it is
    generic form init, builds 3 template instances via TemplateBuilder
    0271); FUN_ handlers -> Form_ChoiceNext/Prev/First/Last/LetterMatch,
    all plated. Device-name table at ROM01:757f (WORKSTATION MEMORY,
    WORKSTATION RAMDISK, PLINTH, V24 ADAPTOR, EXT STORAGE ADAPTER),
    embedded in form template 758b (+0x0c), built by TemplateBuilder.
  * DOCS: mkdocs restructure adopted. Updated TASKS.md/AGENTS.md doc-path
    references to the new layout; Makefile + BUILD.md are now mkdocs-only;
    deleted legacy build.py, validate-mermaid.mjs, package.json/lock.
    (committed 46a2c52)
- 2026-08-27 (user guide + forms-UI docs; plan set):
  * Added manual/user-guide.md (boot, keypad, special keys, field
    navigation, menu map, error screens + codes, error list, error
    recovery) and internals/forms-ui.md (form model, TemplateBuilder,
    device table 757f, 1f96 field-edit dispatch, keymap, error renderer).
    Wired into mkdocs nav + README indexes.
  * Error messages enumerated (ROM00:6d40-6e10): Plinth not connected /
    Line failure / Modem fault / Failed to connect / Invalid reply /
    Invalid command / Invalid data string / Not available + statuses
    (Program received, Session complete, Logging on/off). Qualifiers
    confirmed for Plinth (8000=default, 8001=case-9); the rest are
    ROM-derivable (each error site pushes its own literal) and queued.
  * PARKED (hardware-gated, owner-decision): N/Z vs YES/NO cycle key;
    function-label effects (CHNGE/REFER/HELP/INSRT/F1/F2/STWDL/LIGHT);
    menu-item selection mechanism; Diagnostics sub-menu + self-test
    screens. Documented in user-guide.md "To confirm on hardware".
  * NEXT (user-guide plan): trace the per-error qualifier literals (ROM-
    only), map the Diagnostics sub-menu + self-test screens, finish the
    menu map field detail. Then fold into the final annotation pass.
- 2026-08-27 (error-code map complete; self-test screens added):
  * ERROR CODES DECODED: the error-screen <major> is a per-site error code
    (decimal 8000-series = 0x1F40+), byte-verified across all 21 sites:
    Plinth not connected 8000/8001; Failed to connect 8010,8012-8015;
    Not available 8011,8055,8056,8151,8165,8166; Modem fault 8016;
    Line failure 8050,8054,8150,8160,8164; Invalid reply 8053,8163.
    So the same message text appears at several codes - the code is the
    source-error-site id, the message is the class. This settles the
    original "Error 8000 (238/001)" question: 8000 = site code,
    (238/001) = RCV1/RCV2 counters, message = class text.
  * Renamed the msg wrappers: Session_ShowLineFailure -> SessionMsgLine
    Failure; FUN_44a5/44bd/44d5 -> SessionMsgFailedToConnect /
    SessionMsgInvalidReply / SessionMsgModemFault; SessionShowMessage
    (443c) plate carries the full code->message map. Saved.
  * user-guide.md: complete error list + status lines + loader errors
    (No program in memory / Requested program not in memory / Program not
    built for this system / Program corrupt); boot self-test screens added
    to the menu map. Diagnostic menu sub-detail still to trace (ROM-only).
- 2026-08-27 (Diagnostics menu + "invalid" strings: partial, parked):
  * Diagnostics menu (Main Menu item 4) is defined by a self-referential
    menu template at ROM01:7860-78d0 (item strings "Set Debug mode"/"Set
    Debug Mode" 7b52/7b61, "Status" 7b70, "Device" 7b77; embedded
    pointers 7874/789c/78a0 + action bytes 03/05). It is rendered by the
    same TemplateBuilder (0271) machinery as the form templates. The
    per-item HANDLER addresses (which screen each opens) are inside the
    nested pointer records and need a full menu-template decode - parked
    as a sub-project (ROM-only, no hardware).
  * "Invalid command" (6dfa) / "Invalid data string" (6e0b) have no direct
    xref and no SessionMsg wrapper (unlike "Invalid reply" 6de9 = 44bd).
    LIKELY they are field-VALIDATION messages shown inline (not via the
    error banner), same as the typed-value validation path. Discriminating
    test: find the field-edit code that compares typed input and renders a
    rejection string. Parked.
- 2026-08-27 (screen template struct + field validation; protocol errors):
  * SCREEN TEMPLATE format decoded (ScreenTemplateHeader struct, 14 bytes,
    applied to 758b/75eb/760d): {buildStub, stub2, stub3, stub4: pointer}
    {flags: word 0x0801}{count: word 0x0120/0x0020}{dataPtr: pointer -
    the field's choice/string table, 0x757f for the comm form}. Records end
    0xfffe. TemplateBuilder (0271) is used ONLY for these 3 form templates;
    the MENU (ROM01:7860) is a different structure (menu item records
    {string, action}) rendered by a separate handler.
  * FIELD VALIDATION (investigate agent, byte-verified key claims): four
    field-type validators (ROM00 582a/5834/583e/5848) + Session_FieldParse
    Validate (612a: numeric parse vs limit table e34f by field idx e88f);
    they return HL=0 on rejection and do NOT raise the banner. "Invalid
    reply"/"Invalid data stream" are session PROTOCOL errors dispatched by
    Session_ProtocolErrorDispatch (4f37): 0x09->"Not available"(8102),
    0x0A->"Invalid data stream"(8101). "Invalid command" (6dfa) is DEAD
    (zero refs). Er007 error list updated with 8101/8102; forms-ui.md now
    documents the template struct + validation.
  * OPEN (menu): decode the menu-item record format (ROM01:7860) and its
    per-item handlers - separate sub-project, still pending.
- 2026-08-27 (menu record format decoded):
  * Main Menu table decoded (tbl_menu_main ROM01:772d): title {label ptr,
    attr} + 4 MenuItem records {key:u8, label:ptr, attr:u16}. '1' Load/Run
    Program(0104), '2' Set Clock(0105), '3' Display Status(0106),
    '4' Diagnostics(0001). Selection = type the digit (letter-match on key).
    MenuItem struct defined + applied; menu-advance handler located at
    ROM01:5114/510d (stores key in e84d). Diagnostics menu (7860) is a FORM
    with choice entries (Set Debug mode/Status/Device), not a keyed menu -
    its per-item target screens (attr -> screen id) still to trace.
- 2026-08-27 (menu handlers + programmer-guide cross-refs):
  * Menu machinery pinned further: the menu-table header (7722) holds
    handler ptr 0x510d = the menu label/index resolver (reads key + table,
    indexes table[key*2], strlen/copies the label); 0x5114 = second menu
    handler. Window title "PARCON 1000" (7a82) precedes "Main Menu"
    (7ac4). The remaining attr -> screen-builder dispatch is the one open
    piece. forms-ui.md updated; programmer-guide.md §3 gained a "shell's
    own screen UI" cross-reference (menus/forms are not a BDOS library;
    8000-series banner is the shell's, not the program's).
- 2026-08-27 (attr->screen mapping resolved empirically via emulator):
  * Drove boot -> Main Menu -> digit with the harness. Main Menu: '1'
    Load/Run (Name/From), '2' Set Clock (Time 00.00, Date 01/01/84),
    '3' Display Status (Version Q229, Serial No., total RAM 256k, RAMdisk
    size), '4' Diagnostics. Diagnostics has a single entry "Set Debug
    mode" (attr 0x0003) -> "Set Debug Mode" screen whose FIELDS are
    Status (ON/OFF) and Device (PLINTH). "Status"/"Device" (7b70/7b77)
    are field labels, not menu items (corrects earlier reading). 0x5114
    is a mis-aligned pointer into the 0x510d handler, not an entry point.
    user-guide.md menu map + forms-ui.md Menus section updated.
- 2026-08-27 (DIP executable format specification):
  * Wrote manual/program-formats.md as the byte-level spec: COM (no
    header, load at 0100h) + DIP. RECORD GRAMMAR CONFIRMED (record
    dispatcher SyscallDispatch ram:d6db, handler table ram:d6f4): fn=0
    memset {fn,addr,count}, fn=1 memcpy {fn,src,dst,count}, fn=2 enqueue
    {fn,N,addr[N]} -> N x {0xD7,bank,addr} stubs at queue d684, fn=FFFF
    terminate (wrap d6f4+2*0xFFFF -> d6f2 -> d6ee pop+ret). CHECKSUM
    CONFIRMED (ChecksumBytes ram:d7d1 = 16-bit additive byte-sum, not CRC).
    ROM footer 7FF0-7FFF (chain ptr at 7FFA/7FFC; 7FFE = candidate system
    ID). MISNOMER FIXED: SyscallLoadBlockToMem -> SyscallMemset (it zero-
    fills, not copies); renamed + plated all 5 loader primitives; doc
    mention corrected in os-diposb.md + programmer-guide.md.
  * DIP FILE HEADER still OPEN: the parser is in module A (ROM00:73CE ->
    ram:D893, 2145 bytes, boot-chain memcpy at 7D74), not disassembled.
    Header REQUIRES (from ROM01 error strings 7d3c-7d9d): magic ("Bad DIP
    file"), system ID ("Program not built for this system"), size ("too
    big"), block count ("too many blocks"), checksum ("corrupt") - exact
    offsets unknown. Decoder/linker for the RECORD stream is safe to build
    now; a full DIP file ENCODER needs the header pinned (disassemble
    module A, or capture a DIP from a live link session).
- 2026-08-27 (Module A dug into - DIP parser NOT there; loader primitives boot-only):
  * Disassembled Module A (ram:D893-E0F3, 1360 instr) and Module B
    (ram:D081-D2CA, 471 instr) in Ghidra. Module A = session file/FCB/
    string fns (Fcb_CharTrans area, BDOS RST-8 caller) - NO reference to
    the loader primitives (d6db/d6f4/d6fa/d713/d727/d7d1) or the DIP
    error strings. Module B (ROM01:7BCB, 586B) is DATA: the banner
    "PARCON 1000\n*** Error ***" (D090) + ALL the program-load error
    strings (D1BD "No program in memory", D1F2 "DIP file too big", D203
    "Bad DIP file", D210 "COM file too big", D221 "Program not built...",
    D243 "Program corrupt", D253 "DIP file has too many blocks").
  * KEY: the kernel loader primitives (d6db record dispatcher + handler
    table d6f4 + d684 queue) are referenced ONLY by the boot-chain feeder
    (ROM00:7038 CALL d6db for both banks' 7FFC chains) and kernel init
    (d681/d691). NOTHING at runtime (ROM01 app, module A/B) references
    them - so the runtime DIP program loader is a SEPARATE path that does
    NOT flow through the boot-chain record grammar. This weakens the
    earlier "DIP uses the same grammar as the boot chain" claim; the boot
    grammar proves the loader MACHINERY, not the runtime DIP container.
  * Corrects investigate_deep's inference (it claimed the parser was in
    module A D893-EC6C - wrong; module A is D893-E0F3 and contains no
    parser). DIP parser still to locate - likely ROM01 Load/Run Program
    handler or the dispatch-module RAM block d681+. Header offsets remain
    OPEN (see manual/program-formats.md).
- 2026-08-27 (Load/Run loader path - traced to the runtime-stub wall):
  * Load/Run Program form template at ROM01:7750 (and the Main Menu table
    at 7720 and Diagnostics at 7860 all share the same form/menu
    descriptor grammar). The Load/Run form has fields {label "Name"
    0x7b04, attr 0x0005} and {label "From" 0x7b09, attr 0x0104}. Form
    descriptors carry 4 "stub" handler pointers that are RAM addresses in
    the ZEROED region (e.g. 0xef50/0xef3c/0xefec/0xf0f8): these are
    INSTALLED AT RUNTIME by the boot-chain's enqueued constructor calls
    (bank0 enqueues 134 far-call stubs, bank1 147) - NOT statically
    present. So the program loader (and its DIP header validation) is a
    runtime-installed form-submit action, not reachable as static ROM code.
  * CONCLUSION for the DIP spec: the header cannot be pinned from static
    analysis alone. Discriminating observations: (1) trace the boot-chain
    enqueued constructors to find which one installs the loader/forms stubs
    and then read the installed code at ef50/ef3c ...; or (2) emulator:
    drive Load/Run with a crafted DIP file and watch the ef50/ef3c stub
    execution + which BDOS reads the header; or (3) capture a real DIP file
    from a live Commstar session. Record grammar + checksum remain CONFIRMED
    and safe to implement (see manual/program-formats.md).
- 2026-08-27 (constructor trace - efec mystery RESOLVED; DIP loader is a user action):
  * Emulator dump of ram:efec settles it: efec holds {RST10h(0xD7), bank,
    target} 4-byte TRAMPOLINES = the deferred-call queue (the 134 bank-0 +
    147 bank-1 enqueued constructors). At earliest boot it holds the
    default "LD HL,1; RET" stub; after the queue is drained it holds the
    banked-call stubs (bank 0x01 targets 4FB0/5B2D/51C1/0115/4B69... =
    exactly the chain-B constructor list). So the form templates' four
    "stub pointers" (0xefec/0xf0f8/0xef98/0xefd8) are TRAMPOLINE SLOTS,
    not direct function code - the form builders are ROM01 functions
    bank-called through them. This means the whole form/loader machinery
    IS statically reachable ROM01 code (not battery-RAM code), correcting
    the earlier "runtime-installed / untraceable" conclusion.
  * But the constructors are boot INITIALISATION. The DIP loader is a
    USER ACTION (Load/Run Program -> ENTER on the From field), not a boot
    constructor - so it is a ROM01 function reached from the form's
    submit/load path, not in the constructor set. Next: trace the
    Load/Run form submit action to that function (forms use {label,attr}
    records; attr 0x0104 = the load action), or emulator-drive Load and
    dump the execution/BDOS trace to spot the header read.
- 2026-08-27 (forms/UI: trampoline stubs + exit-dispatch loop documented):
  * emulator dump settled the "stub" question: the form-template's four
    stub fields are 4-byte banked-call trampolines {RST10h, bank, target},
    initialised to "LD HL,1; RET" and later filled by the boot-chain
    deferred-call queue (134+147 constructors). Form builders = ROM01
    functions via d828, NOT battery-RAM code.
  * Ui_FormExitDispatchNext (ROM01:06d3) = the form-transition loop: walks
    a 5-entry double-indirect table at ram:d081 (module B head) and
    bank-calls each callback, then rebuilds the comm form (060b) + posts
    descriptors 7715/7751 (Ui_PostDescriptor 6633). forms-ui.md updated
    (trampoline semantics + new "Screen transition dispatch" section).
  * DIP loader STILL one step out: it is the Load/Run form's submit action
     (ENTER on From), reached through this dispatch/descriptor machinery -
     the exact function that reads the DIP header is not yet pinned. Emulator
     drive (craft a bad DIP/COM, watch the header read + "Bad DIP file"
     error-code setter) remains the recommended fallback.
- 2026-08-28 (runtime DIP/COM loader — documentation maintenance, reviewed findings):
  * **Overturned**: (a) runtime DIP funnels into `ram:D6DB` / safely uses
    `fn=0/1/2/FFFF` grammar — **distinct**: `D6DB` is boot-only; runtime DIP
    has its own 14-byte header + 8-byte blocks; (b) exact DIP header still
    open — **closed**: header 14 bytes `{magic 0xC8C9, sysID 0/0x00E5,
    entry-bank, size clamped 0x8000, run-bank, entry addr, blockCount max 5}`
    LE, plus block `{type, dest bank off, dest addr, payload count}+payload`,
    type 0 direct / type 1 RST10-trampoline expansion; (c) `g_tblFieldTypeRecPtrs`
    as device callbacks — now `g_apScreenHandlerTables` (five per-screen
    tables indexed by selector at `ROM01:034B`, entry 0 → `g_apLoadRunHandlers`
    at `ram:D0F0`); `Ui_FormExitDispatchNext` double-dereferences; (d)
    `ram:D681` as runtime COM/DIP block — now kernel dispatch/boot-loader
    block, runtime loader is `ROM01:0A67-10CE`; (e) old prose names
    `UiDialogOpen3F`/`UiDialogListItem`/`Dialog_StateCheck`/`UiCloseDialog`/
    `SessionHelperRouter0CE7`/`DialogListAction` superseded by
    `Program_*`/`Ui_FormExitDispatchNext`/`g_apScreenHandlerTables`; (f)
     `Bad DIP file` as bad magic — now `0x232B` (9003), "Bad DIP file." =
     truncated block header/payload; `0x2332` (9010), "Program corrupt." =
     block-checksum mismatch
    (`0957` add at `+8` vs `09C2` recompute, i.e. loaded memory changed);
    (g) COM fallback now `<14 bytes` or first word `!=0xC8C9` → `0x0100`.
  * **Exact format (CONFIRMED unless noted)**: DIP header 14 bytes as above
    (LE); blocks 8-byte header + payload; type 0/1 only (other type →
    default/next logic only if applicable, phrased explicitly). Runtime
    expands to 10-byte `DIP_LoadedBlockDescriptor` (checksum at `+8` via
    `Program_GenerateBlockChecksums` `0957`, NOT in file; verified by
    `Program_VerifyBlockChecksums` `09C2`). `ram:ECDA` max entry-bank
    offset is **LIKELY** only. Loader functions named:
    `Program_PrepareLoadGeometry` `0A67`, `Program_LoadByName` `0B82`,
    `Program_ConsumeInputChunk` `0BAC`, `Program_LoadDipOrCom` `0CE7`,
    `Program_RunByName` `106F`, `Program_NormalizeLoadRange` `0AE3`,
    `Program_ReportLoadError` `0CCB`, `Program_GenerateBlockChecksums`
    `0957`, `Program_VerifyBlockChecksums` `09C2`, final `10C6→ram:D7F0`
    `RunLoadedProgram`. No BDOS execute; provider around `0C12`/`0CE7`/
    `ram:D370` still open.
  * **File layout no longer open**; open item updated: physical
    input-provider path / captured real DIP remains open.
  * Docs updated: `program-formats.md` (rewritten), `programmer-guide.md`
    §7b, `forms-ui.md`, `memory-map.md`, `os-diposb.md`, `user-guide.md`,
    `TASKS.md`, `gap-analysis.md` (827 functions). Build `mkdocs build`
    run; no commit.
- 2026-08-28 (COM size ceiling + DIP execution-field semantics):
  * **COM maximum CONFIRMED = 0xCF81 bytes (53,121)**. Kernel startup
    writes D081h to `g_pProgramLoadCeiling` (`ram:D6A3-D6A8`); COM starts
    at 0100h, so capacity is `D081-0100=CF81`, covering 0100h-D080h.
    D081h is not an aligned format constant: the bank-1 boot record at
    `ROM01:7E23` copies resident module B `7BCB→D081`, length 024Ah, making
     D081 the first occupied resident byte. Further COM input reports
     `0x232C` (9004), "COM file too big."
  * Header-field use documented: entry-bank offset + image size establish
    the load range relative to `g_wProgramBankBase`; run-bank offset is
    resolved separately before execution; entry address is the Z80 target
    passed to `RunLoadedProgram`; block count drives 0..5 file-block and
    runtime-descriptor iterations.
  * Ghidra: labelled/typed `g_pProgramLoadCeiling`, annotated its startup
    writer, COM remaining-capacity calculation/error path, boot copy record,
    runtime DIP header and loader plates. Program saved after verification.
- 2026-08-28 (documentation quality review):
  * Added `doc/review.md`: a programmer-manual review of the published
    documentation. It records the incomplete BDOS/RTC/configuration ABIs,
    barcode-hook example risks, storage-guidance conflict, deployment/tooling
    gap, terminology cleanup, and a prioritised roadmap. No firmware finding
    or Ghidra annotation was changed. `mkdocs build --strict` passes.
- 2026-08-28 (reviewer-approved link transaction byte verification):
  * **Finding (all ROM00, CONFIRMED mechanical):** `LinkBlockTx` 3277-3377
    and `LinkBlockRx` 3378-3453 mechanically drive `LINK_CTRL` (4Ah) and
    poll `LINK_STATUS` (4Bh); no electrical names for status/control bits are
    proven. TX ordered sequence: clear ctrl b0, set b0, clear b4, `B=0x80`
    DJNZ delay; `LinkPresent`→`LinkWaitReady` polls status b7 `DE=0x02DA`
    then `0x81` to `LINK_CMD`; low five bits of input `A` (held `C`) to
    `LINK_TXD`; wait status b4 `DE=0x026C`; set ctrl b5, set ctrl b4,
    `B=0x20` delay, clear ctrl b5, wait status b6 `DE=0x026C`; each `OUTI`
    to `LINK_TXD` gated by status b7 `DE=0x06F9`; cleanup clears ctrl b4,b0.
    RX: clear b0, set b5, single `LINK_RXD` read, set b4, `B=0x20` delay,
    clear b5; `INI` from `LINK_RXD` only if status b0 set; if b0 clear,
    b1 set continues b2/b3 decode while b1 clear waits/retries `DE=0x06F9`;
    b2 set extra `INI`; b3 set `EC`; cleanup toggles b1, sets/clears b0,
    clears b4, toggles b1. `LinkProbe` emits `0x1F` to `LINK_PROBE` then
    latch sequence; physical/reset meaning remains SUSPECTED.
  * **Docs updated:** `protocol/commstar.md` rewritten to list only
    mechanical bit numbers and timeout constants, removing unqualified
    electrical labels (`TX-ready`, `RX-ready`, `ACK`, `peer-ready`/`type`,
    `idle/run`, `talk`/`RX-enable`, `clock`, `IR select`) and adding the
    ordered TX/RX/Probe sequences plus Probe SUSPECTED note;
    `internals/io-map.md` revised (4Ah/4Bh rows, Interface-shape section,
    Ghidra label table) to report only confirmed drive/poll behaviour.
    Owner statement preserved: link-id bit 5 selects one of two IR line
    states (V24 ADAPTOR top vs PLINTH back) via `LinkPortSelect`; which
    `LINK_CTRL` bit 1 value maps to which physical connector remains OPEN.
   * **Ghidra:** retained the existing `LINK_CTRL`/`LINK_STATUS`/`LINK_CMD`/
     `LINK_PROBE` labels; added plates and EOL comments to `LinkBlockTx`,
     `LinkBlockRx`, `LinkWaitReady`, `LinkPresent`, and `LinkProbe` for the
     CONFIRMED mechanical sequence. Electrical semantics remain OPEN and were
     not encoded as repeatable claims. Program saved; function count remained
     827.
  * **Open electrical semantics:** the mapping from status/control bit
    numbers to electrical functions (`TX-ready`, `RX-ready`, `ACK`,
    `peer-ready`, `idle/run`, etc.) and the `LINK_PROBE` physical/reset
    effect remain unproven and require a hardware trace / bus capture to
    resolve.
- 2026-08-28 (programmer-manual review actions):
  * Added `manual/supported-profile.md` and made it the programmer-manual
    starting point. It states the CONFIRMED COM boundary and explicitly
    excludes unsafe dispatch, configuration mutation, barcode hooks, and
    unproven Commstar interoperability.
  * Reclassified the BDOS index as ABI evidence rather than a blanket
    supported API, updated navigation, and standardised the guide on `RST 10h`
    (restart vector 2). Added a no-hardware priority order above the hardware
    capture tasks. Contract cards, host-side validation tooling, emulator peer
    work, and final annotation remain open.
- 2026-08-28 (reusable link peer and duplex regression):
  * Added `LinkPeer` to `analysis/micronic/proto.py`: a reusable M1000-facing
    queue/latch peer with captured TX, queued RX, control/command/probe logs,
    and explicitly configurable non-data status bits. It deliberately names no
    electrical bit function.
  * `analysis/comms_duplex.py` now uses that peer to run the real firmware
    byte pumps in both directions. CONFIRMED software result: firmware TX
     writes `05 04 44 00 "from-M1000"`, parsed by the adapter model; firmware
     RX consumes all 14 bytes of the adapter's
     `05 03 04 E0 "reply-to-M"` stream. This does not establish session-level
     compatibility, live RECORD/BLOCK payload content, or physical timing.
- 2026-08-28 (documentation maintenance — reviewer-verified link header correction, Ghidra-applied):
   * **CORRECTED off-by-one (CONFIRMED):** `LinkValidateFrameHeader` (ROM00:30DC) compares RX logical offset **+4**, not +5, to `fdd4`. RX header is `+0..1 LE total length; +2 type; +3 per-link sequence; +4 active link id; +5 never read by ROM link code`. Previous docs (commstar.md validated-frame table, io-map.md address-filter line, `micronic/proto.py:validate_header`, `comms_rx_test.py` comment/frame) said +5 — fixed to +4.
   * **TX prefix (CONFIRMED mechanical, SUSPECTED meaning):** `LinkFramePrefixWrite` (ROM00:316B) writes TX offsets 0..4 as `{len LE, type, sequence, 0x7F}` and leaves offset +5 untouched. Constant `0x7F` at TX +4 is **SUSPECTED**; do not call it an id or broadcast.
   * **Transport framing constraints (CONFIRMED):** `LinkBlockTx` prelude is low 5 bits (`link_id & 1Fh`) sent before descriptor bytes and excluded from descriptor counts; `LinkBlockRx` returns `DE = bytes_read - 2` — identity of the two excluded bytes is **OPEN**. Descriptors: RX `FE0E {6->FDE4, 3->FE38, 0}`, RX `FE32 {9->FE3A, 0}`, TX `FDEA {6->FDDE, 0}`.
   * **Sequencing & replies (CONFIRMED):** sequence slot is `FE43h + (fdd4 & 3Fh)`, init 1; mismatch reply `01EF` tied to type-4 sequence check; reply word `03EE` exists along with `01EE,02E0,02EE,04E0,05E0,01EF` (now 7 values).
   * **Inline dispatch (CONFIRMED numeric cases, local control flow only):** `5A69` abort `44,45,60,61,64`; `53C7` `0..5`; `5410` `0,4,8,9`; `5291` `0,4,9` — do not name as wire commands. Table at `6A4A` is **CONFIRMED** 16 state-display pointers, not a wire map. Link path **no checksum verified**.
   * **Docs updated:** `protocol/commstar.md` (validated-frame table + validation sentence + LinkFramePrefixWrite/TX-0x7F note + LinkBlockRx/Tx prelude/DE-2 + descriptors + sequence slot + 03EE + numeric cases + 6A4A + no-checksum), `internals/io-map.md` (address-filter offset +4 and SUSPECTED/OPEN notes), `analysis/micronic/proto.py` (frame header docstring + `validate_header` offset +4), `analysis/comms_rx_test.py` (comment + RX frame construction to place link id at +4).
   * **Outstanding (OPEN/SUSPECTED, do not guess):** meaning of TX `0x7F` (SUSPECTED); whether offset +5 may be writable by loaded code (OPEN, never read by ROM); identity of the two bytes excluded from `LinkBlockRx` DE count (OPEN); session payload grammar and per-record/per-block byte content still runtime/open (needs live capture or loaded-module trace); connector mapping and electrical bit meanings remain OPEN.
- 2026-08-29 (documentation maintenance — reviewer-approved BDOS review corrections, Ghidra-applied):
   * **Applied established findings only (no new inference):** `Bdos_SelectRst28Mode` (`ram:F55A`), `Bdos_UpdateDriveDirectoryMetadata` (`ROM00:0D79`), `Bdos_InternalTimedWait` (`ROM00:1122`), `Kernel_ConditionalEnableInterrupts` (`ram:F54E`), `Device_LookupConfigEntry` (`ROM00:31FF`).
   * **Overturned false interpretation:** `fn04` (`ROM00:10D2`) was previously described as unsafe / non-returning via `RST 38h` with a stack switch — **superseded**. Correct decode is `CALL ROM00:31FF` `Device_LookupConfigEntry`; `E` preserved, `FBC5` high nibble selects `FE83` entry; descriptor `80h` local output else routed; normal `A=00h`, routed terminal error returns a path-dependent nonzero helper status, and both paths may wait/retry. Summary status **CONFIRMED**.
   * **Corrections applied to `manual/bdos-reference.md`:** normal path `0005->ram:F180-F1CE` joining `F382`, `F376` alternate, `HL=word[FEFA]`, `Kernel_ConditionalEnableInterrupts` name, unspecified-output rule (`BC`/`DE`/`IX`/`IY` not restored); `02h` four `A` results; `0Ah` `1Bh` counted literal block; `21h`/`22h` use `+21h`/`+22h` only (`+23h` not read; 31-byte copy stops before it); `2Dh` mutable mode selector (`FFh` `F57B` no-op, `FEh` `F57E` default, `FDh` `F59F` + `HL->FDBA`, `FCh` `F5C0`, else unchanged; `A` preserved; global unsafe); conditional behaviour of `0Dh`/`1Ch`/`1Eh`/`1Fh`/`30h`/`F4h` via `RST 28h`; `2Eh` drive-metadata not filename search; `FEh` timed wait (`E<<4`, `IY+23h`/`word[FEFA]`, `FD4D` `HALT`, `A=00h`); `FFh` `UIP` polling before both paths; hex suffixes `+0Ch`/`+10h`/`+20h`/`+21h..+23h`; table statuses aligned. Evidence tags preserved; `F376`/`F382`/`F54E` byte-verified envelope unchanged.
   * **Cross-document consistency:** `manual/programmer-guide.md` (`19h` `A` not `HL`, `1Ah` implemented, remove inert-stub grouping for diagnostics, `FEh`/`FFh` semantics, `FC`/`FD` 8-byte `+0` OPEN, configurable `A`/`B` vs `C`/`D` mapping, conservative extension safety); `internals/cp-m-comparison.md` (`06h` `E=FFh`, mutable diagnostics, `1Ah` implemented, configurable mapping, `F5` `<04h`→`0Fh`, `FEh`/`FFh`, handler `0C50`, `2Dh`/`2Eh`); `internals/os-diposb.md` (delete `FD->0DE9` etc. and point to correct `F3h-FFh` table, mutable diagnostics, `2Dh`/`2Eh`, `..//manual` link, `0008->F180` and `F5EA`/`F5ED`/`F5F0`/`F5F3` grouping); `internals/memory-map.md`/`internals/interrupts.md` (`0008->F180`); `manual/supported-profile.md` (diagnostic unsafe path); `doc/review.md` (superseded `1Ah`/`19h`/`02h`/`04h`/`FEh` claims marked). Current names are used in active docs; historical log entries retain their original names.
   * **Build:** `mkdocs build --strict` (see below); no commit; no new coverage numbers added.
   * **Closed stale BDOS items:** previous "all full cards done" phrasing retired; diagnostic-stub claims and `FD->0DE9` wrapped mappings removed.
- 2026-08-29 (documentation maintenance — parent-adjudicated RTC record + CP/M links, no new inference, reviewed findings):
   * **Canonical BDOS eight-byte RTC record published** (`doc/internals/rtc.md#bdos-eight-byte-rtc-record`): `+0` metadata (FC copied/RTC ignored, FD from `g_bRtcRecordMetadata` init `13h` LIKELY century `19` exact OPEN, FF copied unused), `+1` year→`09h`, `+2` month→`08h`, `+3` day-of-month→`07h`, `+4` hour→`04h`, `+5` minute→`02h`, `+6` second→`00h`, `+7` day-of-week→`06h` (convention OPEN, `0=Sunday` LIKELY from `1984-01-01` default); raw binary 24-hour (Reg B `46h`), no firmware conversion/range validation; service identities `FCh=1150`/`FDh=113E`/`FEh=1122`/`FFh=112D`; `FFh` `DE=0` clear and program both poll `UIP`, preamble `RegA|80h` likely ineffective then `2Ah`; evidence addresses as listed in `rtc.md`.
   * **Register-map correction:** rotated HD146818 labels fixed in `rtc.md` and `io-map.md` to `06`=day-of-week, `07`=day-of-month, `08`=month, `09`=year; alarm regs `01/03/05` marked used (RtcSetAlarm `2158-62`); emulator trace labels corrected (`09`=year `54h`, `08`=month `01h`, `07`=day-of-month `01h`, `06`=day-of-week `00h`); `RtcReadRegisterFile` corrected to `00h..09h` (10 bytes) → `g_abRtcRegisterSnapshot` (FD50), not `00h..0Fh`/16 bytes; stale date-gate text corrected to `RTC_AlarmDateMatches` / `g_bRtcAlarmDayOfMonth`/`g_bRtcAlarmMonth`.
   * **Stale-name correction:** `BdosFcAlarmControl` → `BdosFfAlarmControl` in `cp-m-comparison.md` (and linked purposes to canonical layout); `Link_StatusCompare_FD4B` → `RTC_AlarmDateMatches` in active TASKS naming (historical logs retain former name where clearly historical).
   * **BDOS reference alignment:** `manual/bdos-reference.md` FC/FD/FF cards now link to canonical record and summarize exact field use; FE corrected to `E<<4` interval with low→`(IY+23h)` high→`word[FEFA]` (previously mis-described as low nibble from IY).
   * **Programmer guide links:** `manual/programmer-guide.md` table entries and command bullets link to canonical record, give compact layout once without ambiguous "`byte +0 OPEN`" without metadata/LIKELY-century context; `2Dh` `E=FFh` wording corrected to "installs `F57B` no-op target"; `2Eh` wording corrected to entering `A=2Ch` error path (not guaranteed returned `A`); added `### CP/M reference manuals` with verified Bitsavers/Gaby links and DIPOS-override note; renamed `BdosFcAlarmControl`→`BdosFfAlarmControl`.
   * **Review update:** `doc/review.md` RTC-incomplete finding marked resolved for byte layout, preserving OPEN `+0`/day-numbering/range-validation.
   * **fn04 alignment verified:** no doc change; `fn04` already aligned to `Device_LookupConfigEntry` findings in prior pass.
   * **Build:** `mkdocs build --strict` (see below); no commit; no new inference.
 - 2026-08-29 (parent-approved Commstar review and correction pass):
   * **ROM-visible buffer + TX prefix (CONFIRMED):** RX `+0..1` LE
     embedded length, `+2` numeric type, `+3` sequence byte, `+4`
     active link id, `+5` unread by examined ROM path, payload `+6`;
     TX prefix `LinkFramePrefixWrite` (ROM00:316B) writes `+0..1`
     descriptor length, `+2` type, `+3` sequence, `+4=0x7F` (**SUSPECTED**
     meaning) and leaves `+5` untouched.
   * **Validation + transport (CONFIRMED unless OPEN):**
     `LinkValidateFrameHeader` (ROM00:30DC) checks embedded length vs
     caller logical count and `+4` vs active link id `fdd4`, does not
     inspect `+5`; `LinkBlockRx` success `DE=bytes consumed minus 2`
     (identities **OPEN**); examined ROM transport/header path has no
     checksum — integrity inside unresolved loaded-session payloads
     remains **OPEN**.
   * **TX outcomes + retry (CONFIRMED):** bit7 set permits readiness
     and payload writes; bit4 and bit6 waits exit when the bit clears.
     `EBh` reports either pre-payload bit7 wait or the bit4-clear wait;
     `EEh` reports either bit6-clear wait, per-byte bit7 wait, or
     post-payload bit7 wait; `ECh` reports final status bit5 set;
     success `A=00h` carry clear. Retry scheduler
     initial `fdd6=32h/fdd8=6`, later `fdd6=14h/fdd8=3`; caller
     reschedules without testing `A`/carry.
   * **Seven static reply triggers (numeric words, not named
     commands):** `01EE` attempt exhaustion `fdd5=1`; `02EE`
     exhaustion other state; `02E0/04E0/05E0` numeric
     unexpected-type paths; `01EF` type-4 sequence mismatch;
     `03EE` error/reset path ROM00:2E72.
    * **Descriptors + probe + UI fields (CONFIRMED/OPEN):**
      `FE0E {6->FDE4,3->FE38,0}` (structurally mutable), `FE32
      {9->FE3A,0}`, `FDEA {6->FDDE,0}`; `LinkProbe` ROM00:348A writes
      `1Fh` to `LINK_PROBE`, physical effect **OPEN**; `E701` is a
      zero-extended snapshot of received numeric frame type `E5BE` before
      local substitutions (transport error may put `EEh` (238) there),
      `E6FF` is zero-extended received sequence `E5BF`; displayed as
      width-3 decimal `RCV1`/`RCV2` (broader UI meaning remains **OPEN**).
   * **Link-id bit5 (CONFIRMED selector, OPEN mapping):** selects one
     of two external link configurations; which polarity maps to
     owner-confirmed V24 ADAPTOR (top) vs PLINTH (back), and where
     EXT STORAGE attaches, remain **OPEN**.
   * **Retractions (unsupported grammar removed):** removed or
     retracted `[type][16-bit big-endian command][payload]`, semantic
     `TYPE_SESSION/ANSWER/COMMAND` constants, named reply meanings,
     symmetric protocol roles, payload checksums, filenames, and
     claims of verified bidirectional Commstar exchange.
   * **Docs corrected:** `protocol/commstar.md` (envelope, validation,
     TX 0x7F, DE-2, outcomes, retry, reply triggers, descriptors,
     probe address, RCV1/RCV2, bit5 OPEN, retractions),
     `internals/io-map.md` (probe address/effect, `+4` filter,
     SUSPECTED/OPEN notes), `analysis/micronic/README.md`
     (proto scope -> raw byte-latch scaffold), `analysis/README.md`
     (model and harness scope), `analysis/micronic/proto.py` (removed
     unsupported `Frame`/`TYPE_*`/reply semantics), and directed link
     harnesses (opaque byte mechanics only).
   * **Ghidra corrected and saved:** independently reviewed status polarity
     replaced stale `LinkBlockTx`, `LinkWaitReady`, and `LinkPresent`
     plates/EOLs; `LinkReplyEE03` names the existing direct-call stub at
     ROM00:31B0 without assigning command semantics. Function count stayed
     849 across the save. `research/gap-analysis.md` refreshed to 849 total,
     142 `FUN_*`, 707 named/non-`FUN_*` (83.3%).
   * **Regression correction:** the old TX test had accepted the prelude
     alone. It now requires the complete seeded descriptor stream
     `05 04 44 00 41 42 43 44`; the duplex harness reports directed raw
     byte-latch tests only. Added three queue/header regressions.
    * **Verification:** `test_proto.py` 3/3, `test_program.py` 35/35,
      Python byte-compilation, bounded TX/RX/duplex harnesses,
      `mkdocs build --strict`, and `git diff --check` all passed.
      Hardware/runtime questions remain OPEN.
  - 2026-08-29 (parent-approved synthetic builder + loader finalize + docs maintenance):
    * **Bounded synthetic session-builder traces (CONFIRMED mechanics only):**
      `g_wSessionDeviceSelector` at `E52E` is a service-33 device selector
      mapped through `FE83 + selector - 1`, not logical frame type;
      `g_wSessionTxPayloadLength` at `E530` counts payload starting at
      `E534` (`E532-E533` skipped); logical frame type `1` written
      independently by `ROM00:2F6D`; physical low-five-bit prelude excluded
      from quoted logical frames. Trace 4: synthetic stack args
      `(1,6,22h,33h)`, `E6E6=0`, bypassed only separate preflight at `5C1F`
      by forcing `HL=0` at `5C22`; payload length `15`, payload
      `06 00 00 00 80 00 00 4C 00 00 22 33 00 00 05`, logical frame
      `15 00 01 01 7F 00 06 00 00 00 80 00 00 4C 00 00 22 33 00 00 05`.
      Trace 5: args `(1,6,1,44h,55h)`, `E6E6=0`, bypassed preflight at
      `5D05` via `HL=0` at `5D08`; payload length `19`, payload
      `06 00 00 00 80 00 01 55 02 00 44 3C 00 00 00 00 00 00 01`, logical
      frame `19 00 01 01 7F 00 06 00 00 00 80 00 01 55 02 00 44 3C 00 00 00
      00 00 00 01`. Mechanics only — payload constants/fields and complete
      RECORD/BLOCK/C-COMMAND semantics remain **OPEN**; no semantic names
      assigned to cases `4`/`8`/`9` or payload fields.
    * **RCV1/RCV2 provenance corrected (CONFIRMED):** `E701` is zero-extended
      snapshot of received numeric frame type `E5BE` before local
      substitutions (transport error may put `EEh` (238) there); `E6FF` is
      zero-extended received sequence `E5BF`; displayed as width-3 decimal
      `RCV1`/`RCV2`. Broader UI meaning remains **OPEN**. Supersedes stale
      "runtime meaning open and not transport fields" wording in prior
      Commstar entry; docs now state provenance explicitly.
    * **Loader finalize + D370 correction (CONFIRMED):** `ram:D370` is
      `g_pProgramLoaderContinuation`, a coroutine continuation exchanged by
      `Coroutine_SwapContinuation` (`ram:D9F9`), not an input-provider
      pointer; upstream physical/session provider remains **OPEN**.
      `Program_FinalizeInput` (`ROM01:1002`) finalizes on zero completion,
      generates DIP block checksums when needed, and sets loader state `3`
      (nonzero status follows `0x2330` error path). Emulator `--upload`
      uses real loader callbacks (`Program_LoadByName` `ROM01:0B82` →
      `Program_ConsumeInputChunk` `ROM01:0BAC` chunked by request word
      `D36C` → `Program_FinalizeInput` → `Program_RunByName`/
      `RunLoadedProgram`) below Commstar; bounded runs verified: 28-byte
      COM `14+14`, one-block 50-byte DIP `14+8+28` (both entered `0100h`,
      `Hello World`/`A5` at `0200h`), max `0xCF81` COM
      `14 + 207*256 + 115 = 53121` through `D080` with state `3` in
      load-only mode. Host staging uses established `E5C2` payload object
      (guessed `D500` regressed as modified during consume).
    * **Ghidra annotations saved (guarded 916):** `Coroutine_SwapContinuation`
      (`ram:D9F9`), `Program_FinalizeInput` (`ROM01:1002`), TX/RX payload
      objects at `E5C2`/`E5BE`, `Session_TxBlock4`/`Session_TxBlock5`
      mechanics plates, corrected `SessionRxStateMachine` plate; no semantic
      names assigned to `4`/`8`/`9` or payload fields. Deferred analysis
      re-instantiated 67 previously named/symbolized bodies; inventory now
      **916** total (ROM00 521/81/440, ROM01 208/67/141, ram 186/11/175,
      plus existing external import `EXT_FUN_ram_0010`; `159` `FUN_*`,
      `757` named = 82.6 %); strictly additive over captured prior addresses,
      plus the one new finalizer.
    * **Integration tests 3/3:** `MICRONIC_RUN_EMULATOR_TESTS=1
       analysis/venv/bin/python3 analysis/test_boot_upload.py` covers COM
       Hello, DIP Hello, and max-size COM byte verification. `mkdocs build
       --strict` passed; remaining complete Commstar provider/session
       semantics stay **OPEN**.
  - 2026-08-30 (parent-approved bounded form-4 service-33/link IRQ transaction — documentation maintenance, no new inference, reviewed findings):
    * **Verified bounded harness:** `--trace-session-transaction 4` runs
      builder form 4 through the actual service-33/link IRQ path, bypassing
      only the already documented separate preflight as builder trace 4 does
      (forcing `HL=0` at `5C22`). Mechanically valid firmware exercise only.
    * **Service identities (CONFIRMED):** actual service-33 entry is
      `ROM00:2E02` (`DeviceSelectOpen`, retained name); `ROM00:2E72` is
      `Device_Service33Timeout`, not entry; `ROM00:2E85` is
      `Device_Service33Complete`, callback registered through `ram:FDD2`
      (`g_pSvc33Callback`). Successful type-4 processing falls through at
      `30BC` into shared completion `30BD`; callback discards synthetic return
      address `30DB` and returns to `31C1` in IRQ path. `59D0` is the initial
      async-launch return before completion.
    * **Exact successful transaction (CONFIRMED byte-verified):** initial
      wire bytes `03 15 00 01 01 7F 00 06 00 00 00 80 00 00 4C 00 00 22 33 00
      00 05` (first `03` is low-five-bit selector prelude); phase-1
      controller queue `00 06 00 02 01 63 00 02 01` = one uncounted sync `00`,
      six-byte logical type-2 frame `06 00 02 01 63 00`, then two excluded
      copies `02 01`; exact response `03 06 00 03 01 7F 00` = prelude `03`
      plus six-byte logical numeric type-3 frame `06 00 03 01 7F 00`;
      phase-2 queue `00 06 00 04 01 63 00 04 01` with same
      sync/logical/excluded shape; service receive object `E5BC-E5C2`
      becomes `00 00 02 01 00 00 00` (seven bytes).
    * **Peer scaffold (CONFIRMED):** must expose status bit4 while inbound
      bytes remain (so IRQ poll `31B6` dispatches), bit0 while bytes remain,
      and bit1 after drain. No electrical names assigned.
    * **Zero-payload endpoint (CONFIRMED):** object reaches
      `SessionRxStateMachine` `5A81` (via `5A63`
      `Session_RxStateMachineThunk`), retains length `0` and numeric value
      `2`, then takes `5B07 -> 5A13` to resume internal receive polling. It
      does **NOT** return a final numeric result and does **NOT** relaunch
      service 33. Requiring `5B57` would need an invented nonzero
      object/UI outcome, so the regression correctly stops at one completed
      zero-payload poll cycle.
    * **Falsified assumptions corrected:** 12-byte phase-1 expectation
      (actual is 9-byte queue with sync+logical+excluded shape), payload-
      echo reply, `59D0` as post-completion value, and final numeric-result
      via `5B57` — all refuted by bytes.
    * **Excluded-byte placement clarified (CONFIRMED examined-session, OPEN
      controller reason):** the two bytes excluded from `LinkBlockRx` `DE`
      are copies of logical type (`+2`) and sequence (`+3`) in this
      transaction (trailing `02 01`); controller-level reason remains **OPEN**.
      Supersedes wholly-OPEN phrasing in prior docs.
    * **Ghidra (guarded 919, saved):** `Lib_MaxS16` -> `Lib_MinS16` at
      `ROM00:5944`; `UiDialogCommitPair` -> `Program_StreamChunkCallbacks`
      at `ROM01:0741` (mechanics-only 128-byte callback-driven copy using
      `D2E2` state); `UiDialogDrawBlock` -> `Program_BridgeHandlerTables`
      at `ROM01:07EE` (mechanics-only seven-slot handler-table bridge into
      `D0F0`); `5A63` thunk -> `Session_RxStateMachineThunk`; corrected
      `5A81` plate. `Program_StreamChunkCallbacks`/`BridgeHandlerTables`
      are mechanics-only — do not assert a service-33 provider link.
      Inventory: ROM00 524/81/443, ROM01 208/67/141, ram 186/11/175,
      EXTERNAL 1/0/1, total **919** / 159 unnamed / 760 named = **82.7 %**.
      Increase from 916 is the recovered labelled state-machine body at
      `5A81` plus the two new confirmed callback functions at `2E72` and
      `2E85`; the `5A63` thunk already existed.
    * **Tests (CONFIRMED):** `analysis/test_boot_upload.py` now 4 opt-in
      emulator integrations (three prior loader tests plus the form-4
      transport transaction); all 4 passed serially; `test_program.py`
      35/35 and `test_proto.py` 3/3 passed.
    * **Remaining OPEN:** complete command/payload meaning, broader meaning
       of numeric types `2/3/4`, and whether a real peer naturally emits
       these exact controller queues remain **OPEN** — mechanically valid
       firmware exercise, not an interoperable Commstar specification.

- 2026-08-30 (Commstar Load/Run receive sequencing):
  * **CONFIRMED:** state-44 variable reply bytes belong in phase-1 type 2;
    phase-2 type 4 is constrained by the fixed nine-byte `FE32` descriptor.
    A too-long type-4 exhausts that descriptor and reports
    `0x1F76 (8054), "Line failure"`.
  * **CONFIRMED:** the state-44 `OK` classifier scaffold returns inner
    `HL=8`, unwinds through `ram:D84C` to `ROM00:624B`, then starts a new
    receive at `ROM00:2F78` (`FDDC=FE0E`). Injecting before that generation
    transition is consumed by the prior `FE32` operation.
  * **CONFIRMED:** a zero-payload receive-first exchange injected at `2F78`
    reaches the UI states `Logged on` and `Receiving prog`. Program data
    grammar remains OPEN; do not claim an interoperable upload.
  * **CONFIRMED, cross-provider reviewed:** the accepted `OK A5 5A 3C C3`
    scaffold becomes the initial Load/Run byte stream, not a Commstar payload
    grammar. `Program_LoadDipOrCom` requests 14 bytes; fewer than 14 route to
    raw COM, while a 14-byte-or-longer stream requires first word `0xC8C9`
    (`C9 C8`) to select DIP. The observed `OK` prefix irrevocably selects COM;
    restart at byte zero for a DIP experiment. A normal zero-status finalizer
    can end the short stream without filling all 14 bytes.
  * **CONFIRMED:** DIP block input reads an 8-byte serialized prefix into a
    10-byte resident descriptor stride; do not call the resident descriptor an
    8-byte object. The final two resident bytes are not assigned a new meaning
    here.
  * **CONFIRMED:** `0x1F9A (8090), "Line failure"` is the default arm of the
    ROM00 session-result dispatcher at `4E4E`, not a loader parser error. It
    applies when the session result is not one of `0`, `4`, `6`, `8`, or `9`;
    the source of the stalled-harness result remains **OPEN**.
  * **CONFIRMED, cross-provider reviewed:** the later program receive is a
    distinct state-44 caller: the internal basic block `ROM00:4F5A` enters
    mode `0x000A` and calls `Session_ReadStreamChunk` (`3E6A`) with a
    128-byte aggregate maximum. It is not a callable function entry. The
    receive path validates outer metadata but copies `E5C4` inner payload
    bytes unchanged; `3E6A` wraps them only as
    `{u8 count, payload}`. Thus a later raw payload may begin `C9 C8` for DIP
    without an `OK` prefix. The peer envelope that reaches this caller remains
    **OPEN**.
  * **Synthetic compatibility milestone:** `boot_hw.py --trace-loadrun-source
    plinth|v24 --synthetic-loadrun FILE` now feeds a validated COM/DIP file as
    raw program-data payloads after the confirmed control sequence. The
    opt-in emulator regression delivers a 50-byte DIP through
    that path and stops at the explicit EOF-policy boundary. This is a working
    ROM-facing synthetic peer component, not a claim about historical command
    order or EOF/safe-removal semantics; those remain **OPEN**.
  * **Falsified synthetic EOF candidate:** one final zero-length state-44
    program-data payload followed by the ordinary type-4 completion did not
    reach a bounded post-EOF state in the emulator (timed out after 180 s).
    Do not use an empty payload as the synthetic EOF convention. Next ROM-only
    target is the finalizer callback/control path rather than another guessed
    terminal frame.
  * **Deferred internal EOF injection:** static callback-table tracing shows
    that a drained ROM01 producer can return zero when `D0FE=8`, but arming
    that write at the harness's post-stream pause did not reach the expected
    producer breakpoint within 180 s. The callback path is not active at that
    pause; do not expose this internal write as a peer policy. It remains a
    conditional static mechanism, not a tested synthetic EOF implementation.
  * **Working adapter-completion policy:** optional
    `--synthetic-loadrun-finalize` invokes the real ROM01
    `Program_FinalizeInput` callback with zero status after the synthetic
    peer's last payload. The 50-byte DIP integration reaches loader state 3.
    This completes a software-facing transfer, but is not documented as a
    Commstar EOF frame or safe-removal command.
  * **Application policy model:** `micronic.commstar.SyntheticWorkflow`
    defines source, opaque scan upload events, optional validated COM/DIP
    image/run intent, feedback, and safe-removal as explicit adapter policy.
    It is not a recovered historical command grammar.
  * **V24 mode-1 synthetic trace (CONFIRMED bounded emulator behavior):**
     selecting V24, editing Mode from 0 to 1 (`MODEM A/ANS`) with raw `DBh`,
     and accepting the form reaches the same observed program-receive sequence
     as the synthetic PLINTH route in the emulator. A validated DIP file plus
     the adapter finalizer reaches loader state 3. Independent byte review
     confirms the mode-1 table and runtime-stub dispatch path. This does not
     establish equivalence of the historical peers, modem authentication,
     field meanings, or physical connector polarity. Blank mode-0 form
     behavior remains OPEN.
  * **CONFIRMED V24 form layout:** the descriptor at `ROM01:793A` maps Mode,
    Linespeed, User id, Password, Group id, and Telephone number to the
    30-byte `ram:EC97-ECC6` backing object. `EC98=FF` selects the current mode
    record's default speed; mode 0 resolves to encoded `0x0E` (`9600`). The
    post-form call stages Group id, User id, and Password; Telephone number is
    supplied separately only to mode callbacks 0 and 2. This is software
    dispatch evidence only: physical port polarity and historical field
    semantics remain OPEN.
  * **CONFIRMED V24 mode-0 link chain:** mode record `D108` selects shared
    callback `Session_LogonMode0Or2Callback`, session/device selector 4, and
    default wire ID `g_bDeviceWireId4=0x43`. Bit5 is clear, so `LinkBlockTx`
    takes the bit5-clear latch path. This is not a physical-port assignment.
    `0x1F40 (8000)` and `0x1F41 (8001)`, both `"Plinth not connected"`, are
    emitted by earlier connection-result dispatchers, not that callback.
  * **CONFIRMED V24 mode edit:** raw keyboard-ring byte `DBh` invokes
    `FieldCounterEdit`; with `g_wLogonModeEnableMask=FFFFh`, it advanced
    g_bLogonModeIndex from 0 to 1 (`MODEM A/ANS`). Accepting mode 1 reached
    `0x1F40 (8000), "Plinth not connected"`. The byte has no assigned physical
    key identity, and this does not establish a V24 transport path.
  * **Synthetic workflow manifest:** `--synthetic-workflow FILE` resolves a
    `SyntheticWorkflow` PLINTH image relative to its JSON manifest and feeds
    the existing tested path. `run_after_load` verifies the requested/loaded
    names and invokes ROM `Program_RunByName` after state 3; scan serialization,
    feedback, and safe removal remain adapter policy. V24 manifests are
    intentionally rejected pending a tested V24 completion.
  * **CONFIRMED terminal-marker mechanics:** in a state-44 receive object,
    inner marker `E5C0=1` produces result 8 and latches `E44A`, preventing
    refill after the delivered payload. Marker `0` preserves result 0 and
    leaves refill enabled. This relies on `Lib_Eq16`'s inverted Z contract:
    equal returns HL=1 with Z clear. The mechanism is byte-verified at
    `ROM00:5AD2-5AEA` and `ROM00:3D7D-3DEF`, and marker 0 was dynamically
    observed to reach a fresh receive generation.
  * **CONFIRMED synthetic multi-chunk regression:** a 200-byte COM uses a
    tested 126-byte first payload with marker 0, followed by 74 bytes with
    marker 1; the adapter finalizer reaches loader state 3. Phase-14 reply
    accounting accepts the verified type-3 reply as a TX suffix because an
    observed preceding `03` byte is captured separately. This is harness
    mechanics, not a historical Commstar framing claim.
    **OPEN:** 126 is a tested chunk size, not a ROM-proven maximum; do not
    derive a payload limit from state-44's `0x86` capacity until its exact
    descriptor and envelope overhead are byte-verified.
  * **CONFIRMED state-44 receive bound:** `ROM00:6230` passes `0x86` as the
    state-44 application receive capacity. The observed 128-byte synthetic
    object reaches the 0x1FAE (8110), "Line failure" path; its exact
    descriptor and envelope-overhead cause remain OPEN. Do not yet assert a
    raw-payload maximum from the capacity value alone.
  * **Documentation update (2026-08-31):** `doc/protocol/commstar.md` now
    presents the regression-covered synthetic peer as a bounded programmer
    profile: exact accepted controller queues, observed state
    `61 -> 64 -> 45 -> 44` progression after mode setup, program-receive arm,
    and marker/finalizer boundary. This is explicitly not historical Commstar
    grammar. A new V24 mode-1 trace reaches loader state 3 using the same
    synthetic type-2/type-4 responder and is regression covered. Independent
    byte review confirms its mode-table/runtime-stub mechanics. Historical
    modem semantics and physical-port polarity remain OPEN.
  * **Commstar historical-server readiness (2026-08-31):** cross-provider
    review confirms that controller transport and the bounded type-2/type-3/
    type-4 exchange are implementable, but a real historical server remains
    blocked on application/session grammar. The known values `61h`, `64h`,
    `45h`, and `44h` are internal session-state identifiers, not frame types
    or a recovered command dictionary. P0 missing evidence is authentication
    payload/response formatting, record/block object layout, final-block/EOF
    signaling, and session-level retry/abort behavior. Highest-value next
    experiment: a synchronized genuine-server login plus small COM/DIP file
    transfer capture, with link bytes and `FDD4-FDDF`, `FDE4-FE42`, `FE43...`,
    and `E530-E5C8` snapshots at send/receive/completion boundaries.
  * **Documentation review follow-up (2026-08-31):** revised the published
    Commstar page for a physical-server implementer. The synthetic Load/Run
    profile is now explicitly emulator-only; controller queues, logical
    frames, and unknown wire bytes are distinguished; the controller
    turn-taking and TX/RX id asymmetry are explicit; and diagnostics/timing
    limitations are consolidated. Added no-hardware priorities for the
    bypassed builder preflight, timeout accounting, and a wire-visible receive
    arm, plus a physical IR capture before any server claim. No new protocol
    semantics were inferred.
  * **Implementer review v2 follow-up (2026-08-31):** corrected the observable
    subset: only link-id bits 0-4 are visible in the controller prelude, while
    a peer must still supply all eight received-frame id bits. Pinned V24
    state-61 and state-45 controller-boundary TX captures in the emulator
    regression and recorded the state values as externally visible payload
    observations, not a command dictionary. Added the missing seven-byte
    type-2 control form, RX bit-1 stability limit, framing rule, timing-method
    cross-link, and 126/128-byte capacity bracket. State-44 payload size 127
    remains the next bounded probe.
  * **Implementer review v4 follow-up (2026-09-01):** applied the restructure
    review. Corrected the state-45 capture to the full 66-byte frame read off
    the harness (was 2 bytes short and, before that, 2 long with the ASCII at
    the wrong offset); the V24 regression now asserts whole captures instead
    of prefixes, which is what let the transcription drift. Removed the
    contract sections the split had duplicated into the evidence page.
    Documented the request/response object grammar and reclassified the
    session and block formats from "Not implementable" to **Provisional**:
    the three-`u16` request header, the status/marker/length response object,
    and the marker-delimited program stream are consistent across every
    captured exchange. What remains blocked is the IR wire layer, the
    handheld-to-host direction, and several object field meanings.
  * **Next bounded probes:** bisect the state-44 payload maximum at 127 bytes;
    parameterise the banner workstation number (hardcoded at
    `analysis/boot_hw.py:734`) from `SERIAL_TEXT` to confirm the state-45
    object field offsets by measurement.
  * **State-45 field measurement (2026-09-01):** the input-variation probe is
    done. `analysis/boot_hw.py` now takes the banner workstation number from
    `SERIAL_TEXT` (was hardcoded in the expect step) and gains
    `--trace-loadrun-name` for the Load/Run Name field. Varying each input
    alone moves exactly one field and leaves the frame at 66 bytes, giving a
    measured object layout: `LOAD` at object +14 (runtime constant, not a ROM
    literal), workstation number at +18 (8 bytes, right-justified,
    space-padded), program name at +42 (8 bytes, left-justified, NUL-padded).
    Pinned by `test_state45_field_offsets`. The remaining 34 object bytes are
    zero in every capture; their sizes resemble the 9-byte V24 logon fields,
    which is the next thing to vary.
  * **CORRECTION to the object grammar (2026-09-01):** the third `u16` of the
    request header is **not** a general object length. It equals the trailing
    object length for states `00`/`45`/`61`/`64`, but is `0x0080` for state
    `06`, which carries a nine-byte object, and `0x00FF` for state `44`,
    which carries none. The earlier "count is the object length wherever an
    object follows" wording overstated a five-sample pattern and has been
    replaced with a state-dependent size field plus the two exceptions.
  * **Session state names recovered (2026-09-01):** `ROM00:6A4A` is 16
    little-endian pointers to display strings — `NOT-STARTED`,
    `DISCONNECTED`, `CONNECTED`, `READY-RX-DATA`, `READY-RX-PROG`,
    `READY-TX-DATA`, `READY-TX-PROG`, `RECORD-RX`, `BLOCK-RX`, `RECORD-TX`,
    `DATA-SET-TX`, `BLOCK-TX`, `TERMINATED`, `CRASHED`, `REPLY-START`,
    `REPLY-END`. These are the firmware's own state vocabulary and confirm the
    protocol's shape (connect lifecycle, per-direction data/program readiness,
    distinct RECORD and BLOCK modes). They are **not** the wire state values:
    the table is indexed 0-15 while the wire carries `00`/`06`/`44`/`45`/
    `61`/`64`, and `6A4A` has no static xref because the RAM-resident session
    module supplies the index. Mapping the two numberings is a new OPEN item.
  * **Commstar command vocabulary recovered (2026-09-01):** `ROM00:6B67` is a
    parallel table of 17 pointers to command-name strings: `C-INIT-COMMS`,
    `C-DIAL`, `C-ANSWER`, `C-MANUAL`, `C-DROP-LINE`, `C-COMMAND`, `C-RX-CMD`,
    `C-TX-REPLY`, `C-SHUT-DOWN`, `C-RX-REC`, `C-RX-BLK`, `C-BEGIN-FILE`,
    `C-TX-REC`, `C-END-FILE`, `C-TX-BLK`, `C-END-TX`, `C_ABORT` (index 16 is
    verbatim underscore-spelled in ROM). Every pointer resolves inside the
    string block immediately following the table, as does every pointer in
    the 16-entry state table at `6A4A`. Together these give the operation
    vocabulary the earlier notes recorded only as unenumerated "C-* texts":
    RECORD and BLOCK are distinct transfer modes each with RX and TX forms,
    wrapped by BEGIN-FILE/END-FILE/END-TX file framing, with a separate
    command/reply exchange and four link-setup variants.
  * **Index-to-wire mapping is NOT established, and this trace cannot do it
    (2026-09-01):** neither table has a static xref — the RAM-resident
    session module supplies both indices. Scanning the LCD through a
    complete V24 mode-1 Load/Run session shows that none of the 16 state
    names or 17 command names is ever displayed on that path, so the
    existing traces cannot correlate index with wire value.
    **CORRECTION (owner, 2026-09-01):** Load/Run *is* the Commstar session
    screen, so the traced session is a Commstar session; it renders the
    user-facing operation strings at `ROM00:6C8E`, not the internal state or
    command names. The route is therefore a breakpoint on the display-index
    writer, or the `Diagnostics` menu entry. Do not infer a mapping from the
    high nibble of the wire values.
  * **Commstar operation matrix (2026-09-01):** `ROM00:6C8E` holds the
    user-facing strings the session screen renders, in a 2x2 of
    data/program x transmit/receive: titles (`Data Transmission`,
    `Program Transmission`, `Data Reception`, `Program Reception`),
    in-progress (`Sending data`/`Sending prog`/`Receiving data`/
    `Receiving prog`) and completion (`Data transmitted`/
    `Program transmitted`/`Data received`/`Program received`), followed by
    the error strings. All captures exercise `Program Reception` only.
    The matrix matches four of the internal state names
    (`READY-TX-DATA`/`READY-TX-PROG`/`READY-RX-DATA`/`READY-RX-PROG`).
    A consistent but **unproven** reading is RECORD=data, BLOCK=program,
    making `C-TX-REC` the handheld-to-host upload. Since Load/Run is the
    Commstar screen, the uncaptured upload direction is the top row of a
    screen the harness already reaches; what selects the row is the new
    priority question.
  * **Commstar state machine SOLVED (2026-09-01):** `ROM00:692A` is the
    session state-transition matrix, indexed `table[state * 17 + command]`.
    Bit 7 set marks an illegal transition (message box, `ram:E3C2 = 2`);
    bit 7 clear is legal and `entry & 0x7F` is the next state. The `*0x11`
    multiply and the table base are byte-verified at `ROM00:3C06`
    (`SessionCoroJumpTable`). Extent is exactly 14 states x 17 commands =
    238 bytes, `692A-6A17`; unrelated data begins at `6A18`, so state-name
    entries 14 (`REPLY-START`) and 15 (`REPLY-END`) have no row and are
    display-only. The decoded machine: INIT-COMMS opens, DIAL/ANSWER/MANUAL
    connect, C-COMMAND leaves CONNECTED for READY-RX-DATA, RECORD ops loop
    in RECORD-RX/RECORD-TX with BEGIN-FILE/END-FILE/END-TX file framing,
    BLOCK ops loop in BLOCK-RX/BLOCK-TX with no file wrapper, and every
    state accepts C-DROP-LINE (to NOT-STARTED) and C_ABORT (to CRASHED).
  * **RECORD=data / BLOCK=program promoted to CONFIRMED (2026-09-01):** was
    recorded as an unproven vocabulary reading. Each of the four transfer
    operations calls `SessionStartDataMode` (`ROM00:452D`) with its command
    index and loads its own display string: cmd 9 `C-RX-REC` ->
    `Receiving data` (`4EA3`), 10 `C-RX-BLK` -> `Receiving prog` (`4F90`),
    11 `C-BEGIN-FILE` -> `Sending data` (`506A`), 14 `C-TX-BLK` ->
    `Sending prog` (`5222`). `452D` has 15 call sites carrying command
    indices 0..16; only 6 (`C-RX-CMD`) and 7 (`C-TX-REPLY`) are absent.
  * **RENAME (2026-09-01):** `ROM00:3BF5` `CoroutineSetArgs` ->
    `Session_SetState`. The routine hardcodes `LD (E22D),A` and is the sole
    writer of the session state in ROM00 (the only `LD (E22D),A` in the
    image is at `ROM00:3C02`, inside it); the old name predated that finding
    and contradicted the bytes. No doc referenced the old name. `ram:E22D`
    labelled `g_bSessionState` with a repeatable comment; `ROM00:3BE8`
    `Session_GetState` given a plate. Labels added:
    `Session_TransitionTable` (692A), `Session_StateNameTable` (6A4A),
    `Session_CommandNameTable` (6B67), `Session_OpDisplayStrings` (6C8E),
    each with a plate recording the decoded contents. Program saved.
  * **Operation selection narrowed, still OPEN (2026-09-01):**
    `READY-RX-PROG`, `READY-TX-DATA` and `READY-TX-PROG` have no incoming
    legal transition in the matrix, so the operation cannot be selected by
    the handheld walking the table. A second writer of `g_bSessionState`
    must exist in the RAM-resident session module. The C-COMMAND/C-RX-CMD/
    C-TX-REPLY trio plus display-only REPLY-START/REPLY-END point at the
    command-reply exchange, but that is a reading of the table's shape, not
    a byte-level finding.
  * **Adversarial self-review of the state-machine findings (2026-09-01):**
    run in place of the cross-provider review AGENTS.md asks for, at the
    owner's suggestion. Seven falsification attempts; two found real errors.
    - *Table base/stride/polarity:* re-derived from raw bytes rather than
      decompiler output. `LD DE,0011` (3C1A), multiply (3C1D), `ADD HL,DE`
      (3C21), `LD DE,692A` (3C22), `ADD HL,DE` (3C25), `LD E,(HL)` (3C26)
      with **no intervening `INC HL`** — base exactly `692A`, no off-by-one
      of the kind that produced the 31F2/31F5 error. Bit-7 test at 3C35 is
      followed by `JP NZ,3C44`, and 3C44 is the message-box path, so bit 7
      set = illegal. SURVIVES.
    - *Was `Lib_Mul16Mod16` a modulo, not a multiply?* If so the index would
      be `state + command` and the whole reading collapses. Settled
      structurally: column 4 (C-DROP-LINE) is `0x00` in every row at stride
      17 and at no other stride tested. SURVIVES.
    - *Extent 14 rows:* row 14 contains 15 cells decoding to states > 15 and
      cannot be a state row. Row 15's bytes happen to look state-like
      (0/4/5) but sit past a proven-invalid row. SURVIVES.
    - *ERROR FOUND — "every state accepts C_ABORT":* false. `C-DROP-LINE` is
      legal from all 14 states, but `C_ABORT` is legal only from states 1-12;
      it is an **illegal** transition from `NOT-STARTED` and from `CRASHED`.
      The published text also contradicted itself (it claimed both "every
      state accepts C_ABORT" and "CRASHED accepts only C-DROP-LINE").
      Corrected in the doc and the `692A` plate.
    - *Command-index/name-table binding:* previously rested on the 17=17
      count alone. Now corroborated independently — nine semantic predictions
      taken from the NAME ORDER (e.g. READY-RX-DATA + C-RX-REC -> RECORD-RX)
      all land on legal cells with exactly the predicted target, 9/9. And
      `Session_ProgramReceiveMode` (`ROM00:4F5A`), named before this
      analysis, issues command 10 = `C-RX-BLK`. STRENGTHENED.
    - *Unreachable ready states:* exhaustive scan of rows 0-13 finds no legal
      transition targeting states 4, 5 or 6. SURVIVES.
    - *String-load containment:* no `RET` between the `CALL 452D` and the
      display-string load in either checked routine (4E77->4EA3, 4F64->4F90),
      so they are the same linear flow. SURVIVES.
  * **InlineTableDispatch fully decoded (2026-09-01):** format byte-verified
    at `ram:E0B2-E0D8`: `CALL E0B2` followed by `u16 count`,
    `{u16 case, u16 handler} * count`, `u16 default`. Switch value arrives in
    `HL`; the dispatcher tail-jumps (`JP (HL)` at E0D8) so the handler returns
    to the caller's caller and the bytes after the table are unreachable from
    that call. Compare is full 16-bit in two stages (low at E0C1, high at
    E0CD). Counter is pre-decremented, so `count == 0` falls through to the
    default, which is read from the two bytes after the last entry.
    `analysis/decode_inline_tables.py` decodes every site: **45 sites, 188
    cases — 25 in ROM00, 20 in ROM01, none in RAM.** Validated against the
    five tables previously decoded by hand (`4E4E`, `528E`, `53C4`, `540D`,
    `5A66`); all five match exactly. Listing in
    `doc/re-notes/inline-dispatch.md`, regenerable with `--markdown`.
    Case values are not one namespace — each table means what its caller
    switches on.
  * **HYPOTHESIS DISPROVEN — no second writer of `g_bSessionState`
    (2026-09-01):** the previous entry predicted a second writer in the
    RAM-resident module. There is none. Searching ROM00, ROM01 and the
    battery-RAM image for every addressing form (`LD (nn),A/HL/BC/DE`,
    `LD HL/DE/BC/IX/IY,nn`) finds a single write instruction, `ROM00:3C02`
    inside `Session_SetState`. ROM01 and RAM contain no reference to `E22D`
    at all; the only other occurrence in ROM00 is `7D6A`, the boot-time
    memcpy descriptor (`7301 -> E22D`, 205 bytes) already recorded in the
    os-diposb notes.
  * **Operation selection is the runtime-stub slot (2026-09-01, SUSPECTED):**
    the four transfer routines are reachable only through RAM stub slots —
    no `CALL` or `JP` to `4E6D`/`4F5A`/`5034`/`51EC` exists in any image.
    `ROM00:7D88` is the ROM source table (flat 16-bit array, entry i at
    `7D88+2i`, feeding `ram:ED1C+4i`); base confirmed because it reproduces
    all three slot->target pairs already recorded (58->48BF, 60->4AE0,
    68->4F5A). The four operations are indices 59 (`5034`, Sending data),
    68 (`4F5A`, Receiving prog), 70 (`4E6D`, Receiving data) and 73 (`51EC`,
    Sending prog). Also note `SessionStartDataMode` returns early unless
    `ram:E48D` == 2, so the Load/Run path may run an operation routine
    without driving the state machine at all — which would explain why
    states 4/5/6 are unreachable in the transition table yet the traced
    session performs Program Reception.
  * **InlineTableDispatch tables defined as data in Ghidra (2026-09-01):**
    the 45 inline tables were being disassembled as code, producing **279
    bogus instructions** and derailing the surrounding listing.
    `analysis/ghidra/DefineInlineTables.java` is a self-contained Ghidra
    script — no arguments, nothing generated — that scans every initialised
    block for `CALL E0B2`, decodes the following table, clears the range,
    types it `word[2*count+2]` and plates it with the decoded cases. It then
    adds a reference from each entry to its handler and disassembles any
    handler left as raw bytes: the dispatcher reaches handlers through
    `JP (HL)`, so Ghidra has no flow to them and, once the bogus
    fall-through is cleared, a handler reachable only that way reverts to
    undefined bytes. 233 references added. The script is idempotent (a
    second run clears 0) and guards against false positives by skipping any
    candidate whose count exceeds 64 or which overruns its block.
    The Python decoder and the Ghidra script locate the sites independently
    and agree on all 45 — a cross-check on both.
  * **Misaligned handler `ROM01:115F` repaired (2026-09-01):** the one handler
    that would not stay disassembled across runs. `21 00 00 C9` =
    `LD HL,0 / RET` (return 0, "key not handled"); its counterpart at `115B`
    is `LD HL,1 / RET`. Ghidra had decoded the four bytes one byte late as an
    undefined byte plus `NOP / NOP / RET`, because nothing referenced `115F` —
    the dispatcher reaches it via `JP (HL)` — so the true entry was never a
    disassembly seed, and the stale `NOP` at `1160` then blocked the 3-byte
    `LD HL,0000`. `DefineInlineTables.java` now clears code units that start
    *inside* a handler entry before disassembling (never a defined function
    entry). Fully idempotent afterwards: 0 cleared / 0 disassembled /
    0 realigned on a second run.
  * **`ROM01:1163` is the field-editor key dispatch (CONFIRMED):** reached by
    `JP` from `ROM01:10DE` with a keyboard-ring byte in `HL`. Cases
    `0x0D -> 10E1` (returns 1), `0x14 -> 10E5` (sets `ram:D463 = 1`),
    `0xDB -> 10EF` (reads `ram:EB1A`, points `DE` at `ram:EC97`), default
    `-> 115F` (returns 0). `0xDB` is the raw counter-edit byte used to change
    the V24 Log-on Mode field and `ram:EC97` is that form's 30-byte backing
    object, so this reaches the same path as the V24 mode-1 emulator trace,
    from static analysis instead. The `0x14` handler and `ram:D463` are
    unidentified. Plates added at `115F` and `1163`; `115F` labelled
    `FieldKeyDispatch_Unhandled`.
  * **CORRECTION — `Session_SetState` has 46 callers (2026-09-01):** an
    earlier entry found the single `LD (E22D),A` instruction and inferred
    that the session state could therefore only be set through the transition
    path. Wrong inference: the instruction is unique, the *function* is not.
    `ROM00:3BF5` has 46 callers, only one of them (`3C7E`) inside
    `SessionCoroJumpTable`. 26 pass a literal — and only ever `0`
    NOT-STARTED, `2` CONNECTED or `13` CRASHED; 17 pass `(ram:E48C)` and 2
    pass `(ram:E491)`. `E48C` is the cell the dispatcher writes with
    `entry & 0x7F`, so those sites commit a transition the table staged: the
    dispatcher computes the next state, the caller commits it.
  * **State machine is gated by `ram:E48D` (2026-09-01, CONFIRMED):**
    `SessionStartDataMode` forwards to the dispatcher only when `E48D == 2`.
    A full V24 mode-1 Load/Run trace ends with `E48D = 0` (measured with
    `--dump-mem e48d:1`), so that path never consults the transition table,
    yet `g_bSessionState` still advances `00 -> 02` via literal sets — which
    reconciles the apparently unreachable states 4/5/6 with a session that
    plainly performs Program Reception. `E22D` boots to `0` (NOT-STARTED)
    from the `ROM00:7301` block, a useful consistency check; the `OK`/`NO`
    tokens live at `7303`/`7307` in the same block.
  * **`Session_EnableStateMachine` (`ROM00:46E9`) identified (2026-09-01):**
    stores the literal `2` into `E48D` and `0x37` into `ram:E6FC`. `E48D` has
    exactly two writers — this one and `ROM00:4563` (which stores its
    caller's argument then issues `C-INIT-COMMS`). Neither has a direct
    `CALL`/`JP` anywhere; both are reachable only as runtime-stub slots,
    indices 65 (`ram:EE20`) and 66 (`ram:EE24`) in
    `Session_RuntimeStubSourceTable`. So arming the protocol state machine is
    itself a stub-slot call by the loaded session module — the same mechanism
    that selects the four transfer operations. **The open question is now a
    single one: what makes the module call slot 66.** Meaning of
    `E6FC = 0x37` is OPEN. Labels/plates added; program saved.
  * **Nothing in the firmware arms the state machine (2026-09-01, CONFIRMED
    negative):** searching ROM00, ROM01, the upper RAM dumped *live* after a
    completed session, and the banked RAM pages for a `CALL`/`JP` to each
    stub slot finds only two of six invoked — slot 65 (`EE20`, set mode +
    `C-INIT-COMMS`) from `ROM01:1305`, and slot 68 (`EE2C`, `C-RX-BLK`
    Receiving prog) from `ROM01:141F`. Slots 59 (Sending data), 66 (enable
    state machine), 70 (Receiving data) and 73 (Sending prog) have no caller
    anywhere. That matches the direct measurement: slot 66 is what would set
    `E48D = 2`, and `E48D` is 0 at session end, so the transition table is
    never consulted at runtime. The shipped firmware only ever drives Program
    Reception. Live RAM differs from the cold image by 2427 bytes, so the
    module is genuinely loaded and the negative is not a dump artefact. A
    live slot reads `D7 00 63 45` = `RST 10h ; db bank ; dw target`,
    confirming the banked-call thunk shape and the `ROM00:7D88` derivation.
  * **TRAP when searching for stub callers:** `RAM02:1101-11FE` is a
    127-entry descending list of every even address from `EEFE` down to
    `EE02`, so every stub slot address appears there as data. Those are not
    references. Noted in the `ROM00:7D88` plate.
  * **LIKELY — the missing caller is a loaded application:** the stubs are
    fixed addresses in the transfer-vector table (`ED1C-F17F`), the
    documented route for loaded code to reach firmware services, and an
    application's own code is in none of the images searched. That would make
    the handheld-to-host upload an application-facing API rather than a
    firmware UI feature. Under investigation.
  * **Commstar application API CONFIRMED by experiment (2026-09-01):** the
    LIKELY hypothesis is now demonstrated. A 16-byte COM that calls the stub
    at `ram:EE24` leaves `E48D = 2` **and** `E6FC = 0x37` — both side effects
    of `Session_EnableStateMachine` — while a control COM (`HELLO_COM`) that
    makes no such call leaves both at 0. So a loaded application can drive
    Commstar directly through the transfer-vector entry points, which is the
    only demonstrated route to the fifteen operations the firmware UI never
    invokes. Pinned by `CommstarApplicationApiTest`.
  * **Calling convention: the entry points do NOT return (CONFIRMED):** a COM
    writing a marker before the call and another after it leaves only the
    first (`bank2[0200] = AA`, never `55`), while the call's side effects are
    present. Each entry is a banked-call thunk onto a routine that begins
    with a coroutine switch, so control transfers to the session machinery
    and does not resume after the `CALL`. Applications hand the session off;
    they do not drive it instruction by instruction.
  * **Full API surface mapped (2026-09-01):** twenty contiguous slots,
    `ram:EE00`-`EE4F` (indices 57-76 of `Session_RuntimeStubSourceTable`).
    Each slot's command was read from the literal argument of the first
    `CALL 452D` inside its target routine, so the mapping is byte-derived,
    not inferred from ordering. Fifteen of the seventeen commands are
    reachable; `C-RX-CMD` (6) and `C-TX-REPLY` (7) have no slot, consistent
    with neither having a `452D` call site anywhere. Several commands appear
    more than once (`C-SHUT-DOWN` x3, `C_ABORT` x3) via distinct wrapper
    routines that have not been told apart. `EE24` is not a command: it arms
    the state machine. Documented as an ABI in
    `doc/reference/commstar-api.md`.
  * **TEST BUG FIXED (2026-09-01):** the `capture_tx` helper added earlier was
    inserted between `@unittest.skipUnless` and `BootUploadTest`, so the
    decorator attached to the helper and that class was left ungated — its
    slow emulator tests would run without `MICRONIC_RUN_EMULATOR_TESTS=1`.
    Decorator restored; all 12 tests in the module now skip without the opt-in.
  * **CORRECTION — the entry points DO return (2026-09-01):** the previous
    entry claimed "the entry points do NOT return" from a COM experiment.
    Wrong as a general statement. The firmware's own call sites resume
    normally and read a result: `ROM01:141E CALL EE2C` is followed by
    `POP DE` (caller cleans the stack argument) and `LD (D0FE),HL` — **the
    result comes back in `HL`**. Same shape at `ROM01:1305`/`130E`. The COM
    observation is real but narrower: a *bare application* does not resume,
    and that holds with the marker in fixed RAM, so it is not a paging
    artefact. Why is now its own OPEN item.
  * **Commstar calling convention (CONFIRMED from ROM01):** arguments pushed
    on the stack, caller removes them; result in `HL`; the caller stores it
    to `ram:D0FE`, labelled `g_wSessionLastResult`. That cell is also the
    sequencing mechanism — `ROM01:140E-1417` requires `D0FE == 8` before
    issuing `C-RX-BLK`. There is **no** separate "run" or "get status" entry
    point: callers test `D0FE` between commands. `0` and `8` are both treated
    as success at that site.
  * **`ram:D837` is a stack-frame prologue, not a task switch:** it saves
    `IX`/`IY`, adjusts `SP` by `DE`, and re-enters through `D836`. `E04B`,
    `E05A` and `E086` are 16-bit compare helpers (compiler runtime), not
    session guards — an earlier reading of `CALL E086` as a session check was
    wrong.
  * **RENAME (2026-09-01):** `ROM00:46E9` `Session_ConnectCheckCoro` ->
    `Session_InitState`. It performs no connect check: it sets `E48D = 2` and
    `E6FC = 0x37`, then clears a dozen session variables. It was briefly
    labelled `Session_EnableStateMachine`, which named only the `E48D` side
    effect; that stale label is deleted. Note `create_label` on a function
    entry adds a second symbol rather than renaming — use
    `rename_function_by_address`.
  * **CORRECTION — the `E48D` gate polarity is INVERTED (2026-09-01):** two
    entries above state that `SessionStartDataMode` dispatches "only when
    `E48D == 2`". Backwards. The comparison helper `ram:E04B` returns with
    **Z set when its operands differ** (`E055`: `LD HL,0 / XOR A / RET`;
    `E064`: `LD HL,1 / LD A,L / OR H / RET`), and `ROM00:453F` branches
    `JP Z,454B` — so the dispatch path is taken when `E48D != 2`, and
    `E48D == 2` returns 0 **without** dispatching. Consequences: on the
    Load/Run path (`E48D = 0`) the transition table **is** consulted, so
    `g_bSessionState` advancing `00 -> 02` is consistent with the table
    rather than evidence against it; and `Session_InitState` setting
    `E48D = 2` *quiesces* dispatch rather than arming it.
  * **End-to-end confirmation of the state machine (2026-09-01):** a loaded
    COM calling `ram:EE00` (`C_ABORT`) from the boot state puts
    `C_ABORT / called from / NOT-STARTED / Press >> to continue` on the LCD.
    That is `SessionCoroJumpTable`'s illegal-transition path, and it confirms
    in one live run: the table's row/column indexing, that bit 7 set means
    illegal (row 0 column 16 = `0x80`), that both name tables render the
    message, that `g_bSessionState` is the row index, and that it boots to 0.
  * **Why an application call does not return — ANSWERED (2026-09-01):** not
    a calling-convention or scheduler issue. `ram:D837` is an ordinary
    stack-frame prologue: saves `IX`/`IY`, invokes the body through
    `D836` (`JP (HL)`), epilogue at `D84C` restores and returns the result in
    `HL`. The firmware simply stops to talk to the user — an illegal
    transition raises a message box and waits in `SessionWaitContinue` for a
    keypress. `Session_InitState` similarly displays `Comms in progress` and
    does not return. An application must therefore drive a **legal**
    transition sequence, or satisfy the UI.
  * **Reachability of the transition table computed (2026-09-01, CONFIRMED):**
    breadth-first from `NOT-STARTED` over legal transitions reaches only
    `DISCONNECTED`, `CONNECTED`, `READY-RX-DATA`, `RECORD-RX`, `TERMINATED`
    and `CRASHED`. Unreachable: `READY-RX-PROG`, `READY-TX-DATA`,
    `READY-TX-PROG`, `BLOCK-RX`, `RECORD-TX`, `DATA-SET-TX`, `BLOCK-TX`. No
    cell anywhere in the table yields state 4, 5 or 6 — not on the legal path
    and not on the illegal path, where the low seven bits would still become
    the new state. So the only complete transfer the table permits is Data
    Reception (`C-INIT-COMMS` -> `C-DIAL` -> `C-COMMAND` -> `C-RX-REC`).
  * **The table is a PARTIAL validator, bypassed for everything else
    (2026-09-01, CONFIRMED):** Program Reception — which the firmware plainly
    performs — enters `BLOCK-RX`, a state the table cannot reach. That is
    what the mode gate is for. With `ram:E48D = 2`, `SessionStartDataMode`
    returns without consulting the table, so an operation runs whatever the
    state. Proven by A/B: an application that sets `E48D = 2` itself and then
    issues `C_ABORT` from `NOT-STARTED` gets no message box and `E512 = 0`
    (the early-return marker), where the identical call with `E48D = 0`
    raises the illegal-transition box. Treat the table as evidence of the
    protocol's intended shape, not a constraint the firmware enforces.
  * **Still OPEN — what an operation routine waits on:** suppressing
    validation removes the message box but a headless caller still does not
    resume, so the operation routines do more than issue their command. That
    is now the single obstacle to driving a full upload sequence from an
    application.
  * **State machine decoder + generated diagram (2026-09-01):**
    `analysis/decode_state_machine.py` reads the transition matrix and both
    name tables straight out of the ROM image and emits either a report
    (legal transitions, reachability with shortest command paths, states
    never produced by any cell, and the near-universal commands with their
    exceptions) or a Mermaid diagram (`--mermaid`). The published diagram in
    `doc/protocol/commstar.md` is now generated by it rather than drawn by
    hand, so it cannot drift from the firmware; dashed states are those no
    legal path can reach. The script independently reproduces every finding
    from the manual pass, including the `C_ABORT` exception (illegal from
    `NOT-STARTED` and `CRASHED`) that the hand reading originally got wrong.
  * **ANSWERED — what an operation routine waits on (2026-09-01):** it waits
    for the peer. With validation suppressed `SessionStartDataMode` returns 0,
    and the operation wrapper reads 0 as *proceed*: `ROM00:547C` is
    `JP NZ,54E1` (non-zero exits), so zero falls through to `CALL 593A`, a
    thin wrapper on `SessionTxRunState65` (`ROM00:5BA6`). That prepares a
    frame header, calls `SessionSetParams(0x65, 6, 6, 0, 0)`, sends the frame
    via `SessionTxSendFrame33`, then waits in `SessionRxByteLoop`. So the API
    operations are **link transactions**, not local calls that happen to
    block — a call made with no host attached cannot return, and that is the
    protocol working correctly rather than a fault. Exercising the API
    therefore needs a responding peer, which is precisely what a Commstar
    server is.
  * **New wire state value `0x65` (2026-09-01):** passed to `SessionSetParams`
    and `SessionTxSendFrame33` on the `C_ABORT` path. This is the first direct
    evidence that the `44`/`45`/`60`/`61`/`64` family are the parameter an
    operation *transmits*, not merely internal labels.
  * **Still OPEN:** in the bare-COM test the `LinkBlockTx` (`ROM00:3277`) hit
    counter never fired, so execution blocks between entering
    `SessionTxRunState65` and reaching the link driver — plausibly because no
    session was ever opened. `C-INIT-COMMS` (`ram:EE20`, stub slot 65) is the
    legal first command from `NOT-STARTED` and takes a mode byte on the
    stack; driving that first, with the harness's synthetic peer attached, is
    the next experiment.
  * **`C-INIT-COMMS` argument layout (2026-09-01, CONFIRMED):** `ram:EE20`
    reads its mode byte from the caller's stack at **`SP+4`** — the third
    word down from the top of the pushed arguments — so at least three words
    must be pushed. Calibrated by pushing eight distinguishable values and
    observing which reached `ram:E48D` (`0x33`, the sixth of eight pushed).
    The firmware pushes four words, passes mode 0 (`ROM01:12F4`), and unwinds
    20 bytes. `ROM00:4563` created as a function `Session_InitCommsCmd` with
    a plate; its Ghidra body is a stub because the routine runs on into the
    shared init sequence and its extent is not bounded.
  * **An application drove a VALIDATED Commstar transition (2026-09-01):** a
    loaded COM pushing four zero words and calling `ram:EE20` leaves
    `ram:E48C = 1` — the transition table's output for
    `NOT-STARTED` + `C-INIT-COMMS` -> `DISCONNECTED`, exactly what walking
    the table predicts. The table's prediction is therefore confirmed by
    execution, not only by reading. The wrapper then takes its zero-result
    path into session init (`E6FC = 0x37`) and displays
    `Comms in progress`, waiting for the host. Note it *stages* the next
    state in `E48C` without committing it — `g_bSessionState` stays 0; the
    commit sites are the 17 `LD A,(E48C) / CALL Session_SetState` sequences.
  * **Next: an emulator task, not an analysis one.** Attach a responding peer
    to an application-driven session. The harness's synthetic peer is wired
    to the Load/Run trace's phases; generalising it would allow the full
    `C-BEGIN-FILE` / `C-TX-REC` / `C-END-FILE` / `C-END-TX` upload sequence
    to be exercised and captured.
  * **IR control/status bit ROLES established (2026-09-01):** "set bit 5" is
    replaced by what each bit does in the protocol, read directly from the
    branch it drives rather than guessed from electrical convention.
    `LINK_STATUS` (`4Bh`): bit0 a received byte is available (gates `INI` at
    `ROM00:33D4`); bit1 block finished / status valid — while bits 0 and 1
    are both clear the handheld waits, then fails `EEh`; bit2 one further
    byte to take (extra `INI` at `33F4`); bit3 transfer failed, `ECh`; bit4
    inbound data pending, must be CLEAR before the handheld transmits
    (`32BB`); bit5 error latch sampled at end of transmit, set yields `ECh`;
    bit6 handshake busy, must go clear (`32F3`); bit7 ready to accept a
    transmit byte, polled before every `OUTI` (`3319`). The receive decode is
    **one** status read shifted by successive `RRCA` at `33CF`, testing bits
    0,1,2,3 in order — not four separate polls, which the earlier
    "polls bits 0-3" wording implied.
    `LINK_CTRL` (`4Ah`): bit0 transfer active, bit1 port select from
    link-id bit 5, bit4 direction/enable, bit5 strobe.
    Still OPEN: what any bit means electrically at the connector, and whether
    a real controller derives them this way. Two things corroborate the
    reading — the turn-taking rule follows from bit 4, and the synthetic peer
    implementing exactly this table completes real sessions. Repeatables set
    on `io:004A` and `io:004B`; tables added to the protocol page and the
    memory/IO reference.
  * **IR bit names INFERRED and an IR hardware section added (2026-09-01):**
    `LINK_STATUS` bits named `RXRDY`/`RXEND`/`RXTAIL`/`RXERR`/`RXBUSY`/
    `TXERR`/`HSBUSY`/`TXRDY`, `LINK_CTRL` bits `XFREN`/`PORTSEL`/`DIREN`/
    `STROBE`, all marked INFERRED — a naming convenience derived from the
    branch each bit drives, not a datasheet. The protocol page gains a "How
    the IR hardware works" section describing the transfer as the six-step
    handshake it is, and stating the practical consequence: a half-duplex,
    credit-based byte pump where the handheld will not transmit while the
    controller reports inbound data, and will not send a byte until the
    controller says it can take one.
  * **`micronic.peer.CommstarPeer` built (2026-09-01):** a protocol-aware,
    **transport-independent** Commstar host. It parses handheld
    transmissions and generates replies, knowing nothing about the emulator,
    the latches or a serial port — so the same object serves the emulator now
    and a physical IR adapter later. `analysis/test_peer.py` (15 tests, no
    emulator) checks framing, request decode and reply generation against
    captured bytes.
  * **Shadow-mode verification (2026-09-01):** the peer runs alongside the
    hand-written phase script inside a live trace and is asked what it would
    have replied at each point. **V24 mode 1: 12 agreed, 0 differed. PLINTH:
    13 agreed, 0 differed.** The single difference in the first run was
    policy, not protocol — the shadow had no application callback and sent a
    control ack where the script sends the state-44 `OK` object; attaching
    the same policy closed it. Pinned by `CommstarShadowPeerTest`. The
    "unsolicited" counts are peer-initiated type-2 frames the script pushes
    without a preceding request, which the peer correctly does not generate
    as replies.
  * **Next:** retire the phase script in favour of the peer now that they
    agree, and add the upload policy (`C-BEGIN-FILE` / `C-TX-REC` /
    `C-END-FILE` / `C-END-TX`) so a handheld-to-host transfer can be driven
    and captured for the first time.
  * **Phase-script retirement ATTEMPTED AND REVERTED (2026-09-01):** making
    `CommstarPeer` the sole source of replies on the Load/Run path broke
    `test_synthetic_loadrun_streams_multichunk_com` — the two-chunk stream
    hangs (180 s timeout). The single-chunk case passes, so the desync only
    shows with more than one exchange. Diagnosis: the script also performs
    **peer-initiated pushes** — queues sent with no preceding request — and
    the peer, which generates one reply per request it sees, can have a reply
    queued at exactly those points. Feeding the peer's stale reply instead of
    the intended push desynchronises the stream. Reverted rather than shipped;
    shadow mode is retained and still agrees 12/12 (V24) and 13/13 (PLINTH).
    **To retire it properly the peer must model peer-initiated frames**, so it
    knows when it is *not* the one to speak. That is a peer-side change, not a
    harness one.
  * **`--commstar-peer` mode added (2026-09-01):** attaches the protocol peer
    to a plain `--upload` run so a loaded application can hold a session with
    something on the other end, plus an upload policy that records any object
    the handheld sends and acknowledges it. Additive — the Load/Run path is
    untouched. The peer pump is generic: whatever the handheld transmits, the
    peer answers, with no phases or breakpoints.
  * **Application-driven upload attempt (2026-09-01):** a COM issuing
    `C-INIT-COMMS` / `C-BEGIN-FILE` / `C-TX-REC` / `C-END-FILE` / `C-END-TX`
    with the four-word argument layout blocks in the **first** call. The
    screen reaches `Comms in progress`, but `LinkBlockTx` and `LinkOpen` never
    fire and the peer sees no traffic at all (`replies=0`), so the session
    stalls before any transmission. The peer and pump are therefore unproven
    against an application-driven session — they are proven only against the
    Load/Run route.
    *Hypothesis for next time:* the session needs the service-33 / link-IRQ
    plumbing that the Load/Run trace arms and a bare `--upload` run does not.
    Compare what `--trace-loadrun-source` sets up before its first exchange.
