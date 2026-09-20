# Task list — Micronic 1000 reverse-engineering

State: continuously updated as work progresses.

> Historical session log: see [`session-log.md`](session-log.md).

---

## Done (verified vs docs + Ghidra + byte-level traces)


1. Map syscall table at ram:d6f4 (3 loader primitives + hidden terminator)
2. Kernel installers -> Kernel_KernelToRam (ROM00:02FE),
   CopyKernelDispatchBlock (ROM00:3BAA)
3. ROM00 gap analysis; ROM01 gap pass 1
4. Boot load scripts CLOSED (decode_chains.py; grammar fn=0/1/2/FFFF)
5. Deferred-call queue / transfer-vector table SOLVED
   (queue ED1C-F17F doubles as task list AND UI vtable targets)
6. Template builder / object system decoded (ROM01:0271)
7. Warm restart path decoded
8. Diagnostic monitor entry verified as a returning stub (`ROM00:3513`,
   `XOR A; RET`, rechecked 2026-09-20). Prior built-in-monitor and
   service-key monitor-boot claims withdrawn. External monitor/ICE use
   remains SUSPECTED; resolve with alternate-ROM/debugger evidence or an
   interception trace. See [debug facilities](../re-notes/os-diposb.md#debug-facilities).
9. Keyboard matrix fully decoded (H+L+P = HELP service key;
   drive(02)=col bit, sense(00)=row bit, index=row*6+col)
10. Interrupt architecture fully decoded (IM1 -> 0038 -> F5F3 -> F64D ->
    polled fd84 event table; NMI -> 0066 -> F5F6)
11. Clock self-test decoded (Clock_SelftestTickWindow ROM00:2828)
12. Session/Commstar reference data located (ROM00:6A50-6E90)
13. **RTC RESOLVED: 08h/28h indexed pair IS the HD146818** (address
    latch / data). Register map proven from firmware sequences:
    regs 00,02,04,06,07,08,09 = time file; 0A/0B = status/ctrl;
    0C = interrupt flags. See internals/rtc.md. The 4x
    latch cluster (4A/4B/4D/4F) is NOT the RTC (owner-confirmed).
14. **Documentation coverage:** current counts and their scope are maintained
    only in [gap-analysis.md](gap-analysis.md). See the historical pass log
    for earlier baselines; they are not the current state.
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
     `UI_FormExitDispatchNext` (ROM01:06D3) double-dereference. Ghidra
     names: `Program_PrepareLoadGeometry` 0A67, `Program_LoadByName` 0B82,
     `Program_ConsumeInputChunk` 0BAC, `Program_LoadDipOrCom` 0CE7,
     `Program_RunByName` 106F, `Program_GenerateBlockChecksums` 0957,
     `Program_VerifyBlockChecksums` 09C2, `Program_NormalizeLoadRange`
     0AE3, `Program_ReportLoadError` 0CCB, `Program_LoadedProgram` ram:D7F0
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

## In progress

- **Plinth shadow-peer divergence — RESOLVED (2026-09-20):** bisected to
  `e5baacf`; root cause was that the synthetic route pushed the program object
  peer-initiated (on its internal-state oracle/timer), so the request→reply
  peer could not predict it. The route is now **request-driven** (it answers
  the handset's repeated state-`0044` block request) and the shadow peer serves
  the program via `ProgramDownloadPolicy`, giving
  `agreed=14 differed=0 unsolicited=0`. `CommstarShadowPeerTest` passes on both
  routes. See the session log for the full bisection and fix.

- **Documentation consistency corrections (2026-09-20):** current summaries
  reconciled; see `doc/review.md` for implementation status. The local-only
  storage conclusion was overturned by fresh BDOS `2Eh` tracing and review.
  Still open: routed per-operation pointer/request contracts and successful
  peer replies; capture these before claiming operational B:/C:/D: storage.

- **Session modules loaded into Ghidra** (MCP inline script; also in
  FillBatteryRam.java). Module A (D893-E0F3), Module B (D081-D2CA),
  A2 (E104-E233), params (E0F4), misc (E22D), page-zero (E2FA),
  disassembled.
   * `ram:da13` = session-to-BDOS bridge
     (RESOLVED 2026-09-19, CONFIRMED, byte-verified)
     — copies function number → C and argument → DE
     from the session register file (`E0FE`/`E100`,
     populated from the stack by `ram:D86E`), issues
     `CALL 0005`, returns BDOS A zero-extended in HL
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
  * Both directions now run end to end against real firmware: program
    download to the handheld and RECORD upload from it. The synthetic peer
    can now replace its internal RAM/PC receive-arm oracle with a tested
    completion-relative 500 ms delay. Physical timing remains unverified.

- **Decode Commstar session/frame layer** — the validated envelope, numeric
  type-2/3/4 exchange, program-download blocks, RECORD upload stream, and
  principal session transitions now run against real firmware in bounded
  emulation. The state-`0000` exchange formerly called the builder preflight
  is now characterised and regression-tested. Remaining: replace the
  diagnostic receive-arm oracle as the normal peer policy after physical
  validation, recover still-unknown object fields, and establish the physical
  return handshake.

## Next (priority order)


*No analytic work remains — §12 FINAL PASS fully CLOSED 2026-09-19 (items 1,2a,2b,3,4,5,6 DONE), `ram:DA13`/`ram:D36A`/`ram:D837`/`ram:EE00-EE4F`/vtable reader/barcode path all RESOLVED/WITNESSED, 4 `FUN_*` retains documented as dead/reachable-unknown. The only remaining work is owner/hardware-dependent (below). Historical §12/RESOLVED details are in the Detailed backlog; do not re-add analytic items here.*

### Hardware-dependent priorities (unchanged)

1. **Phase 0 gate:** run the `2609` record-stream build (and/or the `2E3E` witness build — 824 bytes, SHA-256 `aa843c38dcb8131612d3d235871397bf6e6ace73d00aeeb50c79d4a7a6f124a0`) and read `LINK_STATUS` bit 6 behaviour with no peer.

2. **Phase 2:** receive-convention sweep with the witness ROM (`2E3E`, now raises `LINK_CTRL` 6/7) + the Arduino `RX_SWEEP` mode — the firmware holds 6/7 clear for the ~10 ms TX transaction and raises them after; whether the controller's receiver is inhibited during that window is Provisional, so a reply timed after the transaction is the safe choice either way (a burst-timed reply at ~1–9 ms lands inside the window in which the firmware holds 6/7 clear).

3. **Phase 3:** bidirectional payload with `micronic.peer.CommstarPeer`.

4. **Keep the existing remaining hardware items** (4Bh/4Ah electrical mapping, complementary port state + EXT STORAGE ADAPTER attachment point — owner confirmation — banked-RAM dump, Z80-bus fallback).

Process: `docs/static-analysis` (PR #15) merged to `master` 2026-09-20; the documentation-review follow-ups (PR #16, #17) also merged. `ir/8-transmit-arm` (PR #14) rebased to code-only (3 commits, `analysis/` only, tests pass) and awaiting merge.

### Detailed and historical backlog

The items below retain evidence and completion history. They are not the
current priority order; the concise lists above are authoritative.
5. **Examine the queued work-item system** — **DONE (2026-08-25,
   delegated analysis, applied + saved).** The FD5C queue is a 10-slot
   countdown-timer/callback table serviced from the RTC wake path, not
   an IRQ dispatcher: RTC_WakeReasonFetch (2206) → Comms_WorkItemSweep
   (224C) → Comms_WorkItemDispatch (2275); register/cancel =
   Comms_WorkItemRegister (2189, CY=full) / Comms_WorkItemCancel (21BA;
   listing shows 3 INC IX but bytes are 4 — stride is 4, do not
   "fix"). ExtBus_BusQueueWorkItem (135C, re-arming poll timer f9ae → 5
   ticks) / ExtBus_BusPoll (12EC; no-edge path has an OPEN weird DI
   fallthrough at 1328). RtcAlarmRegWorkItem → RTC_AlarmSleep (21EC,
    pure-timer + HALT-poll on FD4D, caller Bdos_InternalTimedWait 1129).
   FUN_ROM00__35c9 → Sound_Off (2Bh write; quiet-bus before 2Dh
   timing, LIKELY). Plus created RTC_AlarmDateMatches (223E, formerly
  `Link_StatusCompare_FD4B`) and
   Update remaining OPEN bits: meaning of fd84/RegB runtime bits;
   fbc9 bit0 → fn03 staging link; whether the alarm handler also
   writes FD4D directly.
   Also named from the repair batch + loaded-symbol recovery: the ROM01
   UI survivors (see item 6) and UI_PostDescriptor (6633, posts
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
   `ExtBus_BusComplete`(14A3)→`Link_ResetSession`(30BD); that wakes the
   fn-03 `Link_WaitForLink` HALT (see manual/barcode-reader.md).
8. **Residual inverted-dispatcher doc claims — CLOSED 2026-08-28.** Active
   documentation now uses the corrected model: fn <25h -> F1EB; F3h-FFh ->
   F1D1 wrap via DEC B; unmatched 25h-F2h -> wild pointer, nothing rejected.
8a. **6e77 inline-data repair — DONE 2026-09-17.** The four inline operand
    spans in `Session_EvalRecordSteps` (`ROM01:6E77`) are now defined as
    `uint` data and labelled `tbl_corstep_0`..`3` (`ROM01:6E81`, `6EA5`,
    `6EB4`, `6ED1`); flow resumes correctly at `6E85`/`6EAA`/`6EB8`/`6ED5`.
    The inline bytes are the operands of the `CALL DC37`/`DC23`/`DC30`
    frame-op idiom (consumed 4-byte parameters).  Function count unchanged
    (1101) and the program was saved.  See the 2026-09-17 session entry.
8b. **ram:pending compiler-runtime page — label + plate DONE 2026-09-17.** All
    helpers are already labelled (`Lib_And16` `e023`, `Lib_Not16` `e02b`,
    `Lib_Or16` `e033`, `Lib_Xor16` `e03b`, `Lib_Lnot16` `e043`, `Lib_Eq16`
    `e04b`, `Lib_Ne16` `e05a`, `Lib_SignedLe16` `e06a`, `Lib_SignedGe16`
    `e06b`, `Lib_SignedGt16` `e085`, `Lib_SignedLt16` `e086`, `Lib_Neg16`
    `e09f`, `Lib_Sub16` `e0a9`, `Lib_Unsigned*` `e0d9`/`e0da`/`e0e7`/`e0e8`,
    memmove at `ram:d9a0`).  Plates added for the two that had none
    (`Lib_Not16`, `Lib_Neg16`); the trivial logic ops carry SHORT-form plates.
    **RESOLVED 2026-09-19 (CONFIRMED):** `ram:DA13`
    session-to-BDOS bridge closes the `6A36`
    constructor / `6AA9` stream-reader mapping;
    former `da13` OPEN superseded (see Next
    priorities and 2026-09-19 session entry).
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
      FileSearchNextCb renamed Lib_DecU16 (2026-08-27, below).

### 12. FINAL PASS — complete annotation + naming cleanup (defer
    until the reverse-engineering is done; owner-decision
    2026-08-27)

    One coordinated sweep at the end, not piecemeal ad-hoc
     patches. Baseline 2026-08-27: 935 functions, 131 still
     `FUN_*`, 27 dispatch tables. Status 2026-09-19
      (Ghidra saved; raw-address cites migrated —
      137 + 127 rewrites, missing-label scan 99 → 90
      created; no new inference in this docs pass):

    1. **Name + plate every `FUN_*` — DONE** (see
       `research/gap-analysis.md`; 914 internal / 915
       guarded, 4 retained `FUN_*` with plates and
       documented open questions; 99.6 % named).
    2. **Rename wrong or grandfathered names**
       a. **Grandfathered `Module_Name` churn —
          DONE 2026-09-19 (590 names → 31-module
          taxonomy; 588 applied in Ghidra + 2
          already-renamed collisions; word-boundary
          doc sync across 24 files, commit
          `993a45d`; CONFIRMED):** canonical 31
          modules `Session_` `Bdos_` `Fs_` `Lib_`
          `Link_` `UI_` `Syscall_` `Field_`
          `RegFile_` `Lcd_` `Program_` `Disk_`
          `Tty_` `RTC_` `ExtBus_` `Diag_` `Kernel_`
          `KernelImage_` `Kbd_` `Device_` `Dialog_`
          `Text_` `Comms_` `Clock_` `Power_` `Util_`
          `Coroutine_` `Monitor_` `SelfTest_`
          `Sound_` `Fcb_` `Form_` `Boot_`
          `Barcode_`; normalizations `Kern*`→
          `Kernel_`, `Rtc*`→`RTC_`, `Ui*`→`UI_`
          (owner choice, uppercase per AGENTS.md
          §7), `lcd_*`→`Lcd_`, `tty_*`→`Tty_`,
          `dialog_*`→`Dialog_`,
          `session_*`→`Session_`,
          `Coro*`→`Coroutine_`,
          `Keyboard*`/`Key*`→`Kbd_`,
          `Reg*`→`RegFile_`, `Self*`→`SelfTest_`;
          reassignments `Banked*`→`Kernel_`,
          `Console*`→`Device_`, `Delay*`→`Util_`,
          `Str*`/`Arith*`/`Bcd*`/`Checksum*`/
          `Format*`/`Num*`/`Pack*`/`Table*`→`Lib_`,
          `BlockAlloc*`/`FileSearch*`→`Fs_`,
          `StateWord*`/`CmdDispatch*`→`Session_`,
          `ServiceCall*`/`thunk_*`→`Syscall_`,
          `Nop*`→`Diag_`, `TemplateBuilder`→`Form_`,
          `Port2b*`→`Sound_`,
          `ExtDecodeHook*`→`ExtBus_`,
          `Descriptor*`→`UI_`; do-not-regress
          identities preserved (`RTC_`, `Link_`,
          `Session_`, `ExtBus_`); protected exact
          names kept (`BankedRst08/20/28/30/38`,
          `Rst2Dispatch`/`Rst4IrqPoll`/
          `Rst5FatalScreen`/`Rst6ZeroRet`/
          `Rst7IrqPoll`, `ColdStartSelfTestBanner`,
          `LinkRxDispatcher`).
       b. **Wrong names — DONE 2026-09-19 (5, byte-
          verified, docs synced):** `ROM00:3BB8`
          `Coroutine_TaskSwitch` → `Coroutine_IndexedLookup_6A4A`
          (indexed lookup into table at `6A4A`; real
          `Coroutine_Enter` is `ram:D837` — duplicate
          mis-name corrected; `ram:D837` later renamed
          `Coroutine_Enter` 2026-09-19), `ROM00:3BD0`
          `Coroutine_SessionMul16` →
          `Coroutine_IndexedLookup_6B67` (into `6B67`),
          `ROM00:7C14` `Session_Cmp16Bit` →
          `Session_CmpLeU16` (HL=1 iff HL<=DE unsigned),
          `ROM00:7C22` `Session_Cmp16BitB` →
          `Session_CmpGtU16` (HL=1 iff HL>DE unsigned),
          `ROM01:6F29` `Syscall_Call_Id2Byte` →
          `ServiceCall_BdosFn2` (calls `Session_BdosCall`
          `ram:DA13` with fn 2). Grep confirms 0 stale
          mentions in `doc/`.
     3. **Plate-quality pass — DONE 2026-09-19
        (CONFIRMED, Ghidra saved; function list
        unchanged; plate coverage 100 %):**
        - **Unplated functions — DONE 2026-09-19:** all 144
          functions with `plateLen=0` now carry plates (46
          `ram` — mostly `SessionOpStub_*`/`Lib_*`/`RegFile_*`,
          notable `Fcb_ParseFilename` CP/M FCB parser,
          `Kernel_RunStagedCall` — 33 `ROM00`, 65 `ROM01`);
          no function renamed/created/deleted in that batch;
          plate coverage is now **100 %** (no function lacks
          a plate; CONFIRMED).
        - **Short plates — DONE 2026-09-19:** all 141 plates
          <120 chars reviewed against §8 — **82 KEEP**
          (genuinely trivial — math primitives,
          comparators, simple port I/O, single-RET stubs,
          RST vectors, constant-return helpers, simple
          RAM-cell setters, no-op coroutine stubs) and
          **59 UPGRADE** to the full form
          (brief/mechanics/In-Out-Clobbers/evidence tag,
          ~70 cols, multi-line ASCII; 59 applied in Ghidra;
          function list unchanged; saved). Typical
          upgrades: `Lib_MemMove`, `Bdos_PreparedCall`,
          the `RegFile_*` 32-bit math, `Lib_Mulu16`/
          `Mul16Mod16`, session buffer ops
          (`Session_TxFlush`, `Session_RxRefill`,
          `Session_TxAppendByte`, `Session_RxConsumeByte`),
          TTY key handlers, LCD helpers, message-box
          displays, link init/timeout, clock repack, UI
          descriptor-chain ops. **Item 3 is now DONE** —
          plate coverage 100 %, no SHORT-form plate
          remains that §8 would reject (CONFIRMED).
        Fix plates that contradict their own names and
        re-flow to ~70 cols was done as part of that
        review.
     4. **Comment-style pass — CLOSED 2026-09-19
        except one OPEN label (CONFIRMED; no new
        inference):** of 895 instruction comments, 356
        carried raw-address-like tokens — 137 REWRITE
        (first pass, RAM cell / I/O port cited by
        numeric address → descriptive label; all 137
        applied in Ghidra; function list unchanged;
        0 new labels needed) and 219 KEEP (value/mask,
        legitimate cross-reference, or label already
        present). Second pass found **127** further
        comments still containing a numeric address
        cite resolving to a labelled address
        (secondary cites left by the first pass plus
        others) — all 127 rewritten: every address
        cite replaced with its descriptive label,
        remaining magic numbers / bit masks decoded
        in place, opcode-restating text dropped;
        function list unchanged; saved; no new
        labels needed. Missing-label scan found
        **99** distinct descriptive labels cited in
        comments with no Ghidra symbol; **95**
        resolved to concrete addresses (from
        referencing instructions +
        `memory-map.md`/`unbanked-ram-map.md`);
        **90** created as labels in Ghidra (6 already
        present); function list unchanged; saved
        (CONFIRMED). **Residual closed 2026-09-19
        (CONFIRMED, Ghidra saved):** 3 of the 4
        SUSPECTED labels pinned — `g_bRxRingHead`
        already at `ram:F954` (verified, skipped;
        supersedes `g_bEchoChar` SUSPECTED at same
        address), `g_bLinkCmdShadow` created at
        `ram:F796` (port `4Ch` `LINK_CMD` shadow;
        supersedes `g_bIrStrobeShadow` SUSPECTED at
        same address), `g_bOutputCount` created at
        `ram:FEA3` (supersedes `g_bOutputCount`
        SUSPECTED `F998` — correct address is `FEA3`
        per byte-verified reference);
         `g_wCoroutineStepResult` — **RESOLVED
          2026-09-19 (CONFIRMED): not a fixed RAM
          address.** It names the buffer pointed to by
          `g_pCoroutineStepResultBuf` at `ram:EA24`;
          one writer `ROM01:6DF6 LD (0xEA24),HL` (HL
          from `ROM01:6909` → `Coroutine_Enter`)
         and six readers in `Fs_SeekByteOffset`
         (`ROM01:6DDF-6EED`); layout `+1` = 16-bit
         step-1 result, `+3` = 16-bit step-2 result,
         `+0` unreferenced; `ram:E73E` has zero refs
         program-wide — E73E hypothesis **refuted**
         (CONFIRMED). `g_pCoroutineStepResultBuf` at
         `ram:EA24` carries a repeatable comment and
         four EOLs at `ROM01:6E8F`/`6E9E`/`6EBB`/`6ED8`
         now use the `[*(g_pCoroutineStepResultBuf)+N]`
         form; no function renamed; saved.
         **`Boot_entry+1` bug — FIXED
        (CONFIRMED):** 7 comments corrected at
        `ROM01:1ea1`, `1f96`, `28bb`, `2b7b`, `2c95`,
        `3acb`, `ram:d777` — each cited `Boot_entry+1`
        to mean `0001h` (wrong; `Boot_entry` is
        `ROM00:014b`, so `Boot_entry+1 = 014c`);
        rewritten to `0001h` (intended page-zero cell;
        note CP/M IOBYTE is at `0003h`, not `0001h`).
        3 non-buggy uses of `Boot_entry` retained
        (range marker / state name). **Magic numbers
        — 5 decoded (CONFIRMED):** applied at
        `ROM00:15c4`, `02e5`, `02f1`, `0f37` (PRE) and
        one more — `0x80` = local-console flag, `10h`
        = 16-drive guard, `12h`/`01h` = key scan codes,
        coroutine step-zeroed slots (per-site as
        applied); 12+ comments kept as already
        adequately explained; one intended fix at
        `ROM01:6e8b` had no comment present — skipped
         (CONFIRMED absent). `bdos_entry_impl`
         proposal for `ROM00:F180` — **REJECTED**
         (CONFIRMED, byte-verified): `ROM00:0005` is
         `C3 80 F1` = `JP F180` outside `ROM00`'s
         `0000h..7FFFh` window → target is `ram:F180`
         (`Bdos_DispatchFn`, existing label); phantom
         `ROM00:bdos_entry_impl` was wrong-space; comment
         now `JP Bdos_DispatchFn (ram:F180) vectors
         into the DIPOS kernel (battery RAM)` — not a
         §12 item and now closed (Ghidra saved).
         **CAUTION (CONFIRMED):** 2-digit hex in
        RTC contexts is ambiguous — RTC register index
        (`01h`/`03h`/`05h`/`07h`) is not I/O port `07h`
        = `CTRL_07` (`RTC_ADDR`/`RTC_DATA` are
        `08h`/`28h`); both passes corrected these
        manually — note this hazard for any future
        comment edit. **Review note (CONFIRMED):**
        comment at `ROM00:0178` said "keyboard scan
        init" but the confirmed plate at `Lcd_Init`
        (`ROM00:1EEC`) says LCD subsystem init, so
        the old comment was factually wrong and was
         corrected. **Item 4 is now fully CLOSED**
         — no OPEN labels remain; items 1, 2a, 2b, 3,
         5, 6 are DONE (CONFIRMED). The
         `g_wCoroutineStepResult` pointer-indirected
         buffer is the final closure; E73E hypothesis
         **refuted**.
     5. **Data-typing backlog — DONE 2026-09-19
        (CONFIRMED, Ghidra saved; function list
        unchanged — 915; no new inference).** Types +
        labels created: `ROM01:7545` `ushort[4]`
        `tbl_UiCfgRegionPrefix`; `ROM01:757F`
        `ushort[6]` `tbl_UiCfgNamePointers` (5 name
        pointers + `0000` terminator — the earlier
        `ushort[136]` estimate was corrected);
        `ROM01:758B`/`75EB`/`760D` each typed
        `UiCfgHeader` (new 20-byte struct:
        `EC EF F8 F0 98 EF D8 EF` magic +0..+7,
        fields, LE backlink +12h) as
        `tbl_UiCfgTemplateHeaders` (non-contiguous,
        so individual items); `ROM01:79F4`
        `char[1547]` `str_cfg_option_pool` (existing
        label kept); `ROM00:7C30` `byte[256]`
        `tbl_FontCharWidth` (note `7C50` is offset
        +0x20 within it, not a separate table);
        `ROM00:7D80` `ushort[4]` `tbl_StubTablePrefix`;
        `ROM00:7D88` `ushort[60]`
        `tbl_SessionRuntimeStubSources` (renamed);
        `ROM00:7E50` `ushort[34]`
        `tbl_FnPtrDispatch7E50` (FFFF-terminated);
        `ram:E105` `byte[256]` `g_abFontCharWidth`;
        `ram:D0E0` `byte[448]` `g_abErrorStringTable`;
        41 dispatch-table labels created (16 `ROM01` +
        25 `ROM00`), all `tbl_Dispatch_<name>` —
        previously only 1 of 41 sites had a `tbl_`
        label; 11 plate/repeatable comments set.
        Function list unchanged (915); saved. The
        `ushort[136]` estimate for `757F` and the
        `7C50` separate-table claim are superseded.
     6. **Refresh `research/gap-analysis.md` — DONE
        2026-09-19** (single coverage tracker; headline
        914/915, 99.6 % named; plate coverage updated
        2026-09-19; data-typing + annotation tail
        refreshed 2026-09-19).

    Sequencing: one Ghidra-writing agent at a time,
    `save_program` between, and diff-guard the function
    list each batch (§11). Hold until the remaining open
    items are resolved, so we annotate the final picture
    rather than a moving target.

        **Remaining scope after 2026-09-19 (§12 FINAL
          PASS fully CLOSED):** **no OPEN items remain.**
          Items 1, 2a, 2b, 3, 4, 5, 6 are **DONE** — the
          `g_wCoroutineStepResult` pointer-indirected
          buffer (`g_pCoroutineStepResultBuf` at
          `ram:EA24`, `+1`/`+3` 16-bit results; E73E
          **refuted**, zero refs) was the final OPEN
          label. The `bdos_entry_impl` proposal for
          `ROM00:F180` was a non-§12 item and is now
          **REJECTED** (CONFIRMED) — `ROM00:0005` is
          `C3 80 F1` = `JP F180` outside `ROM00`'s
          `0000h..7FFFh` window → `ram:F180`
          (`Bdos_DispatchFn`, existing label); phantom
          `ROM00:bdos_entry_impl` was wrong-space; Ghidra
          comment now `JP Bdos_DispatchFn (ram:F180)
          vectors into the DIPOS kernel (battery RAM)`;
          no new label needed — §12 remains fully
          CLOSED and the page-zero cleanup below did not
          reopen it.


## Owner corrections to honor


- 4x ports (4A/4B/4C/4D/4F cluster) are NOT the RTC (twice-confirmed)
- No serial EEPROM; serial number is user-entered at banner after
  battery removal, stored at FEAB
- Hardware only has 08/28 as an obvious address+data latch pair.


## Do not regress


- 08/28 device is the RTC: keep Rtc* names (RTC_RegWrite/RTC_RegRead/
  RTC_Init/RTC_WriteTime/RtcSetTimeFromBuffer/RTC_ReadRegisterFile).
- 4x cluster is the external data link: keep Link* names
  (Link_BlockTx/Link_BlockRx/Link_TransferService/Link*). No RTC or
  "comms" naming there.
- RST vector 0010 = Rst2Dispatch (banked dispatch), 0020/0038 =
  Rst4IrqPoll/Rst7IrqPoll, 0028 = Rst5FatalScreen, 0030 = Rst6ZeroRet.
  ROM01 0008/0020/0028 = BankedRst08/BankedRst20/BankedRst28.
  Cold start 01BE = ColdStartSelfTestBanner; 2FBD = LinkRxDispatcher.
- RAM 32-bit session math opcodes keep Session* names (SessionAdd32/
  SessionNeg32/SessionTestCarry/...); empty dispatch slots keep
  SessionOpStub_<addr>.
- External-device bus naming (2026-08-24): port 2Dh = `EXTBUS_EDGE`;
  the 120F-14EE handlers stay `ExtBus*` (ExtBus_BusArm/ExtBus_BusAcquireEdge/
  ExtBus_BusComplete/...). The user **decode-hook socket** keeps neutral
  labels: `fbc0` = RST10 stub, `fbc1` = bank byte, `fbc2` = hook ptr;
  `ExtBus_DecodeHookInstall` (156E) / `ExtBus_DecodeHookDiscard` (1567)
  default it. **SUPERSEDED by owner adjudication (2026-08-24, AGENTS.md
  §3): the side port was used with a barcode pen; the 2D edge-capture
  subsystem IS the barcode reader front end, and `Barcode_` is the
  module prefix for NEW names there.** Existing `ExtBus*` names are
  grandfathered until a deliberate rename pass; do NOT flip back to
  `Reader*`, and do NOT reassign the disproven "EXT STORAGE ADAPTER"
  identity. `Bdos_ReaderInChar` (1080) is genuinely the CP/M fn-03 RDR
  path either way.
18. **Annotation coverage tracker**: **593/593 (100%) named** (Pass A
    complete as of this session). All ROM00 + ROM01 + RAM kernel stubs
    carry meaningful names. Highlights of the closing batch:
    RST vectors ROM00 0010/0020/0028/0030/0038 = Rst2Dispatch/
    Rst4IrqPoll/Rst5FatalScreen/Rst6ZeroRet/Rst7IrqPoll; ROM01 banked
    thunks BankedRst08/20/28; cold start ROM00:01BE =
    ColdStartSelfTestBanner; link RX ROM00:2FBD = LinkRxDispatcher;
    ROM01 field/dialog layer = Field_SelectWalk/Field_ConfigLoad/
    Session_FieldEditLoop/Lib_ToNumberParse/Lib_Accumulate/
    Lib_TableLookup/TextOut*; RAM dispatch slots SessionOpStub_*.
    The only auto created `FUN_ram_8c0c` was a false positive over a
    zero buffer (spurious CALL from a jump-table byte) — deleted.
19. **DIP program format documented** (manual/programmer-guide.md §7b +
    internals/os-diposb.md): DIP = block-structured loader-record stream, same
    grammar as the boot chain (fn 0 copy / 1 move / 2 queue-banked-call
    / FFFF term, bank-tagged); COM = plain single image. Advantages
    (multi-bank, init calls, streamable, diagnostics) vs. .COM; exact
    DIP on-disk header left as live-capture item. Loader primitives
    (D6FA/D713/D727/D7F0/D800) annotated to Pass A+B incl. record-walk
    inline comments + Kernel_DispatchEntry plate.
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
    (117B), Tty_out_char control dispatch (1BEB), select-disk (15B3),
    DMA set (0CEC), RTC get-time (113E), alarm work-item queue
    (2189/21BA), date-rollover (222E/223B), drive valid (0824).

* Structural model 2026-09-18: inline-switch `JP(HL)` cases are blocks,
  not functions — do not re-split the Part B merges.
* Hybrid label model 2026-09-18 (ROM01 14 + ROM00 25 sites,
  CONFIRMED): inline-switch cases are basic blocks of the owning
  routine kept as one function; navigation via labels (not
  functions) — do not re-create case blocks as functions.
* Superseded names above (`3a1c`/`3b53`/`3b7a`/`581f`/`5991`/`62a9`/
  `62b6`/`62ca`/`66ec`/`6707`/`6b0d`/`6b53`) were case blocks; do not
  recreate as functions. The `257f` handlers (`2569`/`2572`/`257b`/
  `2593`) are blocks of `254b` → `257c` → `2593` → `2658`; do not
  recreate.
* `ROM01::3add` `FieldPadValue` is a mid-instruction banking artifact
  (`ROM01::0044` → `ROM00::3add`), not a ROM01 function — do not
  recreate.
* ROM00 dispatch owners (CONFIRMED, 2026-09-18): 23 routines
  `3ede-3f1f`, `3f20-4009`, `4563-46e8`, `46e9-47f5`, `47f6-48be`,
  `48bf-4973`, `4974-4a24`, `4a25-4adf`, `4ae0-4d28`, `4d75-4e6c`,
  `4e6d-4f59`, `4f5a-5033`, `5034-50ec`, `50ed-5178`, `5179-51eb`,
  `51ec-52a4`, `52a5-5427`, `5469-54e4`, `5542-5668`, `56e7-573c`,
  `573d-578e`, `578f-5829`, `59fb-5b57`, `5f58-606b`; sites 8+9 and
  17+18 share owners as above; site-1 is `3f20` (not `3ede`);
  residual `FUN_*` = `2da5`, `4333`, `441b`, `44ed`, `450d`
  (deferred) — do not re-split or recreate the ~89 absorbed
  case-block functions.
* Process — Ghidra function-body extension (CONFIRMED, 2026-09-18):
  `create_function` cannot extend a body past a computed jump;
  body extension must use Ghidra's `Function.setBody(AddressSet)`
  (script), and `FunctionManager.removeFunction` takes an entry
  **Address**, not a Function. The ROM00 pass was saved only after
  a manual `setBody` completion — the annotate stage had left
  owners as 6-byte shells and 2 epilogue functions were briefly
  lost, then recovered by the extension. Do not use
  `create_function` to grow a hybrid owner.


## Open questions

> Historical/resolved open questions have been moved to
> [`session-log.md`](session-log.md) (see `## Resolved open questions`).

* **Remaining (OPEN) — updated 2026-09-20:** analytic work is
  complete — §12 FINAL PASS fully CLOSED 2026-09-19. **4 retained
  `FUN_*`** (ROM00 1, ROM01 2, ram 1) carry plates and are
  documented as dead or reachable-unknown; see
  [`gap-analysis.md`](gap-analysis.md) for the current coverage
  figures and [`session-log.md`](session-log.md) for the resolution
  history. All remaining work is owner/hardware-dependent — see
  *Hardware-dependent priorities* above.

---

Historical session log: see [`session-log.md`](session-log.md).
