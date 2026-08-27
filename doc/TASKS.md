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
    0C = interrupt flags. See rtc-investigation.md. The 4x
    latch cluster (4A/4B/4D/4F) is NOT the RTC (owner-confirmed).
14. **ROM documentation-coverage baseline** (doc/gap-analysis.md):
    of 480 functions, only 88 (18 %) carry meaningful names; 392 are
    still auto `FUN_*` (ROM00 237, ROM01 91, RAM modules ~40). The
    named set is the boot/RTC/link/LCD/clock/diagnostic subsystems.
    In-progress tracked there.
15. **CP/M implementation comparison** (doc/cp-m-comparison.md):
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
17. **DIPOSB programmer's guide** (doc/diposb-programmers-guide.md):
    self-contained doc to read alongside a CP/M 2.2 guide. Covers the
    BDOS call interface, RAM file system (A/B drives, 16-drive select,
    stubbed alloc/DPB fns), device-routed console I/O, the F3-FF
    extension fns (device/config/RTC/alarm/delay), banked calls (RST2),
    and a practical differences/avoid table.

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
- **Full emulator boot to a live link I/O** (updated 2026-08-24,
  emulator research round — scratch scripts in /tmp/opencode:
  boot_diag.py / boot_timeline.py / fixB_regen.py):
  * The 16C9 HALT-wait is the **keyboard event wait**, not just the
    tick: kernel EI/LD A,1/LD (FFA8),A/HALT at 16C3-16C9, wake checks
    fbc9&fbca; measured fbca=07 → caller 1105 = keyboard read waiting
    for fbc9 bit2. tick => fd4f/fbca recompute, but exit needs an
    event bit that no emulated source ever posts.
  * INT injection works (7219/8057 offered INTs accepted) but is
    coarse: one INT per 50000-cycle slice (~71 Hz worst case), and
    `push_tick()` is never called → RTC RegC PF never set → date-
    change/alarm paths dead (fd4f=00).
  * Fix A (timebase): SLICE=3400 (< one 1024Hz period ~3496 cyc),
    accrue unconditionally (drop the ffa8 gate), call rtc.push_tick()
    per elapsed period, then on_handle_active_int() when ffa8!=0.
  * Fix B (events, VERIFIED working): when PC parks in 16C9-16D2 with
    ffa8=1 → fbc9 |= 0x04 and store 0x0D (ENTER) into the FBF0 key
    ring; boot left the wait and entered the dispatch module; repeat
    per menu prompt. Matrix injection via ports 00/02 is NOT viable
    (firmware never scans them during the wait — measured).
  * Recommend A+B together; B commented as a cheat. Also replace the
    slice-boundary PC watchdogs (miss all target PCs) with
    mach.set_breakpoint if the wheel supports it.

## In progress

- **Decode Commstar session/frame layer** — DONE for the *static*
  surface: LinkTransferService (2F86), LinkTransportCall (2F1A), RX
  dispatcher (2FBD), LinkValidateFrameHeader (30DC), frame builders
  (3106/3130), session bootstrap (0F40-10FB), hardware path (4Dh TX /
  4Eh RX / 4Bh status / 4Ah ctrl). Closed: command-id↔name mapping
  (LinkCommandLookup table 31F2 = 2B/2A/23/03; abort set 44/45/60/61/64;
  TX set 00/04/09/0C), link-id/slot (FE83 → fbc5 bits6-7), RECORD/BLOCK
  framing (FDE6 type 2/4 + FDE4 len + cmd-id FDE7), reply prefixes
  (EE01 idle, EF01 mismatch, E0 02/EE 02, E0 04=state3, E0 05=state2).
  Remaining (runtime/live): the per-record/per-block **frame byte**
  content in the session state machine (RECORD-*, BLOCK-*, C-COMMAND)
  — needs a live session or hardware capture.

## Next (priority order)

1. **Capture RECORD/BLOCK payload bytes live** (hardware bus capture on
   4Dh/4Eh, or full UI/Commstar emulation to a live transfer) — the
   one remaining runtime item for the file-transfer tool.
2. **Confirm the exact TX/RX status bits** (4Bh bit0/1/2 RRCA chain,
   bit7 RLCA) and 4Ah strobe timing from LinkBlockRx (branch-confirmed,
   needs traces for timing).
3. **Side/external port — model corrected & fully grounded (2026-08-24)**:
   I/O **2Dh** (`EXTBUS_EDGE`) + **2A/2C** latches are a bit-banged
   **external-device bus front end** (ExtBus*, ROM00 120F-14EE),
   dispatched by **active wire-id `fdca`** via LinkCommandLookup
   `{2B,2A,23,03}` → `0x1221` (2B/2A) / `0x1893` (dead). The default
   FE83 wire table = `{0xAB,0x2B,0x67,0x67}`; **0x2B = EXT STORAGE
   ADAPTER** (the only named device + "V24 ADAPTOR"). **Internal A:/B:
   drives are pure RAM** (never on this bus). **EXT STORAGE data moves
   over the 4x byte transport** (`LinkTransportCall`/`LinkBlockTx/Rx`);
   the 2D edge-bang is a *separate* 2-wire front end. A **user decoder
   hook** lives at `fbc2` (fbc1=bank, fbc0=RST10 stub), defaulted to
   discard (1567). **BDOS fn 03 (RDR:) = `BdosReaderInChar` (1080)** is
   a real reader path (1B/count/data via ring F95E). The earlier
   "barcode/light-pen" branding is **not proven** — retitled neutral.
   See protocol-comms.md + barcode-reader.md (updated).
   **Developer tie-in: install decoder at `fbc2`; read via fn 03,
   or arm directly via RST 10h -> ExtBusArm (1221).**
4. Emulator: verify a full send under trace (needs boot fix).
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
   pure-timer + HALT-poll on FD4D, caller BdosFcSetAlarm 1129).
   FUN_ROM00__35c9 → Sound_Off (2Bh write; quiet-bus before 2Dh
   timing, LIKELY). Plus created Link_StatusCompare_FD4B (223E) and
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
   NEXT: name the survivors (gap-analysis.md lists them).
7. **ROM01 / UI survey for `fbc5` and `fbc2` writers** (review §6.3) and
   **`fbc7/fbc8` consumers** (§6.4, BDOS fn F9 presets) — likely a
   "device" settings screen in ROM01. **CLOSED 2026-08-24 (§6.2)**: the
   reader-completion event bit is `fbc9` bit0, posted by
   `ExtBusComplete`(14A3)→`LinkResetSession`(30BD); that wakes the
   fn-03 `EventWaitForLink` HALT (see barcode-reader.md).
8. **Residual inverted-dispatcher doc claims** (found by the docs
   agent 2026-08-24): `doc/cp-m-comparison.md:27-28` and
   `doc/protocol-comms.md:611` still carry the pre-fix "25h-F2h
   extended table" framing. Fix them with the corrected model (fn
   <25h→F1EB; F3-FF→F1D1 wrap via DEC B; unmatched 25h-F2h → wild
   pointer, nothing rejected).
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
9. **Stale barcode-reader.md leftovers** (docs agent flagged):
   H1 still ends `(was "barcode reader")` and §"What a symbology
   decoder does" still says "(if this is a light-pen)" — both now
   stale versus the owner adjudication. Reword.
10. **Name `FUN_ROM00__35c9`** (the quiet-bus helper in the capture
     path, review §2.3) during the work-item-queue analysis (item 5).
11. **Decode the error-screen format** — owner observed on hardware:
     `Error 8000 (238/001) Plinth not connected`. Determine what the
     three numeric fields mean (`8000`, `238`, `001` — likely error
     code / line-or-module / severity or similar, UNKNOWN). Entry
     points: the "Plinth not connected" path (ROM00:6d6f) and the
     runtime error-code→string table (ram:d0e0 / ROM01 7c80). Byte-
     verify the meaning of each field from the renderer that prints the
     banner, then document it as an "error screen format" section
     (extend protocol-comms.md "Error-path triggers" or add a new
     doc section).

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
19. **DIP program format documented** (diposb-programmers-guide.md §7b +
    os-diposb.md): DIP = block-structured loader-record stream, same
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
  os-diposb.md, AGENTS.md §3 — an earlier "bottom/front" reading was
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
  after any run_analysis (gap-analysis.md records it). Program saved.
- 2026-08-24 (docs batch — delegated; site rebuilt): os-diposb.md +
  diposb-programmers-guide.md dispatcher claims corrected (+HAZARD);
  memory-map.md FE83/FE93 rows fixed (16 one-byte wire ids; letter
  indexing is FE93's); RST2 listings got the missing `LD E,(HL)` in
  memory-map.md + interrupts.md (stray "0186C" fixed); barcode-reader
  fbb7 typo + header re-stated with the owner adjudication.
- 2026-08-24 (emulator research — delegated): stall at 16C9 is the
  keyboard-event wait (fbca=07, caller 1105); INT injection coarse and
  push_tick() never called; Fix A (timebase) + Fix B (fbc9|=4 + FBF0
  ring ENTER, VERIFIED to leave the wait) — details above in the
  emulator in-progress entry; scratch /tmp/opencode/boot_diag.py,
  boot_timeline.py, fixB_regen.py.
- 2026-08-24 (coverage audit #2): 668 functions, 610 (91 %) named, 58
  FUN_* remaining (ROM00 1, ROM01 14, ram 43) — doc/gap-analysis.md
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
    via deferred callback; bits 4-7 unused) - barcode-reader.md updated.
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
  * Docs: cp-m-comparison.md 25h-F2h wild-pointer claim fixed (item 8
    CLOSED); SessionBdosPrep renames propagated (os-diposb.md,
    protocol-comms.md).
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
  * SURVIVES (documented in memory-map.md + the four plates): the
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
    KernSwapCopySrc. memory-map.md: owner-confirmed rationale for the
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
    in cp-m-comparison.md / os-diposb.md / diposb-programmers-guide.md.
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
    extensions) LIKELY. Full table in memory-map.md "Patch/hook
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
    memory-map.md row; BankedCallCommonEntry's ROM00:230A call lands
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
  * 675A renamed StateWordGet_E8D6 + plate. memory-map.md gained the
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
    gap-analysis.md refreshed (5th audit).
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
    gap-analysis.md refreshed (6th audit). This closes the plate debt
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
    latches + arms fbbf). io-map.md updated.
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
  * Device-selection callbacks (ram:D081 = 5 indirect ptrs, Module B):
    [0] WORKSTATION MEMORY -> 0A67 (dialog config),
    [1] WORKSTATION RAMDISK -> 156F (reset slots + banked dispatch),
    [2] PLINTH -> 1177 (no-op), [3] V24 ADAPTOR -> 1177 (no-op),
    [4] EXT STORAGE ADAPTER -> 156F (different param 0x41 vs 0x42).
    "RAMdisk size" string at 7B45. Plate set on ram:D081.
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
    Documented in protocol-comms.md "Error-path triggers".
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