# Session log — Micronic 1000 reverse-engineering

## 2026-09-20 — documentation regression checks and first program

* Added a first-COM walkthrough with source, exact assembled bytes,
  bounded emulator invocation, success criteria, and deployment limits.
  CONFIRMED in the emulator: the 30-byte example reaches bank 2 at
  `0100h`, displays `Hello World`, and writes the marker `0200h=A5h`.
  This callback-injected run does not validate physical IR or the later
  warm-restart return. Recorded that scope in a Ghidra bookmark at
  `ram:D7F0` and saved; before/after function lists are identical.
* Added generated-HTML checks for local links, fragments, assets, malformed
  table paragraphs, and table widths, with six regression tests. Added an
  assembly/source-sync/DIP-packaging test for the documented example.
* Added keyboard-accessible diagram source and explicit rendering-failure
  fallback. Browser smoke checks passed for Mermaid and WaveDrom, light
  and dark themes, narrow layouts, blocked CDNs, and disabled JavaScript.
* PR builds now run the documentation and program-image tests plus browser
  checks without deploying. Publication remains a separate deployment job.
  Strict site build and all seven documentation regression tests passed.

## 2026-09-20 — documentation review fixes

* Reconciled supported-profile/Commstar status, reference status vocabulary,
  navigation/build descriptions, duplicate program-format specifications,
  pointer rules, resident-memory ownership, and checksum-provenance wording.
* CONFIRMED: fresh reads and independent investigation/review overturned
  the all-nonzero-drive-rejected/local-only conclusion. BDOS `2Eh` reaches
  session transport with a resolved drive-table entry. Discarded the
  loaded-software/different-ROM reconciliation derived from that error and
  the unsupported 32/224 KiB A:/B: capacity split. No working remote drive
  or physical attachment is inferred. The reviewer's initial Open pointer
  claim was also rejected: its clear helper leaves HL at `F94Eh`.
* Recorded the remaining request/pointer question in Ghidra and current
  docs. Scoped pointer advice to plain pointers; BDOS FCB/DMA bounce and
  bank/address barcode thunks are verified exceptions. Ghidra comments
  saved without renaming or creating functions.

## 2026-09-20 — documentation accuracy, structure, and rendering review

* Added a dated review to `doc/review.md`, retaining the earlier assessment
  as history. Recorded outstanding consistency, API, navigation, style,
  evidence-strength, and publication-check recommendations.
* CONFIRMED by fresh Ghidra reads: COM capacity remains `CF81h` (53,121
  bytes), spanning selected bank RAM and fixed RAM; `D081h` is the
  exclusive ceiling at resident module B. Added the missing explanation
  and byte-level derivation.
* With independent same-provider review (no cross-provider tool available),
  withdrew the built-in monitor, service-key monitor boot, and DE:BC
  saved-context claims. `ROM00:3513` is `XOR A; RET`; M/Z and cold-boot
  callers continue. External monitor/ICE interception stays SUSPECTED,
  with a Ghidra bookmark specifying the missing evidence.
* Corrected shifted page-zero entries and the claim that RST 20h/28h/30h/
  38h all share the IRQ handler. Fresh initial-image bytes distinguish
  the diagnostic and returning-stub paths; later RAM vector patches are
  a separate question. Updated Ghidra comments and saved the program.
* Fixed six malformed rendered table blocks and the missing archive review
  link. The initial strict MkDocs build had accepted all these defects;
  rendered HTML inspection identified them. No functions renamed/created
  and no ROM/emulator execution or listing repair performed.
* Validation: strict MkDocs build and whitespace check passed; rendered
  HTML scan covered 52 pages with zero malformed table paragraphs or
  broken relative article links/fragments. Ghidra function-list snapshots
  were identical before/after (914 internal entries; guarded count 915).

> **Reverse-chronological historical log.** This file records every
> session of analysis from **2026-08-24** to the present. It is a
> complete dated audit trail of what was analysed, concluded, overturned,
> and saved. The **live worklist**, active items, current open questions,
> and "do not regress" list are in [TASKS.md](TASKS.md). The sessions
> below capture routine annotation, hardware experiments, emulator runs,
> Ghidra repair campaigns, and doc updates; read TASKS.md first for
> today's priorities, then use this log for the evidence trail behind
> any specific finding.

This file contains the historical session log extracted from
`TASKS.md`. The live worklist, active items, and current open questions
are in [TASKS.md](TASKS.md).

---

## Session log

- 2026-08-24 (AGENTS.md maintenance): reconciled the rules file with
  owner adjudication + repo facts. IR-port positions settled by owner:
  **V24 ADAPTOR = top, PLINTH = back** (corrected micronic_notes.md,
  internals/os-diposb.md, AGENTS.md §3 — an earlier "bottom/front" reading was
  discarded); tagged bit5 port-select as byte-verified (Link_BlockTx
  3278 `AND 0x20` → Link_PortSelect 3454); made `Barcode_` the declared
  module prefix for the port-2D capture front end everywhere (§3/§7/
  §13, port 2Dh row); corrected tool prefix to `ghidra-mcp_*`; added
  micronic_notes.md + annotate-subagent pointers. SUPERSEDED the old
  "do not rename back to barcode" do-not-regress entry (above)
  accordingly.
- 2026-08-24 (annotation batch 1 — delegated; verified by spot-check):
  plates set for ExtBus_DecodeHookDiscard (1567), ExtBus_BusComplete (14A3),
  Kbd_ReadChar (18C0, +3 EOLs on fbc9 bits/0xCD hotkey),
  Link_PortSelect (3454); 2 PRE + 5 EOL inline comments in
  ExtBus_BusAcquireEdge (13B8, SP-repurposing, retries, timeout, overflow,
  noise filter, <9 reject, hook dispatch); plate comments on fbc0/fbc1/
  fbc2; io:2d repeatable replaced (EXT STORAGE claim removed → barcode
  front end); stale "ReaderArmRoute/"ReaderEdgeDecode" plate first
  lines of 1221/13B8 fixed. All byte-verified at write time; program
  saved.
- 2026-08-24 (annotation batch 2 — delegated; verified by spot-check):
  Kernel_Image_BdosMain (36A0) plate: inverted dispatcher description
  replaced with the corrected model + HAZARD (verified CP 25/JR C,
  CP F3/JR NC, DEC B, F1EB/2*BC, fn 40h→F06B, F3→F1D1); Link_BlockTx
  (3277) plate tail copy-paste artifact ("Micronic 4x link
  transceiver datasheet") removed; RTC_RegWrite (22DB) indirect OUT
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
  UI_DialogShowMenu 0A42, Session_HelperRouter6621 6621, Text_ScreenInit
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
    Rst7IrqPoll; renamed). d2dc/d2de writers = UI_FormExitDispatchNext's
    own prologue (ROM01::06b9/06cd) - cell comments updated. RegB =
    0x46 at init -> PIE=1 AIE=0 CONFIRMED (RTC_Init 2084; EnablePeriodicIrq
    OR 0x40; ClearAlarmInterrupt AND 0xDF; no RegA writes) - RTC_WakeReasonFetch
    plate upgraded. fbc9 full bit map CONFIRMED (bit0 session event @30C0,
    bit1 date-changed @2235, bit2 kbd @18E0/1968, bit3 date-wait-ack @170B
    via deferred callback; bits 4-7 unused) - manual/barcode-reader.md updated.
    Descriptor records 7715/7751 NOT yet repeatable-commentable (field
    layout inconsistent) - trace UI_PostDescriptor instead.
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
  * ROM01 record API: UI_FindRecordByKey (6909), UI_RecordBindAndExec
    (6a36), UI_RecordMatchAndPost (6aa9; e986/e992 = last-match cache;
    error ids 0x1773/0x17D4/0x17D5), UI_IdToRecOffset32 (0ad3),
    UI_StateInit (1803), Ui_TableScanMatch (6027), UI_DescChainInit
    (659f). Descriptor tables 7715/7751: repeatable comments now carry
    the CONFIRMED cross-links ('1'-'4'/'P'/'<' keys); full field map
    still open (handlers 6319/635e/645d/6464/6588 un-walked).
  * RTC_SetAlarm (2141) verified: RegA=0x2A + RegB |= 0x20 (AIE) &
    0x7F (clear SET) - the FD4F bit5 wake path is LIVE when armed.
    Link_StatusWatcher (2468) corrected: polls RTC regs 07/08 (alarm
    sec/min) -> FD9B/FD9C, NOT Reg C.
  * Docs: internals/cp-m-comparison.md 25h-F2h wild-pointer claim fixed (item 8
    CLOSED); SessionBdosPrep renames propagated (internals/os-diposb.md,
    protocol/commstar.md).
  * Coverage: 686 fns / 672 named (98.0 %), 14 FUN_* left (9 ROM01
    incl. the five UI_PostDescriptor case handlers + 6e77; 5 ram
    ee00-eedc/f8ef with empty listings - GUI pass needed).
- 2026-08-25 (descriptor-op wave — 2 agents read-only; main applied):
  * Five UI_PostDescriptor case handlers named + plated:
    UI_DescShowFieldChain (6319, key 03), UI_DescFieldEditMenu (635e,
    3-byte-stride choice array at D+0Bh), UI_DescOpNoop (645d),
    UI_DescRecordScanLoop (6464, 4-byte-stride scan list at D+0Dh,
    deliberate SP-discard no-return continuation at 653b - PRE'd),
    UI_DescChainNext (6588). Plus UI_FieldEmptyCheck (62e5),
    UI_FieldEditGetChoice (1d80), UI_SvcCall2_07 (7279, DA13(2,7)
    fallback; identity SUSPECTED). Descriptor field map consolidated
    and written onto the 7715/7751 repeatables (key addresses
    corrected: '1'@7731...'4'@7740, 5-byte records @772F).
  * Kernel: Kernel_BankedCallReturn (f3c4, epilogue + deferred-chain
    fdb8/fdba cursor LIKELY); Kernel_BankFnRet (f483) plated (bank-store
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
    (F5F0), BankedRst38Stub(F5F3), Kernel_CallCommonEntry(F64D),
    Kernel_NmiVectorStub(F5F6, function). AGENTS.md §5 corrected:
    0008 -> JP F180 (BDOS), not F5Ex (byte-verified).
  * FDBD/FDBE/FEA4 = kernel error-report state (SUSPECTED): FDBD bits
    1/2 gate the error-report display options; FDBE = failing fn#;
    FEA4 = "error screen active" latch read by Monitor_GetChar. Open:
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
    Kernel_CallBank6_0E00 (the service-2 entry of ServiceCall_BdosFn2
    6f29 -> bank-6:0E00 call), off 7 = Syscall_InvokeServiceFB (the
    service-7 entry of UI_SvcCall2_07). d893 plate updated.
  * ROM00::2bee decoded + named Diag_FatalScreenDeferred: stores A
    (bank) -> FDB9, sets FDB8=FF (the deferred-chain marker
    Kernel_BankedCallReturn tests), joins the fatal screen inline.
    Its wrapper ram:f59f = Bdos_BankedCall3. ram:f5c0 =
    Bdos_BankedCall4 -> Diag_ErrorHandler (2C00). ROM00::2d83 =
    Kernel_ErrorReport (FDBE!=0 -> FEA4=FF; fn prefix via 2C67;
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
    page. Kernel_SetBankNotify (ram:f41b, slot 20 of tbl_KernelJumps)
    = the generic arbitrary-bank selector (A >= 2 = RAM page). EOLs at
    the sweep sites cite the RAM02 overlay.
  * boot_hw.py gained --dump-bank N (writes analysis/ram_bank_NN.bin;
    RAM banks dump the emulated page, ROM banks echo the ROMs) - the
    emulator can now PRODUCE the RAM02 dump for Ghidra. Run when
    memory allows: `timeout 300 venv/bin/python3 boot_hw.py --drive-kbd
    --max-slices 300000 --dump-bank 2`.
  * Still open: RAM-disk driver itself (the Disk*/Fs code that maps
    drive A:/B: blocks to RAM banks) - not yet located; candidates:
    Kernel_SwapCopySrc (f4a8) + the ROM00 3960/3983/398f region.
- 2026-08-25 (owner theory tested + refuted as stated; part survives):
  * THEORY: the RAM-resident sweepers size the RAM for a RAM disk,
    upper bound (41h-1) x 32K = 2 MB. RESULT: refuted - the sweeps
    contain NO read-back and store NO result, and their call sites
    prove the purpose: Mem_BankSweepPutByte is called by
    SetActiveConsoleDevice (15AB/15BE) with HL=3/HL=4 to broadcast the
    console-device (FBC5) and disk (FBC6) cells into every bank's page
    zero; Boot_BankWalkInit replicates the RST vectors (JP F238/F180)
    to all 64 banks so IRQs/RSTs work in any selected bank. Real RAM
    sizing = SelfTest_page_test_4banks (2530, called from Boot_entry 01BB,
    fail flag FDB0) + SelfTest_ram_map_test (267A).
  * SURVIVES (documented in internals/memory-map.md + the four plates): the
    64-bank sweep implies 2 MB of addressable banked-window capacity
    (6-bit bank latch, LIKELY); installed 256K RAM backs part of it.
  * RAM-disk block I/O LOCATED: Bdos_ReadRecordBlock (ram:f4e7) CALLs
    Kernel_SwapCopySrc (f49b: select bank A + LDIR across the window) -
    the storage copy path for drives A:/B:. Write twin still to find.
- 2026-08-25 (RAM-disk block I/O layer CLOSED; main agent, saved):
  * Write twin FOUND (already named): Bdos_PrepWriteBuf (f510: 0x80B
    record FFA3 -> FEFF staging, banked via f498) + Bdos_DoneWriteBuf
    (f523: FEFF -> FFA3). Bdos_PrepReadFromBuf (f4eb: 0x24B header
    stage via FF7F) + Bdos_SwpDirectory (f535: F8B8 dir buffer ->
    [FFA3] DMA) complete the layer. All five plated; staging cells FF7F/
    FFA3/FFA5/FEFF/F8B8 commented; f498 entry EOL'd (bank arg comes
    from FEFE - the envelope's saved-bank cell is reused as the block
    I/O bank operand). Bdos_ReadRecordBlock: C = bank, 0x80B read via
    Kernel_SwapCopySrc. internals/memory-map.md: owner-confirmed rationale for the
    per-bank vector replication added (COM not bank-aware, DIP may be;
    IRQ/RST must work in any bank).
  * Open next: 049f/04c8 block-address helpers (f822/f8b0 math) -
    the record -> (bank, offset) geometry; FDBD/FDBE hardware test;
    emulator verification (memory-gated).
- 2026-08-25 (FS geometry layer decoded; main agent, saved):
  * The 04B8-052E cluster is the DIPOS filesystem geometry layer -
    already named Fs* by an earlier pass; plates + cell comments added
    and 4 auto-FUN helpers renamed (Util_HlPlus2Cy/HlMinus2Cy,
    Fs_HlSubF8b2/Fs_HlAddF8b2). Fs_VolumeInit (0509): A = log2 records
    per block -> f822; f820 = 1<<A, f828 = mask, f82a = A+3 (log2
    block bytes). Fs_InitAllocator (05a1): **f8b0 = 0x100 = 256
    records per 32K bank page** (32768/128), f8b6 = 0x8000 base -
    the RAM-disk geometry CONFIRMED. Fs_BitmapRolExt (049f): 16-bit
    rotate-left A, carry-out -> RST 28h error trap. Disk_DirEntryWalk
    (04c8): 2-byte-stride dir search over the F8B2 table.
    Bdos_ReadRecordBlock therefore: bank in C, record -> offset via
    Fs_BitmapRolExt(f822), 0x80-byte copy via Kernel_SwapCopySrc.
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
    UI_RecordEditModal and UI_RedrawIfRequested plates corrected.
    No ROM writer found for the slot table (loaded software may patch:
    SUSPECTED).
  * BDOS dispatch arrays UNIFIED: F1D1-F234 = ONE 50-word handler
    array tbl_BdosFnHandlers (image of ROM00:36EE-3748); base F1EB =
    array+0x1A (fn 00-24h); F1D1-F1E9 = wrapped F3-FF view (1FDF/
    1893/1877/15A0/15A4/3237/15CB/3241/3248/1150/113E/1122/112D).
    ram:f180 rebuilt as Bdos_DispatchFn (f180-f1d0) with the full
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
    Syscall_InvokeServiceFB family, Bdos_BankedCall3/4, envelope
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
    - CharOrBeep -> SelfTest_Test_PatternWalk275c: the 2740-2796 cluster is
      cold-start SELF-TEST (called from ColdStartSelfTestBanner via
      271F), not char output. Its CALLs into f1ef/f1fb/f206 land in
      BDOS-table data in the post-boot dump - SUSPECTED those
      addresses hold self-test stubs EARLY in boot, before the BDOS
      dispatcher+table are built over the same RAM (discriminating
      tests recorded). KeyCharStore -> SelfTest_Test_NextPatternValue;
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
    Lib_Bytes/Kernel_CallDispatch/Kernel_MemoryVector/SessionMemMove/
    Session_BdosCall/da27/da34/ShrFieldE3b4). 498-plateless debt now
    ~330 (next tranches continue the same pipeline).
  * Small fixes: 62A9/62B6/62CA promoted (Ui_Thunk* trio, vtable-
    reached); CarryBitMacro -> SelfTest_Test_RamPatternWalk (the
    2740-2796 chain CONFIRMED cold-start RAM write-pattern walk);
    5B57 RESOLVED (legal dual entry / mid-instruction view fixed -
    function re-based at 5B57); 19E0-19F0 = keyboard probe table
    (typed byte[17] + records + JR trampolines + manual refs);
    Tty_out_char NOT_CODE "phantoms" were real key handlers - 4
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
    twins, Kernel_SetBank/Kernel_MemCopy/bank variants, NMI/common-entry, BDOS
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
    internals/memory-map.md row; Kernel_CallCommonEntry's ROM00:230A call lands
    mid-Clock_SelftestPeriphCfg - hand-check that boundary;
    ROM01::1b0a nested subroutine = split candidate; the 1fbe EOL
    ("id==13: fall through") may contradict the e04b convention -
    verify pass.
- 2026-08-26 (DB INCIDENT - in-memory wipe, disk safe):
  * During a three-agent parallel round, the in-memory function count
    dropped 746 -> 622. Selectively deleted: UI_FieldListRender (198e),
    UI_RecordEditModal (1b7d) functions, several xrefs (22c0/24fa/28ea
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
    (UI_FieldListRender, UI_RecordEditModal, xrefs 22c0/24fa/28ea,
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
    ROM00:2306 body-boundary note added (230A is Kernel_WorkerPollPort5).
  * QUEUED (next serial batches): LAB batch 6 (40 renames - Agent B
    manifest), tranche-3 plates (~31 + hazard resolutions: delete
    UiDialogDrawBlock2 0879, retype session_router_5994 as data,
    verify StrTrimDispatch 0303, UI_LineWalkArgThunk promote).
- 2026-08-26 (serial application continued; saved):
  * LAB batch 6 APPLIED (40 renames: ModalRunLoop/Session_CoroAsync/
    StatusCursor/SleepDelay/PollTick/PollIntrq/RxProcessFrame/RxDispatch
    internals). ~393 ROM01 in-fn LAB labels remain.
  * TRANche-3 APPLIED: 31 plates (Text* cluster, Str* cluster,
    UiDialogDrawBlock/FieldTableBuild/FieldLineWalk, console wrappers,
    session validators); hazards resolved: UiDialogDrawBlock2 (0879)
    deleted (mid-body), session_router_5994 re-typed as data
    (tbl_sessionRouter5994), StrTrimDispatch (0303) byte-verified
    mid-operand artifact -> deleted + bookmark; UiOpenSaveDialog
    (1add) RENAMED to UI_LineWalkArgThunk - fresh bytes proved it is
    the field-walk arg-marshalling trampoline, not a dialog routine
    (the old name was an unverified relic of the flow-repair
    recovery); Text_HomeCursor (7121) + Session_WordSet_E8D8 (6772)
    promoted. Count 745 = 746 -3 deleted +2 created, no losses.
  * Rename candidates queued: SessionNopWaiter (675A, actually a
    getter) -> Session_WordGet_E8D6; ui_OpenSaveDialog doc-grep done
    (only historical TASKS logs).
- 2026-08-26 (recommended-order rounds; saved serially):
  * 675A renamed Session_WordGet_E8D6 + plate. internals/memory-map.md gained the
    block-I/O staging-cells row (FF7F/FFA5 read pair, FEFF/FFA3 write
    pair, F8B8 dir buffer).
  * LAB batch 7 APPLIED (40 renames: RxIncr/DecrCounter, CountBytes,
    ParseField, ConnectCheck, CmdWalkTable, WaitCharCell,
    RxRecordStage, RxEditBuffer internals). ~352 ROM01 in-fn LAB
    labels remain.
  * TRANche-4 APPLIED: 39 plates (9 FB stub templates, 13 ROM01
    session/coro helpers incl. Lib_Accumulate/Lib_ValueTableFetch/
    CmdRetryCounter, 17 ROM00 BDOS fn handlers incl. the version
    deviation HL=23h, Monitor_Enter/PutChar/GetChar routing, kbd row
    decode, decimal formatter). ROM00::2d82 DEFERRED (body
    mis-bounded - repair first). Plateless ~343 remain. Count 751.
  * NEXT (serial): LAB batch 8 (starts 2f2e; bonus context for
    2f2e-2fec already captured), plateless tranche 5 (unnamed helpers
    cited in tranche 4: ROM01::581F/5991/5E78, ROM00::F4EB/F501/
    F543/F46D + the duplicate-name collisions SessionCommandDispatch
    x4 / SessionCoroThunk x2 / Bdos_GetSetUserCode x2 need
    disambiguation), SessionShl32 anomaly, 2D82 bounds repair.
- 2026-08-26 (batch 8 + collision fixes; applied serially, saved):
  * LAB batch 8 APPLIED (40 renames: FieldEditLoop scanback +
    Session_RxProcessLine full editor internals - flags, trim, key
    dispatch stages DBh/1Ah/7Fh/20h, delete/insert paths, render
    loop, helper spacer). ~304 ROM01 in-fn LAB labels remain
    (next = 34FD).
  * Collision sweep: 5 SessionCommandDispatchStub_* thunks renamed
    (ROM00:5a66/604e, ROM01:3b53/5e2e/62d1 - all plain CALL ram:e0b2
    wrappers); Bdos_GetSetUserCodeRet0Stub_1890 renamed (dead
    constant-zero stub, behaviourally different from 0c96); the real
    SessionCommandDispatch (ram:e0b2) has 20 callers - name kept.
    ROM01::00ef SessionCoroThunk DELETED (pad-region artifact; callers
    759F/75B6 use CALL PO) + bookmark with the discriminating test.
  * Plates: Bdos_GetSetUserCode (0c96) plated. D660/D681/D686/D6C0
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
  * Tranche 6: 6 new Fs* plates (Fs_RecCountIncr, Fs_BitmapRor,
    Fs_SetupGeometry, Fs_AllocQueryFree, Fs_DirScanWildcard,
    Fs_DirBlockRead). The other proposals were already plated
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
    Fs_BlockMapRead, Fs_RecCountRead, Fs_BitmapShiftRight, alloc bitmap
    clear/claim/free, Fs_DirFormat, Fs_DirMakeEntry/FindMatch/
    ResetCursor/EntryAdvance/BlockRead, Fs_DirIntegrityCheck +
    Bdos_ExtFn62 shim, Fs_SearchCommon ('?' extent wildcard), the three
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
    function at ROM00::2d82 deleted; the real Kernel_ErrorReport body
    is 2d83-2dd0 (intact, fully plated with both entries: bit1 path
    msg@2D17, bit2 path msg@2D04); secondary entry labelled
    report_entry_bit1 at 2d82. SAVED.
  * LAB batch 11 APPLIED directly: 44 labels renamed + commented from
    a fresh script-dump (per-label evidence = containing function +
    first instruction + incoming branch sites): Session_WaitKeyState,
    Field_SelectWalk, Session_TableWalkNext, Session_RedrawField,
    SessionDrawFieldLine (incl. cross-fn entry from 75e3). Next batch
    starts at 4730 (~190 remaining).
  * NOTE: the main agent has direct ghidra-mcp tools again, so
    analysis and application run in-loop for accuracy; agents remain
    for routine work.
- 2026-08-25 (plate-refinement sweep EXECUTED; annotate, saved):
  * Enumerator found 40 pseudo-asm offenders, 26 caller-list
    offenders, 147 unwrapped single-liners (of 223 plates).
  * APPLIED: 40 exact multi-line rewrites (no asm restatement, no
    caller lists; Boot_entry, Power_DownSuspend, RTC_WriteTime/
    SetTimeFromBlock, Kernel_WorkerPollPort5, Clock_SelftestTickWindow,
    Diag_ErrorHandler, Link_TransferService, Link_ProcessCommandFrame,
    Kernel_Image_BdosMain, banked wrappers, NMI/IRQ images, session
    routines, dialog/set-clock entries, ExtBus_BusPoll, EvalRecordSteps,
    dispatcher/loader plates, the runtime-page family, etc.);
    20 caller-list excisions; 60 mechanical re-wraps (~70 cols);
    SessionSub16 (e0a9) flagged as undocumented - plate needed.
  * CORRECTED: an enumeration space-typo (ROM01::12ec) caused a wrong
    function shell (Barcode_PollContinuation) in a legitimate ROM01
    gap - deleted; the rewrite went to the real ExtBus_BusPoll at
    ROM00::12ec. Two leftover caller phrases excised (d8ce, e06b).
  * Remaining known debt: ~90 P3-only single-liners beyond the 60-cap
    (next wrap batch), SessionSub16 plate, and any plates still
    holding asm-style flow narration outside the P1 list (reviewed
    per-plate next sweep).
- 2026-08-25 (helper-cluster wave + memory-model resolution; 2 agents
  read-only, main applied + saved):
  * UI helper renames (stale names corrected): SessionLinkTx6292 ->
    UI_PostKeyedEntry (6292; JP 62A6->62D1 gap flagged), StateVarDispatch
    -> UI_RedrawIfRequested (6280, gate cell is eb18 not ebf7),
    UiHandler1B7D -> UI_RecordEditModal (1b7d, six stack args, modal
    loop 1CD6-1D72), SessionCoroWaitByte -> UI_GetStateWordEc41 (2116),
    TextOutChar -> ServiceCall_BdosFn2 (6f29, DA13(2,arg) shim - the
    TextOut identity was unproven). 183c/198e kept (enriched plates:
    9B->10B field-table build; stride-4/5 item lists).
    Diag_FatalErrorScreen (ROM00::2B55) plated with table contents.
  * FB-service path CLOSED mechanically: RST 28h -> F5ED -> F57E
    (bank-0 select + F54E) -> Bdos_BankedCall2 (F590): CALL 2B55;
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
    if bit7 set); ram:ee0c/ee20/ee64/ee84 -> Session_OpStub_ee0c/20/64/84
    (tbl_FieldOpSlots patch sockets, each has a real CALLer);
    ROM01:0ae3 -> Session_DialogStateCheck; ROM01:254b ->
    Session_CondCommandDispatch (gate on (ec49)+0xC -> inline CALL e0b2
    dispatch at 257c); ROM01:40a2 -> Session_MsgTableBuildIfNeeded;
    ROM01:65f5 -> Session_WordSet_E89A; ROM00:3cea -> Session_CoroInit;
    ROM00:3cf7 -> Session_InitAndRunTx; ROM00:54e5 -> Session_WordSet_E519;
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
    Text_PosCursor 70ae + char-emit ServiceCall_BdosFn2 6f29; 73de runs
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
    Callee names cross-checked (UI_FindKeyMatch/UI_SetDialogId/
    UI_SetAttrCells/UI_RenderCharCell/Kernel_MonoCall/UI_FieldLineWalk/
    Session_DispatchSub/Session_DispatchWrap + the Session 32-bit VM op cluster
    dc37/dc49/dce9/dca1/ddfa/dc30/e09f/df42/df5b) - all real, no
    hallucination. Coverage: 750 total / FUN=0 / thunk=13 / plateless
    238 (all ROM00; ROM01 now 0, ram saturated).
  * Boundary issue FOUND + bookmarked (not re-based): ROM01::2f74 holds
    an orphan 11 byte = first byte of LD DE,0x10; Session_FieldEditLoop
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
    sense-vs-no-sense, not on-vs-release. Renamed: Kbd_SenseAllColumns(1a42),
    Kbd_SenseColumn(1a44), Kbd_DriveSetAll(1a77, 0x3F), Kbd_DriveClearAll
    (1a81, 0x00). Plates corrected; 2 first-pass byte-range errors fixed
    (KbdDriveWrite was 1a44-1a76 spanning Kbd_ScanRowDecode; KbdDriveOff
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
    routines, used by the session numeric formatter (Session_CmdHandler53C6).
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
    - ROM01 (6): Form_Builder CALL-on-Z not NZ; UiDialogListItem JP
      09db not fall-through; UI_DialogLayout does not return HL=1;
      Session_WaitCharCell returns HL=1 (not 0) on zero arg; SessionField
      EditLoop has NO 356e call; Session_FieldReady needs (eb53) non-zero
      too.
    - ROM00 (16): BdosDirSearchHelper extent = f823-f82c (reversed);
      Link_SelectActiveDevice AND 3 not 7; ExtBus_BusAdvanceTimer fbce +=
      f9ac (not -=); Comms_LineDeassertRd order (2349 first); KbdColumn
      Strobe branches on Z not carry; Lcd_CharWrapBound uses BC not HL;
      Lcd_clear_spaces loops 0xA0 (160) not 0x60; RTC_PeekDateByte CALL
      not tail-call; Diag_PrintResult 0x80=TIMEOUT else FAIL (swapped);
      Tty_PrintString/Lcd_PrintString NULL-terminated not $; LinkTransport
      Call CLEARS fbc9 bit0 while Link_ResetSession SETS it (pair was
      SWAPPED); UI_Count16 reads 4 bytes not 16; RtcDateChanged
      Check sets fbc9 bit1 unconditionally; RTC_AlarmWriteCtrl is a 15-byte
      fragment (real alarm logic in RTC_SetAlarm).
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
    Ui_CommSetupFormInit (060B) -> Form_Builder (0271).
  * Two wire-id tables, one accessor (~ROM00:31FF): FE93 = drive-letter
    -> wire-id (A=0x00 internal, B=0x7F, C=0x73, D=0x72, E-P=0x00);
    FE83 = 4 device slots [0x80,wire,0x63,0x43] = 0xAB/0x2B/0x67/0x67.
    BDOS std file ops (fn<0x25) reject non-zero wire-id -> external probe
    (Disk_KeyedSearch -> Link_TransportOpen). Plates set on FE93/FE83.
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
    Session_LoadDecCmp, 7c14 Session_CmpLeU16, 7c22 Session_CmpGtU16).
    Data tables identified (not yet typed): ROM00 7c30 lookup, 7c50
    bitmap, 7d80/7e50 fn-ptr tables, ROM01 7545-7fff descriptor table,
    ram:e105 lookup+bitmap, ram:d0e0 string table. 2 mid-instruction
    labels to delete (ram:f1b2, ram:de6a - auto-symbols, need clear-flow).
  * ACRONYM: 14 32-bit-arithmetic plates corrected - dropped the "VM
    register file" over-claim, now name the concrete E3Bx cells.
  * EOL: 41 EOL comments on SessionCommandDispatch (e0b2), Fs_InitAllocator
    (05a1), Kernel_BankedCallEnvelope (f376), Session_CoroStartTask (3d3c).
  * CHURN: 7 FUN_* re-triaged + named: Fs_DirBlockMap (042d),
    Session_DialogIdGet (1548), Kbd_SetKeyState2 (1aec), Kbd_ClearAndPower
    Bit0 (1b1a), Power_LatchClrBit0 (1b39), SessionDivS32 (ddb0),
    SessionModS32 (ddcb). FUN_* = 0.
  * NEXT: data-type the identified tables; guarded re-bases (2f74/52a5/
    4a25); emulator menu reach (higher slices); apply remaining EOL
    (Session_CoroJumpTable 3c06).
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
    Util_CountUp (ROM00:271F) at cold start as FEAB = FEA9*0x20 (FEA9 =
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
    E3B1-E3BF register-file arithmetic: RegFile_File_Add32/And32/Shl32/Neg32/
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
    Link_Probe (348a) hardware probe failure - 0x1F->port 4F, LINK_CTRL(4A)
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
- 2026-08-27 (Link_Probe question + emulator-chase note; documented):
  * Owner-flagged: Link_Probe (348a) is called ONLY by ColdStartSelftest
    Banner (self-test), so the session-connect "Plinth not connected" must
    use a DIFFERENT probe. OPEN: which fn probes the link during connect
    (Link_Present 34ec / Link_WaitReady 34f8 / Session_ConnectCheck 2b43?).
    Documented in protocol/commstar.md "Error-path triggers".
   * EMULATOR NOTE: chase "No program in memory" by driving Load/Run
     Program in boot_hw_visible.py and tracing which BDOS/session error
     code populates d0e0 and e48d/e488. (Error-code->string table is
     runtime-built; not statically visible.)
- 2026-08-27 (byte-verify wave-2 fix + boot_hw merge verified; main):
  * Bdos_SwpDirectory (ram:f535) plate CORRECTED: copies 0x80 bytes FROM
    the F8B8 directory buffer TO [FFA3] (the BDOS DMA address) - the
    earlier plate had the direction reversed. Byte-verified: HL=[FFA3],
    EX DE,HL -> HL=F8B8 src, DE=[FFA3] dst, Kernel_MemCopy(HL=src,DE=dst).
  * Two data-cell plates corrected in the same pass: FFA3 is a 2-byte
    DMA POINTER (set by BDOS fn 1A at Bdos_SetDmaAddress), not a
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
    / Kbd_ScanRowDecode). Page 0 unshifted (ASCII letters; 'N'=0x4E idx21,
    ENTER=0x0D idx22), page 1 shifted (+0x24), page 2 special (+0x48,
    fbdd==2; 'Z'=0x5A idx21). Function keys use codes 0x01/0x06/0x0b/
    0x0c/0x11/0x12/0x14/0x1a/0xd0. Kbd_ScanMain (18f0) produces the code
    into fbe7 -> key ring -> ec41.
  * FIELD-EDIT KEY DISPATCH: Ui_FieldEditPumpLoop (1e0a) reads ec41 and
    tail-jumps to CALL ram:e0b2 with inline dispatch table at ROM01:1f99
    (labelled tbl_fieldkey_dispatch): 0x06/0x0b->1e61, 0x01/0x0c->1ea1,
    0x11->1ece, 0x12->1eed, default->1f23. Session_KeyProcess (40c4)
    branches on 0x01/0x06/0x11/0x12.
  * OWNER KEY MAPPING (hardware, for emulator input): N/Z key edits the
    active field value; YES/NO keys move between fields. Codes: N=0x4E,
    Z=0x5A, YES/NO=0x11/0x12 (which-is-which direction TBD), ENTER=0x0D.
    Recorded in the two Ghidra plates; emulator chase to use these.
- 2026-08-27 (error-screen format CLOSED; investigate + main, applied):
  * TASKS #11 answered (investigate agent, byte-verified by main): the
    "Error 8000 (238/001) Plinth not connected" screen is rendered by
    Session_StateBuild (4351) via Session_MessageBox (4296). CONFIRMED:
    8000 = major error qualifier literal 0x1F40 (8001 = 0x1F41 for the
    0x0009 connect-check case), 11-digit space-padded; NOT e488 (code 6).
    "(238/001)" = RCV1/RCV2 session status from e701/e6ff (3-digit
    zero-padded), template at ROM00:7310 (now tbl_sess_status_fmt) with
    field names RCV1/RCV2/SEND/LOAD/PROG/TIME/ENDC. Annotated: plates on
    7310/e488/e701(g_wSessRcv1)/e6ff(g_wSessRcv2)/Session_StateBuild; EOLs
    at 47ca/47b7/47d0/4380/4399. protocol/commstar.md gained "Error/status
    screen format (CONFIRMED)".
  * MISNOMER FLAGGED: ROM00:403b (named FileSearchNextCb) is actually a
    decimal-to-ASCII formatter (div-10 digit loop + 0x30); used by
    Session_StateBuild. Rename queued (needs rename-hygiene pass).
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
  * FileSearchNextCb -> Lib_DecU16 (ROM00:403b). CONFIRMED decimal
    formatter (div-10 + 0x30, two-pass leading-zero->pad, null-term at
    [width]); stack args value/dest/width/pad at SP+0x0C/0x0E/0x10/0x12.
    Callers: Session_StateBuild (error-screen), Fs_SearchFindNum.
  * SessionSub* naming applied:
    - SessionSub16 -> Lib_Sub16 (ram:e0a9); plate CORRECTED: Z flags the
      FULL 16-bit result (OR L), not just the low byte.
    - SessionSub612A -> Session_FieldParseValidate (ROM01:612a).
    - SessionSub620C -> plate updated: field loop, SUSPECTED dead code
      (init block 61d0-620b unreachable).
    - DELETED SessionSub5DFD (mis-bounded fragment; real entry 5df2) and
      SessionSub6431 (basic block inside UI_DescFieldEditMenu, entry is a
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
- 2026-08-27 (Kernel_TableDispatch: rename + struct + typed all 26 tables):
  * ram:e0b2 renamed SessionCommandDispatch -> Kernel_TableDispatch; plate
    and EOL comments thrown out and redone from the code. Format byte-
    verified (NOT the earlier "sentinel" guess): {count: u16le}
    {case: u16le, handler: u16le} x count {default_handler: u16le}. The
    leading count is loaded once and DEC'd per probe; underflow (D<0)
    enters the trailing default. No per-entry sentinel.
  * Defined struct DispatchTableEntry {caseValue: word, handler: word}
    and typed ALL 26 inline tables after CALL Kernel_TableDispatch via a
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
    generic form init, builds 3 template instances via Form_Builder
    0271); FUN_ handlers -> Form_ChoiceNext/Prev/First/Last/LetterMatch,
    all plated. Device-name table at ROM01:757f (WORKSTATION MEMORY,
    WORKSTATION RAMDISK, PLINTH, V24 ADAPTOR, EXT STORAGE ADAPTER),
    embedded in form template 758b (+0x0c), built by Form_Builder.
  * DOCS: mkdocs restructure adopted. Updated TASKS.md/AGENTS.md doc-path
    references to the new layout; Makefile + BUILD.md are now mkdocs-only;
    deleted legacy build.py, validate-mermaid.mjs, package.json/lock.
    (committed 46a2c52)
- 2026-08-27 (user guide + forms-UI docs; plan set):
  * Added manual/user-guide.md (boot, keypad, special keys, field
    navigation, menu map, error screens + codes, error list, error
    recovery) and internals/forms-ui.md (form model, Form_Builder,
    device table 757f, 1f96 field-edit dispatch, keymap, error renderer).
    Wired into mkdocs nav + README indexes.
  * Error messages enumerated (ROM00:6d40-6e10): Plinth not connected /
    Line failure / Modem fault / Failed to connect / Invalid reply /
    Invalid command / Invalid data string / Not available + statuses
    (Program received, Session complete, Logging on/off). Qualifiers
    confirmed for Plinth (8000=default, 8001=case-9); the rest are
    ROM-derivable (each error site pushes its own literal) and queued.
   * PARKED (hardware-gated, owner-decision): function-label effects
     (CHNGE/REFER/HELP/INSRT/F1/F2/STWDL/LIGHT);
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
    Failure; FUN_44a5/44bd/44d5 -> Session_MsgFailedToConnect /
    Session_MsgInvalidReply / Session_MsgModemFault; Session_ShowMessage
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
    same Form_Builder (0271) machinery as the form templates. The
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
    0xfffe. Form_Builder (0271) is used ONLY for these 3 form templates;
    the MENU (ROM01:7860) is a different structure (menu item records
    {string, action}) rendered by a separate handler.
  * FIELD VALIDATION (investigate agent, byte-verified key claims):
    Session_FieldParseValidate (612a: numeric parse vs limit table e34f by
    field idx e88f) returns HL=0 on rejection and does NOT raise the banner;
    the four ROM00 slots previously described here (582a/5834/583e/5848) are
    session TX paths, not field validators (CONFIRMED, byte-verified):
    `ROM00:582A` `Session_CoroTxFrameAndRx` -> `60CC` (`Session_TxFrameAndRx`),
    `ROM00:5834` `Session_CoroTxFrame33` -> `60D6`
    (`Session_TxFrame33Transaction`), `ROM00:583E` `Session_CoroReturnZero` ->
    `6120` (`Session_ReturnZero`), `ROM00:5848` `Session_TxRecordData`
    forwards two stack args to `6181`. "Invalid reply"/"Invalid data stream"
    are session PROTOCOL errors dispatched by
    Session_ProtocolErrorDispatch (4f37): 0x09->"Not available"(8102),
    0x0A->"Invalid data stream"(8101). "Invalid command" (6dfa) is DEAD
    (zero refs). Er007 error list updated with 8101/8102; forms-ui.md now
    documents the template struct + validation. **CORRECTION 2026-09-18:**
    the four-slot validator description is superseded as above.
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
    dispatcher Syscall_Dispatch ram:d6db, handler table ram:d6f4): fn=0
    memset {fn,addr,count}, fn=1 memcpy {fn,src,dst,count}, fn=2 enqueue
    {fn,N,addr[N]} -> N x {0xD7,bank,addr} stubs at queue d684, fn=FFFF
    terminate (wrap d6f4+2*0xFFFF -> d6f2 -> d6ee pop+ret). CHECKSUM
    CONFIRMED (Lib_Bytes ram:d7d1 = 16-bit additive byte-sum, not CRC).
    ROM footer 7FF0-7FFF (chain ptr at 7FFA/7FFC; 7FFE = candidate system
    ID). MISNOMER FIXED: SyscallLoadBlockToMem -> Syscall_Memset (it zero-
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
  * UI_FormExitDispatchNext (ROM01:06d3) = the form-transition loop: walks
    a 5-entry double-indirect table at ram:d081 (module B head) and
    bank-calls each callback, then rebuilds the comm form (060b) + posts
    descriptors 7715/7751 (UI_PostDescriptor 6633). forms-ui.md updated
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
    at `ram:D0F0`); `UI_FormExitDispatchNext` double-dereferences; (d)
    `ram:D681` as runtime COM/DIP block — now kernel dispatch/boot-loader
    block, runtime loader is `ROM01:0A67-10CE`; (e) old prose names
    `UiDialogOpen3F`/`UiDialogListItem`/`Dialog_StateCheck`/`UiCloseDialog`/
    `SessionHelperRouter0CE7`/`DialogListAction` superseded by
    `Program_*`/`UI_FormExitDispatchNext`/`g_apScreenHandlerTables`; (f)
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
    `Program_LoadedProgram`. No BDOS execute; provider around `0C12`/`0CE7`/
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
    passed to `Program_LoadedProgram`; block count drives 0..5 file-block and
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
  * **Finding (all ROM00, CONFIRMED mechanical):** `Link_BlockTx` 3277-3377
    and `Link_BlockRx` 3378-3453 mechanically drive `LINK_CTRL` (4Ah) and
    poll `LINK_STATUS` (4Bh); no electrical names for status/control bits are
    proven. TX ordered sequence: clear ctrl b0, set b0, clear b4, `B=0x80`
    DJNZ delay; `Link_Present`→`Link_WaitReady` polls status b7 `DE=0x02DA`
    then `0x81` to `LINK_CMD`; low five bits of input `A` (held `C`) to
    `LINK_TXD`; wait status b4 `DE=0x026C`; set ctrl b5, set ctrl b4,
    `B=0x20` delay, clear ctrl b5, wait status b6 `DE=0x026C`; each `OUTI`
    to `LINK_TXD` gated by status b7 `DE=0x06F9`; cleanup clears ctrl b4,b0.
    RX: clear b0, set b5, single `LINK_RXD` read, set b4, `B=0x20` delay,
    clear b5; `INI` from `LINK_RXD` only if status b0 set; if b0 clear,
    b1 set continues b2/b3 decode while b1 clear waits/retries `DE=0x06F9`;
    b2 set extra `INI`; b3 set `EC`; cleanup toggles b1, sets/clears b0,
    clears b4, toggles b1. `Link_Probe` emits `0x1F` to `LINK_PROBE` then
    latch sequence; physical/reset meaning remains SUSPECTED.
  * **Docs updated:** `protocol/commstar.md` rewritten to list only
    mechanical bit numbers and timeout constants, removing unqualified
    electrical labels (`TX-ready`, `RX-ready`, `ACK`, `peer-ready`/`type`,
    `idle/run`, `talk`/`RX-enable`, `clock`, `IR select`) and adding the
    ordered TX/RX/Probe sequences plus Probe SUSPECTED note;
    `internals/io-map.md` revised (4Ah/4Bh rows, Interface-shape section,
    Ghidra label table) to report only confirmed drive/poll behaviour.
    Owner statement preserved: link-id bit 5 selects one of two IR line
    states (V24 ADAPTOR top vs PLINTH back) via `Link_PortSelect`; at this
    session the polarity remained OPEN. **SUPERSEDED 2026-09-06:** fresh UI
    trace plus the owner's top-window capture maps wire-ID bit 5 clear to top
    V24.
   * **Ghidra:** retained the existing `LINK_CTRL`/`LINK_STATUS`/`LINK_CMD`/
     `LINK_PROBE` labels; added plates and EOL comments to `Link_BlockTx`,
     `Link_BlockRx`, `Link_WaitReady`, `Link_Present`, and `Link_Probe` for the
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
   * **CORRECTED off-by-one (CONFIRMED):** `Link_ValidateFrameHeader` (ROM00:30DC) compares RX logical offset **+4**, not +5, to `fdd4`. RX header is `+0..1 LE total length; +2 type; +3 per-link sequence; +4 active link id; +5 never read by ROM link code`. Previous docs (commstar.md validated-frame table, io-map.md address-filter line, `micronic/proto.py:validate_header`, `comms_rx_test.py` comment/frame) said +5 — fixed to +4.
   * **TX prefix (CONFIRMED mechanical, SUSPECTED meaning):** `Link_FramePrefixWrite` (ROM00:316B) writes TX offsets 0..4 as `{len LE, type, sequence, 0x7F}` and leaves offset +5 untouched. Constant `0x7F` at TX +4 is **SUSPECTED**; do not call it an id or broadcast.
   * **Transport framing constraints (CONFIRMED):** `Link_BlockTx` prelude is low 5 bits (`link_id & 1Fh`) sent before descriptor bytes and excluded from descriptor counts; `Link_BlockRx` returns `DE = bytes_read - 2` — identity of the two excluded bytes is **OPEN**. Descriptors: RX `FE0E {6->FDE4, 3->FE38, 0}`, RX `FE32 {9->FE3A, 0}`, TX `FDEA {6->FDDE, 0}`.
   * **Sequencing & replies (CONFIRMED):** sequence slot is `FE43h + (fdd4 & 3Fh)`, init 1; mismatch reply `01EF` tied to type-4 sequence check; reply word `03EE` exists along with `01EE,02E0,02EE,04E0,05E0,01EF` (now 7 values).
   * **Inline dispatch (CONFIRMED numeric cases, local control flow only):** `5A69` abort `44,45,60,61,64`; `53C7` `0..5`; `5410` `0,4,8,9`; `5291` `0,4,9` — do not name as wire commands. Table at `6A4A` is **CONFIRMED** 16 state-display pointers, not a wire map. Link path **no checksum verified**.
   * **Docs updated:** `protocol/commstar.md` (validated-frame table + validation sentence + Link_FramePrefixWrite/TX-0x7F note + Link_BlockRx/Tx prelude/DE-2 + descriptors + sequence slot + 03EE + numeric cases + 6A4A + no-checksum), `internals/io-map.md` (address-filter offset +4 and SUSPECTED/OPEN notes), `analysis/micronic/proto.py` (frame header docstring + `validate_header` offset +4), `analysis/comms_rx_test.py` (comment + RX frame construction to place link id at +4).
   * **Outstanding (OPEN/SUSPECTED, do not guess):** meaning of TX `0x7F` (SUSPECTED); whether offset +5 may be writable by loaded code (OPEN, never read by ROM); identity of the two bytes excluded from `Link_BlockRx` DE count (OPEN); session payload grammar and per-record/per-block byte content still runtime/open (needs live capture or loaded-module trace); connector mapping and electrical bit meanings remain OPEN.
- 2026-08-29 (documentation maintenance — reviewer-approved BDOS review corrections, Ghidra-applied):
   * **Applied established findings only (no new inference):** `Bdos_SelectRst28Mode` (`ram:F55A`), `Bdos_UpdateDriveDirectoryMetadata` (`ROM00:0D79`), `Bdos_InternalTimedWait` (`ROM00:1122`), `Kernel_ConditionalEnableInterrupts` (`ram:F54E`), `Device_LookupConfigEntry` (`ROM00:31FF`).
   * **Overturned false interpretation:** `fn04` (`ROM00:10D2`) was previously described as unsafe / non-returning via `RST 38h` with a stack switch — **superseded**. Correct decode is `CALL ROM00:31FF` `Device_LookupConfigEntry`; `E` preserved, `FBC5` high nibble selects `FE83` entry; descriptor `80h` local output else routed; normal `A=00h`, routed terminal error returns a path-dependent nonzero helper status, and both paths may wait/retry. Summary status **CONFIRMED**.
   * **Corrections applied to `manual/bdos-reference.md`:** normal path `0005->ram:F180-F1CE` joining `F382`, `F376` alternate, `HL=word[FEFA]`, `Kernel_ConditionalEnableInterrupts` name, unspecified-output rule (`BC`/`DE`/`IX`/`IY` not restored); `02h` four `A` results; `0Ah` `1Bh` counted literal block; `21h`/`22h` use `+21h`/`+22h` only (`+23h` not read; 31-byte copy stops before it); `2Dh` mutable mode selector (`FFh` `F57B` no-op, `FEh` `F57E` default, `FDh` `F59F` + `HL->FDBA`, `FCh` `F5C0`, else unchanged; `A` preserved; global unsafe); conditional behaviour of `0Dh`/`1Ch`/`1Eh`/`1Fh`/`30h`/`F4h` via `RST 28h`; `2Eh` drive-metadata not filename search; `FEh` timed wait (`E<<4`, `IY+23h`/`word[FEFA]`, `FD4D` `HALT`, `A=00h`); `FFh` `UIP` polling before both paths; hex suffixes `+0Ch`/`+10h`/`+20h`/`+21h..+23h`; table statuses aligned. Evidence tags preserved; `F376`/`F382`/`F54E` byte-verified envelope unchanged.
   * **Cross-document consistency:** `manual/programmer-guide.md` (`19h` `A` not `HL`, `1Ah` implemented, remove inert-stub grouping for diagnostics, `FEh`/`FFh` semantics, `FC`/`FD` 8-byte `+0` OPEN, configurable `A`/`B` vs `C`/`D` mapping, conservative extension safety); `internals/cp-m-comparison.md` (`06h` `E=FFh`, mutable diagnostics, `1Ah` implemented, configurable mapping, `F5` `<04h`→`0Fh`, `FEh`/`FFh`, handler `0C50`, `2Dh`/`2Eh`); `internals/os-diposb.md` (delete `FD->0DE9` etc. and point to correct `F3h-FFh` table, mutable diagnostics, `2Dh`/`2Eh`, `..//manual` link, `0008->F180` and `F5EA`/`F5ED`/`F5F0`/`F5F3` grouping); `internals/memory-map.md`/`internals/interrupts.md` (`0008->F180`); `manual/supported-profile.md` (diagnostic unsafe path); `doc/review.md` (superseded `1Ah`/`19h`/`02h`/`04h`/`FEh` claims marked). Current names are used in active docs; historical log entries retain their original names.
   * **Build:** `mkdocs build --strict` (see below); no commit; no new coverage numbers added.
   * **Closed stale BDOS items:** previous "all full cards done" phrasing retired; diagnostic-stub claims and `FD->0DE9` wrapped mappings removed.
- 2026-08-29 (documentation maintenance — parent-adjudicated RTC record + CP/M links, no new inference, reviewed findings):
   * **Canonical BDOS eight-byte RTC record published** (`doc/internals/rtc.md#bdos-eight-byte-rtc-record`): `+0` metadata (FC copied/RTC ignored, FD from `g_bRtcRecordMetadata` init `13h` LIKELY century `19` exact OPEN, FF copied unused), `+1` year→`09h`, `+2` month→`08h`, `+3` day-of-month→`07h`, `+4` hour→`04h`, `+5` minute→`02h`, `+6` second→`00h`, `+7` day-of-week→`06h` (convention OPEN, `0=Sunday` LIKELY from `1984-01-01` default); raw binary 24-hour (Reg B `46h`), no firmware conversion/range validation; service identities `FCh=1150`/`FDh=113E`/`FEh=1122`/`FFh=112D`; `FFh` `DE=0` clear and program both poll `UIP`, preamble `RegA|80h` likely ineffective then `2Ah`; evidence addresses as listed in `rtc.md`.
   * **Register-map correction:** rotated HD146818 labels fixed in `rtc.md` and `io-map.md` to `06`=day-of-week, `07`=day-of-month, `08`=month, `09`=year; alarm regs `01/03/05` marked used (RTC_SetAlarm `2158-62`); emulator trace labels corrected (`09`=year `54h`, `08`=month `01h`, `07`=day-of-month `01h`, `06`=day-of-week `00h`); `RTC_ReadRegisterFile` corrected to `00h..09h` (10 bytes) → `g_abRtcRegisterSnapshot` (FD50), not `00h..0Fh`/16 bytes; stale date-gate text corrected to `RTC_AlarmDateMatches` / `g_bRtcAlarmDayOfMonth`/`g_bRtcAlarmMonth`.
   * **Stale-name correction:** `BdosFcAlarmControl` → `Bdos_FfAlarmControl` in `cp-m-comparison.md` (and linked purposes to canonical layout); `Link_StatusCompare_FD4B` → `RTC_AlarmDateMatches` in active TASKS naming (historical logs retain former name where clearly historical).
   * **BDOS reference alignment:** `manual/bdos-reference.md` FC/FD/FF cards now link to canonical record and summarize exact field use; FE corrected to `E<<4` interval with low→`(IY+23h)` high→`word[FEFA]` (previously mis-described as low nibble from IY).
   * **Programmer guide links:** `manual/programmer-guide.md` table entries and command bullets link to canonical record, give compact layout once without ambiguous "`byte +0 OPEN`" without metadata/LIKELY-century context; `2Dh` `E=FFh` wording corrected to "installs `F57B` no-op target"; `2Eh` wording corrected to entering `A=2Ch` error path (not guaranteed returned `A`); added `### CP/M reference manuals` with verified Bitsavers/Gaby links and DIPOS-override note; renamed `BdosFcAlarmControl`→`Bdos_FfAlarmControl`.
   * **Review update:** `doc/review.md` RTC-incomplete finding marked resolved for byte layout, preserving OPEN `+0`/day-numbering/range-validation.
   * **fn04 alignment verified:** no doc change; `fn04` already aligned to `Device_LookupConfigEntry` findings in prior pass.
   * **Build:** `mkdocs build --strict` (see below); no commit; no new inference.
 - 2026-08-29 (parent-approved Commstar review and correction pass):
   * **ROM-visible buffer + TX prefix (CONFIRMED):** RX `+0..1` LE
     embedded length, `+2` numeric type, `+3` sequence byte, `+4`
     active link id, `+5` unread by examined ROM path, payload `+6`;
     TX prefix `Link_FramePrefixWrite` (ROM00:316B) writes `+0..1`
     descriptor length, `+2` type, `+3` sequence, `+4=0x7F` (**SUSPECTED**
     meaning) and leaves `+5` untouched.
   * **Validation + transport (CONFIRMED unless OPEN):**
     `Link_ValidateFrameHeader` (ROM00:30DC) checks embedded length vs
     caller logical count and `+4` vs active link id `fdd4`, does not
     inspect `+5`; `Link_BlockRx` success `DE=bytes consumed minus 2`
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
      {9->FE3A,0}`, `FDEA {6->FDDE,0}`; `Link_Probe` ROM00:348A writes
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
     replaced stale `Link_BlockTx`, `Link_WaitReady`, and `Link_Present`
     plates/EOLs; `Link_ReplyEE03` names the existing direct-call stub at
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
      `Program_LoadedProgram`) below Commstar; bounded runs verified: 28-byte
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
      `ROM00:2E02` (`Device_SelectOpen`, retained name); `ROM00:2E72` is
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
      controller reason):** the two bytes excluded from `Link_BlockRx` `DE`
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
    default wire ID `g_bDeviceWireId4=0x43`. Wire-ID bit 5 is clear, so
    `Link_BlockTx` takes the wire-ID-bit-5-clear latch path. This is not a
    physical-port assignment by itself.
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
    modem semantics remained OPEN; the physical top-port polarity was closed
    by the later 2026-09-06 correction.
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
    (`Session_CoroJumpTable`). Extent is exactly 14 states x 17 commands =
    238 bytes, `692A-6A17`; unrelated data begins at `6A18`, so state-name
    entries 14 (`REPLY-START`) and 15 (`REPLY-END`) have no row and are
    display-only. The decoded machine: INIT-COMMS opens, DIAL/ANSWER/MANUAL
    connect, C-COMMAND leaves CONNECTED for READY-RX-DATA, RECORD ops loop
    in RECORD-RX/RECORD-TX with BEGIN-FILE/END-FILE/END-TX file framing,
    BLOCK ops loop in BLOCK-RX/BLOCK-TX with no file wrapper, and every
    state accepts C-DROP-LINE (to NOT-STARTED) and C_ABORT (to CRASHED).
  * **RECORD=data / BLOCK=program promoted to CONFIRMED (2026-09-01):** was
    recorded as an unproven vocabulary reading. Each of the four transfer
    operations calls `Session_StartDataMode` (`ROM00:452D`) with its command
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
  * **Kernel_TableDispatch fully decoded (2026-09-01):** format byte-verified
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
    Sending prog). Also note `Session_StartDataMode` returns early unless
    `ram:E48D` == 2, so the Load/Run path may run an operation routine
    without driving the state machine at all — which would explain why
    states 4/5/6 are unreachable in the transition table yet the traced
    session performs Program Reception.
  * **Kernel_TableDispatch tables defined as data in Ghidra (2026-09-01):**
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
    `Session_CoroJumpTable`. 26 pass a literal — and only ever `0`
    NOT-STARTED, `2` CONNECTED or `13` CRASHED; 17 pass `(ram:E48C)` and 2
    pass `(ram:E491)`. `E48C` is the cell the dispatcher writes with
    `entry & 0x7F`, so those sites commit a transition the table staged: the
    dispatcher computes the next state, the caller commits it.
  * **State machine is gated by `ram:E48D` (2026-09-01, CONFIRMED):**
    `Session_StartDataMode` forwards to the dispatcher only when `E48D == 2`.
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
    entries above state that `Session_StartDataMode` dispatches "only when
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
    That is `Session_CoroJumpTable`'s illegal-transition path, and it confirms
    in one live run: the table's row/column indexing, that bit 7 set means
    illegal (row 0 column 16 = `0x80`), that both name tables render the
    message, that `g_bSessionState` is the row index, and that it boots to 0.
  * **Why an application call does not return — ANSWERED (2026-09-01):** not
    a calling-convention or scheduler issue. `ram:D837` is an ordinary
    stack-frame prologue: saves `IX`/`IY`, invokes the body through
    `D836` (`JP (HL)`), epilogue at `D84C` restores and returns the result in
    `HL`. The firmware simply stops to talk to the user — an illegal
    transition raises a message box and waits in `Session_WaitContinue` for a
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
    what the mode gate is for. With `ram:E48D = 2`, `Session_StartDataMode`
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
    for the peer. With validation suppressed `Session_StartDataMode` returns 0,
    and the operation wrapper reads 0 as *proceed*: `ROM00:547C` is
    `JP NZ,54E1` (non-zero exits), so zero falls through to `CALL 593A`, a
    thin wrapper on `Session_TxRunState65` (`ROM00:5BA6`). That prepares a
    frame header, calls `Session_SetParams(0x65, 6, 6, 0, 0)`, sends the frame
    via `Session_TxSendFrame33`, then waits in `Session_RxByteLoop`. So the API
    operations are **link transactions**, not local calls that happen to
    block — a call made with no host attached cannot return, and that is the
    protocol working correctly rather than a fault. Exercising the API
    therefore needs a responding peer, which is precisely what a Commstar
    server is.
  * **New wire state value `0x65` (2026-09-01):** passed to `Session_SetParams`
    and `Session_TxSendFrame33` on the `C_ABORT` path. This is the first direct
    evidence that the `44`/`45`/`60`/`61`/`64` family are the parameter an
    operation *transmits*, not merely internal labels.
  * **Still OPEN:** in the bare-COM test the `Link_BlockTx` (`ROM00:3277`) hit
    counter never fired, so execution blocks between entering
    `Session_TxRunState65` and reaching the link driver — plausibly because no
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
    link-ID bit 5, `LINK_CTRL` bit 4 direction/enable, and `LINK_CTRL` bit 5
    strobe.
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
    screen reaches `Comms in progress`, but `Link_BlockTx` and `LinkOpen` never
    fire and the peer sees no traffic at all (`replies=0`), so the session
    stalls before any transmission. The peer and pump are therefore unproven
    against an application-driven session — they are proven only against the
    Load/Run route.
    *Hypothesis for next time:* the session needs the service-33 / link-IRQ
    plumbing that the Load/Run trace arms and a bare `--upload` run does not.
    Compare what `--trace-loadrun-source` sets up before its first exchange.
  * **CORRECTION — handheld-to-host data IS captured (2026-09-01):** the
    readiness tables carried "Receive records/files from a handheld — Not
    implementable — no handheld-to-host exchange is captured" for many
    commits. False since the state-45 decode. The handheld sends objects to
    the host in its type-1 requests, and `CommstarPeer` receives and decodes
    them in every trace: **9 bytes at state `0x0006`** and **54 bytes at state
    `0x0045`** (the operator text). Split into two rows: receiving data a
    handheld sends in a request is Provisional and works; a RECORD-mode file
    transfer is still uncaptured. The blanket claim was wrong.
  * **`LINK_CMD` (`4Ch`) has one value (2026-09-01, CONFIRMED):** `81h`,
    written by `Link_Present` (`ROM00:34EC`) after `TXRDY`, shadowed at
    `ram:F796`. No other value exists in ROM00, ROM01 or the battery RAM, so
    there is nothing to decode from variation — it is a fixed "begin" token,
    not a command byte with fields.
  * **`LINK_PROBE` (`4Fh`) addresses id `7Fh` (2026-09-01):** `Link_Probe`
    computes `7Fh AND 1Fh` — exactly the masking that forms a prelude from a
    link id — and writes the result. So `7Fh` is used **as an id** in at least
    one place, not as arbitrary filler. The earlier "do not call it an id or
    broadcast" caution should soften: "not an id" is no longer tenable,
    though "broadcast" remains unproven.
  * **HYPOTHESIS DISPROVEN — the stall is not missing IRQ plumbing
    (2026-09-01):** the previous entry guessed the application route lacked
    the service-33 / link-IRQ setup the Load/Run trace arms. It does not.
    Every cell in the documented arming condition is **identical** on both
    routes: `FDD4=43`, `FDD5=01`, `FDDC=FE0E`, `FDC5=E530`, `FDC7=E5BA`,
    `FDD2=2E85`. The only difference is `g_bSessionState` — `02` CONNECTED on
    Load/Run versus `00` NOT-STARTED for the application.
  * **The stall is INSIDE the transfer, not before it (2026-09-01):** the link
    port shadows show the application route got further than reported. Both
    routes end with `F796=81h` (the present handshake completed) and
    `F797=03h` (the prelude was written to `LINK_TXD`). They differ only in
    the control shadow: Load/Run ends at `F794=02h` (transfer closed, port
    select still set) while the application ends at `F794=C2h` — **bits 6 and
    7 set, which `Link_BlockTx` never drives**. The peer sees no reply-worthy
    traffic because no complete frame was ever streamed.
    *Next:* find what drives `LINK_CTRL` bits 6 and 7 — nothing in the decoded
    transmit path does — and localise the stall between the prelude write and
    the payload stream. The harness's `W` PC-hit counters are useless for this
    (they sample `pc` between emulator slices and miss almost everything); a
    real `--watch-pc` using `mach.set_breakpoint` is the tool to add first.
  * **`LINK_CTRL` bits 6+7 identified: the receive-arm (2026-09-01,
    CONFIRMED):** they are always driven as a **pair** — set by
    `Link_PortLatchSetHi` (`ROM00:34BD`), cleared by `Link_PortLatchClr`
    (`ROM00:34D2`) — and the whole mechanism is the link interrupt poll,
    now `Link_IrqPollArmOrService` (`ROM00:31B6`):
    clear `RXARM`; test `RXBUSY` (status bit 4); if pending, run the receive
    dispatcher (`2FBD`) leaving `RXARM` clear; if idle, set `RXARM`.
    So an idle handheld sits with `RXARM` set, telling the controller it is
    ready to be given data, and `Link_BlockTx` clears it at `ROM00:327D` for
    the duration of a transmit. **For a physical adapter this is the signal
    to watch — `RXARM` set means the handheld is listening**, and
    `LINK_CTRL` is the only place it says so. That completes the `LINK_CTRL`
    bit map: 0, 1, 4, 5, 6, 7 all now have roles; 2 and 3 are never driven.
  * **CORRECTION — `F794 = C2h` is not an anomaly (2026-09-01):** the previous
    entry flagged the application route ending with `LINK_CTRL` bits 6 and 7
    set as suspicious, "which `Link_BlockTx` never drives". True but
    misleading: `Link_BlockTx` does not drive them, the interrupt poll does,
    and `C2h` (`RXARM` + `PORTSEL`) is the **normal idle value**. Load/Run
    ends at `02h` only because it stopped inside a transfer, where
    `Link_BlockTx` had cleared them. The two routes' control shadows are
    therefore consistent, and the stall is still unlocalised.
  * **Still OPEN — where the application-route transfer stalls.** Both routes
    reach the present handshake (`F796=81h`) and write the prelude
    (`F797=03h`); the application never streams a complete frame, so the peer
    has nothing to answer. The `RXARM` reading removes the only apparent
    asymmetry, so localising it needs real instrumentation: a `--watch-pc`
    built on `mach.set_breakpoint`, since the existing `W` counters sample
    `pc` between emulator slices and miss almost every hit.
  * **`--watch-pc` added (2026-09-01):** comma-separated hex addresses, real
    breakpoints via `mach.set_breakpoint`, reporting bank and registers at
    each hit. This is the instrument the `W` counters could never be: they
    sample `pc` between emulator slices and read zero even on a route that
    demonstrably transmits. Two caveats worth knowing: it matches raw
    addresses **regardless of bank**, so `ROM00:2FBD` and `ROM01:2FBD` are
    conflated; and heavy watching perturbs timing, because every breakpoint
    ends a slice — watching six addresses was enough to stop the upload path
    completing.
  * **ROOT CAUSE of the application stall — the harness, not the firmware
    (2026-09-01):** `run_loaded_program` executes a loaded COM in its **own**
    loop, and that loop never called `advance_rtc`. With no RTC the periodic
    interrupt never fires, so `Link_IrqPollArmOrService` never runs, so the
    receive path never runs: the handheld could transmit but never hear the
    reply. The `--watch-pc` reporting and the peer pump were also only in the
    main loop, which is why the peer appeared to see no traffic at all. All
    three fixed. Note this also invalidates the earlier reading of `F796=81h`
    / `F797=03h` as "the application reached the wire" — it had, but the
    evidence for that was not what I claimed at the time.
  * **HANDHELD-TO-HOST TRANSFER ACHIEVED (2026-09-01):** a loaded COM driving
    `C-INIT-COMMS` (mode 0) -> `C-DIAL` -> suppress validation
    (`ram:E48D = 2`) -> `C-BEGIN-FILE` -> `C-TX-REC` -> `C-END-FILE` completes
    five commands, reaches session state `CONNECTED` (`E22D = 02`), performs
    ten request/reply exchanges, and **uploads three objects to the host**:
    9 bytes at state `0006`, then 128 and 72 bytes at state `0045`.
    `CommstarPeer` receives all three. Every command returns, so an
    application genuinely drives a sequence.
    The state progression `NOT-STARTED -> DISCONNECTED -> CONNECTED` is
    exactly what the transition table predicts for `C-INIT-COMMS` then
    `C-DIAL`, now confirmed by execution.
    **Still open:** the record format and how a record is nominated. The
    demonstration passed a zero argument to `C-TX-REC`, so the handheld sent
    whatever buffer that selects — the bytes look like resident code, not
    application data. `C-END-TX` also did not complete (marker stopped at B5).
  * **RECORD FORMAT ESTABLISHED — a real upload with controlled content
    (2026-09-01):** `C-TX-REC` takes a **pointer** to a counted buffer, and
    unlike the other entry points it reads the **last** word pushed (caller
    `SP+0`), not the third down (`SP+4`). `ROM00:50ED` reads a 16-bit value
    at callee `SP+0Ch` and passes it to `ROM00:3E14`, which walks
    `[u8 count][payload]` sending one byte at a time — the same
    `{count, payload}` shape `Session_ReadStreamChunk` uses on the receive
    side. Before that it sends a single byte `1Eh` via `ROM00:3D9B`.
    `C-END-TX` flushes.
    What reaches the host for `"HELLO-FROM-M1000"`:
    `c3 03 01 · 1e · 48454c4c4f2d46524f4d2d4d31303030 · 1c` — the payload
    verbatim, between a three-byte prefix and a `1c` suffix. Confirmed with a
    second payload (`"SCAN:0042:WIDGET"`). Pinned by
    `CommstarRecordUploadTest`.
    A zero argument sends whatever `mem[0]` happens to select, which is why
    the first attempt uploaded 128 and 72 bytes of resident code.
  * **New wire state `0062`:** the session passes through it between `0006`
    and the `0045` upload. Unexplained.
  * **Still OPEN after the upload works:** the `c3 03 01` prefix and `1c`
    suffix; state `0062`; and clean teardown — `C-END-TX` does not return, so
    although the record flushes during it, a repeated multi-record upload has
    not been demonstrated. The regression tolerates the non-zero harness exit
    for that reason, and says so.
  * **UPLOAD STREAM FORMAT DECODED (2026-09-01):** `[u8 namelen][name] 1Eh
    [record] 1Ch`. Both `C-BEGIN-FILE` (`ROM00:5034`, via `3EDE`) and
    `C-TX-REC` (`ROM00:50ED`, via `3E14`) take a **pointer** to a counted
    buffer `[u8 count][bytes]`, read from the **last** word pushed (caller
    `SP+0`, callee `SP+0Ch`) — not the third-down slot the other entry points
    use. The two marker bytes come from `ROM00:3D9B` calls with literals:
    `1Eh` at `5107` in `C-TX-REC`, `1Ch` at `5193` in `C-END-FILE`; those are
    the only two literal `3D9B` sites in the image.
    Note the asymmetry: the **name** is sent with its count byte, the
    **record** is not — `3E14` sends `buffer[1..count]` only.
    Verified with `[06]"MYFILE"` + `"SCAN:0042:WIDGET"`, and a second
    name/payload pair. Pinned by `CommstarRecordUploadTest`.
  * **`c3 03 01` explained (2026-09-01):** it was never a protocol prefix. An
    earlier attempt passed a **null pointer** to `C-BEGIN-FILE`, so it read
    `mem[0]` — `C3h`, the first byte of resident code — as the name length.
    With a real name buffer the field is the filename, as designed. A good
    reminder that an unexplained constant is often just a bad argument.
  * **Still OPEN after this pass:** the intermediate wire state `0062`; whether
    multiple `C-TX-REC` calls append records to one file (untested); and
    `C-END-TX` still does not return, so clean session teardown is
    undemonstrated. The regression tolerates the harness's non-zero exit for
    that reason and says so in a comment.
  * **Multi-record uploads confirmed (2026-09-01):** repeated `C-TX-REC` calls
    **append**, so the general stream form is
    `[u8 namelen][name] (1Eh [record])* 1Ch`. Two records under one name
    arrive as `05 "STOCK" 1e "REC-ONE" 1e "REC-TWO" 1c`.
  * **LIKELY — the markers are ASCII information separators (2026-09-01):**
    `1Eh` is RS (record separator) and `1Ch` is FS (file separator), used
    exactly as ASCII defines them: `1Eh` before each record, `1Ch` to end the
    file. Corroborating detail: only those two are ever sent — GS (`1Dh`) and
    US (`1Fh`) appear nowhere in the session code. Tagged LIKELY (era
    convention combined with observed behaviour), not CONFIRMED.
  * **`C-END-TX` explained — structural, not a bug (2026-09-01):**
    `ROM00:52A5` reads the session state (`CALL 3BE8`) and branches on it to
    pick "Program Transmission" (states 6 or 11) or "Data Transmission"
    otherwise, setting `ram:E514`/`E516` to the title and completion strings —
    which is where the 2x2 operation matrix strings actually get chosen. It
    then issues command 15. But `C-END-TX` is legal only from
    `READY-TX-DATA`, `READY-TX-PROG`, `DATA-SET-TX` or `BLOCK-TX` — exactly
    the states the transition table can never reach. Since the upload only
    works with validation suppressed, the session is still `CONNECTED` when
    `C-END-TX` runs (`E22D=02`, `E518=02` measured), the firmware notices,
    and the screen goes to `Comms in progress` / `Abort pending`.
    **So the upload is a forced one:** records reach the host intact, but the
    session aborts rather than closing. This is the practical consequence of
    the reachability result — a *validated* upload does not appear possible in
    this firmware.
  * **State `0062` located, not explained (2026-09-01):** the only
    `LD HL,0062` in ROM00 is at `5E16`, in the sequence push 6 / push 6 /
    push 62h / `CALL 5973` — the same shape as
    `Session_SetParams(0x65, 6, 6, ...)` in `Session_TxRunState65`. So `0062` is
    a session TX parameter emitted by the "state-62 builder" the earlier notes
    mention. What the exchange means is still open.
  * **`C-END-TX` DOES take an argument (2026-09-01, CONFIRMED):** a 16-bit
    value at the last-pushed slot (callee `SP+0Ch`), same as `C-BEGIN-FILE`
    and `C-TX-REC`. Which disposition it takes is decided by the mode gate at
    `ROM00:530D`: if `ram:E48D == 1` it takes the **clean completion** —
    display the `E516` string ("Data transmitted" / "Program transmitted") and
    commit the state from `E48C`; otherwise it reads the caller's argument at
    `533E` and sends it via `ROM00:3F20` -> `58B8(arg+1, 00FFh, arg)`. Note
    the `00FFh` constant is the same value seen in the state-44 request's
    size field.
  * **Why the demonstration aborts (2026-09-01):** with the session at
    `CONNECTED` neither disposition is available. `E48D = 2` suppresses
    dispatch so `C-END-TX` takes the argument path with an argument the test
    never meant to supply — hence `Abort pending`. `E48D = 1` lets the
    dispatch run, but `table[CONNECTED][C-END-TX] = 8Dh` is illegal (next
    state `CRASHED`), so `452D` returns non-zero and `ROM00:52F8` exits
    before the completion path. **A clean finish needs both `E48D = 1` and a
    state from which `C-END-TX` is legal**, i.e. `READY-TX-DATA`,
    `READY-TX-PROG`, `DATA-SET-TX` or `BLOCK-TX` — so clean teardown and the
    reachability question are the same question.
  * **More unexamined arguments:** `C-END-FILE` also reads a 16-bit argument
    (`ROM00:523F`, same slot) and `C-INIT-COMMS` reads **three**
    (`4569` at `SP+10h`, `45D1` at `SP+18h`, `45EE` at `SP+1Ah`). None is
    characterised; the demonstration supplies zeros and works, so they are
    not mandatory for the paths exercised.

## Commstar: the argument sweep, and the reachability question answered (2026-09-01)

* **CORRECTION to the entry above.** `C-END-FILE` takes **no** argument, and
  `C-INIT-COMMS` takes **ten**, not three. Both errors came from the same
  mistake in the first sweep, and it is worth recording because it is easy to
  repeat.
  * `ROM00:523F` is inside `C-TX-BLK` (`51EC`–`52A4`), not `C-END-FILE`
    (`5179`–`51EB`). The scan derived each routine's extent from Ghidra's
    function list, but Ghidra has **no functions defined between `4D25` and
    `5307`**, so one stale boundary swallowed the following routine whole.
    Routine starts in this region are better found from the frame prologue
    `LD DE,nnnn / CALL D837`, which is what `analysis/commstar_args.py` now
    does.
  * The offset in `LD HL,off / ADD HL,SP` is relative to **SP at that
    instant**, and argument marshalling pushes as it goes. Reading
    `off − 0Ch` without tracking the stack depth misplaces every argument
    fetched with a push outstanding — which is why `C-INIT-COMMS`'s slots
    looked sparse and non-contiguous. With the depth tracked they come out as
    ten consecutive 16-bit slots, `SP+0` through `SP+18`, and `C-COMMAND`'s
    three match `ROM01:1343`'s three pushes exactly. That agreement is the
    check that the tracker is right.
* **`ram:E492` is a 54-byte command record**, assembled field by field at
  `ROM00:4B84`–`4C05` through the bounded copy `ram:DB89(dst, src, maxlen)`,
  and transmitted whole at `ROM00:4C11`–`4C19` as wire state `0045`. The
  destinations are contiguous and their maxima tile the record exactly. This
  **explains the state-45 object measured earlier**: the runs the experiment
  saw as "zero in every capture" are five identity fields latched by
  `C-INIT-COMMS`, and the "8-byte program name plus padding" at +42 is one
  12-byte parameter field taken from `C-COMMAND`'s `SP+2`.
* **The `LOAD` field is the operation name.** `ROM00:731B` is
  `tbl_sess_operations`, seven records of `{char name[5]; u8 target_state;}`,
  copied to `ram:E247` at boot by the descriptor at `ROM00:7D68`. This
  **corrects** the note above and in `forms-ui.md` that treated
  RCV1/RCV2/SEND/LOAD/PROG/TIME/ENDC as display field names belonging to
  `tbl_sess_status_fmt`; that template is only `7310..731A`, and nothing
  reads `731B` as text.
* **States 4, 5 and 6 are NOT unreachable — this closes the open question.**
  `C-COMMAND`'s first argument indexes `tbl_sess_operations`; `ROM00:4B3D`
  stages the target state in `ram:E491` and `ROM00:4C69` commits it through
  `Session_SetState` **with no gate at all** — not the transition table, not
  `E48D`. The firmware does this itself: `ROM01:135F`/`1365` push index 3
  (`LOAD` -> `READY-RX-PROG`) or 4 (`PROG` -> `READY-TX-PROG`) and call
  `ram:EE0C`. So states 4 and 6 are reached in ordinary Load/Run operation.
  State 5 (`SEND`, index 2) has no ROM caller but uses the identical
  instruction, and the index is unbounded — **LIKELY** reachable from an
  application. The table's rows 4/5/6 being wired as transition *sources*
  with no incoming cell is the design signature of exactly this.
  * Consequence: **clean teardown is not blocked.** `C-END-TX`'s completion
    path needs `E48D = 1` and a state from which it is legal; `SEND` or
    `PROG` reaches those states without touching `E48D`.
  * `analysis/decode_state_machine.py` now reads the operation table too and
    draws those edges, so the generated diagram shows every state's entry.
* **Wire state `0062` is the direct-connection substitute for dialling.**
  `ROM00:5DFD` is a bare 6-byte control frame, byte-identical to the `0065`
  and `0000` routines but for the immediate. `C-DIAL` and `C-ANSWER` send it
  when the link type in `ram:E520` is not 6; `C-MANUAL` always does. Only
  link type 6 (a modem) takes the `0060`/`0061` paths, so **an IR peer should
  expect `0062` and never `0060`.** All twelve `Session_SetParams` call sites
  are now enumerated on the protocol page.
* **The block commands are the program path.** `C-TX-BLK` passes its buffer
  to `ROM00:3E14`, the same walker `C-TX-REC` uses, so blocks and records
  share the `[u8 count][payload]` memory format. `C-RX-BLK` is the mirror via
  `Session_ReadStreamChunk`, with a **hard-coded 128-byte maximum** pushed at
  `ROM00:4FAD` — so its buffer must be at least 129 bytes. The block path
  emits **no separator bytes**: `ROM00:3D9B` has exactly four call sites and
  the only two literals (`1Eh` at `5107`, `1Ch` at `5193`) are both on the
  record path. Records need separators because they are variable-length items
  in one stream; blocks are framed by the transport's payload-length field.
* **Still open:** which of the four blank identity fields is User id,
  Password, Group id or Telephone. The V24 Log-on form collects exactly four
  string fields for the four unidentified slots, and the 6-character maximum
  on `SP+12` is the only distinguishing clue. Also open: `C-COMMAND`'s
  `SP+4`, and the `0045` flag byte, which is **LIKELY** a last-block marker
  (0 from the automatic flush at `6187`, 1 from the explicit flush at `61F9`)
  and would be settled by capturing a transfer longer than 128 bytes.

## Commstar: closing the identity fields and the binary-data question (2026-09-01)

* **`C-INIT-COMMS`'s ten arguments, CONFIRMED from the firmware's own call
  site.** `ROM01:12AD`–`1304` pushes ten words and cleans up with
  `LD HL,0014h / ADD HL,SP / LD SP,HL` — twenty bytes, ten words, matching
  the sweep exactly. The mode word at `SP+4` is literal **0**, which is an
  independent check on the slot arithmetic: `ram:E48D` measures 0 on the
  Load/Run path in every emulator run.
  * `SP+10`=`ECAB`, `SP+12`=`D120`, `SP+14`=`EC8E`, `SP+16`=`EC99`,
    `SP+18`=`ECA2` are the five identity strings; `SP+8` is the constant 60
    (**SUSPECTED** a timeout in seconds); `SP+0`, `SP+2`, `SP+6` go to
    `ROM00:5669`.
* **The identity fields are the V24 Log-on form's, LIKELY in display order.**
  `ram:EC97` is the form's backing object: Mode (`+0`), Linespeed (`+1`), then
  four fixed 9-byte string fields at `+2`, `+11`, `+20`, `+29` (`EC99`,
  `ECA2`, `ECAB`, `ECB4`). The form's field descriptors at `ROM01:78E1` are
  `{u16 index; u16 label_ptr}` in display order — Mode, Linespeed, User id,
  Password, Group id, Telephone number. Taking the object's order to match
  gives User id -> `E6C4` -> record `+26`, Password -> `E6D9` -> record `+34`,
  Group id -> `E6D0` -> record `+0`.
  * **Why only LIKELY:** no table in either ROM pairs a field index with its
    buffer — the form editor computes the address — so the ordering is an
    inference from the uniform 9-byte stride, not a byte-proof. **The
    confirming experiment is to type a distinct value into each of the four
    form fields and read back `E6C4`, `E6D9`, `E6D0`.**
  * Telephone (`ECB4`) is **never passed to `C-INIT-COMMS`**, which fits:
    **nothing in either ROM calls `C-DIAL`, `C-ANSWER` or `C-MANUAL`.** The
    number is collected for a dial path the firmware itself never takes.
  * Still open: `ram:D120` -> `E6E8` -> record `+8`, max 6 characters. Not a
    form field, unidentified.
* **"Blocks are programs, records are data" is about framing, not content.**
  Nothing in the firmware inspects what is handed to it; the labels come from
  the display strings alone (`6CE8` "Sending prog", `6CDB` "Sending data").
  What is hard and fast: **the record path is not 8-bit clean.** `ROM00:3E14`
  sends every byte raw — no comparison, no escape, no stuffing — so a record
  containing `1Eh` or `1Ch` is indistinguishable from a separator on the wire,
  with no way to quote it. The block path carries no in-band markers, so it is
  8-bit clean. **Binary data files therefore go on the block path.**
  * The handheld never parses separators either: the only `1Eh`/`1Ch`
    comparisons in ROM00 are at `279B`, `018E`, `27BA`, none in the session
    code. Segmenting the record stream is entirely the **host's** job.
* **`LD DE,nnnn / CALL D837` is a frame prologue, not a cross-page call.**
  `ram:D837` (from `analysis/battery_ram.bin`) is
  `e1 c5 44 4d 21 00 00 39 eb 39 f9 d5 dd e5 fd e5 60 69 cd 36 d8`:
  POP HL (return address) / PUSH BC / BC = return / HL = SP / EX DE,HL /
  ADD HL,SP / LD SP,HL — so **DE is the local-frame size**, 0 meaning no
  locals — then PUSH old SP / PUSH IX / PUSH IY and jump back to the caller.
  The genuine inter-bank call is `RST 10h ; db bank ; dw target`.
* **CONFIRMED: the state-`0045` arg field is a last-block marker
  (2026-09-01).** Measured, not inferred: a 200-byte record is segmented by
  the 128-byte wire buffer into `arg=0 len=128` then `arg=1 len=83`, matching
  the static prediction (0 from the automatic flush `ROM00:6187`, 1 from the
  explicit flush `ROM00:61F9`). Concatenating the frames reproduces the
  211-byte stream byte for byte, so **frames carry no internal headers** and a
  peer reassembles by plain concatenation, ending when it sees `arg = 1`.
  `analysis/boot_hw.py` now logs the arg with each received record.
  * The first attempt appeared to send 371 bytes for a 211-byte stream. That
    was the test's own fault, not the firmware's: `build_record_upload_com`
    defaults put the name buffer at `0xE870`, only 0x20 bytes above the record
    buffer at `0xE850`, so a 201-byte record ran straight over it. With the
    name buffer moved *below* the record buffer the stream is exact. Worth
    remembering when writing COMs that drive uploads.
  * The capture also shows wire state **`0062` live** in the request sequence
    (`0000 0006 0062 0045 0045`), confirming the direct-connect state
    identified statically.

## Ghidra listing repair consolidated; the D837 no-return flag was eating functions (2026-09-01)

Built `analysis/ghidra/AnalyseMicronicRom.java`: one self-contained,
idempotent script replacing the throwaway repair scripts. Five passes —
frame-helper flow, boot-load chains, `RST 10h` inline operands,
`Kernel_TableDispatch` tables, compiler frame prologues. Full write-up in
`doc/re-notes/ghidra-repair-script.md`.

* **CONFIRMED and consequential: `ram:D837` was flagged no-return, and that
  flag deletes C function bodies.** The bytes (`D836`-`D857`, byte-verified)
  show the helper pops the `CALL`'s return address and re-enters it through
  `CALL D836` = `JP (HL)`, so `CALL D837` *falls through* to the caller's
  body. With the flag set, Ghidra's non-returning-function repair treats
  every compiled routine's body as dead code. Measured: a run of the other
  four passes with the flag still set created 143 functions and background
  auto-analysis then deleted **61 existing** ones (59 hand-named, incl.
  `Lib_StrCmp`, `Lib_StrCopy`, `Program_LoadedProgram`, `Kernel_RunStagedCall`,
  most of the `SessionOpStub_*` farm). All 61 were restored from a pre-run
  `list_functions_enhanced` snapshot — the §11 diff-guard rule paid for
  itself. The flag is now clear and pass 1 re-clears it on every run.
* **RESOLVED 2026-09-19 (CONFIRMED,
  byte-verified) — `ram:D837` renamed
  `Coroutine_Enter`; duplicate `Coroutine_TaskSwitch`
  mis-name fixed.** The duplicate was `ROM00:3BB8`
  `Coroutine_TaskSwitch`, now
  `Coroutine_IndexedLookup_6A4A` (indexed lookup into
  table `6A4A`; sibling `ROM00:3BD0`
  `Coroutine_SessionMul16` → `Coroutine_IndexedLookup_6B67`).
  `ram:D837` is now `Coroutine_Enter` (`CONFIRMED
  ram:D837-D857`): coroutine frame-entry / context-switch
  helper — pops the continuation, switches `SP` by `DE`,
  saves `BC`/`IX`/`IY`, calls via `ram:D836` (`JP
  (HL)`), returns `HL` with `Z` iff `HL==0`; entered by
  `LD DE,0; CALL ram:D837` (`DE` = frame size). See
  §12 item 2b (now closed) and
  `doc/re-notes/open-questions.md`.
* **Two bugs fixed from `AnnotateRst10Calls.java`:** enqueued boot-chain
  targets resolve in the bank whose chain is running (`ROM00`/`ROM01`), not
  in the flat `ram` space — that left 156 dangling references in the bank-0
  chain alone, now repointed; and the script no longer overwrites comments.
* **Function count 934 -> 1087**, all 934 originals verified intact by an
  address-and-name diff. Includes the eight routines between `ROM00:4D25` and
  `5307` that previously had no function at all. Second run reports zero
  changes in every pass.
* Two prologue sites stay deliberately deferred: `ROM00:7409` and `7472` are
  the ROM images of RAM module A (`ram:D8CE`, `ram:D937`), where internal
  addresses would resolve against the wrong space.

## Commstar: who starts a session, and a bad entry-point table (2026-09-01)

* **CORRECTION: the stub-slot table had four slots mislabelled, and there are
  no duplicate wrappers.** Derived properly this time —
  `Session_StartDataMode` (`ROM00:452D`) has fifteen call sites in ROM00 and
  each pushes a distinct literal command index, so slot -> command is
  one-to-one and complete. The earlier table listed `C_ABORT` three times and
  `C-SHUT-DOWN` three times and said the duplicates were untold-apart; that
  was wrong, and so was the observation (made the same day) that "the
  duplicate wrappers differ in arity". Five slots dispatch no command:
  * `EE24` `46E9` — initialises the session.
  * `EE30` `4D29`, `EE48` `4D4F` — **message-box helpers**
    (`"   not available"` / `"   in Workstation"`), differing only in buffer
    pair (`E278`/`E279` vs `E288`/`E289`).
  * `EE38` `5444` -> `5915` -> `62C7` — **solicits a data block**, wire states
    `0043` then `0044`.
  * `EE4C` `5428` -> `58F9` -> `63CA` -> `612A` — **sends a data block**, wire
    state `0045`.
  The last two never call `452D`, so no state validation applies to them.
* **CORRECTION: `C-DIAL`, `C-ANSWER` and `C-MANUAL` *are* called.** The
  earlier claim that nothing calls them came from scanning for the direct
  opcodes `CD 10 EE` and friends. The call is **indirect**:
  `ROM01:131D`-`1330` reads the connect-command address from the selected
  link-method record and calls it through `ram:D828`. On `LOCAL LINK` — the IR
  path — that is `C-DIAL`, with `ECB4` (Telephone) as its argument.
* **The link-method table, byte-verified** at `micron2.bin 0x7C52` -> `ram:D108`,
  four 6-byte records mapping 1:1 onto the strings at `0x7A2F`:
  `LOCAL LINK` (type 4, `C-DIAL`, 9600, number `ECB4`), `MODEM A/ANS`
  (type 6, `C-ANSWER`, 1200), `MODEM A/DIAL` (type 6, `C-DIAL`, 1200,
  `ECB4`), `MODEM MAN/D` (type 6, `C-MANUAL`, 1200). The adjacent table at
  `0x7C4C` (`05 06 07 0A 0C 0E`) is **baud rates**, matching the six strings
  at `0x7A5F` — not link types.
  * So **`ram:E520` is 4 for the IR link and 6 for any modem method**, and it
    is a caller-supplied parameter, never probed from hardware.
* **The handheld is the sole initiator. CONFIRMED.** `C-COMMAND` is a
  generator, not a parser — `ROM00:4C19` transmits the 54-byte record and only
  then reads a reply.
  * There *is* an always-armed interrupt receive path: `ROM00:2352` is a
    `{u8 mask, u16 handler}` table copied to `ram:FD84`; mask `04` vectors to
    `ROM00:31B6`, which tests `RXBUSY` and calls the receive dispatcher **with
    no session-state test**. `31B6` has no xref in Ghidra — it is reachable
    only through that table.
  * But the dispatcher `ROM00:2FBD` exits upward only at `ROM00:30D7`,
    `LD HL,(FDD2) / JP (HL)`, and **`ram:FDD2` has exactly one writer**,
    `ROM00:2F36`, inside the transaction starter. An unsolicited frame can
    therefore never reach the session layer. This is "no path exists", not
    "no path found".
  * `C-ANSWER` is not a listen primitive: it transmits (`0061` on link type 6,
    `0062` otherwise). "Answer" means telling the far end to answer a phone.
* **There is no Plinth detection.** `Plinth not connected.` (`ROM00:6D6F`,
  referenced only at `ROM00:4463`) is the `C-INIT-COMMS` failure message,
  printed when the peer does not answer — whatever is attached. `Link_Probe`
  (`ROM00:348A`) returns a status byte that **both callers discard**
  (`ROM00:0202`, `0229`); it is a cold-boot controller reset. Plinth vs V24
  adaptor is a menu choice (`micron2.bin 0x7663`) that becomes bit 5 of the
  link id; `Link_PortSelect` (`ROM00:3455`) drives port `2Ch` as well as
  `LINK_CTRL` bit 1. **RESOLVED 2026-09-01**, see below — and "connector" was
  the wrong word: both are IR ports on the handheld. Formerly: which polarity
  is which connector — needs a
  hardware test.
* **Retry budget for a host implementer:** a request retries `32h` = 50 times
  (`ROM00:2F58` / `30FC`), a reply `14h` = 20 times (`ROM00:3042`).
* **OPEN, flagged as a hazard:** with the link idle, a frame of a type other
  than 2 or 3 that passes the length and id checks reaches the `JP (HL)`
  through `FDD2`, which is `0000` on a cold machine. **LIKELY** a reset. Do not
  send unsolicited frames; a type-2 frame is the safe probe.
* **OPEN:** whether the Plinth can assert NMI. `Kernel_HandlerImage`
  (`ROM00:3B13`) wakes/aborts the machine and the physical NMI source is
  unrecorded. If the Plinth drives it, a host could at least wake a unit —
  though still not start a session.

## Pass 0 and the stub farm: correcting an earlier rejection (2026-09-01)

**The earlier rejection of `FillBatteryRam.java` as "out of scope memory
mutation" was wrong** (owner correction). It is a *prerequisite*, not a
mutation: `micron1.bin` holds only the two ROM banks, and everything the ROM
calls into lives in unpaged battery RAM — `ram:D837` (frame prologue helper),
`E0B2` (Kernel_TableDispatch), `DB89`/`E04B`/`DFCC` (string, compare,
multiply), `D828` (indirect call), `D893` (module A), `F180` (resident
kernel), and the `ED1C` stub farm. Without it none of that disassembles, and
the consolidated script's own pass 1 would silently no-op because its byte
check reads `D837`, which is empty on a freshly imported program. It is now
**pass 0**, running before everything else, and the ordering dependency is
stated in the script's plate.

Folding it in turned up two defects in the original, both byte-verified:

* **The `ram:E104` copy length was wrong.** `FillBatteryRam.java` hardcoded
  `0130h`; the chain record at `ROM00:7D7C` says `0129h`. `7C2F + 0129h =
  7D58`, exactly where the boot-load chain script starts — the blob ends where
  the chain begins — so `0130h` over-reads **seven bytes of the chain script
  itself** into `ram:E22D`, on top of the misc-config block copied there a
  moment earlier. Measured: at `0130h` the destination mismatches in 6 bytes,
  at `0129h` it matches exactly. The six chain-backed copies are now derived
  from the chain walk (one source of truth); the five copies performed by ROM
  code, which appear in no chain, stay hardcoded with the performing routine
  named against each. The script diffs the two lists and reports drift.
* **`removePhantomFunctions` would have destroyed the resident kernel.** It
  deleted every `ram` function at or above `F100` — true of the database it
  was written for, catastrophic now that `F180` holds the kernel. On the
  current database that predicate matches **61 functions**, 58 hand-named,
  including `Bdos_DispatchFn`, every `Syscall_InvokeService*`,
  `Kernel_BankedCallEnvelope`, `Kernel_SetBank`, `Kernel_CallCommonEntry` and the
  `SessionOpStub_*` farm. It now requires both a still-generated `FUN_` name
  and a non-instruction entry. The stub-farm template fill is likewise
  refused if any slot begins with `D7`, i.e. if the image is a post-boot dump
  with live thunks.

**CONFIRMED: the runtime stub farm is 281 slots, and the fn=2 chain handler is
its installer.** New pass 6 links them all.

* Slot *i* is the 4 bytes at `ram:ED1C + 4*i`. `ram:D727` (byte-verified)
  reads the queue cursor `(d684)`, then per source word stores `D7h`, the live
  bank shadow `(f791)`, and the 2-byte target, advancing 4 — so a slot is an
  inter-bank thunk `RST 10h ; db bank ; dw target`, in the same four bytes as
  the `LD HL,1 / RET` template it replaces.
* **There is no separate installer**, which is why a scan for a pointer to
  `ROM00:7D88` finds nothing: the handler reads the words inline out of the
  record stream as it walks the chain. `7D88` is just where bank 0's fn=2
  record keeps them. The stub source table and the deferred-call enqueue list
  are the same 134 words, not two tables.
* Bank 0 supplies slots 0..133 (ROM00 targets), bank 1 slots 134..280 (ROM01).
  281 × 4 = 1124 bytes = exactly `ED1C..F17F`, which is exactly the range
  `Kernel_InitCopyData` pre-fills, ending exactly on `F180`. The three
  slot→target pairs recorded here earlier from a live RAM dump (58 → `48BF`,
  60 → `4AE0`, 68 → `4F5A`) all reproduce, which is what fixes bank-0-first.
* The whole farm currently reads `21 01 00 C9` — all 1124 bytes match the
  template at `ram:D6D7`, so this is the genuine cold state, not damage. Every
  `CALL 0EExxh` in ROM01 and in loaded programs was therefore a dead end with
  no reference to its target; pass 6 adds all 281 edges plus a per-slot EOL.
* **Chain-walk trap, recorded so nobody re-introduces it:** the 134 words at
  `ROM00:7D88` also parse as plausible 6-byte records (the first reads
  `src=3BAA dst=62C7`). The walker must consume the fn=2 record by its
  declared word count, which lands exactly on the `FFFF` terminator at
  `7E94`. The script prints the chain span every run so this is visible.

Verified: two consecutive runs, second reports zero changes in every pass;
`list_functions_enhanced` diff before/after shows **zero lost, zero renamed**
at 1087 functions.

## Commstar: the controller transaction decoded (2026-09-01)

* **`Link_BlockTx` (`ROM00:3277`) and `Link_BlockRx` (`ROM00:3378`) are decoded
  end to end.** This is the layer a physical IR adapter implements, and it was
  the last major undecoded one. Full step-by-step listings are on the protocol
  page; the load-bearing results:
* **The prelude byte is `link id & 1Fh`, written at `ROM00:32B3`.** That is
  why a peer cannot recover the full 8-bit id from the wire — the firmware
  masks it to five bits before it leaves. `link_id_from_prelude` in
  `analysis/micronic/peer.py` is necessarily guessing the top three bits.
* **There is no checksum anywhere in either routine** — not a single
  accumulating `XOR` or `ADD` in 478 bytes. Integrity is not this layer's job.
  Per the user, the physical link is **synchronous** (clock and data in each
  direction) between emitter/detector pairs almost in contact, so little
  stray light enters and errors are unlikely. A host must not expect a
  checksum and must not add one.
* **The two "trailing excluded bytes" are signalled out of band, CONFIRMED.**
  Receive status `4Bh` bit 2 gates a single extra `INI` at `ROM00:33F3`. The
  frame's length field never covers them, which is why the peer appends them
  separately. Their *meaning* stays open — nothing in `Link_BlockRx` interprets
  them, so it is a controller convention this ROM cannot explain.
* **Receive status register `4Bh`:** bit 0 = byte waiting, bit 1 = end of
  frame, bit 2 = one further byte to take, bit 3 = controller error. The
  framing is carried entirely by these bits; there is no in-band delimiter.
* **Transmit result convention:** carry clear with `A = 0` on success; carry
  set with `EBh` (controller absent or not ready), `ECh` (status bit 5 error)
  or `EEh` (timed out).
* **Timing budget for an adapter:** `026Ch` = 620 spin-loop counts for a
  handshake response (9.92 ms), `06F9h` = 1785 per payload byte (24.69 ms),
  on a 3.6864 MHz Z80 (clock corrected 2026-09-03),
  plus fixed settling delays of 128, 32 and 2 `DJNZ` iterations. Generous for
  on-board hardware, much less so across a millisecond round trip — **an
  adapter bridging to a host over USB should service the latch handshake
  locally rather than round-tripping each byte.**
* **OPEN, and only hardware can answer it:** the prelude is written to the
  same data latch (`4Dh`) as the payload but *before* the strobe sequence, so
  whether the controller forwards it onto the IR line or consumes it as
  addressing is not determinable from the firmware. It decides whether the
  prelude is a byte an adapter will see. A logic capture settles it.
* **Port-select mechanics resolved.** "Connector" was the wrong word: Plinth and V24 are
  two **IR ports on the handheld** — base and top — and the connector is the
  infrared link itself. `Link_BlockTx` tests link-id bit 5 (`ROM00:3278`,
  `AND 20h`) and hands it to `Link_PortSelect` (`ROM00:3454`), which drives
  `LINK_CTRL` bit 1 and port `2Ch` bit 5 **together**: wire-ID bit 5 clear ->
  both set, wire-ID bit 5 set -> both clear. The session's inference that
  wire-ID bit 5 clear meant Plinth was later **REJECTED**: a reproduced V24
  UI run also uses `43h`, and the owner's top-window capture maps that
  clear-bit state to V24.

## Commstar: both directions demonstrated, and the session ends cleanly (2026-09-01)

* **Program download driven end to end through the peer.** A loaded COM runs
  `C-INIT-COMMS` -> `C-DIAL` -> `C-COMMAND(3 "LOAD")` -> `C-RX-BLK` until
  status 8, against `micronic.peer.ProgramDownloadPolicy`. Wire states
  `0000 0006 0062 0064 0045 0044`x4. A 300-byte image arrives in three blocks,
  reassembles by plain concatenation byte for byte, and the screen ends on
  `Program received`. Note the final `C-RX-BLK` carries data **and** status 8
  in the same call. Regression `CommstarProgramDownloadTest`.
* **`C-COMMAND`'s third argument (`SP+4`) is the reply buffer** — this closes
  an open question. `ROM00:4C32` pushes it into `ROM00:3F20`, which solicits
  `0044` with `size = 00FFh`; `ROM00:3F65` matches the first two bytes of the
  answer against the table at `ram:E22F`. Byte-verified at `micron1.bin`
  `0x7303`: `4F 4B 00 00 | 4E 4F 00 01 | 44 4D 00 02` — `OK`->0, `NO`->1,
  `DM`->2, anything else -> error `0x1F75` (8053) `Invalid reply`. **A host
  that never answers a command cannot advance the session.**
  * This also explains the previously-unexplained `0044` with `size = 00FFh`
    in the Load/Run trace: it is the command's **reply read**
    (`ROM00:3F39` pushes `00FFh`), not a block request, which pushes `0080h`
    at `ROM00:3D59`.
* **A host must never send more than 126 bytes of object data. CONFIRMED by
  measurement.** 126 completes a download; **127 is silently dropped** — no
  type-3 ack, the handheld re-requests, and after retries the session ends
  `Session aborted` with `C-RX-BLK` returning 4. `MAX_OBJECT_DATA` enforces
  it. **The mechanism is NOT derived**: `ROM00:620B` sets the `0044` frame
  length to `86h` = 134 and 134 - 8 = 126 is consistent with an eight-byte
  preamble, but the RX frame struct at `ram:E5BA` is 138 bytes with its data
  area at `+0Ah`, which suggests a different budget. The two readings are
  unreconciled — treat 126 as measured, not derived.
* **Clean teardown demonstrated, confirming the reachability finding
  empirically.** `C-COMMAND` index 2 `SEND` puts the session in
  `READY-TX-DATA`; a full upload then ends through `C-END-TX`'s completion
  path. States read back from `g_bSessionState`: `1 2 5 9 9 10 2`
  (`DISCONNECTED` -> `CONNECTED` -> `READY-TX-DATA` -> `RECORD-TX` ->
  `RECORD-TX` -> `DATA-SET-TX` -> `CONNECTED`), every result 0, screen
  `Data transmitted`. Regression `CommstarCleanTeardownTest`.
* **Two earlier claims overturned.**
  * **`C-END-TX`'s argument path is not an abort path.** `ROM00:534D`, its
    `OK` case, displays `ram:E516` and commits `ram:E48C` exactly as `531C`
    does. Mode 0 ends as cleanly as mode 1. What produced `Abort pending` in
    the earlier demonstration was the session sitting at `CONNECTED` with
    `E48D = 2`, not the disposition argument.
  * **`E48D = 1` stops `C-COMMAND` transmitting at all.** Byte-verified:
    `ROM00:4B4C JP Z,4B5D` takes the record-building path only when
    `E48D != 1`; when it is 1, `4B4F` sets the state from `ram:E491` and
    `4B5A JP 4D25` returns, never reaching the record build at `4B84` or the
    transmit at `4C19`. So mode 1 advances the handheld's state while telling
    the host nothing. **A real session wants mode 0**, which both sends the
    command record and still ends cleanly.
  * Also corrected: the `ram:D0FE` guard at `ROM01:140E` reads the opposite
    way to what the API page said. `ram:E04B` returns NZ on *equal*, so
    `JP NZ` means equal — the loop **stops** at 8 rather than starting there.
* **OPEN, and reproducible:** a driver image of exactly **561 bytes** fails at
  its first `0064` exchange with result 4. 556-560 and 562 all pass, two
  different 561-byte images both fail, and neither a reply delay nor a
  different slice size fixes it — only moves which `0064` fails. No ROM
  mechanism explains a length dependency, so this is presumed a harness
  artifact. Discriminating experiment: instrument `ROM00:60D6` / `59FB` reply
  classification on a failing run. Recorded in the test file so an innocuous
  edit that changes a driver's length does not cost someone an afternoon.

## Commstar: closing open items (2026-09-01)

* **CORRECTION: the `43h` / `63h` link-id story was wrong, twice over.**
  * They are **not** a fixed pair inside 4-byte device slots. `ROM00:31FF` is
    the accessor and it decodes as a device-number lookup on a **flat
    16-entry array**: `CP 41h` splits drive letters (-> `ram:FE93`) from
    device numbers (-> `ram:FE83`), then `DEC A` / `CP 10h` / `ADD HL,DE`.
    So `ram:FE83` = `80 AB 63 43 80 2B 63 43 80 67 63 43 80 67 63 43` maps a
    device number to a wire id, and `43h`/`63h` are the ids of two particular
    devices.
  * **Measured: the Load/Run source picker does not select the IR port.**
    Running the harness both ways, `--trace-loadrun-source plinth` and
    `--trace-loadrun-source v24`, the traces genuinely diverge (13 agreed /
    1 unsolicited vs 12 agreed / 2 unsolicited) yet **both carry prelude `03`
    and link id `43h`**. The earlier "LIKELY `43h` = Plinth" rested on the
    default screen reading `PLINTH`; that argument is void, because the V24
    route produces `43h` too.
  * The likely source of the confusion: there are **two** pickers. The
    five-entry storage picker at `micron2.bin 0x757F` (`WORKSTATION MEMORY`,
    `WORKSTATION RAMDISK`, `PLINTH`, `V24 ADAPTOR`, `EXT STORAGE ADAPTOR`) is
    what the harness drives; the two-entry picker at `0x7663` sits in the
    comms setup form and **no current trace exercises it**.
  * Still CONFIRMED and unaffected: `Link_BlockTx` routes on wire-ID bit 5
    (`ROM00:3278`) and `Link_PortSelect` drives `LINK_CTRL` bit 1 and port
    `2Ch` bit 5 together. At this session the physical mapping remained OPEN.
    **SUPERSEDED 2026-09-06:** the V24 trace plus owner capture maps wire-ID
    bit 5 clear/output bits set to the top port.
* **CLOSED: `ram:D120` -> `E6E8` -> command record `+8`.** It is not a
  credential buffer. `D120` is the byte immediately after the four 6-byte
  link-method records at `ram:D108` (`D108 + 4*6 = D120`) — the table
  terminator. It has **exactly one reference in either ROM**, the
  `C-INIT-COMMS` push at `ROM01:12B9`, and **nothing writes it**. The pointer
  therefore addresses a zero byte, the bounded copy yields an empty string,
  and record `+8` is blank in every trace. A vestigial slot.

## Documentation review pass: Commstar pages reconciled (2026-09-01)

A read-only-to-the-ROM review of the Commstar documentation after a long
editing session. No new firmware analysis was commissioned; everything below
was byte-verified against `micron1.bin` / `micron2.bin` before the doc was
changed. Files touched: `doc/protocol/commstar.md`,
`doc/reference/commstar-api.md`, `doc/reference/commstar-peer.md`,
`doc/re-notes/open-questions.md`, `doc/re-notes/commstar-evidence.md`,
`doc/re-notes/os-diposb.md`, and the four index pages.

* **Contradiction, now resolved: "the transition table is never consulted by
  the firmware at runtime."** That sentence in `protocol/commstar.md` was the
  exact inverse of the truth and sat forty lines below a paragraph saying the
  opposite. `Session_StartDataMode` (`ROM00:4533`) skips the table only when
  `E48D == 2`; `E48D` measures **0** in every session, so the table is
  consulted on **every** command the firmware issues. Both the offending
  sentence and the "the table is gated off on the traced path" claim in
  *What selects the operation* are replaced.
* **The real mechanism for states 4/5/6.** `C-COMMAND` is validated by the
  matrix like everything else (`ROM00:4AEA` calls `Session_StartDataMode(5)`
  and bails at `4AF3`); what it does differently is discard the staged
  `ram:E48C` and write `ram:E491` instead at `ROM00:4C62`. So the table is a
  complete validator of command *order* and an incomplete description of
  *states*. Documented that way now, in place of "partial validator … bypassed
  for everything else".
* **`ram:E48D` is three-valued, and this was nowhere stated.** Byte-verified,
  four readers, two different comparison constants: `Session_StartDataMode`
  (`4533`) tests **2**; `C-COMMAND` (`4B40`), `C-SHUT-DOWN` (`4D92`) and
  `C-END-TX` (`530D`) each test **1**. Mode 0 = normal, mode 1 = advances
  state without transmitting, mode 2 = validation off. Added as its own
  section on the protocol page and to the `E48D` watch item.
* **Entry-point call scan redone across all images.** The old table claimed
  "only two of the six invoked". A full scan for `CALL`/`JP` to each of the
  twenty slots finds **six** direct callers — `EE00` `C_ABORT` (`ROM01:11A4`),
  `EE0C` (`1369`), `EE14` `C-DROP-LINE` (`11A7`, `152B`), `EE20` (`1304`),
  `EE2C` (`141E`), `EE3C` `C-SHUT-DOWN` (`151C`) — plus three reached
  indirectly through the link-method callback (`EE04`, `EE10`, `EE28`). So
  **eleven** slots have no caller, not fifteen. The API page's "fifteen of the
  twenty" is corrected.
* **Slot indices were wrong in one table.** Index is `(addr − ED1C) / 4`:
  `EE00` = 57, `EE14` = 62, `EE3C` = 72.
* **Stale claims removed.** `protocol/commstar.md`'s scope paragraph still
  said the missing pieces included "any handheld-to-host transfer" ten lines
  above a table row describing one working; the RECORD-transfer row still said
  the session "ends in an abort" and that `C-END-TX` is legal only from
  unreachable states; `reference/commstar-peer.md` still said "no capture of
  an upload exists yet"; `reference/commstar-api.md`'s *Suppressing
  validation* section still justified `E48D = 2` as "how the firmware itself
  reaches operations the table cannot" (the firmware never sets it, and no
  demonstrated sequence needs it). All corrected, with the superseded
  application-driven sequence kept and flagged rather than deleted.
* **`open-questions.md` was the worst-drifted page.** *What selects the
  Commstar operation* and *why a bare COM does not resume* both still asserted
  that states 4/5/6 needed `E48D = 2`; *state-44 payload maximum* still asked
  for the 127 bisection that has since been done; the state-45 item still
  listed `LOAD`-varies and the `arg` marker as open. All four updated, with
  the retractions stated explicitly.
* **Byte-verifications performed for this pass** (all fresh reads, none from
  recall): `452D`, `4533`-`4562`, `4563`-`4572`, `46E9`-`470D`, `4AE0`-`4B3D`,
  `4B40`-`4B5A`, `4C05`-`4C7E`, `4D29`-`4D74` (the two message-box helpers),
  `4D75`-`4DB5`, `4F9A`-`4FC3`, `5179`-`51EB`, `51EC`/`523F`, `52A5`-`537D`,
  `5428`/`5444`, `58F9`/`5915`, `332E`-`3377` (`EBh`/`ECh`/`EEh` + carry),
  `348A`, `34EC`/`34F8`, `3508`, `31FF`-`321F`, `ram:E04B`, `ram:E05A`,
  `ROM01:1280`-`1369`, `ROM01:140E`-`14C7`, `micron1.bin 0x7301`-`0x7345`
  (`OK`/`NO`/`DM` + `tbl_sess_operations`), `micron2.bin 0x7C52` (the four
  link-method records), and `ram:FE83`/`FE93` in the battery-RAM dump.
* **`ram:E04B` and `ram:E05A` are opposite.** `E04B` is `==` (equal → `HL=1`,
  **NZ**); `E05A` is `!=` (equal → `HL=0`, **Z**). They appear nine
  instructions apart at `ROM01:1414` and `ROM01:1430` testing the same cell
  against the same constant. Every polarity error corrected on the API page
  started here, so it is now called out explicitly in an admonition.
* **Discriminating observation recorded for the port question.** `ram:FE83`
  is byte-verified in a live dump as `80 AB 63 43 80 2B 63 43 80 67 63 43 80
  67 63 43`; device 3 is `63h` and device 4 is `43h`, and the `LOCAL LINK`
  mode record's selector is 4 — which is why every IR trace carries `43h`.
  The test is therefore "which device number does the two-entry comms picker
  (`micron2.bin 0x7663`) select?", not "which label does the storage picker
  show?". **No mapping to PLINTH/V24 is asserted**; that stays OPEN.
* **OPEN and unfixed by this pass:** `analysis/commstar_args.py` still prints
  the retracted slot labels (`EE30`/`EE48` as `C-SHUT-DOWN`, `EE38`/`EE4C` as
  `C_ABORT`). Its *argument* output is correct and agrees with the API page;
  only the names are stale. Left alone because `analysis/` was out of scope
  for this pass.
* **Also unresolved:** the protocol page and the evidence page disagree in
  emphasis about whether `0x7F` at frame offset +4 is an id. `Link_Probe`
  computing `7Fh AND 1Fh` proves `7Fh` is used *as an id* somewhere; what it
  means at offset +4 is still SUSPECTED. Both pages now say that, in those
  words.
* **One more compressed-into-wrong correction, fixed.** The API page's
  `C-END-TX` correction said `Abort pending` came from "the session sitting at
  `CONNECTED` with `E48D = 2`, where `C-END-TX` is an illegal transition".
  With `E48D = 2` the table is *not* consulted, so illegality cannot be the
  trigger in that case. The earlier TASKS note (2026-09-01, "Why the
  demonstration aborts") had it right and the summary lost it: mode 2 fails by
  taking the argument path with an argument the test never supplied, and mode 1
  fails because `table[CONNECTED][C-END-TX] = 8Dh` (byte-verified at
  `micron1.bin 0x695B`; bit 7 set, next state `CRASHED`) makes
  `Session_StartDataMode` return non-zero and `ROM00:52F8` exit. Both halves are
  now on the page.

## Commstar: the 561-byte anomaly was a harness bug (2026-09-01)

* **CLOSED, and it was memory corruption, not timing.** `analysis/boot_hw.py`
  staged each upload chunk as up to **256 bytes at `ram:E5C2`**, reaching
  `E6C1`. A real service-33 receive is a 134-byte object at `ram:E5BC` with
  its body 8 bytes in, so the firmware never writes past `ram:E641`. The extra
  128 bytes buried **live Commstar session state** — including `ram:E69F`-`E6B3`,
  the buffer `Session_RxByteGet` (`ROM00:65C2`) reads and the 16-bit count at
  `ram:E6A9` it tests and decrements, called from `Session_RxByteLoop` at
  `ROM00:5A21`.
  * **Why it depended on length:** chunks run 14, then 256-byte chunks, then a
    short remainder. The remainder overwrites only the low end of the window,
    so bytes from the *previous* chunk survive above it — making the residue a
    direct function of image length. A loaded program opening a session then
    read it back.
  * **The `--slice-ticks` observation was a red herring** and is consistent
    with corruption: it changes *where* the bad reader state surfaces, not
    whether it exists. Timing is ruled out as a cause.
  * **Bisected to a single byte. CONFIRMED:** restoring `ram:E6AA` alone fixes
    a 561-byte driver; forcing `ram:E6AA` to `01h` or `06h` reproduces the
    symptom verbatim in an otherwise-passing 560-byte driver (first `0064`
    after `C-DIAL` returns 4, states `0000 0006 0062 0064 0065`), while
    thirteen other values pass.
  * **Fix:** `UPLOAD_BUFFER_MAX = 126` caps every staged chunk to the real
    receive-object size, and the window is restored after finalize. Note 126
    is the same limit the object-size work reached independently.
  * **Regression:** `CommstarCleanTeardownTest.test_the_image_length_does_not_change_the_outcome`
    runs one driver at six lengths (556-561). Verified to **fail on the
    pre-fix harness at exactly 561** and pass after — established as a fix,
    not merely observed green.
* **Still open, narrowed:** `ram:E6AA` alone is not the whole rule — 569- and
  577-byte drivers carry the identical `E6A9`/`E6AA` pair and passed even
  pre-fix, so other residue in the window participates. The natural 560-byte
  residue `0xC306` (a nominally huge count) survives a whole session while
  `0x0608` does not, which a plain "count > 0 means read buffered garbage"
  reading cannot explain. Next experiment: single-step `ROM00:65C2`-`65DF` on
  a poked failing run versus a passing one, logging `(E6A9)` and the byte
  returned per call. Does not affect the fix, which removes the input.
* **`ROM00:65C2` `Session_RxByteGet`, byte-verified.** A pushback/lookahead
  reader: if the 16-bit count at `ram:E6A9` is zero it falls through to `65E0`
  to fetch (via the `ram:E6AD` / `E6AE` / `E6AC` flag bytes); otherwise it
  decrements the count and returns `mem[ram:E69F + count]`. Initialiser
  `ROM00:6526` sets `E69D=0, E6A9=0, E6AB=0, E6AC=6, E6AD=0`. Callers:
  `ROM00:5A21`, `5FE8`, `57C4`, `57EE`, `7E6E` (computed), `ram:EEE8`. There
  is **no literal `E6AA` reference anywhere** — it is only ever touched as the
  high half of the `E6A9` word, which is why an address search finds nothing.
* **Rule for test authors:** anything the harness writes into fixed RAM
  (>= `0x8000`) before a loaded program runs is **live session state, not
  scratch**. Keep host staging within the size a real firmware transfer would
  use, and restore the window afterwards. **A test whose result changes when
  you add a NOP is a memory-collision symptom, not a timing one.**

## Commstar: buffers must be unbanked, and a map of where they can go (2026-09-02)

* **CONFIRMED: every buffer passed to a Commstar entry point must live in
  unbanked RAM (`0x8000`-`0xFFFF`).** A COM's own spare space above its code
  cannot serve, which was the obvious idea and is wrong. Each entry point is a
  four-byte thunk `RST 10h ; db bank ; dw target`; `ROM00:0010` compares the
  target bank against `ram:F791` and takes `ram:D74B` when they differ, which
  **switches the lower-32K bank and jumps**. Nothing maps the caller's page
  while the callee runs, so a routine executing in ROM00 sees ROM at
  `0x0000`-`0x7FFF`, not the caller's data.
  * The design says so itself: the cross-bank path maintains a **shadow stack**
    at `ram:E36F`, because the ordinary stack would otherwise be unreachable.
  * Positive confirmation, not just absence: **every** buffer the firmware
    passes is unbanked — `ROM01:141A` -> `C-RX-BLK` at `ram:D39D`,
    `ROM01:1343` -> `C-COMMAND` at `ram:D422`, `C-INIT-COMMS`'s strings at
    `ECAB`, `EC99`, `ECA2`, `EC8E`, `D120`.
  * Corroborated from the disk path: `ram:F510` reads the DMA address and does
    `CP 0x80 / RET NC`, so the BDOS bounces a sector through `FEFF` exactly
    when the caller's buffer is below `0x8000` and uses it in place when it is
    already unbanked (`ROM00:3A2D`).
* **New page: `doc/re-notes/unbanked-ram-map.md`** — a full region map of
  `0x8000`-`0xFFFF` with evidence tags, ranked scratch recommendations, a
  do-not-touch list, and a recipe for verifying a candidate empirically.
* **The crowding is invisible to an address search**, which is why guessing has
  cost us twice. The firmware's idiom is one base literal plus a walked
  pointer, so live buffers read as unreferenced holes:
  * `F9B5`-`FBB4` (512 B) is the **barcode edge-timing capture buffer**, and it
    is filled by `PUSH` — `ROM00:13BF` sets `SP = FBB5`, pushes a word per
    edge, then reverses in place with `IX = F9B5` / `IY = FBB3`. Zero
    `LD (nn)` references.
  * `D481`-`D680` is the **loaded program's stack**: `LD SP,D681` at
    `ram:D7FA` / `ROM00:71A9` (`31 81 D6`), growing down.
  * `FEFF`-`FF7E` and `FF7F`-`FFA2` are the **BDOS sector and FCB bounce
    buffers**; `F8B8`-`F937` the directory swap buffer.
* **Recommended scratch: `C000`-`D080`**, immediately below the loader's
  ceiling — `ROM00:7052` `21 81 D0 / 22 BD E3` sets
  `g_pProgramLoadCeiling = D081`, and module B begins exactly there. No
  instruction in either ROM or any of the five RAM-resident modules touches
  `8006`-`D080`. **A strong negative bounded by disassembly coverage, not a
  proof** — hence the empirical recipe on the map page.
* **Second instance of the staging-collision bug, fixed before it bit.**
  `boot_hw.py` had `UPLOAD_NAME_ADDR = 0xD600`, which is above the `D081`
  ceiling but **`81h` bytes inside the loaded program's stack**. Moved to
  `0xC000`. `UPLOAD_BUFFER_ADDR` stays at `E5C2`: that path deliberately
  impersonates the service-33 receive object, so the address is correct there
  and is not general scratch.
* **CORRECTION to this project's own framing:** `analysis/battery_ram.bin` is
  **not a hardware dump**. It is a dump of the Ghidra `ram` block after
  `FillBatteryRam.java` — a simulation. Every copy matches ROM exactly and
  `ED1C`-`F17F` still holds the `21 01 00 C9` fill pattern. Read as ground
  truth it would license "zero, therefore free" for seven spans, four of them
  provably live.
  * But the related claim that the standalone `FillBatteryRam.java` over-copy
    is *visible* in that dump does **not** hold: `E22D`-`E238` reads
    `00 00 4F 4B 00 00 4E 4F 00 01 44 4D`, matching `ROM00:7301` exactly. The
    script bug is real; the dump does not show it.
* **Still unidentified, not invented:** `F68D`-`F77F`, `FD64`-`FD83`,
  `FE45`-`FE82`, `FFA9`-`FFFF`.

## Unbanked RAM: two of the four unknown spans identified (2026-09-02)

* **`FD64`-`FD83` CLOSED — slots 2-9 of a 10-slot countdown-timer table based
  at `ram:FD5C`**, stride 4, entry `{u16 ptr to a down-counter, u16 callback}`.
  Two independent walkers: `ROM00:2189` (`21 5C FD` / `0E 0A` = 10 slots /
  `11 03 00 19` after an `INC HL` = stride 4) and `ROM00:21BA`
  (`DD 21 5C FD`, four `DD 23`, `79 FE 0A`). `FD5C + 10*4 = FD84`, flush
  against the comms config table — the fit is exact. Swept from the RTC
  periodic interrupt (`ROM00:2214` latches Reg C to `FD4F`; `221F`
  `E6 40 / C4 4C 22`, Reg C bit 6 = `PF`).
* **`FE45`-`FE82` CLOSED — entries 2-63 of a 64-byte per-link frame-sequence
  table based at `ram:FE43`.** `ROM00:317B` `21 43 FE / 06 40 / 36 01 / 23 /
  10 FB` fills 64 entries with `01`; `ROM00:3192` computes
  `FE43 + (FDD4 & 3Fh)`; accessors at `31A1` / `31A6` / `31AB`; `ROM00:3084`
  compares against the received byte at `FDE7`. `FE43 + 64 = FE83`, flush
  against the device wire-id table — again exact.
* **Both were already solved elsewhere in this repo and never reached the
  map.** The `FD5C` timer table was recorded in this log on 2026-08-25 with
  Ghidra names applied, and `FE43h + (fdd4 & 3Fh)` has been CONFIRMED in
  `commstar-evidence.md` throughout. The map drew both row boundaries **two
  entries into** the structure — precisely the "base literal plus walked
  pointer" failure its own methodology note warns about. **Lesson: harvest
  existing documentation before deriving, and treat a region boundary that
  does not abut its neighbour as a smell.**
* **`F68D`-`F77F` (243 B) — OPEN, characterised.** Ruled out: any static
  reference (the only literal naming `F68D` is `ROM00:0308` `01 8D F6`, the
  *terminator* of `Kernel_KernelToRam`'s copy loop), any `SP`-fill, and any
  write through boot-to-Main-Menu or a synthetic Load/Run. **LIKELY** spare
  room in a round 1536-byte kernel arena: `F180 + 0x600 = F780` while the
  image is `0x50D`, and `ROM00:0318` re-enters the same copy loop with
  terminator `F235`, a second shorter install — so the arena is deliberately
  larger than its image. Next experiment: fill `F68D`-`F799` and read the
  stack low-water mark.
* **`FFA9`-`FFFF` (87 B) — OPEN, characterised.** Every surviving `FFxx`
  literal in either ROM is a small negative constant (`-1`, `-4`, `-8`, `-32`,
  `-48`, ...) feeding `ADD HL,rr`, not an address. Power-on `SP = FFFF` never
  pushes — `ROM00:014B` `F3 / 2A D0 FB / F9` is the first thing executed.
  Neither bounce buffer overruns into it (`FF7F`+`24h` -> `FFA2`;
  `FEFF`+`80h` -> `FF7E`). Next experiment: a disk-heavy workflow, not
  Commstar.
* **Methodological, and it matches what I hit independently:** a naive
  raw-opcode scan of these images yields roughly **50% false positives**.
  `ROM00:31CC` decodes as `LD SP,FE7E` mid-stream but is really
  `LD HL,31F2 / LD A,(HL)` — that artefact alone would have "identified"
  `FE45`-`FE82` as an SP-filled buffer. An alignment-consensus filter is
  required, and a scan that ignores instruction boundaries proves nothing.

## New reference page: memory and I/O map (2026-09-02)

`doc/reference/memory-map.md` is now the programmer-facing reference for the
memory and I/O contract, written for three jobs the owner named: Commstar
host work, a barcode decoder module, and OS function hooks that patch the
ROM. The evidence trail stays in `doc/re-notes/unbanked-ram-map.md`; the
reference page summarises and cross-links rather than duplicating.

**Merged two pages into one.** `doc/reference/memory-io.md` already existed
covering thin versions of the same ground, and the two had begun to
*disagree* — the old page called port `04h` an "output/power latch", which
the byte evidence contradicts. `memory-io.md` is retired, its ten inbound
links repointed, and a `redirect_maps` entry added so old URLs still resolve.

Established and byte-verified this pass:

* **Port `04h` is an active-low interrupt-enable mask, `05h` the matching
  active-low status.** `ROM00:22E9` = `3E 1F / F3 / ED 56 / 2F / 32 84 F7 /
  D3 04` — load `1Fh`, `DI`, `IM 1`, **`CPL`**, shadow to `ram:F784`, then
  `OUT (04h)`. `ROM00:230A` = `DB 05 / 32 85 F7 / 2F / E6 08` — read `05h`,
  snapshot to `ram:F785` (a shadow not previously listed), complement, test.
  This **corrects** the old page's "output/power latch" reading.
* **`RST 18h` is unusable.** The `RST 10h` dispatcher occupies `0010`-`001E`,
  fifteen bytes, so it runs straight through the `0018` slot: the byte there
  is `D7`, the high half of the `JP NZ,D74B` operand. An `RST 18h` executes
  that as a nested `RST 10h` and falls into garbage. Relevant to anyone
  looking for a spare restart vector to hook.
* **There is no heap.** No allocator-shaped routine exists; `ram:E3BD`
  (`g_pProgramLoadCeiling`) has one writer storing the constant `D081` and two
  readers, both in the loader and both subtracting — a fence, not a break.
  Every buffer in the firmware is at a literal address.
* **The shadow stack has a hard limit of 21 nested cross-bank calls** and no
  check; frame 22 overwrites the cursor at `ram:E36F` itself.
* **The `(0006)` trap:** two writers (`F180` at `ram:F456`, `D681` at
  `ram:D7BE`), neither of them the load ceiling. A CP/M program trusting
  `(0006)-1` believes it owns 1536 bytes it does not.
* **An uninstalled stub slot is not a stub.** The arena is seeded by smearing
  one template, and the template is `21 01 00 C9` — `LD HL,1 / RET`.
* **A BDOS handler is entered with bank 0 selected** (`ram:F382`-`F396`), so a
  patched handler in the banked window must be in bank 0 or above `8000`.
* **The firmware writes the unbanked rule into its own decode hook:**
  `ROM00:145B` `BIT 7,H` tests whether the hook address is `>= 8000` before
  deciding whether to route through the `FBC0` stub.
* **`ROM01` performs essentially no port I/O** — its only genuine access is
  `OUT (47h),A` at `ROM01:0042`. Four apparent I/O sites in the database
  (`ROM01:0D07`, `ROM01:0F00`, `ROM00:6FFD`, `ROM00:7021`) are misalignment
  artefacts, not instructions.
* **New port `33h`**, read once at `ROM00:1ED9`, alignment sound, containing
  stub unreferenced. Left **unknown** with candidates listed and no pick.
* **`48h` is a 2-bit output echoed in `49h` bits 0-1** (`ROM00:24F2`-`251B`).
  All its call sites are IR/link diagnostics, so the existing `LCD_STROBE`
  label is **not supported**; flagged rather than renamed.

**PARTLY CLOSED (2026-09-06):** every output latch's bit usage is now
tabulated in `reference/memory-map.md#latch-bit-usage`, exhaustively, by
matching the shadow read-modify-write idiom across ROM00. Port `2Ch` gets its
own table at `#port-2ch-bits`: bit 5 IR port select CONFIRMED, bit 4 backlight
LIKELY, bits 0/1 external-port strobe and read-enable with their mechanisms
CONFIRMED and their loads OPEN, bits 2/3/6/7 never written. Also settled:
`LINK_CTRL` bits 2 and 3 are the only bits on that latch no instruction ever
writes; `CTRL_07` is a two-bit output; `02h` bit 6 is a power-down wake-scan
mode flag (`ROM00:175E`). **Still OPEN:** port `33h`'s identity, and what the
`2Ah` bits and `CTRL_07`'s two bits actually drive, which need
hardware. Whether banks 2+ map to specific SRAM pages is LIKELY, not shown.

## Unbanked RAM: the last two spans, and a memory write-watch (2026-09-02)

* **New harness instruments, documented in `--help` and `analysis/README.md`:**
  `--watch-mem LO:HI[,...]` (inclusive ranges; hooks the CPU write callback so
  it catches `PUSH` and `LDIR` as well as `LD (nn),r`; reports address, value,
  PC, SP and bank; per-range print cap via `--watch-mem-limit`, counting
  uncapped; exit summary of write count, distinct writing PCs and address
  extent) and `--fill-mem LO:HI[,...]` / `--fill-mem-value NN` (seeds a marker
  pattern at the point the destructive power-on RAM test finishes, and reports
  survival plus lowest/highest changed byte).
  * Two calibrations worth keeping: `mach.pc` inside a write callback is the
    address of the instruction **after** the writer, and `PUSH` does go through
    the callback — which is what makes a watch below a stack top a valid depth
    measurement. Positive control: `--watch-mem f780:f799` over a plain boot
    gives **61,923 writes from 33 PCs**.
* **`F68D`-`F77F` and `FFA9`-`FFFF`: unwritten across every workload we can
  drive.** Five workloads, both spans watched: cold boot to Main Menu and
  Display Status; Load/Run PLINTH download; Commstar record upload; Commstar
  program download; and a **BDOS file/disk workload** (~70 calls through the
  `0005` gate — `C3 80 F1`, verified — covering reset, select, DMA both
  banked and unbanked, search-first/next, delete, make, write-seq, open,
  read-seq, random read/write, file-size, close). **Zero writes into either
  span in all five.** Tagged CONFIRMED for those workloads, OPEN for anything
  outside them.
  * The disk workload is the discriminating test the map nominated for
    `FFA9`-`FFFF`, and it landed: **15,851 writes into `F8B8`-`F937`** and
    **6,391 into `FEFF`-`FFA8`** (169 of 170 addresses, 35 PCs) — the bounce
    buffers were exercised hard and **did not** overrun into `FFA9`.
  * **Not covered, and stated as such:** barcode capture, the EXT STORAGE
    ADAPTER drives, a real V24 peer, alarm/sleep-wake, and any non-harness
    application — plus the standing 61%/37% disassembly bound.
* **The system stack never gets near `F68D`.** `--fill-mem f68d:f819` (safe
  because the seed point coincides with `ROM00:01D4` `31 1A F8` resetting `SP`)
  gives an identical low-water mark of **`F7EA`** in all five workloads: the
  stack peaks 48 bytes deep, leaves 80 of its 128 bytes unused, and stops
  **107 bytes short of `F77F`**. So "stack headroom" does not explain the span
  either. The deepest frame's two lowest words are `31C5` / `2346`, both
  boot-time link bring-up.
* **The kernel-arena hypothesis is DISPROVEN, not LIKELY.** `ROM00:02FE` is
  `11 B5 00 21 E8 35 19 11 80 F1 01 8D F6 7E 12 23 13 7B B9 20 F8 7A B8 20 F4
  C9` — the copy loop terminates on `DE == BC == F68D`, an **address**, so the
  `0x50D` length is derived from `F68D` rather than the other way round, and
  `0x600` appears nowhere.
  * `ROM00:0318` also is not a "second shorter kernel": it installs a
    **different image**, `35E8`-`369C` (`0xB5` bytes), a bank-switching helper
    set — `ROM00:35E8` begins `D3 47`, `OUT (47h),A`, the bank-select port.
    `ROM00:01ED` (`CD 18 03`) installs the helpers early in cold boot, because
    RAM sizing needs bank switching before a kernel exists; `ROM00:023E`
    (`CD FE 02`) installs the full kernel later, just before the warm-boot
    entry at `024D` that `ROM00:01A3` (`CA 4D 02`) jumps to. Neither image
    reaches `F68D`.
* **Barcode could not be driven**, and that is a harness limit, not a firmware
  one: `boot_hw.py`'s input callback returns a constant `FFh` for unmodelled
  ports including `EXTBUS_EDGE` (`2Dh`), so the edge loops at `ROM00:13CB` /
  `13ED` never see a transition. Driving it needs a wand model feeding timed
  `2Dh` transitions. Static bound recorded instead: the capture pushes from
  `SP = FBB5` with a single-byte counter capped at `ROM00:140F` (`FE 80`), so
  at worst 256 pushes fill exactly `F9B5`-`FBB4` and neither span is reachable.

## Resident code: the install API, and DIP destinations verified (2026-09-02)

* **The decode-hook install call is BIOS jump-table entry 24, not a BDOS
  function.** Reachable portably as `CALL (0001h)+45h` -> `ram:F27D` ->
  `ROM00:1587`. `ROM00:0100`-`014A` is a 25-entry CP/M-style BIOS jump table
  mirrored in unbanked RAM at `ram:F235`-`F27F`; entries 0-16 are stock CP/M
  2.2, 17-24 are DIPOS-B extensions.
* **It takes TWO arguments and the docs stopped four instructions early.**
  Byte-verified `ROM00:1587`-`159F` =
  `ED 53 C2 FB / 3A FE FE / 32 C1 FB / 3E D7 / 32 C0 FB / 29 x6 / 22 B0 F9 / C9`:
  * `DE` = hook address -> `ram:FBC2`
  * caller's bank (from `ram:FEFE`) -> `ram:FBC1`
  * `D7` -> `ram:FBC0`, making the socket a four-byte `RST 10h` thunk
  * **`HL` = re-arm budget -> `ram:F9B0`, shifted left six times (x64)**
  A caller that sets only `DE` silently writes garbage into the budget.
* **`BIT 7,H` at `ROM00:145B` is a fast path, not a gate on banked hooks.**
  Byte-verified `ROM00:1450`-`146E`: both branches converge on
  `LD HL,FBC0 / JP (HL)`; the direct jump is taken only for a hook at
  `>= 8000h` **whose first byte is already `D7`**. So `FBC1` matters for
  essentially every hook, and a banked hook is fully supported.
* **The hook is entered with ONE stack word**, `[SP+2] = 0FBB9h` — the address
  of the parameter block, not registers. `FBB9`/`FBBA` = width-table pointer
  (init `F9B5`), `FBBB` = element count. Zero `FBBB` to reject and re-arm;
  that is the entire body of the ROM's discard hook at `ROM00:1567`.
* **The socket survives program exit, warm boot and power cycling.**
  `FBC1`/`FBC2` have exactly two writers in the whole firmware, both
  installers. It is reset only by a cold start.
* **CONFIRMED by experiment: a DIP type-0 block honours a destination in
  unbanked RAM.** The acceptance rule is `destAddr + count <= (ram:E3BD)`
  = `D081h` (`ROM01:0E9C`-`0EA7`), which permits `8000`-`D080`. A two-block
  DIP targeting `C000` placed its 32-byte payload exactly there — verified
  with `--fill-mem c000:c03f --dump-mem c000:64`: the seeded markers are
  overwritten for exactly 32 bytes and survive from `C020` on, so the copy is
  precisely placed with no overrun, and the load reported success rather than
  error 9002. This was checked *before* the documentation promised it.
* **A COM can do the same with a run-time copy loop** — unbanked RAM is mapped
  throughout, so `LD HL,payload / LD DE,0C000h / LDIR` reaches it. DIP versus
  COM is a tooling and timing choice, not a capability one; both are now
  documented in `program-formats.md`. Neither can write the socket at
  `FBC0`-`FBC3` from a block, since that is above the ceiling — running code
  must do it.
* **CORRECTION to `doc/reference/memory-map.md`:** it said the kernel recopy
  `ROM00:02FE` runs "on every boot" and concluded a BDOS-table patch never
  survives a reset. Wrong on both counts. `CALL 02FE` has **exactly one call
  site**, `ROM00:023E`, inside `ColdStartSelfTestBanner` *after* the warm entry
  at `024D`; and `ROM00:01A3` `JP Z,024Dh` skips `01A6`-`024C` whenever
  `ram:F81C` holds `55h`, so the RAM test at `01BB` is not unconditional
  either. A `F1EB`/`F1D1` patch persists across warm boot and power cycle,
  exactly like the barcode hook.
* **`ram:ECD8`, the program bank base, has one writer** (`ROM01:0A98`, from a
  storage-geometry byte) and there is **no allocator, bitmap or free list** —
  every Load/Run reuses the same bank. That is why a hook pointing into a
  program bank is unsafe even though the call mechanism supports it.
  Note `boot_hw.py` writes `ECD8` itself, so "programs run in bank 2" is a
  harness convention, not an observed device behaviour. **OPEN:** read `ECD8`
  after a genuine device-path load.

## Barcode: wand model, measured hook contract, working Code 39 decoder (2026-09-02)

* **The capture path can now be driven.** `analysis/boot_hw.py` models the
  wand on port `2Dh` (`--barcode-scan`, `--barcode-widths`,
  `--barcode-decode`, `--barcode-bdos`, `--barcode-expect`); new modules
  `analysis/micronic/z80asm.py` (a two-pass Z80 assembler, so injected
  payloads live as readable source) and `analysis/micronic/barcode.py` (wand,
  Code 39 encoder, Python reference decoder, the Z80 decode hook, a hook
  probe). `analysis/test_barcode.py` has 24 tests, all passing including the
  5 emulator-gated ones.
* **Capture mechanics, CONFIRMED (`ROM00:13BB`-`1441`):** arm waits for port
  `2Dh` **bit 0 = 1**; **widths are counts of port polls, not time** (each
  element pre-increments at `13E8`, so N samples records as N+1; ~14.9 us per
  count at 3.6864 MHz); minimum element 8 (`13FA`), maximum `1800h` ends
  the capture without recording the final element (`13DF`/`13EA`); 128-element
  cap at `140F`.
  * **The 128 cap is geometric**: the table is `PUSH`ed down from `FBB3` and
    reverse-copied head-to-tail to `F9B5`, and 128 x 2 bytes is exactly where
    source and destination meet.
  * **CORRECTION to a Ghidra comment:** the EOL at `ROM00:13FA` says "first
    element < 8 loops". The test is in the per-element path and applies to
    **every** element.
* **FIRMWARE BUG: the hook is handed an uncapped element count.**
  `ROM00:1409` stores the raw count in `ram:F9B4`; the cap at `140F` applies
  only to the copy loop; `1446` reads the raw value back and `1449` gives it
  to the hook. Fed 140 elements, the hook's block reads count 140 while only
  128 entries exist. **A decoder must clamp.** The shipped Code 39 decoder
  rejects counts above 128.
* **Hook contract, measured rather than inferred:**
  * Socket `ram:FBC0` is a four-byte `RST 10h` thunk — `FBC0` = `D7`,
    `FBC1` = bank, `FBC2`/`FBC3` = address. Not a single pointer cell.
  * Entered with **one stack argument**: `[SP+0]` return, `[SP+2]` = `FBB9`.
    Identical same-bank and cross-bank; `HL` is not a parameter. Interrupts
    off, `FBC1`'s bank paged in, every register but `SP` free to clobber.
  * Parameter block: `FBB9`/`FBBA` = width-table pointer, **`FBBB`/`FBBC` =
    a 16-bit count**. `ROM00:147E` reads it with `LD BC,(FBBB)` as an `LDIR`
    length — so the reference page's "status byte" at `FBBC` was wrong and
    would have copied 256 extra bytes per unit.
  * Return: repoint `FBB9`, set the count, `RET`. **Count 0 = reject and
    re-arm.** **Do not write `ram:FBB5`** — a nonzero value there suppresses
    the completion event and hangs a blocked `BDOS 03h`.
  * **Delivery capacity is 26 bytes** (`F95E`-`F977`); the `LDIR` at
    `ROM00:148B` is unbounded, so more overruns the device-table pointer.
  * `BIT 7,H` at `145B` is a **fast path, not a gate** — both branches reach
    the hook; the direct jump needs the hook at `>= 8000h` *and* starting
    with `D7`.
* **`BDOS 03h` framing CONFIRMED by execution:** `1Bh`, count, bytes. A
  driven Code 39 `A1` scan returns `1B 02 41 31`.
* **A working Code 39 decode hook** (494 bytes assembled) thresholds each
  character at the midpoint of its own nine widths, so it needs no absolute
  calibration; validates `count = 10k-1` and the `*` delimiters. Driven end
  to end: wand -> firmware capture -> hook -> `BDOS 03h` -> `A1`.
* **UPC/EAN is feasible on this hook** — 59 elements fits the 128 cap, the
  arm and terminator behave, 13 digits fits the envelope. The cost is decoder
  complexity (delta decoding against a guard-bar module estimate, four-way
  element classification, parity tables), plus the loss of Code 39's
  self-checking property.
* **CORRECTION to `AGENTS.md`:** its restart-vector list said "`0008` ->
  `JP F180` (BDOS), `0010` -> `JP F5E1`". The bytes: `0005: C3 80 F1`
  (the CP/M BDOS gate), `0008: C3 E1 F5`, and **`0010` is not a jump at all**
  — the dispatcher is coded inline, which is also why `RST 18h` is unusable.
  The stale `doc/internals/memory-map.md` path in that bullet is fixed too.
 * **`analysis/test_barcode.py` imported `z80` at module level**, so it could
   not be collected by the system interpreter (which has pytest but not `z80`)
   nor run by the venv (which has `z80` but not pytest). The import is now
   guarded and the CPU-level test class skips without it, so the suite behaves
   like the others under both.
- 2026-09-02 (owner hardware keyboard test; docs updated):
  * CONFIRMED by owner observation: YES/NO move form focus forward/back;
    YES on the final field beeps. Shift selects the underline-cursor
    punctuation/numeric page; Sun is one-shot and Sun+F/J/N gives X/Y/Z.
    Shift+N is the byte-verified 0xDB code and beeps in Load/Run `From`.
  * The old conclusion that the located `ROM01:1f96` dispatcher explained
    all `From` input is discarded. The owner observes unshifted N advancing
    `From` in block-cursor mode, but 1f96 has no 0x4E case. This is an OPEN,
    mode-dependent path or translation question; no function names or
    dispatcher interpretation were changed.
- 2026-09-02 (keyboard-page and Load/Run editor review):
  * RESOLVED the dispatch confusion. Load/Run `From` uses the generic editor
    continuation at ROM01:2f75-34aa, not the `1f96` five-byte choice-object
    dispatcher. Page 0 N=0x4E takes its printable path; page 1 Shift+N=0xDB
    matches the enumerate/change path and advances `PLINTH -> V24 ADAPTOR`.
    Sun+N=0x5A is page 2's one-shot Z. `Lib_Eq16` returns one with Z clear on
    equality, so 0xDB falls through the `JP Z` at 3235; the earlier branch
    reading was reversed and is discarded.
  * Owner observed the visible cursor change underline -> block on entry to
    a list field. LIKELY this is coupled to page 1; it is not a proof because
    page 2 overrides the same scanner state. User guide now carries three
    physical-key grids and distinguishes Shift from one-shot Sun. Open only:
    capture the actual keyboard-ring byte with FBDC/FBDD to prove the visual
    cursor/page relation.
- 2026-09-02 (input-mode chain and physical IR selection):
  * CONFIRMED the field transition behind the owner-observed underline ->
    block: text mode emits ESC A -> ROM00:1e9f -> fbdc=0/page 0/HD61830
    cursor blink; list mode emits ESC B -> 1ea8 -> fbdc=1/page 1/character
    blink. The editor sends ESC A/B via boot-installed EEF0->6772->F13C->
    71E2 thunks. This closes the cursor/page question; Sun page 2 is still a
    one-key override.
  * CONFIRMED by owner hardware observation: initiating Load/Run PLINTH
    flashes the back/base IR port; V24 ADAPTOR flashes the top port. This
    proves UI-to-physical-connector routing only, not Link_PortSelect bit-5
    polarity; retain that separate hardware question.
- 2026-09-02 (terminal escape table): documented the 17 byte-verified ESC
  second-byte commands at ROM00:2050 and corrected its handler-table base to
  ROM00:2062. ESC A/B/S/R carry the text/list input-mode path; X/Y/H/U retain
  mechanical descriptions until their parser-state/display meanings are
  traced.
- 2026-09-02 (physical IR TX capture): added `analysis/decode_ir_scope.py`, a
  streaming Keysight segmented-CSV decoder. The owner V24 no-peer capture has
  50 segments and exactly three rising-edge-sampled CH2 patterns: 17-bit
  `10000001000001011` (16), 21-bit `000010000001000001011` (15), and 22-bit
  `0000110000001000001011` (19), at 121.993-us median clock period. This is
  raw physical evidence only: framing/order/polarity and queue correspondence
  remain open until a return-path capture exists.
- 2026-09-02 (physical IR repeat analysis): added
  `analysis/correlate_ir_scope.py`. The active CSV segments have a 90.605-ms
  median timestamp gap; owner correction below establishes continuous 0-V
  levels in that interval, with no CH1 clock edges. Their family order has
  repeated `BC` (13), `CB` (12), and `CBC` (10) runs. The first eight sampled
  bits are A=`10000001`, B=`00001000`, C=`00001100`; conditional MSB-first
  values are 0x81/0x08/0x0C. Superseded below: the 0x81/0x0C substring matches
  are not byte-boundary evidence.
- 2026-09-02 (IR polarity and HDLC test): inverted, right-aligned A/B/C share
  `01111110111110100`; `01111110` is at the same aligned offset and the tail
  is `111110100`. This is LIKELY an HDLC-style delimiter only, because the
  tail has HDLC-compatible five-one/zero stuffing. Full HDLC is SUSPECTED:
  there is no closing flag, variable payload, or FCS in these 50 fixed bursts.
  Resolve with a variable transfer capture and a verified unstuffed FCS.
- 2026-09-02 (owner correction, inverted HDLC alignment): timestamp gaps are
  continuous 0-V/no-clock intervals, not absent acquisition time. More
  importantly, raw `10000001 000001011` is an inverted `0x7E` flag followed
  by five raw zeroes and a stuffed raw one; removing that one gives
  `00000011` = the known `0x03` Link_BlockTx prelude. This supersedes the
  earlier speculative 0x81=LINK_CMD and C-prefix=0x0C matches. Full HDLC is
  still SUSPECTED until a closing flag and FCS are observed.
- 2026-09-02 (no-peer physical boundary): reconstructed B's omitted clock cell
  from its 244-us gap; A/B/C all de-stuff to raw `0x03`. Static callers show
  every transmit funnels through Link_TransferService, so later Load/Run fields
  cannot expose byte 0x0C while the physical exchange stops after 0x03. Open:
  determine the minimal optical acknowledgement that makes the link hardware
  release the next byte; capture `LINK_TXD` and IR together if possible.

## IR link exerciser review (2026-09-06; burn image superseded)

The `1CBD` image and hash in this historical entry were **SUPERSEDED** by the
pre-burn audit below. Its `1225` successor has since failed its first physical
run and is also retired; see the later hardware-result entry.

* **Replacement ROM00 reviewed and rebuilt as wire format v13.** The burnable
  image is `analysis/rom_exerciser/micron1_exerciser.bin`, 32768 bytes,
  sum16 `1CBD`; stock `micron1.bin` remains sum16 `ACF8`, and ROM01 is
  untouched. The guarded build reports 703 changed bytes and 22 bytes free
  across the six filler regions.
* **SHOWSTOPPER FIX — interrupt source attribution is now direct.** The v12
  plan inferred that an `IRQN` increment with `KEY=FFh` came from the link.
  That is invalid because `KEY` is sampled only once near the start of a
  record; a keypad edge can occur later. The ISR now reads active-low port
  `05h`, complements and ORs it into wire-only `ISRC`: bit 0 is keypad, bit 2
  is link. Records are 11 bytes:
  `{COUNT,OR,AND,RXD,SIDE,CTRL,WD,KEY,IRQN,ISTAT,ISRC}`.
* **SHOWSTOPPER FIX — the keypad positive control is actually armed.** Merely
  writing IRQ mask `FAh` did not reproduce the paired sleep configuration.
  After every scan the exerciser now writes `48h` to `ram:F782` and port
  `02h`, matching `ROM00:1766`-`177F`. This selects column 3; N, ENTER and YES
  are known positive-control keys.
* **SHOWSTOPPER FIX — both ports now receive all 128 effective CTRL states.**
  Alternating the port with the raw sweep counter correlated one port with odd
  values and the other with even values, so each could cover only 64 states.
  `RLCA` now moves that parity bit into forced port-select bit 1 first. A
  regression test proves 128 distinct states on each port.
* **Safety fix:** the RAM target of the NMI vector receives `RETN` (`ED 45`),
  not `RET`, and is installed before LCD initialisation. This restores IFF1
  correctly if a stray NMI occurs.
* **CORRECTION — wire-ID bit 5 set was not the top-port state.** The September 6
  `63h` claim equated `Session_TxBlock4`'s first stack argument at
  `ROM00:5C04` with the unrelated two-option string table index at
  `ROM01:7663`; no xref supports that correlation. Fresh PLINTH and V24
  Load/Run runs both reach `Link_PortSelect` with `fdd4=43h`: wire-ID bit 5 is
  clear, while `LINK_CTRL` bit 1 and port `2Ch` bit 5 are set. The V24 run
  enters its distinct Log-on form and emits distinct application data, so the
  UI choice was genuine. Combined with the owner's capture of that operation
  at the top V24 window, **wire-ID bit 5 clear is CONFIRMED top**. Wire-ID bit
  5 set clears both output bits and is LIKELY back by two-port elimination; it
  remains a direct exerciser observation. The harness now
  logs and regression-tests `FDD4/CTRL.b1/2C.b5` for both UI routes.
* **Documentation/Ghidra clarity pass:** the canonical mapping now separates
  all three signals explicitly: `fdd4=43h` means wire-ID bit 5 clear, which
  forces `LINK_CTRL` bit 1 set and port `2Ch` bit 5 set. It also records the
  selection-time values (`02h`/`20h`), active baseline (`03h`), and inverse
  `63h` row (`00h`/`00h`, active baseline `01h`). Matching comments were
  saved in Ghidra; function count remained 1101.
* **Durable notation rule:** `AGENTS.md` now requires every bit statement to
  identify its owning value whenever more than one register, port, RAM cell,
  or wire byte is in scope. Compact wording remains allowed after one owner
  is unambiguous. `CLAUDE.md` is a relative symlink to `AGENTS.md`, making the
  neutral file the single authoritative instruction source without drift.
* **Validation:** guarded rebuild reproduced sum16 `1CBD`; 88 tests passed,
  33 emulator-dependent cases skipped, and 5 subtests passed. A bounded
  30,000-slice emulator run reached the controller, emitted preamble
  `A5 5A 0D 80 80`, streamed 11-byte records, and repeatedly wrote the
  keypad arm value `48h`. The harness does not assert a link INT for this
  dedicated ROM, so direct `ISRC` behavior remains a hardware test. Two
  targeted emulator integration tests also passed for the PLINTH and V24 UI
  routes with the new port-select tuple assertions. The rebuilt image SHA-256
  is `01bd49402645b78413fecc07af31c47ed097ca2379bdff74920857b37157696a`.
* **SUPERSEDED hardware sequence — do not execute:** (1) read and `cmp` both fitted ROMs; (2) burn
  and label `1CBD`; (3) run the pin walk; (4) capture at least 60 seconds in
  `LISTEN_ONLY`, pressing N/ENTER/YES until `ISRC` bit 0 proves the IRQ path;
  (5) read `ISRC` bit 2, phase-1 `HSBUSY`, phase-2 `RX byte`/`RXD`, and
  watchdog count in that order; (6) repeat the same geometry with the
   `conn3`-`conn13` stimuli; (7) preserve the raw capture, decoder output, and
   a photo/video of the LCD. Only after that first result should the fixed
   phases be replaced by a keypad-steered follow-up ROM.

## Physical-capture audit and state-0000 exchange (2026-09-07)

* Replayed the available Keysight files with `analysis/scope_ir_decode.py`.
  The 50-segment CSV yields exactly the documented three burst forms; every
  form decodes under the current model to delimiter `81h` plus prelude `03h`
  at a 122.07 us cell. The single-segment H5 reproduces CSV segment 0. Capture
  SHA-256 values are now recorded in `re-notes/ir-wire-protocol.md`.
* Raw `conn3`-`conn13` captures were not in the repository archive inspected
  during this pass. This availability note is superseded by the later raw
  capture audit below.
* Fixed the consolidated Arduino sketch's mode selection: `PULSE_TEST` and
  `LADDER_TEST` were both enabled, and the preprocessor silently selected the
  ladder. The default now selects only `LADDER_TEST`; invalid combinations
  fail preprocessing, and `ADDR_SWEEP` explicitly requires `PULSE_TEST`.
* **CONFIRMED:** the calls at `ROM00:5C1F` and `ROM00:5D05` are not an unknown
  out-of-band preflight. They call `Session_TxFrameAndRx`, which performs the
  state-`0000` control exchange. The ordinary type-2/type-3/type-4 exchange
  satisfies it, and the bounded program-download regression passed with the
  request sequence beginning `0000`, `0006`, `0062`, `0064`, `0045`.
  Ghidra now carries the function plate and call-site EOL comments; the
  program was saved with the function count unchanged at 1101.

## Completion-relative receive arm and emulator clock fix (2026-09-07)

* **SHOWSTOPPER FIX:** `analysis/boot_hw.py` still advanced its RTC using
  `CPU_HZ=3,579,545` after the owner corrected the hardware clock to
  3.6864 MHz. The emulator constant, `micronic_notes.md`, and the durable
  repository instructions now agree on 3.6864 MHz.
* Added `--synthetic-loadrun-arm-delay-us`. In this mode the peer decides when
  to send each receive-first state-44 object solely from elapsed emulated CPU
  ticks after it supplies the preceding type-4 completion. It does not inspect
  `PC`, `FDD5`, `FDDC`, callback pointers, or descriptor pointers to make that
  decision.
* **CONFIRMED in bounded emulation:** a nominal 275 ms delay (actual 275.223 ms)
  loses the receive-first object; nominal 300 ms succeeds at both boundaries
  (actual 300.070 and 300.690 ms) and reaches loader state 3. The regression
  uses 500 ms and passes with 1700-, 3400-, and 6800-tick slices. This closes
  the PLINTH DIP path, V24 mode-1 DIP path, and a 200-byte two-chunk COM path.
  RAM/PC visibility is therefore no longer an emulator-server requirement.
  The corresponding physical-wire epoch, maximum acceptance delay, and
  hardware reliability are still OPEN.

## Raw conn3-conn13 capture audit (2026-09-07)

* Located all eleven packed-digital Keysight CSVs in the owner's external
  `$HOME/micronic-scope-traces` archive. They contain exactly 3,877 complete
  1,893-sample segments. SHA-256 values and per-run decoded contents are now
  recorded in `re-notes/ir-wire-protocol.md`; the large captures remain
  outside git.
* Added `analysis/scope_ir_experiments.py`, which streams each CSV and
  classifies the waveform actually captured instead of reconstructing Arduino
  sweep state from segment numbers. **CONFIRMED from the raw masks:** scope D0
  and scope D1 are handheld data and clock; scope D2 and scope D3 are Arduino
  clock and data. These are scope pod channels, not Arduino pin numbers.
* **CONFIRMED, conn13:** among valid adjacent-cadence pairs, a burst-gated
  response whose scope-D3 data emission ends 3.03-6.01 ms after the handheld
  clock ends produces the +15.6 ms retry extension 163/163 times. Late or
  capture-censored responses produce it 0/243 times; silent controls produce
  it 0/76 times. This is consistent with the firmware's 9.92 ms
  `LINK_STATUS` bit-6 (`HSBUSY`) timeout at `ROM00:32F3`.
* **CORRECTION:** the conn13 cutoff is not a universal final-light-off rule.
  In conn11 every valid observation for decoded addresses `00h`-`3Fh` and
  `7Fh` reacts, including 62 whose scope-D3 data emission ends after 9.92 ms;
  `FFh` reacts 0/2 times. In conn12 all frame-bearing free-running- and
  gated-clock groups react, including 78 late endings, while clock-only and
  silent controls react 1/80 and 0/80 respectively. Preamble/clock state
  therefore affects entry into an additional controller/firmware path. No
  tested stimulus produces a post-handshake payload.
* **SUPERSEDED below:** conn13's 93.748 and 109.371 ms population medians were
  initially described as 96 and 112 periods of a 1,024 Hz running RTC. Fresh
  call-order analysis shows that 1,024 Hz is confined to the clock self-test;
  `RTC_Init` subsequently leaves the post-boot RTC at 64 Hz.
* Unit tests cover scope-channel ownership and stuffed address recovery. The
  exact Arduino source snapshot used for each early capture remains OPEN;
  decoded waveform classifications do not depend on it.
* Planned a no-EPROM discriminator: capture stock-ROM Z80 I/O reads of
  `LINK_STATUS` while replaying conn13 silent/early/late stimuli. This directly
  observes `LINK_STATUS` bits 4, 6, and 7 and separates receive dispatch, the
  bit-6 acknowledge wait, and the first-byte bit-7 wait. Matching OPEN
  bookmarks were saved at `ROM00:32F3` and `ROM00:3318`; `Link_BlockTx`'s plate
  now qualifies every bit with its owning register.

## Retry scheduler cadence correction (2026-09-07)

* **CORRECTION, CONFIRMED:** cold boot calls `Clock_SelftestTickWindow` at
  `ROM00:0208`, where `RTC_PeriphRegSetup` writes RTC Register A = `26h`
  (1,024 Hz), then calls `RTC_Init` at `ROM00:024A`. Its
  `RTC_SetTimeFromBlock` call leaves RTC Register A = `2Ah` (64 Hz). A bounded
  300,000-slice emulator boot reached the banner and reported
  `RTC rate =64.0 Hz (RS=0xa)`.
* The conn13 medians therefore match **six and seven 64 Hz periods**, not 96
  and 112 1,024 Hz ticks. `Link_TransferService` copies its configured delay
  of six into the retry countdown and registers itself with
  `Comms_WorkItemRegister`; `RTC_WakeReasonFetch` invokes
  `Comms_WorkItemSweep` once per observed RTC Register C PF event.
* **LIKELY mechanism:** the common interrupt worker keeps maskable interrupts
  disabled while callbacks execute, and RTC Register C PF is latched rather
  than counted. `analysis/link_retry_cadence.py` executes the real service and
  sweep routines under that rule. A `LINK_STATUS` bit-6 timeout takes 11.43 ms
  and produces a steady 93.750 ms retry. Clearing `LINK_STATUS` bit 6 and then
  holding `LINK_STATUS` bit 7 clear at the first payload byte takes 26.27 ms
  plus the acknowledge delay; a 6 ms delay crosses two RTC boundaries and
  reproduces the 109.375 ms retry.
* The cadence remains non-unique evidence. A `LINK_STATUS` bit-4-driven
  receive dispatch can also occupy the interrupt worker. The planned
  stock-ROM bus capture remains the discriminating experiment for
  `LINK_STATUS` bits 4, 6, and 7.
* **Scheduler annotation correction:** `Comms_WorkItemDispatch` does not
  continue at `ROM00:2268` after an expiry. Its `POP HL; RET` at
  `ROM00:2289` discards that return address and returns directly to the sweep
  caller, so the first expired slot ends the current pass. The Ghidra plates
  for register, sweep, and dispatch now record the exact slot structure and
  control flow.
* **Physical-priority correction (owner-supplied):** attaching a logic
  analyser to the Z80 bus is harder than programming the socketed ROM. The
  prepared v13 replacement-ROM exerciser is now the next physical task;
  stock-ROM bus capture is retained only as a fallback.

## Replacement-ROM pre-burn audit (2026-09-07)

* **SHOWSTOPPER FIX — HD61830 cursor-page carry:** the previous v13
  `lcd_at` helper rewrote cursor-address low register R10 without following it
  with cursor-address high register R11. The Hitachi HD61830 datasheet Table 2
  requires R11 to be rewritten after R10 because an R10 bit-7 transition from
  set to clear can increment R11. After the 160-cell clear, the first live
  record could therefore land in display-RAM page 1 and leave the visible row
  blank. `lcd_home` now writes `R10=00h` then `R11=00h`, byte-for-byte matching
  `ROM00:1F91`-`1F9E`.
* **The failed image's LCD initialization used the stock routine.** The
  hand-maintained register table and clear loop were removed.
  `power_lcd_init` writes
  `CTL_LATCH_2A=20h`, waits within one percent of the stock
  `ROM00:0152`-`015D` reset loop's Z80 cycle count, sets the contrast shadow to
  `40h`, and tail-calls the complete stock `Lcd_Init` at `ROM00:1EEC`. This is
  the minimum byte-proven path: the stock special-boot route also reaches
  `Lcd_Init` after that latch state and reset delay.
* **Stack collision margin increased.** A bounded run of the old image found
  a deepest stack write at `C7F6h`, only nine bytes above the last exerciser
  state byte at `C7EDh`; an interrupt there had only two bytes of remaining
  margin. The stack now starts at `C900h`, 275 bytes above that state byte,
  within the documented free upper TPA.
* **Burn image supersedes the September 6 fingerprint:** guarded build is
  32768 bytes, 674 bytes differ from stock, 54 filler bytes remain, sum16 is
  `1225`, and SHA-256 is
  `9162097f6ca6bf56674d6cdcd2d3bcb25050902efc813d4eba3dcee3b019ffeb`.
  The old `1CBD` image and hash in the historical entry above must not be
  burned.
* **Validation:** six dedicated exerciser tests now lock the image fingerprint,
  stock `Lcd_Init` entry bytes and HD61830 command sequence, R10-then-R11 home
  sequence, region bounds, stack separation and CTRL sweep. The full
  `analysis/` suite passes: 95 passed, 33 emulator-dependent tests skipped and
  71 subtests passed. A bounded 30,000-slice run logged the complete stock LCD
  sequence, 160-space clear, contrast `40h`, ASCII top row
  `00808000FF0300FF0000`, preamble `A5 5A 0D 80 80`, and 3,154 decoded records
  with no counter discontinuity or watchdog trip. The final partial record is
  the intentional slice-limit stop. The repository-wide suite additionally
  collected 105 passing tests but its 102 barcode build cases could not start
  because this sandbox cannot run their `sudo docker` assembler command; that
  is unrelated to the exerciser.
* **Ghidra saved:** `Lcd_sync_status` now records the R10/R11 low-then-high
  requirement, and reset at `ROM00:0152` records the latch plus delay contract.

## Replacement-ROM first hardware result (2026-09-07)

* **FAILED; discard the flash-ready conclusion.** Owner-supplied result from
  the physical `1225` ROM00 image: constant buzz and uniformly black screen;
  programmer read-back verified the burn. Whether the Arduino received the
  v13 preamble or records remains an OPEN discriminator.
* **CONFIRMED omitted cold-start sequence:** unlike the normal ROM path, the
  `1225` image did not read `IRQ_STATUS`, write `IRQ_MASK=FFh`, or write
  `SOUND=00h` before `Lcd_Init`. The stock bytes do exactly those operations at
  `ROM00:01B1`-`01B9`, immediately before the normal cold path reaches
  `Lcd_Init` at `ROM00:01E1`. The emulator does not model the beeper and did not
  expose the omission. `SOUND=00h` is independently byte-confirmed as the
  `Sound_Off` operation at `ROM00:35C9`-`35CD`.
* **LIKELY causal split, pending hardware retest:** leaving `SOUND` at its
  power-on state explains the constant buzz. Whether the missing
  `IRQ_MASK=FFh` write also gates or resets LCD hardware is not established;
  port `04h` is confirmed as the active-low interrupt mask but has other latch
  manipulation in the ROM. The corrected candidate reproduces the full
  `IRQ_STATUS`/`IRQ_MASK`/`SOUND` quiesce sequence before the unchanged stock
  LCD call. After the owner confirmed a verified burn and a uniformly black
  panel, the candidate was made self-calibrating: it starts port `46h` at
  `00h`, then physical YES/NO tail-call the stock byte-adjustment routines once
  per 64-record frame. The same adjustment remains live in the `DEAD` loop and
  pin-walk mode, so calibration does not depend on a successful link opening.
  The guarded candidate is 32768 bytes, differs from stock in 713 bytes, has
  sum16 `2692`, and SHA-256
  `cf2474dbd4be30a04998382f8e9946522cb2f87f91a7b516f40ff3119ae04c65`.
  These identify the replacement burn artifact; the retired `1225` checksum
  remains explicitly excluded.
* **Replacement validation:** 101 analysis tests pass, 33 emulator-dependent
  tests skip, and 71 subtests pass. Five CPU-level cases execute the new
  contrast dispatcher and the real stock adjusters, verifying NO decreases
  the port-`46h` value, YES increases it, both endpoints saturate, and no key
  performs no write. A bounded 30,000-slice run begins with
  `CTL_LATCH_2A=20h`, `IRQ_MASK=FFh`, `SOUND=00h`, then the complete stock LCD
  register/clear sequence and `LCD_CONTRAST=00h`. It decodes 3,154 records
  with no counter discontinuity or watchdog trip. The strict documentation
  build passes.
* **Ghidra saved:** the stock reset listing at `ROM00:01B1`-`01B9` now records
  the complete pre-LCD quiesce sequence and gives each bitfield/register its
  unambiguous owner.

## Replacement-ROM second hardware result and LCD cross-check (2026-09-07)

* **Owner-supplied hardware result:** the verified `2692` image produced a
  brief power-up bleep rather than the `1225` image's constant buzz, confirming
  execution reached `SOUND=00h` before `Lcd_Init`. The panel remained uniformly
  black and physical YES/NO caused no visible change. Whether the Arduino saw
  preamble `A5 5A 0D 80 80` remains the key discriminator for progress beyond
  LCD initialization.
* **DISCARDED:** the initial hypothesis that real keypad sense was inverted.
  Stock `Kbd_ScanMain` treats a nonzero masked `KBD_SENSE` result as a pressed
  key at `ROM00:1915`-`1921`, matching the exerciser's active-high test.
* **CONFIRMED keypad bug:** the `2692` scanner calculated
  `6*drive-bit-index + sense-bit-index`. Stock `ROM00:1921`-`1933` calculates
  `6*sense-bit-index + drive-bit-index`, using the one-hot decoder at
  `ROM00:1A52`. Lee Davison's independent `KEY_scan` uses the same ordering.
  Thus physical NO (table index 17) became 32 and physical YES (table index 23)
  became 33 in `2692`; neither could reach its contrast handler. The current
  scanner calls the stock decoder for both coordinates, and CPU-level tests
  inject the physical NO/YES matrix states and obtain 17/23.
* **Davison LCD cross-check:** the 1998 Micronic monitor source in `micron.zip`
  on the archived Micronic download page independently uses ports `23h`/`03h`
  for the HD61830, port `46h` for contrast, and the same reset-time port-`2Ah`,
  port-`05h`, port-`04h`, and port-`2Bh` sequence. Its controller values overlap
  the stock sequence, and it writes port `46h` before issuing any HD61830
  command. The `1E3E` and later candidates follow that ordering.
* **Unsafe filler draft discarded before burn:** zero runs `ROM00:325B`-`3266`
  and `ROM00:7D1E`-`7D2F` are table storage, as already recorded in the
  exerciser README. The final candidate uses neither.
* **Excessive full-page clear discarded before burn:** Davison clears all
  eight display-RAM pages, but stale off-screen RAM cannot explain a uniformly
  driven-black LCD. The candidate retains only stock `Lcd_Init` and its normal
  160-cell clear.
* **Scope reduction:** the optional port-`2Ch` pin walk was removed to keep the
  corrected keypad scanner and LCD diagnostics within previously vetted filler.
  It maps the barcode-side connector rather than the IR link and is not needed
  for this protocol run.
* **`1E3E` hardware result (owner-supplied):** both beeps were heard and the
  LCD became uniformly clear rather than black. This confirms that stock
  `Lcd_Init` returned. **Correction 2026-09-10:** this does not establish
  physical contrast polarity: value, ordering and delay changed together,
  and the earlier run did not prove its final contrast write was reached. NO/YES
  produced no visible change. That does not re-open the confirmed matrix
  formula: YES began saturated at `FFh`, while both keys were polled only after
  link startup and contrast dispatch occurred only at 64-record boundaries or
  in the `DEAD` loop. The Arduino was not set up, so whether execution reached
  those polling paths was not observed.
* **`1E3E` interaction design discarded:** an endpoint with no text is not a
  usable contrast target, and making keypad handling conditional on link
  progress defeats the diagnostic. The post-`Lcd_Init` tone served its purpose
  and is removed from the next candidate.
* **Current candidate:** the 32768-byte `27E8` image uses the established
  `g_bLcdContrast` shadow, starting both it and port `46h` at `C0h`. After the
  same pre-init contrast write, approximately 476 ms settle, and complete
  stock `Lcd_Init`, it repeatedly displays `CONTRASTxx`. NO decrements the
  shadow and port value by two; YES increments both by two.
  Physical ENTER is byte-verified as matrix index 22 from
  `tbl_kbd_map[22]=0Dh`; ENTER alone leaves setup and begins link initialization.
  The image differs from stock in 715 bytes and has SHA-256
  `f02073d9743faab7b69c1ff85bdabc018a328000507ecf51574bba95e03814ca`.
* **Validation:** all 17 dedicated exerciser tests pass under the Z80
  environment; the complete analysis suite reports 106 passed, 33 skipped,
  and 71 subtests passed. The new CPU-level integration case drives the
  physical NO coordinates, observes `g_bLcdContrast` and port `46h` change
  from `C0h` to `BEh`, verifies `CONTRASTC0` then `CONTRASTBE` on the LCD-data
  writes, drives the physical ENTER coordinates, and proves the setup routine
  returns. A bounded 3,000-slice boot run logs the pre-init and stock
  `LCD_CONTRAST=C0h` writes followed by repeated `CONTRASTC0` and all six
  keypad-drive values; no link port is touched before ENTER. The 334-byte
  post-setup link body is byte-identical to the already-validated `1E3E` body.
* **Ghidra saved:** `g_bLcdContrast` and `g_bKbdMatrixIndex` now name and type
  the two relevant RAM bytes. `Kbd_ScanRowDecode`'s plate records its exact
  bit-index contract, and the `Kbd_ScanMain` arithmetic carries a PRE comment
  for the confirmed `6*sense-line-index + drive-line-index` mapping. The stale
  `g_bLcdContrast` repeatable that called the byte a power/clock latch is
  corrected; its plate and the `LCD_CONTRAST` repeatable record the
  owner-observed physical polarity. `tbl_kbd_map[22]=0Dh` carries the ENTER
  mapping in place. The owner results and replacement diagnostic sequences are
  bookmarked at the stock LCD contrast write.

### 2026-09-10 — readable exerciser screen, keypad still unresolved

* **Owner-supplied result:** `27E8` displays `CONTRASTC0`; keys have no
  observable effect. Initial LCD text output works. Repeated setup-loop
  execution and hardware keypad scanning are not established by static text.
* **Discarded explanation:** waiting for IR progress cannot explain this
  result, because this setup screen precedes link initialization. The old
  link-dependent interaction design was a defect, but removing it did not
  resolve the observed keypad failure.
* **Validation limit:** synthetic sense inputs test the decoding algorithm,
  not the actual keypad's response. Local ROM inspection and Davison's
  monitor agree on OUT `02h`, two PUSH/POP pairs, IN `00h`, AND `3Fh`.
  No byte-level cause of the current failure has been established.
* **Next diagnostic, not yet implemented:** preserve LCD initialization;
  show a changing heartbeat, all six raw sense readings with their drive
  masks, and the decoded key index before any link operations. This separates
  a stalled loop, unexpected sense inputs, and decoding/dispatch failure.
* **Correction pending in Ghidra:** the previous session's physical-polarity
  claim in the contrast RAM plate and port repeatable was overconfident;
  contrast, ordering and delay were confounded. README and this log are
  corrected. MCP currently exposes only `vingcard2100`, not `micronic1000`;
  no unrelated program was modified. Reopen Micronic before correcting and
  saving those annotations. No replacement ROM or proven keypad fix this turn.

### 2026-09-10 — rebuild with visible keypad diagnostics (`2D4D`)

* **Implemented:** preserve the working LCD startup and shadow-based contrast
  adjustment. Replace static `CONTRASTC0` with `C` and hex fields for contrast,
  decoded key, incrementing heartbeat and six masked sense readings. The raw
  display is a separate complete scan in drive-mask order
  `01h,02h,04h,08h,10h,20h`. This fixes diagnostic observability, not a proven
  physical keypad cause. The failure's cause remains OPEN.
* **Compaction:** derive the drive index from the scan counter (`6-B`), fold
  the constant wire-ID mask at assembly time, and share the RX final control
  write with TX via one extra JR after the arm delay. No new patch regions;
  original LCD initialization, command timing and settling loops retained.
  Timing prose now uses the owner-stated 3.6864 MHz clock.
* **Build:** 32768 bytes, sum16 `2D4D`, 717 bytes differ from stock; SHA-256
  `dd90a72ff05e9d26c35c599f171e09e5962ea740387b78ab0917e188e1419242`.
  Seven unused bytes remain across the six guarded regions. ROM01 untouched.
* **Validation:** 56 dedicated tests pass, including all 36 single-key
  coordinates; full diagnostic rows for NO/YES/no-key then ENTER; contrast
  shadow/output consistency, stack balance and no pre-ENTER IR writes;
  cold boot with RAM filled `00h`, `FFh`, and `A5h`. Synthetic port responses
  cannot establish the physical sense-byte values. No hardware success claim.
  Full analysis suite: 145 passed, 33 skipped, 71 subtests passed;
  strict documentation build and whitespace checks passed.
* **Ghidra correction completed:** connected to `micronic1000`, opened
  `/micron1.bin` without analysis, freshly read contrast helper bytes and
  corrected the shadow plate and port repeatable after same-provider review
  (cross-provider reviewer unavailable in this environment). Removed the
  unisolated physical-polarity claim; preserved verified shadow mechanics.
  Program saved. This resolves the preceding entry's pending correction.
* **Next hardware observation:** whether the heartbeat changes, the decoded
  key value, and the six sense bytes at rest/with NO or YES held. ENTER still
  starts IR; Arduino remains unnecessary for the setup diagnosis.

### 2026-09-10 — owner validates keypad and selects contrast default

* **CONFIRMED (owner-controlled hardware test, `2D4D`):** heartbeat changes;
  idle key `FFh` and all six sense bytes zero; NO gives key `11h` and the
  drive-`20h` sense byte `04h`, while contrast decreases; YES gives key
  `17h` and that sense byte `08h`, while contrast increases. Releasing either
  key restores idle. Decreasing the contrast byte darkens the screen in the
  tested range. Owner prefers `A4h`; no endpoint appearance claim is made.
* **Implemented:** change only initial contrast `C0h` to `A4h`. Rebuilt
  32768-byte image sum16 `2D31`, SHA-256
  `7f2efaa6a4893c889dc6f0059a8411952a2a622419d390c1d892fb2648707bf6`.
  Existing `2D4D` can be adjusted manually; avoid a burn for this change alone.
* **Ghidra:** same-provider reviewer checked the scoped owner-observation
  claim (cross-provider unavailable). Contrast shadow plate now records the
  controlled result and preference, retaining the prior-failure uncertainty;
  mechanics-only port repeatable unchanged. Program saved.
* **Next:** with Arduino `LISTEN_ONLY` ready, press ENTER and capture the
  transition into the link test. Physical ENTER/IR success is not yet reported.

### 2026-09-10 — ENTER recognised, no Arduino output reported

* **Owner result:** after ENTER, no Arduino output; LCD transcribed as
  `CA41612000000000800`. Its leading fields are contrast `A4h`, key `16h`
  (ENTER), heartbeat `12h`. The transcription is 18 characters, whereas the
  complete diagnostic row is 19; do not infer every sense field from it.
* **Open observation:** does the heartbeat remain `12h` after releasing
  ENTER, and do NO/YES still change the contrast? Inspect the entire LCD for
  `DEAD`, including the next row: the current error printer does not home the
  cursor after setup, so its marker starts after the diagnostic text.
* **SUSPECTED:** if the row freezes without an error marker, execution may
  be waiting for LINK_STATUS bit 7 in the first reporting operations.
  Stock Link_Present at ROM00:34EC-34F7 has a bounded ready wait and then
  writes LINK_CMD=81h. The exerciser's subsequent putbyte/putflag waits
  retry indefinitely; no new screen is rendered before the preamble.
  A PC/status observation or explicit startup-stage indicator would
  distinguish this from other failures. No Arduino output alone does not
  prove absence of physical IR activity or identify the controller state.

### 2026-09-10 — post-ENTER startup diagnostic ROM (`2726`)

* **Owner follow-up:** heartbeat remains `12h` after ENTER, NO/YES no longer
  affect contrast, and no `DEAD` marker appears anywhere. The setup loop has
  stopped updating; a reporting ready-wait stall remains SUSPECTED, not proven.
* **Implemented:** retain the validated setup, raw keypad display and LCD
  startup; show stages 01 probe, 02 select/baseline, 03 initial frame open,
  04 preamble, 05 record stream. Replace indefinite reporting-ready retries
  with a terminal error after 255 status samples. Initial open retains 16
  stock bounded attempts. Error homes and replaces all 20 first-row cells
  with `EESSRRCCNN` and spaces: stage, fresh error-entry status, control
  shadow, completed data-write count modulo 256. NO/YES stay live; reset to
  restart. A transmitted-byte count means OUTs completed, not IR delivery.
* **Scoped experiment:** suspend port alternation, TX/RX arm phases and
  control sweeps to fit these diagnostics in existing vetted filler. Keep
  the top V24 baseline and original 11-byte record layout. Version `0Eh`
  identifies the changed experiment; decoder suppresses phase interpretation
  for it and for captures without a known phase-bearing preamble.
* **Flag bug fixed:** the prior constant-folded `LD A,LINK_ID & 20h` did not
  establish the caller-Z contract of Link_PortSelect. Progress rendering
  exposed this in tests (control `01h` instead of `03h`). Fresh bytes at
  ROM00:3454-3489 and caller ROM00:3278-327A confirm the flag dependence,
  already correctly described by the Ghidra plate. Use XOR A for fixed-top
  Z-set selection. Same-provider review approved this narrow correction.
  Discard the earlier claim that constant-folding was generally equivalent;
  do not infer that it caused the older hardware freeze.
* **Build:** 32768 bytes, sum16 `2726`, 698 changed bytes versus stock,
  SHA-256 `813006c23f350142c83abe1deb495286a62e7eece4e9e0b49c97bdb225b60827`.
  Original six filler regions and boot jump only; 25 filler bytes remain.
* **Validation:** 63 dedicated tests pass. Full CPU boot plus ENTER tests
   cover never-ready, failure immediately after the first command, mid-preamble,
   first record-frame flag and later record transmission, plus always-ready
   streaming. Assert exact error rows, cleared suffixes, completed write counts,
   stage progression, reset stack, live NO adjustment on error, top-port latch
   outputs, and no data writes after failure. Existing keypad/LCD tests remain.
   Physical handshake behaviour remains unverified by these synthetic inputs.
   Full suite: 152 passed, 33 skipped, 71 subtests passed. Strict documentation
   build passes; reviewed flag-contract and hardware-test bookmarks saved in
   Ghidra. No new hardware-success claim is made for this candidate.

### 2026-09-12 — session-module UI/field analysis and IR wire provenance (parent-adjudicated, bytes verified, cross-reviewed; no new inference)

* **A1 — `ram:e701`/`ram:e6ff` are display snapshots, not counters
  (CONFIRMED).** `g_wSessRcv1` (`ram:e701`) and `g_wSessRcv2` (`ram:e6ff`)
  are snapshots of the last-consumed RX object's frame-type byte at
  `ram:e5be` and sequence byte at `ram:e5bf`, via live-copy cells
  `ram:e646`/`ram:e648` (`ROM00:5AA3`/`ROM00:5AAC`). Three direct static
  writers: live copy at `ROM00:5AA3`/`ROM00:5AAC`; init-zero at
  `ROM00:45C4`/`ROM00:45CA` and `ROM00:4737`/`ROM00:473D`. Single direct
  reader at `ROM00:4380`/`ROM00:4399` in `Session_StateBuild`, via
  `Lib_DecU16` (width 3) into the RCV1/RCV2 error/status screen. They
  are not builder inputs and not counters. Broader UI meaning beyond that
  display remains OPEN.

* **A2 — RECORD/BLOCK senders via `Session_Tx4Param`/`Session_Tx5Param`
   (CONFIRMED mechanics; RECORD vs BLOCK mapping OPEN at that date — SUPERSEDED 2026-09-17, see new entry below).**
   `ROM00:5669` `Session_Tx4Param` (4 stack args: 1 word + 3 byte; direct
   `CALL Session_TxBlock4` `ROM00:5BF7` at `ROM00:5699`; result word
   `g_wTxBlock4Result` at `ram:e64e`) and `ROM00:56A4` `Session_Tx5Param`
   (5 byte args; direct `CALL Session_TxBlock5` `ROM00:5CD7` at
   `ROM00:56DC`; result `g_wTxBlock5Result` at `ram:e65a`). Both builders
   also reachable via `Session_RuntimeStubSourceTable` entries `ROM00:7D96`
   (index 7 → `ROM00:5BF7`) and `ROM00:7D98` (index 8 → `ROM00:5CD7`).
   `TxBlock4` fills payload cells `ram:e650`-`ram:e656` (first stack word
   argument `==1` selects device `63h` else `43h` → `ram:e52e`;
   `ram:e658=8`); `TxBlock5` fills `ram:e65c`-`ram:e668`. Whether
   `Tx4Param`/`Tx5Param` map to RECORD vs BLOCK remains OPEN at that date;
   discriminator is to correlate one wrapper with a captured RECORD/BLOCK
   UI transaction. **2026-09-17 correction:** the premise is discarded; see next entry — the real RECORD/BLOCK senders are `C-TX-REC`/`C-TX-BLK` via `ROM00:3E14`/`ROM00:3D9B`, not `Session_Tx4Param`/`Session_Tx5Param`.

* **A3 — `SessionRxStateMachine` (`ROM00:5A81`) Out contract corrected
  (CONFIRMED).** Seeds `ram:e646` from zero-extended received type byte
  at `ram:e5be`; substitutes only numeric values `4` (`ROM00:5B18`), `8`
  (`ROM00:5AE7`), `9` (`ROM00:5AFE`) locally; does NOT restrict the
  received type to `{2,3,4,8,9}`.

* **A4 — `ram:e6fc` zero-length wait threshold (`g_bSessZeroLengthWaitSec`)
  (CONFIRMED mechanics; 55 s semantics LIKELY).** Written `0x37` (=55 s)
  at `ROM00:4587` and `ROM00:46FA`; read at `ROM00:5AF0` → `ROM00:6443`,
  which compares baseline against RTC-derived current time (BDOS `FDh`
  via `ram:DA13`; minute-boundary `+60`) and returns whether
  `baseline + threshold_seconds ≤ current_seconds`; when true, result `9`.
  The elapsed-seconds threshold role is byte-verified; that `0x37` means
  55 seconds of wall time is LIKELY (era convention combined with
  observed value).

* **A5 — `ram:e48c` session error-code cell (CONFIRMED mechanics; full
  runtime-writer map OPEN).** 17 direct readers, no direct static writer;
  written indirectly via `ROM00:454B`-`ROM00:4557` → `ROM00:3C06`
  (`Session_CoroJumpTable`); table at `ROM00:692A + 17*ram:E22D + selector`,
  masked `0x7F`, written through destination pointer at `ROM00:3C94`-`ROM00:3C9E`
  (byte `ram:e48c` via `HL` indirection). Full set of runtime selectors
  that drive it remains OPEN.

* **A6 — `ram:e085` `Lib_SignedGt16` contract (CONFIRMED; closes
  previously-OPEN polarity item).** `HL_out = (signed HL > signed DE) ? 1
  : 0`. Used at `ROM00:5AB7`-`ROM00:5AC1` with `HL=0`, `DE=length` to
  detect negative length. Byte-verified at `ram:e085`.

* **B — `conn3`-`conn13` Arduino source provenance (investigation only,
  NOT archived; SUSPECTED map).** The per-run build-mode snapshot of
  `analysis/arduino/m1000_ir_probe/m1000_ir_probe.ino` for `conn3`..`conn12`
  remains not archived; `TASKS` open item 3 stays OPEN and raw captures
  remain only in `$HOME/micronic-scope-traces` (SHA-256 banked in
  `re-notes/ir-wire-protocol.md`). The on-disk sketch is a single
  mutually-exclusive-mode build (`LADDER_TEST` currently `#defined`;
  `#error` guards at `m1000_ir_probe.ino:108`-`128`). A run→mode map is
  **INFERRED** from decoded-contents strings vs sketch mode structures and
  must be recorded as **SUSPECTED** only: `conn13→LADDER_TEST`
  (near-explicit), `conn12→FREERUN_TEST` (near-explicit),
  `conn11→ADDR_SWEEP` (near-explicit),
  `conn10`/`conn9`/`conn8→PULSE_TEST`, `conn6→ORIENTATION_TEST`,
  `conn4→LISTEN_ONLY`, `conn3`/`conn5`/`conn7→`generic `#else` sweep. Do
  NOT infer mode from capture filenames — filename digit is run index, not
  mode. Discriminating observation that would confirm or refute: the single
  `Serial` banner line emitted by `setup()` captured with each CSV, or a
  versioned `.ino` copy per run.
  **Codex session logs checked 2026-09-13:** `~/.codex/sessions/2026/09/`
  (days 06-10, 12) contain no per-run mode, banner, or `.ino` snapshot for
  `conn3`-`conn13`. The one Micronic session (01a07851, 2026-09-06/07) and
  its three guardian transcripts state the per-run sketch is not under
  `/home/philpem` and record only a mid-edit dual-flag
  `PULSE_TEST`+`LADDER_TEST` snapshot (since fixed), not a per-run build.
  Raw CSV files are MSO samples with no embedded banner. Provenance
  confirmed absent from sessions; SUSPECTED map stands.

Cross-links: `re-notes/commstar-evidence.md` (senders, snapshots,
threshold) and `re-notes/ir-wire-protocol.md` (SUSPECTED run→mode map).
No Ghidra changes; docs only.

### 2026-09-13 — transmit arm added (`2609` supersedes `2726`)

* **Hardware result `2726` (CONFIRMED):** `EE04580302` — stage `04`,
  `RR=0x58`, `CC=03h`, `NN=02` — with no emission on either port; controller
  accepted `LINK_TXD` writes but the existing hardware run showed nothing
  optically. Diagnosis (CONFIRMED): missing stock handshake arm — the ROM
  exerciser's transmit path omitted the `ROM00:32CC-32EE` arm that raises
  `LINK_CTRL` bit 5 then bit 4, settles, then drops bit 5 leaving bit 4 SET.
* **Fix (CONFIRMED):** new code `arm_tx` at `0x0250` replicates that sequence
  exactly (raise bit 5, then bit 4, 32-iteration settle ~0.11 ms at 3.6864 MHz,
  drop bit 5; bit 4 left SET so `CTRL_SHADOW` is `13h` after the arm vs `03h`
  before). Called in preamble after first byte `A5` (mirroring stock order
  flag→byte→arm) and at each record-frame start (`COUNT` multiple of 64, just
  after `COUNT`); preserves `B`/`E` (record loop `OR`/`AND` snapshot) using
  `D` for its settle. Two dead writes (`V_ID`/`V_BASE`) removed to make room.
* **Reclaimed guarded region `scr` at `0250-02FD` (CONFIRMED):** overwrites the
  stock cold-boot/banner flow reached only by fall-through from warm-boot entry
  `024D` (this ROM never runs it) and never CALLed (Ghidra xrefs: none; byte
  scan for `CALL`/`JP` into the range finds only a self-jump at `0x02E2`).
  Build refuses unless untouched stock bytes at `0250-02FD` hash to SHA-256
  `826a1915a2f2ec88fe5e8d25cc1c8d5d89d9327a1b544d45d2680f7346694364`.
* **Build `2609` (CONFIRMED):** 32768 bytes, sum16 `2609` (was `2726`),
  716 changed bytes vs stock (was 698), SHA-256
  `ec7d06b03167531c3099ce3afc925c013b6abee0cc6b62096c123c203f7b7b72` (was
  `813006c23f350142c83abe1deb495286a62e7eece4e9e0b49c97bdb225b60827`); old image
  `2726` 698-byte diff retired. Wire version stays `0Eh`, record layout
  unchanged (arm is ROM-side only).
* **Tests (CONFIRMED):** 63 exerciser tests pass; full suite 152 passed / 33
   skipped (71 subtests passed). No Ghidra changes; docs updated
   (`analysis/rom_exerciser/README.md`, `doc/re-notes/exerciser-test-plan.md`).

### 2026-09-13 — receive path, awaited `LINK_STATUS` bit 6, and re-framing of `conn3`–`conn13` (parent-adjudicated, bytes verified; docs only, no new inference, no Ghidra)

* **Findings 1–4 — `LINK_STATUS` bit 6 and `LINK_CTRL` bits 6/7 (CONFIRMED unless noted):**
  1. `LINK_STATUS` bit 6 is polled CLEAR in exactly two places, both inside
     `Link_BlockTx` — `ROM00:32F3` and `ROM00:3336`; timeout to `ROM00:3356`
     with `A=0xEE`. **No** bit-6 test exists in the receive path. Other
     readers: bit 4 at `ROM00:32BB` (`CPL`/`AND 10h`, waits clear) and
     `ROM00:34E7` (`AND 10h`, IRQ decision); bit 7 at `ROM00:3318` (`RLCA`,
     per-byte) and `ROM00:34FB` (`AND 80h`, `Link_WaitReady`); bit 0 at
     `ROM00:33CF` (`RRCA`, gates `INI` loop); `ROM00:34BA` returns raw byte
     (`Link_Probe`). 2. `LINK_CTRL` bits 6 and 7 are the `ROM00:34BD` (sets both)
     / `ROM00:34D2` (clears both) pair; `Link_BlockTx` clears both at entry
     (`ROM00:327D`) and never raises them during the transaction; they are set
     by the IRQ handler when `LINK_STATUS` bit 4 is clear (`ROM00:31C2`), by
     `LinkRxDispatcher` (`ROM00:3010`/`3028`/`3056`), and by `Link_TransferService`
     (`ROM00:2FAE`). 3. `Link_BlockRx` (`ROM00:3378`) opens with the same
     bit-5/bit-4 arm as `Link_BlockTx` (`ROM00:32CC`–`32EE`) but inserts a dummy
     `IN A,(4Eh)` (`LINK_RXD`) before setting bit 4 (`ROM00:338C`); byte path uses
     `LINK_STATUS` bit 4 (IRQ) and bit 0 (`INI` gate) reading `LINK_RXD` (`4Eh`).
  4. **CONFIRMED ordering:** `Link_TransferService` (`ROM00:2F58`) calls
     `Link_BlockTx` at `ROM00:2F9A` and then calls `ROM00:34BD` (raise
     `LINK_CTRL` 6/7) at `ROM00:2FAE`, immediately after the transmit
     transaction returns, returning at `ROM00:2FB1`; `Link_BlockTx` itself has
     no 6/7 writer. So the receive path is re-enabled only after the transmit
     transaction completes. **LIKELY:** at the interrupt level the link is
     firmware-managed and half-duplex — the transmit transaction clears the
     `LINK_CTRL` 6/7 pair (RX interrupt enable) for its duration, so a peer
     reply during the controller's own TX cannot raise the RX interrupt. Name
     `HSBUSY` for `LINK_STATUS` bit 6 is the project's coinage, not
     ROM-derived; firmware only waits for it to clear after the arm.
* **Re-framing (analysis, SUSPECTED):** `conn3`–`conn13` Arduino replies were
  delivered while the controller's `LINK_STATUS` bit-6 wait had never completed
  (exerciser `2726` omitted the arm; `2609` restores it). If the receive window
  only opens after the transmit transaction completes, those negatives are
  **SUSPECT** and should not be treated as settled.
* **Open questions A–D and plan Phases 0–3 recorded in docs:** A — is bit 6
  transmit-complete (clears in a few hundred µs with no peer) or handshake/peer?
  Discriminator: `2609` `OR`/`AND` with arm held and no peer. B — when is the
  receive window opened relative to the transaction, and must the reply arrive
  inside it? C — does the receive path use the same HDLC sense/polarity/phase?
  Not ROM-derivable; needs a hardware sweep. D — does own TX raise `LINK_STATUS`
  bit 4 / link IRQ with no peer? See
  `doc/re-notes/ir-wire-protocol.md#the-receive-path-and-the-awaited-status-bit`
  and
   `doc/re-notes/exerciser-test-plan.md#ir-handshake-investigation-plan-phases-03`
   for the full phase definitions and the offline work list (static map, emulator
   traces, RX-witness exerciser variant, Arduino sweep modes, bench procedure).
   No Ghidra changes; `mkdocs build --strict` gated.

### 2026-09-13 — witness build and RX sweep (CONFIRMED, emulator/syntax validated; docs only, no new inference, no Ghidra)

* **Witness build (CONFIRMED):** `analysis/rom_exerciser/build.py` now builds two variants from the one source — default record-stream (`micron1_exerciser.bin`, 32768 bytes, sum16 `2609`, 716 changed bytes, SHA-256 `ec7d06b03167531c3099ce3afc925c013b6abee0cc6b62096c123c203f7b7b72`) unchanged, and with `--witness` `micron1_witness.bin` (32768 bytes, sum16 `2DA4`, 812 changed bytes, SHA-256 `863121e8b379c6578aaabffde464596506732989b9c3ab1453ffe4df9f868887`). Both live in the same reclaimed `scr` region at `0250-02FD`; default build strips the witness code and stays byte-identical to `2609` (CONFIRMED). The witness does the stock opening (Link_Probe, top-V24 port select, control setup), writes the flag via Link_Present, writes ONE first data byte (`A5`), performs the `arm_tx` handshake, then STOPS transmitting and watches the receive path. It never writes `LINK_CMD`/`LINK_TXD`/`LINK_CTRL` after the arm, so nothing it sends can disturb the receive path being measured (CONFIRMED by emulator: exactly one `0x81` to `LINK_CMD`, one `0xA5` to `LINK_TXD`, the arm values `23h`/`33h`/`13h`, then silence). Witness LCD row: `W` then six hex bytes `OR AND ISRC IRQN ARMD HB` — `OR`/`AND` are `LINK_STATUS` over the current window (~0.1 s, reset after each LCD update) so a stimulus is visible live; `ISRC`/`IRQN` sticky for the run; `ARMD` is `LINK_STATUS` sampled immediately after the arm; `HB` heartbeat; reset only by power-cycling; the IR channel is being listened to, so the LCD is the only readout.
* **Arduino `RX_SWEEP` mode (CONFIRMED code; syntax-checked with host stub, no AVR toolchain in CI):** `analysis/arduino/m1000_ir_probe/m1000_ir_probe.ino` gains `RX_SWEEP` (set `RX_SWEEP 1`, all other mode flags `0`). It answers each handheld burst with one combination of: flag sense `{0x81, 0x7E}`; data polarity `{normal, complemented}`; data-to-clock phase `{-4,-2,0,+2,+4}` eighths of a cell (transmit convention is a −2/8-cell data lead); content `{flag only, flag+03h, flag+03h+legal body+flag}`. Reply ~3 ms after the handheld burst; one combination advances per burst and the parameters are printed. It does NOT score itself: the controller's reaction is read from the witness ROM (`LINK_STATUS` `OR`/`AND`, `ISRC`).
* **Validation (CONFIRMED):** emulator tests lock the witness fingerprint and verify `test_witness_stops_transmitting_after_the_arm` (65 exerciser tests pass); Arduino sketch syntax-checked with host stub, no AVR toolchain in CI. Docs updated (`analysis/rom_exerciser/README.md`, `doc/re-notes/exerciser-test-plan.md`, `doc/research/TASKS.md`); `Next` priority lists refreshed. No Ghidra changes.

### 2026-09-13 — static receive-chain state map (docs only, no new inference, no Ghidra; parent-adjudicated, bytes verified)

* **Static map added (CONFIRMED, `ROM00`):** `re-notes/ir-wire-protocol.md` § *Receive-chain state map* records the ROM's receive chain byte-for-byte: `Link_IrqPollArmOrService` (`ROM00:31B6` clear 6/7, test `LINK_STATUS` bit 4, dispatch or re-arm), `LinkRxDispatcher` (`ROM00:2FBD` `Link_BlockRx` at `3378`, validate at `30DC`, cancel at `21BA`, dispatch on `FDD5`/`FDE6`), `Link_BlockRx` arm (`3378`–`33A6` with dummy `LINK_RXD` at `338C`) and byte loop (`33CF` `RRCA` on `LINK_STATUS` bit 0, `INI` on `4Eh`, timeouts `EE`/`ED`/`EC`), `Link_ValidateFrameHeader` (`30DC` length <6 / embedded-length mismatch / link-id +4 vs `FDD4`), dispatcher branches (`3002` on `FDE6`, `302C` setup, error `FE14`/`FFFF`, command path `3084`–`30DB` with per-link slot at `FE43+(FDD4&3F)`, `FDD5=4`, `FBC9` bit 0, `JP (FDD2)`), slot helper `3192`/`31A1`/`31A6`/`31AB` and `317B` table, complete `LINK_CTRL` 6/7 SET (`34BD`: `31C2`/`3010`/`3028`/`3056`/`2FAE`) and CLEAR (`34D2`: `31B6`/`327D`/`30B3`/`2EC2`/`2ED4`/`34B7`) points, and state cells (`FDD5`/`FDD4`/`FDD6`/`FDD7`/`FDD8`/`FDCA`/`FDCB`/`FDDC`/`FDE6`/`FDE7`/`FDEA`/`FE14`/`FBC9` bit 0). Exerciser note: its own IM-1 ISR never calls `Link_InitSlots`; separate.
* **TASKS update:** `Next` No-hardware priority 1 marked **DONE 2026-09-13** (this pass); renumbered so top is now the emulator demonstration of the handshake gating, followed by the static backlog; hardware priorities unchanged (Phase 0 `2609`/`2DA4`, Phase 2 witness+`RX_SWEEP`, Phase 3 `CommstarPeer`). No new inference; evidence tags preserved.

### 2026-09-17 — emulator handshake-gating demonstration and witness RX-enable fix (CONFIRMED, emulator; docs only, no Ghidra, no new inference)

* **Finding 1 — emulator trace (CONFIRMED):** synthetic controller `LINK_STATUS` bit 6 never clears. Stock `Link_TransferService` inner path (`ROM00:2F86`) runs `Link_BlockTx` (`ROM00:3277`) to completion — one `LINK_CMD`=`81h`, one `LINK_TXD`=`03h`, `LINK_CTRL` 6/7 clear throughout — returns `A=0EEh`/carry set (`ROM00:3356`), then calls `ROM00:34BD` at `ROM00:2FAE` and raises `LINK_CTRL` 6/7 (observed `42h`, `0C2h`). So "stock firmware never reaches the `2FAE` RX-enable" is FALSE: carry is ignored. *Harness detail:* stub `RET` at resident-kernel helper `0F54Eh` (absent from flat memory), not a firmware finding.
* **Finding 2 — temporal gating (CONFIRMED firmware write pattern):** gating is temporal, not permanent. `LINK_CTRL` 6/7 cleared for the whole `Link_BlockTx` transaction and restored by `34BD` at `2FAE` after it, on success or `0EEh` timeout. Firmware holds 6/7 clear for ~10–12 ms (bit-6 wait is 620×59 T ~=9.92 ms at 3.6864 MHz, `ROM00:32F0`, within ~93.75 ms retry) then raises them for the remainder (CONFIRMED firmware latch writes). Whether the controller's receiver is inhibited during that window is Provisional (see Finding 4); IF 6/7 gates the receiver the `conn3`–`conn13` replies inside that window were missed, ELSE the failure is framing/convention.
* **Correction to re-framing (CONFIRMED firmware write pattern; consequence Provisional):** `conn3`–`conn13` Arduino replies were sent ~1–9 ms after the handheld's burst, i.e. inside the window in which the firmware holds LINK_CTRL 6/7 clear (~10–12 ms: 620×59 T ~=9.92 ms at `ROM00:32F0`). Firmware holds 6/7 clear for that window then raises them via `34BD` at `2FAE` after every attempt (CONFIRMED) — so wording implying "the RX was never enabled" is refuted. Whether framed data could be received inside that window depends on the Provisional 6/7 reading: IF 6/7 gates the receiver the replies were missed and the optical reaction was a front-end/cadence effect, ELSE the failure is framing/convention (question C). Either way, a reply timed after the transaction is the safe choice.
* **Code fix (CONFIRMED by emulator):** every exerciser build left `LINK_CTRL` 6/7 clear so RX IRQ could never fire (`ISRC` bit 2 inert). Witness now sets them before listening (`ctrl_or 40h` then `ctrl_or 80h`, as `34BD`/`2FAE` does). New witness image: sum16 `2E3E`, 824 changed bytes, SHA-256 `aa843c38dcb8131612d3d235871397bf6e6ace73d00aeeb50c79d4a7a6f124a0` (was `2DA4`, 812 bytes, `863121e8b379c6578aaabffde464596506732989b9c3ab1453ffe4df9f868887`); default `2609` unchanged; 65 exerciser tests pass.
* **Docs updated:** `re-notes/ir-wire-protocol.md` (Finding 4 extended + re-framing corrected + state-map 7 updated), `re-notes/exerciser-test-plan.md` (witness fingerprint updated + `LINK_CTRL` 6/7 enable noted + Phase 0/2 timing: stimulus must arrive after ~10 ms TX window), `analysis/rom_exerciser/README.md` (witness fingerprint + enable + temporal note), `research/TASKS.md` (Next: emulator DONE 2026-09-17, top no-hardware now static backlog; hardware priorities unchanged). `TASKS` also refreshed witness to `2E3E` in Next hardware gate. No Ghidra changes; evidence tags preserved.

### 2026-09-17 — session-module RECORD-vs-BLOCK mapping resolved (CONFIRMED, `ROM00`; docs only, no Ghidra, no new inference; parent-adjudicated, bytes verified)

* **Resolves the "session-module RECORD-vs-BLOCK mapping" open item** carried in `Next` static backlog and in the 2026-09-12 A2 entry ("whether Tx4Param vs Tx5Param is RECORD vs BLOCK: OPEN"). All addresses below byte-verified in `ROM00`.
* **Finding 1 — the commands (CONFIRMED).** `C-TX-REC` is `ROM00:50F3` (selector 12, error decade 8130/8131) and `C-TX-BLK` is `ROM00:51F2` (selector 14, error decade 8150/8151), per the `452D` call-site table already in `re-notes/commstar-evidence.md` (wrappers `50F3`/`51F2` vs `ROM00:6B67` `C-*` name table; cf. error-decade table in that page). **CORRECTION 2026-09-18:** was 8120/8121 and 8140/8141 (shifted one command; byte literals `0x1FC2`/`0x1FC3`=8130/8131 and `0x1FD6`/`0x1FD7`=8150/8151).
* **Finding 2 — shared TX stream walker (CONFIRMED).** Both transmit through the same TX stream walker `ROM00:3E14` — direct `CALL` at `ROM00:511B` in `C-TX-REC` and at `ROM00:5247` in `C-TX-BLK`. `ROM00:3E14` walks a counted source buffer (pointer at `SP+0x0C`), comparing with `E0E7` and appending each byte via `ROM00:3D9B`.
* **Finding 3 — the accumulator and 128-byte chunking (CONFIRMED).** `ROM00:3D9B` is the byte accumulator: it appends the byte to a buffer at `e3c6` with a count at `e446`, and when the count reaches `0x80` (128) it flushes via `ROM00:3D11`. So records and blocks are both chunked into 128-byte objects (126 data bytes + 2-byte header, matching the documented "objects of at most 126 data bytes").
* **Finding 4 — RECORD/BLOCK difference is pre-walk setup, not wire chunking (CONFIRMED).** `C-TX-REC` pre-seeds the accumulator with `3D9B` of `0x1E` at `ROM00:5107` before walking; `C-TX-BLK` calls `ROM00:3CF7` (`Session_InitAndRunTx`, which calls `ROM00:3CEA` then `ROM00:5834` -> `ROM00:60D6`) at `ROM00:5210` before walking. `C-END-FILE` (`ROM00:517F`) also appends via `3D9B` at `ROM00:5193`.
* **Finding 5 — RX mirror (CONFIRMED).** `C-RX-BLK` (`ROM00:4F5A`, wrapper `4F60`) uses the RX stream walker `ROM00:3E6A` at `ROM00:4FB9`; `ROM00:3E6A` consumes via `ROM00:3DCB`. No `3E14`/`3E6A` cross-use.
* **Finding 6 — stub exposure (CONFIRMED).** Stream primitives are exposed as transfer-vector services: `3E14` via `ROM00:7DD2` / `ram:edb0`; `3E6A` via `ROM00:7DBA` / `ram:ed80`; `3D9B` via `ROM00:7DD4` / `ram:edb4`; `3D11` via `ROM00:7DB6` / `ram:ed78`; `3CF7` via `ROM00:7DC4` / `ram:ed94`.
* **Finding 7 — CORRECTION: `Session_Tx4Param`/`Session_Tx5Param` are NOT RECORD/BLOCK senders (CONFIRMED mechanics; discard the earlier framing).** `Session_Tx4Param` (`ROM00:5669`, 4 stack args: 1 word + 3 byte) calls `Session_TxBlock4` (`ROM00:5BF7` at `ROM00:5699`; result `g_wTxBlock4Result` at `ram:e64e`); `Session_Tx5Param` (`ROM00:56A4`, 5 byte args) calls `Session_TxBlock5` (`ROM00:5CD7` at `ROM00:56DC`; result `g_wTxBlock5Result` at `ram:e65a`). Their only direct callers are `ROM00:4689` (inside `C-INIT-COMMS`, whose flow runs `ROM00:4563` -> `ROM00:4600` and ends at the `46D6` result switch) and `ROM00:4796` (the `ROM00:46E9` InitState stage ending at the `47E3` switch), plus the transfer-vector stubs (`ROM00:7DE4`/`7DE6`, `ram:edd4`/`edd8`). They are the connect/init control-object senders. Likewise `Session_TxBlock4` (`ROM00:5BF7`) / `Session_TxBlock5` (`ROM00:5CD7`) are reached only via those wrappers (`5699`/`56DC`), the stub table (`7D96`/`7D98`) and RAM stubs (`ram:ed38`/`ed3c`) — not from the `3E14` RECORD/BLOCK walker path. The open question "whether Tx4Param vs Tx5Param is RECORD vs BLOCK" is therefore closed: neither is; the premise was wrong.
* **Docs updated:** `re-notes/commstar-evidence.md` (Session-module senders block corrected to Findings 1-7; RCV1/RCV2 and `e6fc` bullets retained), `research/TASKS.md` (A2 entry marked superseded; `Next` refreshed so top no-hardware item is `ram:D370` runtime loader, followed by guarded structural repairs and the deferred final annotation sweep; this log entry). No Ghidra changes.
* **Next:** `ram:D370` provider trace is now the top no-hardware item; hardware priorities unchanged.

### 2026-09-17 — runtime loader `ram:D370` coroutine rendezvous substantially advanced (CONFIRMED, ROM01/ram; docs only, no Ghidra, no new inference; parent-adjudicated, bytes verified)

* **Advances the "runtime loader `ram:D370` input-provider path" open item** carried in `Next` static backlog. Byte-verified in `ROM01`/`ram`. All tags CONFIRMED unless noted.
* **Finding 1 — coroutine-driven loader (CONFIRMED).**
  The runtime Load/Run loader (`ROM01:0A67`-`ROM01:10CE`)
  is coroutine-driven. Its routines enter via
  `LD DE,0; CALL ROM01:D837` (`Coroutine_Enter`,
  `ram:D837`, `CONFIRMED ram:D837-D857`) and yield to a
  peer with `LD HL,D370; CALL ROM01:D9F9`
  (`Coroutine_SwapContinuation`, `ram:D9F9`).
* **Finding 2 — `Coroutine_SwapContinuation` (CONFIRMED).** `ram:D9F9`-`ram:DA0A` swaps the current continuation with the 16-bit word at the address in `HL`, then returns: `Z` when the peer slot was empty (the caller continues), `NZ` when it yielded to the peer (`EX SP,HL; LD HL,1; RET`).
* **Finding 3 — `ram:D370` is the loader's peer/rendezvous slot (CONFIRMED).** A byte search for the address (`70 D3`) finds it ONLY inside the loader region: `ROM01:0BA3`, `ROM01:0CEE`, `ROM01:0D15`, `ROM01:0DB5`, `ROM01:0E69`, `ROM01:0EE9`, `ROM01:0F6C`. No code outside the loader writes or reads `D370`, so the peer is resumed by the coroutine scheduler rather than registered by a distinct ROM routine.
* **Finding 4 — loader request protocol (CONFIRMED).** The loader sets `D368` (destination offset), `D36A` (destination pointer), `D36C` (requested byte count), `D36E` (delivered count), then swaps `D370`; the peer fills the bytes and swaps back. `Program_ConsumeInputChunk` (`ROM01:0BAC`) consumes `min(D36C, D393)` and advances `D36A`/`D36E` (e.g. `ROM01:0C2B`-`ROM01:0C9A`).
* **Finding 5 — `Program_LoadDipOrCom` routing (CONFIRMED).** `ROM01:0CE7` requests 14 bytes (`D36C=0x0E` at `ROM01:0D08`-`ROM01:0D0B`), routes on the first little-endian word (`0xC8C9` → DIP at `ROM01:0DD7`) and on the first-chunk length (`D399 < 14` → raw COM at `ROM01:0D3B`). The DIP header/block parser is `ROM01:0E40`-`ROM01:0F80` (reads the serialized header at `D39B` +0/+4/+6/…). This matches the existing "Loader-stream boundary" text.
* **Finding 6 — loader staging cell RESOLVED
  2026-09-19 (CONFIRMED, byte-verified): the
  `ram:D36A` pointer protocol; five targets.**
  The "staging cell" is the `ram:D36A` pointer
  protocol: loader sets `D36A` (pointer), `D36C`
  (count), `D368` (dest offset) and `D393`
  (limit), yields via `ram:D370`, and
  `Program_ConsumeInputChunk`
  (`ROM01:0BAC-0C9A`) copies `min(D36C,D393)`
  bytes FROM `D36A` TO `ECD8+D368` (CONFIRMED,
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
  unchanged, saved. Feeder remains the session
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
* **Finding 7 — `UI_FormExitDispatchNext` (CONFIRMED).** `ROM01:06D3` pumps five handler slots at `D081` via `ram:D828`.
* **Docs updated:** `re-notes/os-diposb.md`
  (Runtime program loading: replaced "exact
  staging cell remains OPEN" with `ram:D36A`
  pointer protocol + five targets, labels, and
  residual peer-learning OPEN),
  `manual/programmer-guide.md` (§7b source-bytes
  sentence updated to same), `research/TASKS.md`
  (runtime loader marked **RESOLVED 2026-09-19
  (CONFIRMED)** with the pointer protocol + five
  targets; `Next` refreshed so top no-hardware
  item is now `ram:EE00-EE4F`; this log entry;
  prior `SUBSTANTIALLY ADVANCED` wording
  superseded). No Ghidra changes in this docs
  pass; evidence tags preserved; style preserved;
  no new inference.
* **Next:** loader staging cell is **RESOLVED**;
  top no-hardware item is now `ram:EE00-EE4F`
  (see `Next` above); hardware priorities
  unchanged.

### 2026-09-17 — guarded structural repairs: 6e77 inline data fixed, 6431 operand documented (Ghidra saved; function count stable)

* **`Session_EvalRecordSteps` (`ROM01:6E77`) inline-data repair — DONE.** The four 4-byte inline operand spans (the consumed parameters of the `CALL DC37`/`DC23`/`DC30` frame-op idiom, which pops the return address and copies 4 bytes to `E3B1`/`E3B9`) were misdisassembled as instructions (`00 00 00 00` NOPs at `6E81`; `FF FF FF FF` RST 38h at `6EA5`; `07 00 00 00` at `6EB4`; `7F 00 00 00` at `6ED1`). Each is now a `uint` data item with a label `tbl_corstep_0`..`tbl_corstep_3`; flow resumes correctly at `6E85`/`6EAA`/`6EB8`/`6ED5`. CONFIRMED: `CALL DC23`/`DC30`/`DC37` (`ram:DC23`-`ram:DC44`) pop the return, compute return+4, push it, and copy four bytes from the inline operand.
* **`ROM01:642F`-`6431` re-check — partially done.** The bytes `21 0C 00` are `LD HL,0x000C` (the `ADD HL,SP` at `6432` then reads a stack argument); Ghidra has a stale instruction boundary at `6430` showing `INC C; NOP`. No clear-data tool is exposed and `clear_flow_and_repair` cannot free a data-blocked boundary, so the three operand bytes are now a single `byte[3]` data item at `ROM01:642F` with a PRE comment recording the true instruction. A full clear-flow repair remains OPEN (needs a Ghidra script; the inline-script path is broken — the shared `~/ghidra_scripts` bundle has pre-existing compile errors).
* **Validation:** function count `1101` before and after; `save_program` succeeded. The 2026-08-25 note's "6e77 REPAIRED" had left the inline operands still misdecoded; this pass is the actual fix.
* **Remaining in the guarded-repairs item:** `ram:pending` compiler-runtime page (`e020`-`e0aa`) plates, `ROM01:7580`-`7670` data-typing, code-gap and data-typing tail, `ROM00:7409`/`7472` module-A deferred sites.

### 2026-09-17 — guarded structural repairs, part 2: compiler-runtime plates done; large data regions blocked by tooling

* **`e020`-`e0aa` compiler-runtime page — label + plate DONE.** Every helper is already labelled (`Lib_And16` `e023`, `Lib_Not16` `e02b`, `Lib_Or16` `e033`, `Lib_Xor16` `e03b`, `Lib_Lnot16` `e043`, `Lib_Eq16` `e04b`, `Lib_Ne16` `e05a`, `Lib_SignedLe16` `e06a`, `Lib_SignedGe16` `e06b`, `Lib_SignedGt16` `e085`, `Lib_SignedLt16` `e086`, `Lib_Neg16` `e09f`, `Lib_Sub16` `e0a9`, `Lib_Unsigned*` `e0d9`/`e0da`/`e0e7`/`e0e8`).  The two with no plate were plated: `Lib_Not16` (`ram:E02B`-`E032`, `HL=~HL`, Z iff input FFFFh) and `Lib_Neg16` (`ram:E09F`-`E0A8`, `HL=-HL`, Z iff input 0).  The trivial logic ops keep SHORT-form plates.  **RESOLVED 2026-09-19 (CONFIRMED):**
  `ram:DA13` session-to-BDOS bridge closes the
  `6A36` constructor / `6AA9` stream-reader mapping;
  former `da13` OPEN superseded (see Next
  priorities and 2026-09-19 session entry).
* **`ROM01:7580`-`7670` data-typing — BLOCKED by tooling.** The region is a config-descriptor table misdecoded as code (pointers into ROM01, high byte `75`/`79`/`7a`).  `apply_data_type` with `clear_existing` clears only the single code unit at the start address and then conflicts on the next defined instruction (`Conflicting instruction exists at ROM01::7589`), so a multi-instruction data range cannot be defined; `clear_flow_and_repair` does not free a data/instruction-blocked boundary.  No clear-region/clear-data tool is exposed and the inline-script path is broken (the shared `~/ghidra_scripts` bundle has pre-existing compile errors).  Region remains bookmarked.  Same limitation blocks the `ROM01:6431` full repair.
* **`ROM00:7409`/`7472` — deferred by design.** They are the ROM images of RAM module A (`ram:D8CE`, `ram:D937`), whose internal addresses resolve against the wrong space; not a repair target.
* **Validation:** function count `1101` unchanged; `save_program` succeeded.
* **Docs updated:** `research/TASKS.md` (items 1 and 8b updated; this entry).  No code changes.

### 2026-09-17 — script tooling restored; 6431 and 7580-7670 repairs completed

* **Root cause of the broken inline-script path:** `~/ghidra_scripts` is a single Ghidra OSGi bundle; one bad `.java` fails the whole bundle, so `run_script_inline` (which writes its generated script into that folder) could not load.  It had accumulated 14 broken files (`ExtendFunction`, `Batch9A`, `Batch9Scan`, `McpInlineVerify`, `X`, `EnumLabs`, `EnumLabs2`, `ClearDataAt31FF`, `FixRTCBody`, `FixRTCBody2`, `create_fns`, `McpInline`, `FindQualifierLiterals`, `CreateFn`) plus one stray generated file.  Moved all 15 to `/tmp/opencode/ghidra_scripts_broken/` (reversible); the 9 known-good scripts remain.
* **`ROM01:6431` — DONE.** A script ran `listing.clearCodeUnits(642F, 6431, false)` then `DisassembleCommand(642F)`; `642F` now disassembles as `LD HL,0x000C`, followed by `ADD HL,SP` (a stack-argument read).  PRE comment added.  CONFIRMED.
* **`ROM01:7580`-`7670` — DONE.** The same script cleared the misdecoded code units and defined a 241-byte data array (`db[241]`); a PLATE records that it is the config-descriptor table (ROM01 pointers, high byte `75`/`79`/`7a`; From template at `758B` with flag `+9=08h` and source-name array `+12=757F`).  Detailed struct typing deferred to the final sweep.  CONFIRMED.
* **API notes (this Ghidra):** `Listing` exposes `clearCodeUnits(Address, Address, boolean)` but **no** `clearData`/`clearListing`; `clearCodeUnits` also removes conflicting data at the start, so a code/data region can be freed and re-disassembled.  `AddressFactory` must be imported explicitly in scripts.
* **Validation:** function count `1101` before and after; `save_program` succeeded.  Ghidra still prints stale cached build-failure metadata referencing the moved files until the script manager is refreshed or Ghidra restarts; functionally the inline path works.

### 2026-09-18 — final-sweep batch 1: coverage refresh + 27 renames (docs only, reviewer-approved scope; no new inference)

* **Coverage tracker refreshed:** `research/gap-analysis.md` updated to 2026-09-18 (12th audit): **1099 functions, 252 auto `FUN_*`** (ROM00 574/105, ROM01 329/145, ram 195/2, EXTERNAL 1/0; 847 named, **77.1 %**). Was 919 total / 159 `FUN_*` in the stale 2026-08-30 audit; increase reflects functions defined since then, not new coverage. See `gap-analysis.md` headline.
* **Batch 1 of the final naming sweep (reviewer-approved scope; docs updated here, Ghidra applied separately):** deleted 2 false functions (`ram:b57c`, `ram:ff21` — zero-filled RAM created from mid-instruction flow errors) and renamed+plated 27: `ram:d7fe`=Lib_EmitBankedCallStub, `ram:db40`=Lib_StrCmpN, `ram:def7`/`df03`/`df0c`=Lib_Signed{Le,Ge,Gt}32, `ram:df21`/`df2d`=Lib_Unsigned{Le,Ge}32, `ram:df18`=Lib_UnsignedLt32 (was SessionTestCarry; correction), `ram:ee3c`/`f13c`=Session_OpStub_72/264, `ROM00:1e01`/`1e0f`/`1e1d`/`1edd`=Tty_Cursor{Left,Up,Back,Home}, `ROM00:3d9b`/`3d11`/`3dcb`/`3d59`/`3e14`/`3ede`=Session_{TxAppendByte,TxFlush,RxConsumeByte,RxRefill,TxWriteBuffer,TxAppendString}, `ROM00:3f5b`/`3fce`/`3fd8`/`3fe2`/`3f65`=Session_SetMode3/4/5/6 and Session_SetModeByName, `ROM00:4262`=Session_CoroNoOp, `ROM00:3562`=Sound_BeepTimed. Function count 1101->1099. No Ghidra edits in this docs pass.
* **Deferred in batch 1 (left as `FUN_*`):** `ram:d7c5`, `ROM00:4333`, `ROM00:44ed`, `ROM00:450d`, `ROM00:2da5` — to be worked in later batches.
* **Remaining:** 252 auto `FUN_*` (ROM00 105, ROM01 145, ram 2), to be worked in further batches (investigate -> review -> annotate), plus the code-gap/data-typing tail and the deferred final sub-items (TASKS §12 FINAL PASS).
* **Reviewer correction noted:** the existing `ram:df36` plate ("strictly-greater-than") is correct; `ram:df18` was the misnamed one (corrected to Lib_UnsignedLt32 in this batch).

### 2026-09-18 — final-sweep batch 2: 84 renames + doc corrections (docs only, reviewer-approved scope; no new inference)

* **Batch 2 of the final naming sweep (84 functions renamed+plated):** C-* wrappers, result-switch arms, connect dispatchers, tails, trampolines/workers, stubs — including `ROM00:582A` `Session_CoroTxFrameAndRx` (trampoline to `60CC` `Session_TxFrameAndRx`), `ROM00:5834` `Session_CoroTxFrame33` (to `60D6` `Session_TxFrame33Transaction`), `ROM00:583E` `Session_CoroReturnZero` (to `6120` `Session_ReturnZero`), `ROM00:5848` `Session_TxRecordData` (forwards two stack args to `6181`), plus remaining C-* dispatch scaffolding. No new inference; plates carry CONFIRMED mechanics and In/Out/Clobbers per §6/§8.
* **Deferred in batch 2 (left as `FUN_*`):** `ram:d7c5`, `ROM00:4333`, `ROM00:44ed`, `ROM00:450d`, `ROM00:2da5` — to be worked in later batches.
* **Doc corrections applied in this pass (parent-adjudicated, bytes verified):**
  1. `re-notes/commstar-evidence.md` — session error-decade table corrected (row was shifted one command from C-BEGIN-FILE onward): C-BEGIN-FILE `0x1FB8`/`0x1FB9` = 8120/8121, C-TX-REC `0x1FC2`/`0x1FC3` = 8130/8131, C-END-FILE `0x1FCC`/`0x1FCD` = 8140/8141, C-TX-BLK `0x1FD6`/`0x1FD7` = 8150/8151; duplicate paragraph at `RECORD vs BLOCK` and `TASKS` Finding 1 updated to same.
  2. `re-notes/forms-ui.md` + `research/TASKS.md` field-validation paragraph — removed the four field-type validator description for `ROM00:582A`/`5834`/`583E`/`5848`; re-described as session TX paths above (batch-2 names `Session_CoroTxFrameAndRx`, `Session_CoroTxFrame33`, `Session_CoroReturnZero`, `Session_TxRecordData`).
  3. `reference/commstar-api.md` — qualified `ram:EE00-EE4F` static bytes: twenty `LD HL,1; RET` no-op slots (4 bytes each, `21 01 00 C9`), **not** `RST 10h; db bank; dw target` thunks in the static image; computed-call xrefs (e.g. `ram:EE04 -> ROM00:48BF`) describe intended/runtime-populated routing; whether/when they become `RST 10h` thunks at runtime is **OPEN**; kept `ROM00:7DFA` 20-word source-table description and noted RAM arena is patched at runtime.
  4. `research/gap-analysis.md` — headline refreshed to 168 auto `FUN_*` (was 252); total functions 1099; named = 931 (84.7 %).
* **Remaining:** 168 auto `FUN_*` (ROM00 21, ROM01 145, ram 2), to be worked in further batches; code-gap/data-typing tail and deferred final sub-items (TASKS §12 FINAL PASS) remain.
* **Function count:** 1099 stable (no creates/deletes in this docs pass; batch-2 Ghidra edits applied separately).

### 2026-09-18 — final-sweep ROM01 Part A: 61 renames + 6 structural repairs (Ghidra saved; count 1099 → 1093)

* **Part A of the ROM01 cluster (73 targeted):** 61 functions renamed+plated,
  12 `(retain)` plated-only (symbols kept — no unproven identity).
* **Structural (diff-guarded, Appendix-justified):** 50 compiler-prologue
  shells (`LD DE,0 / CALL ram:d837`, body at entry+6) extended to their real
  bodies; the duplicate heads `ROM01::0115`/`01e6` merged into the existing
  `Lib_TrimInsert`/`Lib_CopyPad`; the mid-instruction fragments `ROM01::0303`
  (`StrTrimDispatch`, inside `02f9`) and `ROM01::13ef` (`FieldFillBuffer`,
  inside `13d8`) deleted. Guarded total 1099 → 1093.
* **Corrections (byte-verified, cross-reviewed):** `0x2335` (9013)
  `"Source not available"` (table → `ram:d284`) and `0x2336` (9014)
  `"Dest. not available"` (→ `ram:d299`) are **mapped**, not unmapped;
  `Session_StateMachine2806`'s inline-data hazard is void
  (`ROM01::0020 → ram:f5ea → ram:f64d`, no inline operand); `14cf` rejects a
  **nonzero** argument; `13d8` returns the processed count (`original −
  remaining`).
* **Coverage (Part A snapshot):** auto `FUN_*` = **109** (ROM00 **23** —
  the prior 21 was an estimate, ROM01 84, ram 2); named **984 (90.0 %)**.
* **Part B — DONE 2026-09-18 (see next entry).** The REVISE review's
  block on "enumerating named functions inside the 32 shell body ranges"
  is resolved: no such overlap was found and none of the 12 superseded
  names had external callers. The `3acb`/`FieldPadValue` page-zero
  banking question is resolved: `ROM01::0040`/`ROM00::0040` both select
  bank 0, so `ROM01::0044`'s `JP 3ADD` resolves physically to
  `ROM00::3add`; `ROM01::3add` `FieldPadValue` deleted as a
  mid-instruction banking artifact (CONFIRMED). Coverage now: auto
  `FUN_*` = **42** (ROM00 23, ROM01 17, ram 2); named **986 (95.9 %
  internal)**; see `gap-analysis.md` headline (internal 1028 / guarded
  1029; ROM01 84→17).
* **Process:** `AGENTS.md` updated on **master** (`20dba56`) — diagnose
  listing pollution by function-list delta (not close/reopen); closing a
  program without saving is GUI-only; read-only agents may still write
  findings/verdict files.

### 2026-09-18 — final-sweep ROM01 Part B

* **Part B applied (Ghidra saved) — ROM01 cluster finished
  (CONFIRMED).** 32 compiler-prologue shells (`LD DE,0 / CALL
  `ram:d837``) extended to their full bodies (27 named, 5 retained);
  38 computed-dispatch blocks and 12 named interior fragments absorbed
  into their parent routines and deleted; `FUN_7599`/`FUN_7e14` deleted
  as data; `ROM01::3add` `FieldPadValue` deleted as a mid-instruction
  banking artifact (`ROM01::0040`/`ROM00::0040` both select bank 0, so
  `ROM01::0044`'s `JP 3ADD` resolves physically to `ROM00::3add`).
  Guarded total 1093 → 1029; internal 1092 → 1028.

* **Cluster merges (CONFIRMED):** parents extended and their
  inline-switch case blocks absorbed — `3a04` `Session_FieldDispatch`
  (→`3b7a`), `444f` `Session_RedrawField` (→`463e`), `576c`
  `Session_DispatchSub` (→`5839`), `583a` `Session_DispatchWrap` (→`59a8`),
  `6292` `UI_PostKeyedEntry` (→`62e4`), `6633` `UI_PostDescriptor`
  (→`6759`), `6aa9` `UI_RecordMatchAndPost` (→`6b6c`). All 12 interior
  adjudications were **MERGE** (internal-only callers, no external
  references).

* **Structural model decision (CONFIRMED — record prominently):** an
  inline-switch case reached via `CALL ram:e0b2`
  (`Kernel_TableDispatch`) + `JP(HL)` is a **basic block of the routine
  that owns the table**, not an independent function. Example: `3a04`
  runs its prologue, computes the switch value, `JP 3b53`
  (dispatcher); table `3b56` cases (`01→3acb`, `02/80→3a1c`, `04→3a99`,
  `08→3a40`, `10→3a75`, `20→3a51`, `40→3ab2`) each `JP 3b7a` (the routine
  `RET`). So `3a04`'s body legitimately spans `3a04-3b7a` and the cases
  are blocks.

* **Superseded Part-A names (12), deleted in Part B because they were
  case blocks, not functions (CONFIRMED — no external callers, grep
  verified no `doc/` refs):** `3a1c` `Field_FlagHandler3a1c`, `3b7a`,
  `3b53` `SessionCommandDispatchStub_3B53`, `581f`, `5991`, `62a9`,
  `62b6`, `62ca`, `66ec`, `6707`, `6b0d`, `6b53`.

* **Coverage now (CONFIRMED, Ghidra):** internal 1028 / guarded 1029
  total; auto `FUN_*` = **42** (ROM00 23, ROM01 17, ram 2); named
  **986 (95.9 % internal)**. ROM01 dropped 84→17; the 17 are the 12
  Part-A `(retain)` entries + 5 B1 `(retain)` shells. See
  `research/gap-analysis.md` headline + cluster section.

* **Flag for follow-up (OPEN):** Part A named dispatch-case targets of
  table `257f` as separate functions (`Field_StepForward 2569`,
  `Field_StepBackward 2572`, `Field_StepNoop 257b`, `Field_StepRender
  2593`) and `Field_FlagHandler3a1c`. Under this model those are LIKELY
  the same mis-split (Ghidra auto-functions at `JP(HL)` case targets)
  and should be audited in a later pass. Do NOT change them now.
  Discriminating check: whether the `257f` targets are `JP(HL)` case
  blocks of a table-owning routine (record the owning routine and that
  no external caller reaches the target except via the table).
  Added to open questions below.


## Resolved open questions

These items were moved from the `## Open questions` section of
`TASKS.md` when they were resolved.

### Original heading: Open questions / do-not-regress


* **RESOLVED 2026-09-18 — Part-A dispatch-case audit (was OPEN):**
  Part A had named `257f` case targets as separate functions
  (`Field_StepMode1 2569`, `Field_StepMode2 2572`,
  `Field_ApplyStepMode 2593` — previously `Field_StepForward` etc.,
  plus `Field_StepNoop 257b` and `Field_FlagHandler3a1c`). **CONFIRMED
  now:** they are blocks of the routine at `254b` (prologue
  `11 00 00 CD 37 D8` → `JP 257c` dispatcher → `2593` shared
  continuation → `RET 2658`). The earlier "audit `257f` OPEN" item is
  closed; the functions were absorbed/labelled in Half A (owner
  `14CF`/`10CF` region — exact owner/labels in
  `/tmp/opencode/rom01_dispatch_auditA.md`). The inline-switch cases
  are basic blocks, not functions (hybrid label model, standard).

* **RESOLVED 2026-09-18 — ROM00 dispatch audit (CONFIRMED):**
  ROM00 has **25 `CALL ram:e0b2` dispatch sites — all audited**
  (same hybrid as ROM01). Owners 23 routines (sites 8+9 share
  `Session_CmdCommand 4ae0-4d28`, sites 17+18 share
  `Session_CmdEndTx 52a5-5427`); key extents
  `Session_TxAppendString 3ede-3f1f`, `Session_CoroJumpTx 3f20-4009`,
  `Session_InitCommsCmd 4563-46e8`, `Session_InitState 46e9-47f5`,
  `Session_LogonMode0Or2Callback 47f6-48be`,
  `Session_CmdAnswer 48bf-4973`, `Session_CmdManual 4974-4a24`,
  `Session_CmdDropLine 4a25-4adf`, `Session_CmdCommand 4ae0-4d28`,
  `Session_CmdShutDown 4d75-4e6c`, `Session_CmdRxRec 4e6d-4f59`,
  `Session_ReceiveProgram 4f5a-5033`,
  `Session_CmdBeginFile 5034-50ec`, `Session_CmdTxRec 50ed-5178`,
  `Session_CmdEndFile 5179-51eb`, `Session_CmdTxBlk 51ec-52a4`,
  `Session_CmdEndTx 52a5-5427`, `Session_CmdAbort 5469-54e4`,
  `Session_RxRecord 5542-5668`, `Session_GetParamE520 56e7-573c`,
  `Session_AnswerConnect 573d-578e`,
  `Session_ManualConnect 578f-5829`, `Session_RxByteLoop 59fb-5b57`,
  `Session_TxStringSender 5f58-606b`; site-1 corrected to `3f20`
  (see below); ~89 case-block functions absorbed, ~113 labels
  created; residual ROM00 `FUN_*` = 5 deferred (`2da5`, `4333`,
  `441b`, `44ed`, `450d`). Full maps in Ghidra (labels) and audit
  notes.

---

## Dated session entries (continued)

### 2026-09-18 — ROM01 dispatch-case label model applied

* **Hybrid model now the standard (CONFIRMED).** Inline-switch
  dispatch (`CALL ram:e0b2` `Kernel_TableDispatch` + inline table +
  `JP(HL)`) cases are **basic blocks of the owning routine**, kept as
  one function; navigation is restored with **labels** (not functions)
  at each case target and shared continuation. Rationale: case blocks
  have no prologue and use the parent's frame, so naming them as
  functions asserts a false ABI; labels give the greppable name
  without that. Recorded in `re-notes/inline-dispatch.md` and
  `research/gap-analysis.md`. No new inference; no Ghidra edits in
  this docs pass — findings are parent-verified.

* **ROM01 dispatch audit complete — 14 sites = all ROM01
  `CALL ram:e0b2` sites (CONFIRMED).** Half A (7 owners, 27 case
  functions merged + labelled): `Program_LoadDipOrCom 0CE7-0FE5`,
  `Field_ResetCounterDispatch 10CF-1176`,
  `Session_AdvanceStageOnZero 14CF-153D`,
  `UI_FieldEditGetChoice 1D80-1FF2`, `Session_RxDispatch 2880-28FD`,
  `Session_ConnectCheck 2B43-2C4E`, `Session_CmdWalkTable 2C4F-2CD2`;
  40 labels + 37 EOL comments. Half B (7 already-merged sites
  `3b53`/`45d1`/`4a2d`/`581f`/`5991`/`5e2e`/`66ec`): 33 labels, no
  merges; `5e41` `CmdHandlerCount` renamed `FieldFormat_Default`.
  Guarded total 1028 → 1001 internal (1002 guarded). All owners
  byte-verified (`11 00 00 CD 37 D8` prologue → final `C9`); the two
  flagged external xrefs (`7571→0DEF`, `767D→10EF`) were confirmed
  descriptor-data misdecodes, not callers. Full maps in
  `/tmp/opencode/rom01_dispatch_auditA.md` and
  `/tmp/opencode/rom01_dispatch_auditB.md`.

* **Superseded Part-A separate-handler names — RESOLVED (CONFIRMED).**
  The `257f` handlers (`Field_StepMode1 2569`,
  `Field_StepMode2 2572`, `Field_ApplyStepMode 2593`) are blocks of
  the routine at `254b` (prologue) → `JP 257c` dispatcher → `2593`
  shared continuation → `RET 2658`. The earlier "audit `257f` OPEN"
  item is closed; the functions were absorbed/labelled in Half A
  (owner `14CF`/`10CF` region — exact owner/labels in the Half-A
  audit file). `Field_FlagHandler3a1c` likewise a case block.

* **Coverage now (CONFIRMED):** internal **1001** / guarded **1002**;
  auto `FUN_*` = **42** (ROM00 23, ROM01 17, ram 2); named **959
  (95.8 %)**. Updated in `research/gap-analysis.md` headline +
  paragraph (from 1028 / 42 / 986). Count dropped because 27
  dispatch-case functions were absorbed as labels — not a coverage
  loss.

* **Remaining (OPEN):** ROM00 has **25 `CALL ram:e0b2` dispatch sites
  not yet audited** (same hybrid to apply); record as the next
  structural item with site-list source (search `CALL 0xe0b2` in
  ROM00). See "Open questions" above.

* **Docs updated:** `research/gap-analysis.md` (headline, structural
  model, ROM01 label-pass section, remaining ROM00 note),
  `re-notes/inline-dispatch.md` (hybrid model standard),
  `research/TASKS.md` (this entry + resolved `257f` + ROM00 open).
  `mkdocs build --strict` (site_dir `site-mkdocs`) run; no Ghidra
  edits.

### 2026-09-18 — ROM00 Kernel_TableDispatch hybrid pass complete
(Ghidra saved, docs only in this pass, no new inference;
parent-verified)

* **ROM00 dispatch pass complete (CONFIRMED).** All 25 ROM00
  `CALL ram:e0b2` (`Kernel_TableDispatch`) sites audited and
  converted to the hybrid model: one function per
  prologue-delimited routine + **labels** at case
  targets/continuations.

* **Owners extended — 23 routines (CONFIRMED; sites 8+9 share
  `Session_CmdCommand 4ae0-4d28`, sites 17+18 share
  `Session_CmdEndTx 52a5-5427`).** Key extents:
  `Session_TxAppendString 3ede-3f1f`,
  `Session_CoroJumpTx 3f20-4009`, `Session_InitCommsCmd 4563-46e8`,
  `Session_InitState 46e9-47f5`,
  `Session_LogonMode0Or2Callback 47f6-48be`,
  `Session_CmdAnswer 48bf-4973`, `Session_CmdManual 4974-4a24`,
  `Session_CmdDropLine 4a25-4adf`, `Session_CmdCommand 4ae0-4d28`,
  `Session_CmdShutDown 4d75-4e6c`, `Session_CmdRxRec 4e6d-4f59`,
  `Session_ReceiveProgram 4f5a-5033`,
  `Session_CmdBeginFile 5034-50ec`, `Session_CmdTxRec 50ed-5178`,
  `Session_CmdEndFile 5179-51eb`, `Session_CmdTxBlk 51ec-52a4`,
  `Session_CmdEndTx 52a5-5427`, `Session_CmdAbort 5469-54e4`,
  `Session_RxRecord 5542-5668`, `Session_GetParamE520 56e7-573c`,
  `Session_AnswerConnect 573d-578e`,
  `Session_ManualConnect 578f-5829`, `Session_RxByteLoop 59fb-5b57`,
  `Session_TxStringSender 5f58-606b`. All owners byte-verified
  (`11 00 00 CD 37 D8` prologue → final `C9`); interiors
  discriminated by that prologue check.

* **Site-1 owner correction (CONFIRMED).** The audit first named
  `3ede` as owner of the `3fec` dispatcher, but `ROM00::3f20`
  (`Session_CoroJumpTx`) is itself a prologue entry
  (`11 00 00 CD 37 D8`) with real external callers (`5346`, `4c3a`,
  `ROM00::7dbe` vector, `ram:ed88`). Corrected: `3f20` is the
  dispatcher's owning routine (`3f20-4009`); `3ede` is a separate
  routine ending at `3f1f`.

* **Absorbed (CONFIRMED):** ~89 case-block functions deleted (12
  from the audit Deletion List + 77 interior blocks found by a
  prologue check). Discriminator: only real routine entries start
  with `11 00 00 CD 37 D8`; among all interiors only `3f20` did —
  all others were blocks (no external callers). ~113 labels created
  at case targets.

* **Coverage now (CONFIRMED, Ghidra):** internal **914** / guarded
  **915**; auto `FUN_*` = **24** (ROM00 5, ROM01 17, ram 2); named
  **890 (97.4 %)**. Updated in `research/gap-analysis.md` headline
  + paragraph (from 1001 / 42 / 959). Count dropped because ~89
  dispatch-case functions were absorbed as labels — not a coverage
  loss. ROM00 residual `FUN_*` = 5 deferred (`2da5`, `4333`,
  `441b`, `44ed`, `450d`).

* **Process note — do not regress (CONFIRMED):** `create_function`
  cannot extend a body past a computed jump; body extension must use
  Ghidra's `Function.setBody(AddressSet)` (script), and
  `FunctionManager.removeFunction` takes an entry **Address**, not a
  Function. The ROM00 pass was saved only after a manual `setBody`
  completion — the annotate stage left owners as 6-byte shells and
  2 epilogue functions were briefly lost, then recovered by the
  extension.

* **Remaining (OPEN) — updated 2026-09-18:** ROM01 and ROM00
  dispatch models are now both applied (CONFIRMED — 14 + 25
  sites). **10 retained `FUN_*`** (ROM00 1, ROM01 8, ram 1)
  with documented open questions plus the tail: only
  `ram:e020-e0aa` compiler-runtime plates (residual),
  `ROM00:7409`/`7472` module-A sites, and the code-gap tail
  remain (`ROM01:757F-768E` now done — see next entry).

* **Docs updated:** `research/gap-analysis.md` (headline + paragraph
  + new ROM00 section + remaining work), `re-notes/inline-dispatch.md`
  (ROM00 completed, residual note), `research/TASKS.md` (this entry
  + Open questions resolved + Do not regress process note).
  `mkdocs build --strict` (site_dir `site-mkdocs`) run; no Ghidra edits
  in this docs pass — findings are parent-verified.

### 2026-09-18 — residual `FUN_*` finished; `ROM01:7580`
data-typing unblocked (Ghidra saved; docs only in this pass, no
new inference; parent-verified)

* **Residual `FUN_*` pass complete (CONFIRMED, Ghidra saved).**
  24 targets: **14 renamed + plated, 10 retained with plates
  (symbols kept).**

  * **Renamed (14, CONFIRMED):**
    `Session_ConfigShow` (`ROM00:2DA5`),
    `Session_CoroYield` (`ROM00:4333`, prologue 5-byte
    `11 00 00 CD 37 D8`), `Session_Yield` (`ROM00:44ED`),
    `Session_CmdCommandYield` (`ROM00:450D`),
    `Session_ReturnTruePop` (`ROM01:0406`),
    `Session_SetEditState` (`ROM01:2132`),
    `Session_SetEditState2` (`ROM01:213F`),
    `Session_StoreFieldState` (`ROM01:2159`),
    `Session_StoreFieldState2` (`ROM01:216B`),
    `Session_HandleFieldNavRx` (`ROM01:2806`),
    `Field_ReturnOneStub1` (`ROM01:4A41`),
    `Field_ReturnOneStub2` (`ROM01:4A67`),
    `Field_ReturnOneStub3` (`ROM01:4B5F`),
    `Lib_Thunk_MemMove` (`ram:D7C5`).

  * **Retained (10, CONFIRMED retained, plates set, symbols
    kept) with documented open questions:**
    `ROM00:441B` (zero xrefs, dead coroutine yield);
    `ROM01:0904` (alignment padding `NOP; NOP; RET`);
    `ROM01:1177`/`156F`/`1664`/`168E`/`16B8` (compiler retain
    stubs reachable only via session-object dispatch — need
    vtable mapping);
    `ROM01:4D86`/`4E79` (text-buffer builders; compiler-frame
    args `SP+0x0E`–`0x16` undecoded);
    `ram:D937` (zero xrefs, dead stub).

  * **Correction applied during review (CONFIRMED):** the
    `Field_ValidateAlwaysPass*` name/evidence was wrong — the
    pointers sit at odd offsets (`ROM01:7E87`/`7E8B`/`7E8D`), so
    the names were changed to the mechanics
    `Field_ReturnOneStub1/2/3` and the table described as the
    `ROM01:7E87` pointer table. The "7E85 vtable" claim is
    **withdrawn**; the validator role is **SUSPECTED** only.
    `Session_CoroYield`'s prologue is the 5-byte
    `11 00 00 CD 37 D8` (CONFIRMED).

* **Data-typing tail — `ROM01:7580-7670` UNBLOCKED and applied
  (CONFIRMED, Ghidra saved).** Previously "blocked by tooling"
  (`apply_data_type` could not clear a multi-instruction range;
  the inline-script path was broken). Now fixed via an inline
  script using `Listing.clearCodeUnits(start,end,false)` +
  `ArrayDataType`:

  * `ROM01:757F-768E` is retyped `undefined[272]` with labels
    `tbl_UiCfgTemplates` (`757F`),
    `tbl_UiCfgNode0_DeviceSelect` (`758B`),
    `tbl_UiCfgNode1_BaudSelect` (`75EB`),
    `tbl_UiCfgNode2_Toggle` (`760D`),
    `tbl_UiCfgNode3_PortSelect` (`764F`),
    `tbl_UiCfgNode4_MasterConfig` (`7669`), and
    `str_cfg_option_pool` (`79F4`).

  * **Structure (CONFIRMED mechanics):** five variable-length UI
    form-template nodes (20-byte header
    `EC EF F8 F0 98 EF D8 EF` + fields + LE self-backlink at
    `+12h`) whose string pointers reference the shared option
    pool at `79F4-7A82` (`"PLINTH"`, `"V24 ADAPTOR"`,
    `"LOCAL LINK"`, baud rates, `ON`/`OFF`). Referenced from
    `Field_ConfigLoad` (`ROM01:05E0-06B0`) at `0620 LD HL,0x758B`,
    `0658 LD HL,0x75EB`, `066A LD HL,0x760D`.

  * **Unresolved (OPEN/SUSPECTED):** the `E1` prefix at `757F`,
    the `F479` header pointer (**SUSPECTED** bank-qualified),
    exact field semantics, and the end boundary above `768E`.

* **Coverage now (CONFIRMED, Ghidra):** internal **914** /
  guarded **915**; auto `FUN_*` = **10** (ROM00 1, ROM01 8,
  ram 1); named **904 (98.9 %)**. Updated in
  `research/gap-analysis.md` headline + paragraph (from
  914 / 24 / 890). The `ROM01:7580-7670` blocked item was
  removed from the remaining list.

* **Remaining tail — superseded 2026-09-18:** the code-gap
   sweep is now **complete (121 → 12)** — see next entry;
   no structural items remain beyond the 12 non-code
   gaps and the 4 documented `FUN_*` retains.

* **Docs updated:** `research/gap-analysis.md` (headline,
   paragraph, residual pass + `757F-768E` sections, remaining
   work), `research/TASKS.md` (this entry + remaining-tail
   update). No Ghidra edits in this docs pass; no new
   inference; evidence tags preserved.
   `mkdocs build --strict` (site_dir `site-mkdocs`) run.

### 2026-09-18 — tail: compiler-runtime plates, module-A
images, retained stubs resolved; code-gap model corrected
(docs only, no new inference, no Ghidra; parent-verified,
Ghidra saved)

* **Item A — compiler-runtime plates `ram:e020-e0aa`
  (CONFIRMED, Ghidra saved).** 7 plates added:
  `Lib_And16` (`e023`), `Lib_Or16` (`e033`),
  `Lib_Xor16` (`e03b`), `Lib_Lnot16` (`e043`),
  `Lib_SignedLe16` (`e06a`), `Lib_SignedGe16` (`e06b`),
  `Lib_SignedLt16` (`e086`). 6 others in the range were
  already plated.

* **Item B — module-A ROM images (CONFIRMED, Ghidra
  saved).** `ROM00:7409` and `ROM00:7472` are compiled-C
  prologues (`11 00 00 CD 37 D8`) with zero `ROM00`-space
  xrefs that reference `ram`-space addresses
  (`ram:d837`, `ram:e104`) — i.e. module-A code destined
  for battery RAM. Labelled as data
  (`tbl_ModuleA_RomImage_7409`,
  `tbl_ModuleA_RomImage_7472`); **no functions created**.
  Deferred by design (wrong address space if created in
  `ROM00`).

* **Item C — retained `FUN_*` resolved (CONFIRMED, Ghidra
  saved).** 6 renamed:
  `ROM01:156f`→`Session_Obj_Method_6784`,
  `1664`→`Session_Obj_Method_6b6d`,
  `168e`→`Session_Obj_Method_6c84`,
  `16b8`→`Session_Obj_Method_696f` (each prologue → `CALL`
  a work function → tail-call `ROM01:1548`),
  `4d86`→`Session_Obj_BuildTextBuf1`,
  `4e79`→`Session_Obj_BuildTextBuf2` (text-buffer builders,
  `COMPUTED_CALL` from `ROM01:7f1d`/`7f1f`). 4 retained
  with plates: `ROM01:1177` (trivial stub),
  `ROM00:441b` (zero-xref dead, sibling `443c` used),
  `ram:d937` (zero-xref bit-flag dispatcher over
  `ram:e104`), `ROM01:0904` (alignment padding).

* **Coverage now (CONFIRMED, Ghidra):** internal **914** /
  guarded **915**; auto `FUN_*` = **4** (ROM00 1,
  ROM01 2, ram 1); named **910 (99.6 %)**. Updated in
  `research/gap-analysis.md` headline + paragraph (from
  914 / 10 / 904).

* **Code-gap model corrected — record prominently (do not
  regress) (CONFIRMED).** `find_code_gaps` reports 121
  gaps (~13.6 KB) in `ROM01`/`ROM00`. A first-pass
  classification labelled ~83 as "real missed functions",
  but this is **WRONG**: spot-check showed e.g.
  `ROM01:1b83` is the **body continuation** of
  `UI_RecordEditModal` (a 6-byte `11 00 00 CD 37 D8`
  prologue shell at `1b7d`), not a new function. The gaps
  are overwhelmingly **truncated-body continuations** of
  the preceding compiled routine (the same idiom as the
  Part A/B shell extensions). Correct action per gap: if
  the gap start lacks the `11 00 00 CD 37 D8` prologue
  it is a continuation → **extend the preceding
  function's body** (via `ExtendFunctionBody.java`); if it
  has the prologue it is a separate routine; if it decodes
  as strings/pointer tables it is data (e.g.
  `ROM01:73E4-7FFF` is the UI/config data region, not
  code). **Do NOT create functions from this list.** This
  correction was made by the parent before any mass write,
  and nothing was mass-applied.

* **Remaining (OPEN) — updated 2026-09-18:** code-gap
  sweep complete (121 → 12) — no structural items
  remain beyond the 12 non-code gaps and the 4
  documented `FUN_*` retains; see next entry.

* **Docs updated:** `research/gap-analysis.md` (headline +
  paragraph + tail + code-gap model sections + remaining
  work), `research/TASKS.md` (this entry + remaining
  line). No Ghidra edits; no new inference; evidence
  tags preserved; ~70-col wrapping.
  `mkdocs build --strict` (site_dir `site-mkdocs`) run.

### 2026-09-18 — code-gap sweep complete (121 → 12;
truncated-body continuations absorbed)

* **Code-gap sweep complete (CONFIRMED, Ghidra saved).**
  `find_code_gaps` dropped **121 → 12**. The gaps were
  overwhelmingly **truncated-body continuations** of
  compiled routines — Ghidra stopped at the
  non-returning `CALL ram:d837`, leaving a 6-byte
  prologue shell (`11 00 00 CD 37 D8`) — **not** new
  functions.

  Applied (count unchanged, internal 914):

  * **209 shells extended** to their continuation (gap
    ends in `RET`, no prologue inside) via
    `Function.setBody` (`ExtendFunctionBody.java`);
  * **4 tail-`JP` continuations extended**
    (`ROM01:254b`→`2568`, `2659`→`2805`,
    `2e6f`→`2f74`, `07ee`→`0903`) — these end in a
    tail-call `JP` rather than `RET`, so the first
    pass missed them;
  * **`ROM01:73de` `UI_TableRenderRev` extended to
    `7544`** (its continuation; `73e4` is not a
    function entry but the body after the shell
    prologue).

  **No functions created or deleted**; count
  unchanged (internal 914).

* **Remaining 12 gaps — all non-code, expected**
  (CONFIRMED):

  * six page-zero RST-vector areas
    (`ROM01:0001-0007`, `000b-001f`, `0023-0027`,
    `002b-002f`, `0033-0037`, `003b-00ff`);
  * `ROM01:257c-2592` — the inline
    `CALL ram:e0b2` dispatcher belonging to the
    `254b` routine;
  * small padding/data (`03e9-0405`, `09c8-09d0`,
    `09ee`, `6f60`);
  * `ROM01:7545-7FFF` — the UI/config data region
    (descriptors/strings/tables, partly typed:
    `tbl_UiCfgTemplates` at `757F`,
    `str_cfg_option_pool` at `79F4`, etc.).

  These are data/vector regions, not missed code,
  and `find_code_gaps` flags uncovered executable
  memory including data.

* **Model — do not regress (CONFIRMED):** code gaps
  in this firmware are truncated-body continuations;
  the correct fix is **body extension**
  (`ExtendFunctionBody.java` / `Function.setBody`),
  never creating functions from the gap list.
  Discriminator: gap start lacks the
  `11 00 00 CD 37 D8` prologue → continuation; a
  continuation may end in `RET` or a tail-`JP`.

* **Coverage unchanged (CONFIRMED):** internal 914 /
  guarded 915; auto `FUN_*` = 4; named 910
  (99.6 %). The sweep changed function *bodies*,
  not the count.

* **Remaining (CONFIRMED):** no structural analysis
  items remain beyond the 12 non-code gaps and the
  4 documented `FUN_*` retains. Dispatch models
  (ROM01 14 + ROM00 25) and code-gap sweep are
  closed.

* **Docs updated:** `research/gap-analysis.md`
  (headline, code-gap sweep 121→12, remaining
  gaps, model, remaining work),
  `research/TASKS.md` (this entry). No Ghidra
  edits; no new inference; evidence tags
  preserved; ~70-col wrapping.
  `mkdocs build --strict` (site_dir `site-mkdocs`)
  run.

### 2026-09-19 — §12 FINAL PASS items 2b + 3 (5 wrong
names renamed, 144 unplated functions plated)

* **Item 3 — plate-quality, unplated functions DONE
  (CONFIRMED, Ghidra saved, no function renamed/
  created/deleted in that batch).** All 144 functions
  with `plateLen=0` now carry plates: 46 `ram` (mostly
  `SessionOpStub_*`/`Lib_*`/`RegFile_*`; notable
  `Fcb_ParseFilename` CP/M FCB parser,
  `Kernel_RunStagedCall`), 33 `ROM00`, 65 `ROM01`.
  **Plate coverage is now 100 %** (no function lacks a
  plate). A pre-existing set of ~141 plates <120 chars
  still needs the §8 full-form review (brief purpose /
  mechanics / In-Out-Clobbers / evidence tag, ~70 cols,
  multi-line ASCII) — recorded as **OPEN** in §12.

* **Item 2b — wrong names, 5 renamed + docs synced
  (CONFIRMED, byte-verified, Ghidra saved).**
  `ROM00:3BB8` `Coroutine_TaskSwitch` →
  `Coroutine_IndexedLookup_6A4A` (indexed lookup into
  table at `6A4A`, not a task switch; real
  `Coroutine_Enter` is `ram:D837` — duplicate
  mis-name corrected; `ram:D837` later renamed
  `Coroutine_Enter` 2026-09-19), `ROM00:3BD0`
  mis-name corrected), `ROM00:3BD0`
  `Coroutine_SessionMul16` →
  `Coroutine_IndexedLookup_6B67` (into `6B67`),
  `ROM00:7C14` `Session_Cmp16Bit` → `Session_CmpLeU16`
  (HL=1 iff HL<=DE unsigned), `ROM00:7C22`
  `Session_Cmp16BitB` → `Session_CmpGtU16` (HL=1 iff
  HL>DE unsigned), `ROM01:6F29`
  `Syscall_Call_Id2Byte` → `ServiceCall_BdosFn2` (calls
  `Session_BdosCall` `ram:DA13` with fn 2).
  `doc/research/TASKS.md` mentions updated; grep
  confirms 0 stale mentions in `doc/` for the 5 old
  names. Rename hygiene per AGENTS.md §7 (symbol +
  plate + docs + TASKS in one pass).

* **Item 2a — mass rename of ~487 grandfathered
  CamelCase + lowercase-legacy names to `Module_Name`
  style NOT done — OPEN by owner decision per
  AGENTS.md §7.** Deliberately deferred as the owner's
  repo-wide pass; a wrong piecemeal mass rename is
  worse than none. Recorded as **OPEN** in §12
  remaining scope.

* **Item 4 — comment-style pass NOT done — OPEN.**
  Migrating raw-address cites to labels, decoding
  remaining magic numbers/masks in place, dropping
  opcode-restating comments per §8 — recorded as
  **OPEN** in §12 remaining scope.

* **§12 remaining scope after this pass:** item 2a
  (mass rename, owner), item 3 short-plate review
  (~141), item 4 (comment-style). Items 2b and 3
  (unplated) are closed; data-typing and gap-analysis
  items remain as previously closed.

* **Docs updated in this pass:** `research/TASKS.md`
  (§12 scope updated, §12 2026-09-19 entry,
  `ram:D837` duplicate-name correction,
  `Syscall_Call_Id2Byte`/`Session_Cmp*` sync),
  `research/gap-analysis.md` (headline 2026-09-19,
  plate coverage 100 % with breakdown, remaining
  annotation tail), `re-notes/open-questions.md`
  (`ram:D837` filing resolved). No Ghidra edits in
  this docs pass; no new inference; evidence tags
  preserved; ~70-col wrapping. `mkdocs build
  --strict` (site_dir `site-mkdocs`) run — see
  below.

### 2026-09-19 — §12 item 2a mass rename (590 names
→ 31-module Module_Name taxonomy)

* **Item 2a — mass rename DONE 2026-09-19 (590
  names → 31-module `Module_Name` taxonomy; 588
  applied in Ghidra + 2 already-renamed
  collisions; word-boundary doc sync across 24
  files, commit `993a45d`; CONFIRMED):** canonical
  taxonomy `Session_` `Bdos_` `Fs_` `Lib_` `Link_`
  `UI_` `Syscall_` `Field_` `RegFile_` `Lcd_`
  `Program_` `Disk_` `Tty_` `RTC_` `ExtBus_`
  `Diag_` `Kernel_` `KernelImage_` `Kbd_`
  `Device_` `Dialog_` `Text_` `Comms_` `Clock_`
  `Power_` `Util_` `Coroutine_` `Monitor_`
  `SelfTest_` `Sound_` `Fcb_` `Form_` `Boot_`
  `Barcode_` (31 modules); normalizations
  `Kern*`→`Kernel_`, `Rtc*`→`RTC_`, `Ui*`→`UI_`
  (owner choice, uppercase per AGENTS.md §7),
  `lcd_*`→`Lcd_`, `tty_*`→`Tty_`,
  `dialog_*`→`Dialog_`, `session_*`→`Session_`,
  `Coro*`→`Coroutine_`, `Keyboard*`/`Key*`→`Kbd_`,
  `Reg*`→`RegFile_`, `Self*`→`SelfTest_`;
  reassignments `Banked*`→`Kernel_`,
  `Console*`→`Device_`, `Delay*`→`Util_`,
  `Str*`/`Arith*`/`Bcd*`/`Checksum*`/`Format*`/
  `Num*`/`Pack*`/`Table*`→`Lib_`,
  `BlockAlloc*`/`FileSearch*`→`Fs_`,
  `StateWord*`/`CmdDispatch*`→`Session_`,
  `ServiceCall*`/`thunk_*`→`Syscall_`,
  `Nop*`→`Diag_`, `TemplateBuilder`→`Form_`,
  `Port2b*`→`Sound_`, `ExtDecodeHook*`→`ExtBus_`,
  `Descriptor*`→`UI_`; do-not-regress identities
  preserved (`RTC_`, `Link_`, `Session_`,
  `ExtBus_`); protected exact names kept
  (`BankedRst08/20/28/30/38`,
  `Rst2Dispatch`/`Rst4IrqPoll`/
  `Rst5FatalScreen`/`Rst6ZeroRet`/`Rst7IrqPoll`,
  `ColdStartSelfTestBanner`,
  `LinkRxDispatcher`); docs name-synced across
  24 files (word-boundary replace).

* **Item 4 — scope quantified 2026-09-19
  (CONFIRMED count; OPEN):** of 895 instruction
  comments, **356 carry raw-address-like tokens**
  (hex/address cites that §8 says should be
  descriptive labels, not bare addresses) — not
  yet migrated; also pending: decoding remaining
  magic numbers/masks in place and dropping
  opcode-restating comments per §8 anti-patterns.
  Recorded as **OPEN** with the 356 figure in §12.

* **§12 remaining scope after this pass:** item 3
  short-plate review (~141), item 4 comment-style
  (356 raw-address comments + magic-number/
  opcode-restating cleanup). Item 2a is **DONE**;
  items 2b and 3 (unplated) already closed.

* **Docs updated in this pass:** `research/TASKS.md`
  (§12 item 2a DONE with 31-module taxonomy +
  normalizations/reassignments, §12 item 4 quantified
  356, §12 remaining scope updated, this 2026-09-19
  entry), `research/gap-analysis.md` (annotation
  tail updated — item 2a DONE, item 4 with 356).
  No Ghidra edits; no new inference; evidence
  tags preserved; ~70-col wrapping. `mkdocs build
  --strict` (site_dir `site-mkdocs`) run — see
  below.

### 2026-09-19 — §12 item 4 comment-style
 (raw-address cites migrated; 137 rewrites)

* **Item 4 comment-style — raw-address cites
  migrated (CONFIRMED, Ghidra saved; 137 REWRITE
  / 219 KEEP of 356 flagged; function list
  unchanged; 0 new labels needed).** Of 356
  flagged instruction comments, a re-verified pass
  classified **137 REWRITE** (comments citing a RAM
  cell or I/O port by numeric address, now replaced
  with the descriptive label) and **219 KEEP** (the
  flagged token was a value/mask, legitimate
  cross-reference target, or label already present).
  All 137 applied in Ghidra; function list
  unchanged; 0 new labels needed (every cited
  address already had a documented label).

* **Residual within item 4 (still OPEN):** (a) some
  rewrites still contain a secondary raw address
  (e.g. `(0006)` survived alongside the replaced
  `d682`); (b) decoding remaining magic numbers /
  bit masks in place; (c) dropping comments that
  merely restate the opcode. These are the
  remainder of the comment-style pass.

* **CAUTION recorded (CONFIRMED):** 2-digit hex in
  RTC contexts is ambiguous — an RTC register index
  (`01h`/`03h`/`05h`/`07h`) is not the I/O port of
  the same number (`07h` = `CTRL_07`);
  `RTC_ADDR`/`RTC_DATA` are `08h`/`28h`; the pass
  corrected these manually. Note this hazard for
  any future comment edit.

* **§12 remaining scope after this pass:** item 3
  short-plate review (~141), item 4 residual —
  secondary raw addresses, magic-number / bit-mask
  decoding, opcode-restating comments.

* **Docs updated in this pass:** `research/TASKS.md`
  (§12 item 4 PARTIALLY DONE + CAUTION + remaining
  scope updated, this 2026-09-19 entry),
  `research/gap-analysis.md` (annotation tail
  updated — item 4 raw-address cites migrated with
  137/219 split + residual + CAUTION). No Ghidra
  edits; no new inference; evidence tags preserved;
  ~70-col wrapping. `mkdocs build --strict`
  (site_dir `site-mkdocs`) run — see below.

### 2026-09-19 — §12 item 3 short-plate review
 (141 reviewed: 82 KEEP / 59 upgraded)

* **Item 3 short-plate review complete (CONFIRMED,
  Ghidra saved; function list unchanged; no new
  inference).** All **141** functions with plates
  <120 chars were reviewed against §8: **82 KEEP**
  (genuinely trivial — math primitives,
  comparators, simple port I/O, single-RET stubs,
  RST vectors, constant-return helpers, simple
  RAM-cell setters, no-op coroutine stubs) and
  **59 UPGRADE** to the full form
  (brief/mechanics/In-Out-Clobbers/evidence tag,
  ~70 cols, multi-line ASCII). The 59 were applied
  in Ghidra; function list unchanged; saved.
  Typical upgrades: `Lib_MemMove`,
  `Bdos_PreparedCall`, the `RegFile_*` 32-bit math,
  `Lib_Mulu16`/`Mul16Mod16`, session buffer ops
  (`Session_TxFlush`, `Session_RxRefill`,
  `Session_TxAppendByte`, `Session_RxConsumeByte`),
  TTY key handlers, LCD helpers, message-box
  displays, link init/timeout, clock repack, UI
  descriptor-chain ops.

* **Item 3 is now DONE (CONFIRMED):** plate coverage
  **100 %**, no SHORT-form plate remains that §8
  would reject.

* **§12 remaining scope after this pass:** **only
  item 4 residual** — secondary raw addresses
  surviving a rewrite (e.g. `(0006)` alongside
  replaced `d682`), magic-number / bit-mask
  decoding, opcode-restating comments per §8.

* **Docs updated in this pass:** `research/TASKS.md`
   (§12 item 3 DONE — short-plate review
   141: 82 KEEP / 59 upgraded; §12 remaining scope
   narrowed to only item 4 residual; this
   2026-09-19 entry), `research/gap-analysis.md`
   (headline + plate coverage + annotation tail
   updated — item 3 DONE, 141 reviewed
   82/59, no SHORT-form remains). No Ghidra edits in
   this docs pass; no new inference; evidence tags
   preserved; ~70-col wrapping. `mkdocs build
   --strict` (site_dir `site-mkdocs`) run — see
   below.

### 2026-09-19 — §12 item 4 residual (127 more comments
 rewritten; item 4 substantially done)

* **Item 4 residual complete (CONFIRMED, Ghidra
   saved; function list unchanged; no new inference).**
   A second pass found **127 instruction comments**
   that still contained a numeric address cite
   resolving to a labelled address (secondary cites
   left by the first 137-rewrite pass, plus others).
   All 127 were rewritten: every address cite
   replaced with its descriptive label, remaining
   magic numbers / bit masks decoded in place,
   opcode-restating text dropped; function list
   unchanged; saved; no new labels needed.

* **Two review notes from the pass (CONFIRMED):**
   (a) `ROM00:F180` is unlabelled and a label
   `bdos_entry_impl` was proposed (not yet applied);
   (b) the comment at `ROM00:0178` said "keyboard
   scan init" but the confirmed plate at `Lcd_Init`
   (`ROM00:1EEC`) says LCD subsystem init, so the
   old comment was factually wrong and was corrected.
   RTC 2-digit ambiguity was handled (register
   indices not confused with ports).

* **Item 4 is now substantially DONE (CONFIRMED):**
   raw-address cites (137 + 127) migrated;
   magic-number decoding and opcode-restating
   cleanup applied across both passes. Remaining
   **OPEN (minor):** the `bdos_entry_impl` label
   proposal for `ROM00:F180`, and any deeper
   magic-number decoding in comments not covered
   by the two scans.

* **Docs updated in this pass:** `research/TASKS.md`
    (§12 item 4 SUBSTANTIALLY DONE — 264 rewrites
    with breakdown + review notes + CAUTION retained
    + remaining scope narrowed to two minor items;
    this 2026-09-19 entry), `research/gap-analysis.md`
    (annotation tail updated — item 4 substantially
    done, 137+127 migrated, residual narrowed).
    No Ghidra edits in this docs pass; no new
    inference; evidence tags preserved; ~70-col
    wrapping. `mkdocs build --strict` (site_dir
    `site-mkdocs`) run — see below.

### 2026-09-19 — §12 item 4 residual: missing comment
 labels (90 created; 4 unresolved; Boot_entry+1 bug)
 (Ghidra saved; docs only in this pass, no new
 inference; parent-verified)

* **Missing-label residual addressed (CONFIRMED,
   Ghidra saved; function list unchanged; no new
   inference).** Scanning all instruction comments for
   label-like tokens (`g_*`, `tbl_*`, `str_*`,
   `bdos_*`, `Boot_*`) found **99 distinct
   descriptive labels cited in comments that had no
   Ghidra symbol**. **95** were resolved to concrete
   addresses (from the referencing instructions +
   `memory-map.md`/`unbanked-ram-map.md`); **90 were
   created as labels in Ghidra** (6 were already
   present), function list unchanged, saved
   (CONFIRMED).

* **4 labels remain UNRESOLVED (SUSPECTED, address
   not pinned; each needs the specific path read to
   confirm) — OPEN:** `g_bEchoChar` (SUSPECTED
   `F954`, may share with `g_bRxRingHead`),
   `g_bIrStrobeShadow` (SUSPECTED `F796`),
   `g_bOutputCount` (SUSPECTED `F998`),
   `g_wCoroutineStepResult` (SUSPECTED `E73E`,
   `SP+0E` indirection).

* **New issue found — `Boot_entry+1` bug (OPEN,
   CONFIRMED mechanics).** `Boot_entry` exists at
   `ROM00:014b`, but several comments written during
   the comment-style pass use `Boot_entry+1` to mean
   address `0001` — which is wrong (`Boot_entry+1`
   = `014c`). These comments need correcting to a
   correct label for `0000`/`0001` (e.g. a
   `reset_entry`/page-zero label) or back to the
   address. Record as an **OPEN** sub-item of item
   4; specific comment addresses to be enumerated
   and fixed in the next comment pass.

* **TASKS.md:** this entry added and §12 remaining
   scope updated to: the 4 unresolved labels, the
   `Boot_entry+1` comment corrections, and any deeper
   magic-number decoding in comments not covered by
   the two scans. `bdos_entry_impl` proposal for
   `ROM00:F180` remains OPEN alongside these.

* **Docs updated in this pass:** `research/TASKS.md`
   (§12 item 4 updated with missing-label 99→95→90
   + 4 UNRESOLVED + `Boot_entry+1` OPEN + §12
   header/remaining-scope refreshed; this 2026-09-19
   entry), `research/gap-analysis.md` (annotation
   tail updated — item 4 now includes 90 created,
   4 UNRESOLVED, `Boot_entry+1` OPEN). No Ghidra
   edits in this docs pass; no new inference;
   evidence tags preserved; ~70-col wrapping.
   `mkdocs build --strict` (site_dir `site-mkdocs`)
   run — see below.

### 2026-09-19 — §12 item 4 residuals closed (3 labels pinned,
 7 Boot_entry fixes, 5 magic numbers decoded) (Ghidra
 saved; docs only in this pass, no new inference;
 parent-verified)

* **Missing-label residual CLOSED except one OPEN
   (CONFIRMED, Ghidra saved; function list unchanged;
   no new inference).** Of the 4 SUSPECTED labels from
   the 99→90 scan, **3 pinned:** `g_bRxRingHead`
   already at `ram:F954` (verified, skipped — no new
   symbol; the `g_bEchoChar` SUSPECTED at same address
   was a mis-identification), `g_bLinkCmdShadow`
   created at `ram:F796` (port `4Ch` `LINK_CMD` shadow;
   supersedes `g_bIrStrobeShadow` SUSPECTED at same
   address), `g_bOutputCount` created at `ram:FEA3`
   (supersedes `g_bOutputCount` SUSPECTED `F998` —
   correct address is `FEA3` per byte-verified
   reference). **1 remains OPEN:**
   `g_wCoroutineStepResult` SUSPECTED `E73E`
   **UNRESOLVED** — zero references program-wide
   (CONFIRMED); `EA24 = g_pCoroutineStepResultBuf` is
   CONFIRMED, but `E73E` could not be pinned without
   tracing indirect writes to `EA24` (the only OPEN
   label).

* **`Boot_entry+1` bug FIXED (CONFIRMED, Ghidra saved).**
   7 comments corrected at `ROM01:1ea1`, `1f96`, `28bb`,
   `2b7b`, `2c95`, `3acb`, `ram:d777` — each cited
   `Boot_entry+1` to mean `0001h` (wrong; `Boot_entry`
   is `ROM00:014b`, so `Boot_entry+1 = 014c`);
   rewritten to `0001h` (intended page-zero cell; note
   CP/M IOBYTE is at `0003h`, not `0001h`). 3 non-buggy
   uses of `Boot_entry` retained (range marker / state
   name) — no change. The `Boot_entry+1` bug is now
   CLOSED.

* **Magic numbers decoded (CONFIRMED, Ghidra saved).**
   5 comments decoded at `ROM00:15c4`, `02e5`, `02f1`,
   `0f37` (PRE) and one more — `0x80` = local-console
   flag, `10h` = 16-drive guard, `12h`/`01h` = key scan
   codes, coroutine step-zeroed slots (per-site as
   applied); 12+ comments kept as already adequately
   explained (CONFIRMED); one intended fix at
   `ROM01:6e8b` had no comment present — skipped
   (CONFIRMED absent).

* **§12 item 4 is now CLOSED** except the single OPEN
   `g_wCoroutineStepResult` label. Items 1, 2a, 2b, 3,
   5, 6 are DONE. The `bdos_entry_impl` proposal for
   `ROM00:F180` is tracked separately and is not a §12
   item.

* **TASKS.md:** this entry added and §12 remaining scope
   narrowed to: **only** the `g_wCoroutineStepResult`
   label (`E73E` UNRESOLVED; `EA24` pointer
   `g_pCoroutineStepResultBuf` is CONFIRMED and is the
   lead for any future trace of indirect writes to
   resolve it).

* **Docs updated in this pass:** `research/TASKS.md`
    (§12 item 4 CLOSED except the single OPEN
    `g_wCoroutineStepResult`; remaining-scope refreshed;
    this 2026-09-19 entry), `research/gap-analysis.md`
    (headline + annotation tail updated — item 4 CLOSED,
    3 labels pinned, 7 Boot_entry fixes, 5 magic numbers
    decoded, only `g_wCoroutineStepResult` remains OPEN).
    No Ghidra edits in this docs pass beyond the saved
    labels/comments above; no new inference; evidence
    tags preserved; ~70-col wrapping. `mkdocs build
    --strict` (site_dir `site-mkdocs`) run — see below.

### 2026-09-19 — §12 final OPEN label closed
 (g_wCoroutineStepResult is pointer-indirected)
 (Ghidra saved; docs only in this pass, no new
 inference; parent-verified)

* **`g_wCoroutineStepResult` — RESOLVED
   (CONFIRMED): not a fixed RAM address.** It names
   the buffer pointed to by `g_pCoroutineStepResultBuf`
   at `ram:EA24`. Traced: exactly **one writer**
   (`ROM01:6DF6 LD (0xEA24),HL`, HL from the coroutine
   frame allocator `ROM01:6909` →
   `Coroutine_Enter`) and **six readers**, all in
   `Fs_SeekByteOffset` (`ROM01:6DDF-6EED`). Buffer
   layout: offset `+1` = 16-bit step-1 result, offset
   `+3` = 16-bit step-2 result, offset `+0`
   unreferenced. `ram:E73E` has **zero references
   program-wide** — the earlier `E73E` hypothesis is
   **refuted** (CONFIRMED).

* **Applied (CONFIRMED, Ghidra saved; function list
   unchanged):** `g_pCoroutineStepResultBuf` label
   created at `ram:EA24` with a repeatable comment
   ("Pointer to coroutine step-result workspace
   buffer (offsets +1/+3 hold 16-bit step results).");
   the four EOL comments at `ROM01:6E8F`/`6E9E`/
   `6EBB`/`6ED8` rewritten from `g_wCoroutineStepResult`
   to the `[*(g_pCoroutineStepResultBuf)+N]`
   pointer-dereference form. No function renamed;
   function list unchanged; saved.

* **§12 FINAL PASS is now fully CLOSED (CONFIRMED)**
   — no OPEN items remain (items 1, 2a, 2b, 3, 4, 5,
   6 done). The `g_wCoroutineStepResult` label was
   the final OPEN item; the earlier `E73E` hypothesis
   is refuted and superseded by the `EA24` pointer-
   indirected model.

* **Docs updated in this pass:** `research/TASKS.md`
    (this entry + §12 item 4 marked fully CLOSED and
    remaining scope emptied; E73E hypothesis noted as
    refuted), `research/gap-analysis.md` (headline +
    annotation tail updated — §12 fully CLOSED, no
    OPEN labels; `g_wCoroutineStepResult` RESOLVED
    pointer-indirected, E73E refuted). No Ghidra edits
    in this docs pass beyond the saved label/comments
    above; no new inference; evidence tags preserved;
    ~70-col wrapping. `mkdocs build --strict`
    (site_dir `site-mkdocs`) run — see below.

### 2026-09-19 — page-zero comment corrections
 (bdos_entry_impl rejected; Boot_entry
 over-substitution fixed) (Ghidra saved; docs only
 in this pass, no new inference; parent-verified)

* **`bdos_entry_impl` proposal — REJECTED
   (CONFIRMED, byte-verified, Ghidra saved; no new
   label needed).** `ROM00:0005` is `C3 80 F1` =
   `JP F180` (CONFIRMED, byte-verified); `F180`
   lies outside `ROM00`'s `0000h..7FFFh` 32K bank
   window, so it targets the RAM-resident kernel at
   `ram:F180`, whose existing label is
   `Bdos_DispatchFn` (CONFIRMED, existing symbol).
   The phantom `ROM00:bdos_entry_impl` at `F180`
   was a wrong-space invention — `F180` cannot be
   in `ROM00` — and is **REJECTED** (CONFIRMED).
   The Ghidra comment at `ROM00:0005` now reads
   `JP Bdos_DispatchFn (ram:F180) vectors into the
   DIPOS kernel (battery RAM)`; no new label was
   created. The non-§12 `bdos_entry_impl` proposal
   tracked alongside §12 is now **closed as
   REJECTED**; correct label remains the existing
   `Bdos_DispatchFn` at `ram:F180` (Ghidra saved).

* **`Boot_entry` over-substitution — FIXED
   (CONFIRMED, Ghidra saved; 4 comments).**
   `Boot_entry` is `ROM00:014b` (CONFIRMED). An
   earlier comment-style pass replaced literal
   `0000` with `Boot_entry` in four comments where
   `0000` was not the boot entry: two were
   **memory-range starts** at `ROM00:0000` and
   `ROM00:17d3` — restored to
   `0000h..ROM00:7FFFh` (CONFIRMED); two were
   **state identifiers** at `ROM00:5c1f`/`5d05` —
   restored to `State-0000` (CONFIRMED). All four
   corrected (Ghidra saved); no function
   renamed/created/deleted. Distinct from the
   earlier 7-comment `Boot_entry+1` → `0001h` fix
   (already CLOSED).

* **§12 FINAL PASS — remains fully CLOSED
   (CONFIRMED).** This was cleanup of the last
   page-zero comment artefacts; items 1, 2a, 2b, 3,
   4, 5, 6 remain **DONE**, no OPEN items remain,
   and no Ghidra inference was performed in this
   pass. Gap-analysis tail and §12 item-4 /
   remaining-scope wording already carried the
   pre-cleanup CLOSED state — this entry only
   corrects the artefact comments and the rejected
   phantom proposal; §12 is not reopened.

* **Docs updated in this pass:** `re-notes/
   cp-m-comparison.md` (BDOS entry corrected to
   `JP Bdos_DispatchFn (ram:F180)` with
   byte-verified `C3 80 F1` and REJECTED phantom
   note), `research/TASKS.md` (§12 item-4 and
   remaining-scope `bdos_entry_impl` notes updated
   to REJECTED/CLOSED + this 2026-09-19 entry),
   `research/gap-analysis.md` (annotation tail
   `bdos_entry_impl` proposal → REJECTED, CLOSED).
   No Ghidra edits beyond the saved comments above;
   no new inference; evidence tags preserved;
   ~70-col wrapping. `mkdocs build --strict`
   (site_dir `site-mkdocs`) run — see below.

### 2026-09-19 — da13 semantics resolved
 (session-to-BDOS bridge; 6A36 constructor /
 6AA9 stream-reader) (Ghidra saved; docs only
 in this pass, no new inference;
 parent-verified, byte-verified)

* **`ram:DA13` RESOLVED (CONFIRMED,
  byte-verified) — session-to-BDOS bridge.**
  Copies function number → C and argument → DE
  from the session register file (`E0FE`/`E100`,
  populated from the stack by `ram:D86E`), issues
  `CALL 0005`, returns BDOS A zero-extended in
  HL. Staged-op wording superseded; plain BDOS
  `CALL 0005` is the mechanism.

* **`ROM01:6A36` = record constructor
  (CONFIRMED).** Writes a record via BDOS
  `0x22` Write Random at `ROM01:6A85`-`6A89`;
  stores the caller key at record+0x26; called
  from the write path `Fs_WriteBytes` at
  `ROM01:6D58`.

* **`ROM01:6AA9` = record stream-reader
  (CONFIRMED).** Reads a record via BDOS `0x21`
  Read Random at `ROM01:6AFB`-`6AFF` with an
  `E986`/`E992` key cache (cache hit
  short-circuits the call); called from the read
  path `Fs_ReadBytes` at `ROM01:6BD8`.

* **Plates updated in Ghidra (CONFIRMED,
  byte-verified) for `ram:DA13`,
  `ROM01:6A36` (staged-op wording corrected to
  plain BDOS `CALL 0005`), and `ROM01:6AA9`.**
  Function list unchanged; saved.

* **TASKS.md:** closed the `da13` OPEN item
  wherever it appeared — `Next` no-hardware
  priority 1 marked RESOLVED 2026-09-19
  (CONFIRMED) with contract + 6A36/6AA9 mapping
  and removed from the remaining backlog;
  renumbered/refreshed `Next` no-hardware
  priorities so the former item 2 (loader staging
  cell) is now the top item; removed the
  "Still OPEN: da13" text. Added this session
  entry.

* **Docs updated in this pass:** `research/
  TASKS.md` (this entry + `Next` priorities
  refreshed/renumbered + `ram:da13` In-progress
  bullet updated to RESOLVED bridge + "Still
  OPEN: da13" text marked RESOLVED). No Ghidra
  edits in this docs pass beyond the saved plates
  above; no new inference; evidence tags
  preserved; ~70-col wrapping. `mkdocs build
  --strict` (site_dir `site-mkdocs`) run — see
  below.

### 2026-09-19 — loader staging cell resolved
 (D36A pointer protocol; five targets) (Ghidra
 saved; docs only in this pass, no new
 inference; parent-verified, byte-verified)

* **Loader staging cell RESOLVED 2026-09-19
  (CONFIRMED, byte-verified) — the `ram:D36A`
  pointer protocol; five targets.** The
  "staging cell" is the `ram:D36A` pointer
  protocol: the loader sets `D36A` (pointer),
  `D36C` (count), `D368` (dest offset) and `D393`
  (limit), yields via `ram:D370`, and
  `Program_ConsumeInputChunk`
  (`ROM01:0BAC-0C9A`) copies `min(D36C,D393)`
  bytes FROM `D36A` TO `ECD8+D368` (CONFIRMED,
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
  unchanged, saved (Ghidra saved).

* **Residual sub-question (OPEN, does not affect
  the WHAT):** no ROM00 code reads
  `D36A`/`D36C`/`ECDC`/`D372`/`D39B`; how the
  session peer learns these addresses (presumably
  via the RAM coroutine scheduler `ram:D820`-
  `D85F` feeding the `ROM00:7E00` dispatch table)
  remains untraced.

* **TASKS.md:** closed the loader staging-cell
  OPEN wherever it appeared — `Next` no-hardware
  priority 1 marked **RESOLVED 2026-09-19
  (CONFIRMED)** with the pointer protocol + five
  targets and removed from the remaining backlog;
  renumbered/refreshed `Next` no-hardware
  priorities so the top item is now
  `ram:EE00-EE4F`; updated the
  `SUBSTANTIALLY ADVANCED … exact staging cell
  remains OPEN` session-log entry (Finding 6,
  Docs updated, Next) to the RESOLVED pointer-
  protocol description with residual OPEN; removed
  the "Still OPEN: da13" loader-next wording.
  Added this session entry.

* **Docs updated in this pass:** `research/
  TASKS.md` (this entry + `Next` priorities
  refreshed/renumbered + 2026-09-17 Finding 6
  + Docs updated + Next corrected to RESOLVED),
  `re-notes/os-diposb.md` (Runtime program loading:
  replaced "exact staging cell remains OPEN" with
  `ram:D36A` pointer protocol + five targets,
  labels, and residual peer-learning OPEN),
  `manual/programmer-guide.md` (§7b source-bytes
  sentence updated to same, `0BAC` → `0BAC-0C9A`,
  loader staging cell RESOLVED with residual
  OPEN), `research/gap-analysis.md` (loader note
  updated to RESOLVED `ram:D36A` pointer protocol
  + five targets with residual OPEN). No Ghidra
  edits in this docs pass beyond the saved labels
  above; no new inference; evidence tags
  preserved; ~70-col wrapping. `mkdocs build
  --strict` (site_dir `site-mkdocs`) run — see
  below.

### 2026-09-19 — D837 renamed Coroutine_Enter; EE00 arena
  populated by ROM at boot (CORRECTION to "not
  ROM-patched") (docs only, no Ghidra, no new
  inference; parent-verified, Ghidra saved)

* **RESOLVED 2026-09-19 (CONFIRMED, byte-verified)
  — `ram:D837` renamed `Coroutine_Enter`.**
  Coroutine frame-entry / context-switch helper,
  not a scheduler task switch: pops the
  continuation (body address) from the stack;
  switches `SP` to the coroutine frame by the `DE`
  frame offset; saves `BC`/`IX`/`IY`; calls the
  body via `ram:D836` (`JP (HL)`); restores;
  returns the body's `HL` with `Z` iff `HL==0`.
  Entered by the ubiquitous `LD DE,0; CALL
  ram:D837` prologue (`DE` = frame size). Plate
  updated (In: `DE` = frame size, return address =
  body; Out: `HL` = body result, `Z` iff `0`;
  Clobbers `AF`/`BC`/`DE`/`HL`, `IX`/`IY`
  preserved; `CONFIRMED ram:D837-D857`). Sibling
  `Coroutine_SwapContinuation` (`ram:D9F9`)
  unchanged. Rename hygiene: synced every
  `Coroutine_TaskSwitch` mention in `doc/` to
  `Coroutine_Enter` for `ram:D837`; historical
  `ROM00:3BB8` duplicate → `Coroutine_IndexedLookup_6A4A`
  record retained as former name. The earlier
  “Should `ram:D837` keep the name
  `CoroutineTaskSwitch`?” OPEN in
  `doc/re-notes/open-questions.md` is now RESOLVED
  (name changed).

* **RESOLVED 2026-09-19 (CONFIRMED,
  byte-verified + emulator; CORRECTED 2026-09-19) —
  `ram:EE00-EE4F` is a stub farm populated by ROM
  at boot via bulk copy.** `--watch-mem EE00:EE4F`
  with `hello.com` shows arena written at boot:
  writer PCs `D6D6` (×80) and
  `D736`/`D73B`/`D73E`/`D740` (×20 each), installing
  the `21 01 00 C9` (`LD HL,1; RET`) no-op pattern
  into all 20 slots (CONFIRMED). Earlier "no ROM
  writer" claim missed the bulk copy (no per-slot
  xref; `ROM00:7DFA` 20-word source copied en bloc);
  only `ROM01:11A4` calls `0xEE00`. No `D7` (`RST
  10h` thunk) writes observed even with COM loaded;
  runtime patching by loaded software remains
  possible but unobserved (OPEN). Comment at
  `ram:EE00`.

* **TASKS.md:** closed both OPEN items wherever they
  appeared — `Next` no-hardware priorities
  `ram:EE00-EE4F` and `ram:D837` marked **RESOLVED
  2026-09-19 (CONFIRMED)** with evidence and removed
  from the no-hardware backlog; renumbered/refreshed
  `Next` so top no-hardware item is now the
  data-typing backlog (§12 item 5 remainder); updated
  the 2026-09-01 listing-repair entry (PARTIALLY
  ADDRESSED → RESOLVED) and the 2026-09-17 loader
  Finding 1 to `Coroutine_Enter`. No Ghidra function
  created/deleted beyond the saved rename/comment.

* **Docs updated in this pass:** `research/TASKS.md`
  (Next renumbered/refreshed + both RESOLVED entries
  + this session entry), `re-notes/open-questions.md`
  (D837 naming OPEN → RESOLVED `Coroutine_Enter`),
  `re-notes/os-diposb.md` (NOT standard CP/M + Form
  Builder + Queue purpose + Loader rendezvous updated
  to `Coroutine_Enter` with `CONFIRMED ram:D837-D857`),
  `re-notes/unbanked-ram-map.md` (`D681-D892` row),
  `re-notes/ghidra-repair-script.md` (Pass 1 table +
  body + identity), `reference/commstar-api.md` (Entry
  points + Every buffer must live… updated to RESOLVED
  ROM has no writer; stub farm, runtime patching OPEN
  — loaded-software patching plausible/unverified),
  `research/gap-analysis.md` (HL writer). No Ghidra
  edits in this docs pass beyond the saved rename at
  `ram:D837`/`ram:EE00` comment; no new inference;
  evidence tags preserved; ~70-col wrapping. `mkdocs
  build --strict` (site_dir `site-mkdocs`) run — see
  below.

### 2026-09-19 — EE00 framing corrected (ROM has no
  writer; loaded-software patching OPEN) — **SUPERSEDED
  2026-09-19 by boot-copy correction** (docs only,
  no Ghidra, no new inference; parent-verified)

* **Correction at that time:** the earlier EE00 write
  had said the `RST 10h`-thunk hypothesis “has no ROM
  patching mechanism” and left the runtime question
  “OPEN only for loaded software”. That framing
  under-stated that loaded software could patch.

* **Rewritten then:** `reference/commstar-api.md`
  (both Entry points and Every buffer must live…
  passages) and `research/TASKS.md` (Next
  `ram:EE00-EE4F` RESOLVED entry and the 2026-09-19
  D837/EE00 session entry's EE00 bullet) to:
  **CONFIRMED** no per-address ROM writer of
  `ram:EE00-EE4F`; static image twenty
  `LD HL,1; RET` slots.

* **SUPERSEDED 2026-09-19 (CORRECTION):** emulator
  `--watch-mem EE00:EE4F` with `hello.com` shows
  **ROM populates the arena at boot by bulk copy
  (D6D6/D736/D73B/D73E/D740)** installing the no-op
  stubs (`21 01 00 C9`); earlier scan missed the
  bulk copy (no per-address xref). No `D7` thunk
  writes observed even with COM loaded; thunk-
  patching by loaded software is **unobserved
  (OPEN)**. See current `commstar-api.md` and
  the emulator Phases 2–3 entry below.

* **D837 unchanged:** `ram:D837` `Coroutine_Enter`
  resolution (CONFIRMED `ram:D837-D857`) not
  modified.

* **Docs updated in this pass:** `research/TASKS.md`
   (this entry + two RESOLVED rewrites) and
   `reference/commstar-api.md` (two passages). No
   Ghidra edits; no new inference; evidence tags
   preserved; ~70-col wrapping. `mkdocs build
   --strict` (site_dir `site-mkdocs`) run — see below.

### 2026-09-19 — data-typing backlog applied
 (types + 41 `tbl_` labels) (docs only, no Ghidra,
 no new inference; parent-verified, Ghidra saved)

* **Data-typing backlog applied (CONFIRMED,
   Ghidra saved; function list unchanged — 915).**
   Types + labels created:
   `ROM01:7545` `ushort[4]` `tbl_UiCfgRegionPrefix`;
   `ROM01:757F` `ushort[6]` `tbl_UiCfgNamePointers`
   (5 name pointers + `0000` terminator — the
   earlier `ushort[136]` estimate was corrected);
   `ROM01:758B`/`75EB`/`760D` each typed
   `UiCfgHeader` (new 20-byte struct:
   `EC EF F8 F0 98 EF D8 EF` magic +0..+7,
   fields, LE backlink +12h) as
   `tbl_UiCfgTemplateHeaders` (non-contiguous, so
   individual items); `ROM01:79F4` `char[1547]`
   `str_cfg_option_pool` (existing label kept);
   `ROM00:7C30` `byte[256]` `tbl_FontCharWidth`
   (note `7C50` is offset +0x20 within it, not a
   separate table); `ROM00:7D80` `ushort[4]`
   `tbl_StubTablePrefix`; `ROM00:7D88`
   `ushort[60]` `tbl_SessionRuntimeStubSources`
   (renamed); `ROM00:7E50` `ushort[34]`
   `tbl_FnPtrDispatch7E50` (FFFF-terminated);
   `ram:E105` `byte[256]` `g_abFontCharWidth`;
   `ram:D0E0` `byte[448]` `g_abErrorStringTable`;
   41 dispatch-table labels created (16 `ROM01` +
   25 `ROM00`), all `tbl_Dispatch_<name>` —
   previously only 1 of 41 sites had a `tbl_`
   label; 11 plate/repeatable comments set.
   Function list unchanged (915); saved.

* **Minor / deferred — no further action
   (CONFIRMED):** the 4 retained `FUN_*`
   (documented retains with open questions needing
   emulator coverage / vtable mapping), the 12
   non-code code gaps (page-zero RST vectors, the
   `254b` inline dispatcher, padding, and the
   `7545-7FFF` data region), and `ROM00:7409`/
   `7472` (module-A ROM images, deferred by design)
   are all recorded as such; nothing actionable
   remains there (CONFIRMED; see `Next`
   no-hardware priorities and §12 item 5).

* **TASKS.md:** marked §12 item 5 DONE with the
   types + labels above; updated the `Next`
   no-hardware list so only the minor/deferred
   item remains (data-typing removed); updated
   the §12 FINAL PASS headline to list item 5 as
   DONE; added this session entry.

* **Docs updated in this pass:** `research/
   TASKS.md` (this entry + §12 item 5 DONE +
   `Next` refreshed + §12 FINAL PASS headline) and
   `research/gap-analysis.md` (data-typing section
   + annotation tail refreshed — see there). No
   Ghidra edits; no new inference; evidence tags
   preserved; ~70-col wrapping. `mkdocs build
   --strict` (site_dir `site-mkdocs`) run — see
   below.

### 2026-09-19 — emulator Phase 1 coverage
 (1177 reachable; 0904/441b/d937 unhit)
 (emulator `analysis/boot_hw.py`, exit 0,
 bounded; docs only, no Ghidra, no new
 inference; parent-verified)

* **Phase 1 (coverage of the 4 retained
   `FUN_*`) — partial result (CONFIRMED for
   `ROM01:1177`; others SUSPECTED).**
  Two bounded runs via `analysis/boot_hw.py`
  (exit 0):
   - `--watch-pc 0904,1177,441b,d937
     --drive-serial --max-slices 400000`:
     totals `0904=0 1177=2 441B=0 D937=0`.
     `ROM01:1177` hit twice (`bank=01`,
     `AF=7742 BC=06AB DE=D101 HL=1177
     SP=D671`) (CONFIRMED reachable — it is
     not dead; identity remains unknown; the
     retain's open question was identity,
     not reachability).
   - Session-heavy rerun
     `--trace-session-transaction 4
     --max-slices 600000`: same totals
     (`1177=2`, others 0) (CONFIRMED for
     `ROM01:1177`).
  Conclusion: `ROM01:1177` is **CONFIRMED
  reachable** (2 hits at boot/session) — it
  is not dead; its identity remains unknown
  (the retain's open question was identity,
  not reachability). `ROM01:0904`,
  `ROM00:441B`, `ram:D937` were **not
  reached** in either run → **SUSPECTED dead
  or state-specific** (candidates not yet
  exercised: DIP/COM load, commstar session,
  barcode scan). No conclusion is warranted
  from absence in these two runs alone.
* **Phases 2 (vtable dump `ROM01:7C80`/
  `ram:D130`) and 3 (stub-patch trace
  `--watch-mem EE00:EE4F` on a load path) are
  not yet run** (pending).
* **TASKS.md:** updated the emulator plan
  section — marked Phase 1 partially done with
  the above result, noted `ROM01:1177`
  reachable, and listed the unexercised state
  candidates for the three unhit addresses;
  kept Phases 2–3 pending. No Ghidra edits.
* **Docs updated in this pass:**
  `research/TASKS.md` (emulator plan partial
  result + this entry). No Ghidra edits; no
  new inference; evidence tags preserved;
  ~70-col wrapping. `mkdocs build --strict`
  (site_dir `site-mkdocs`) run — see below.

### 2026-09-19 — emulator Phases 2-3 (vtable
  big-endian; EE00 boot-copy correction) (emulator
  + static read; docs only, no Ghidra, no new
  inference; parent-verified)

* **Phase 2 — session-object vtable resolved
    (CONFIRMED, static).** `ROM01:7C80` and its RAM
    copy `ram:D130` are tables of **big-endian
    16-bit ROM01 addresses** (hi byte first), not
    little-endian words. Decoded `ROM01:7C80`:
    `13C8 14CF 143E 156F 15D8 1512 1664 168E 16B8
    16D0 166F 15F5 153B 1664 168E 16B8 16ED 1675
    1791` … (19 entries then a different structure
    at `7CA6`). Crucially, the retained stubs appear
    as entries: **`156F`, `1664`, `168E`, `16B8`**
    — so those four are session-object vtable
    entries (methods), which is their vtable mapping.
    `ram:D130` holds the same entries (`11B1 13BB
    13D8 13C8 14CF 143E 156F 15D8 1512 1664 168E
    16B8 16D0 166F 15F5 153B`), i.e. the vtable
    copied to RAM. **Byte-order evidence: only
    big-endian interpretation yields valid ROM01
    code addresses matching the known stubs.**
    **SUPERSEDED 2026-09-19 — see next entry:**
    table is **43 entries, `FFFF` at `ROM01:7CD8`**;
    RAM base is `ram:D128` (`D130 = D128+8`);
    `ram:D128` diverges at entries 3–6; **reader
    OPEN** (zero xrefs to `ROM01:7C80` /
    `ram:D128`/`D130`; SUSPECTED `ROM01:11E5`).

* **Phase 3 — stub arena IS written by ROM at
    boot (CORRECTION; CONFIRMED, emulator).**
    `--watch-mem EE00:EE4F` with `hello.com` via
    `--upload` shows the arena written at boot:
    writer PCs `D6D6` (×80) and
    `D736`/`D73B`/`D73E`/`D740` (×20 each),
    installing the `21 01 00 C9` (`LD HL,1; RET`)
    no-op pattern into all 20 slots (CONFIRMED).
    **Mechanism:** `Kernel_InitCopyData`
    (`ram:D6C0`, `ROM00:7039`) copies `21 01 00 C9`
    at `D6C9` `D6D7`→`ED1C` and `0x460` bytes at
    `D6D4` `ED1C`→`ED20` including `EE00-EE4F`
    (old "does NOT touch `EE00`" wrong). **Thunk-
    write mechanically possible (CONFIRMED):**
    DIP type-0 `dest=EE00` (no range check at
    `ROM01:0ED1`→`D36A`) or COM `LD (EE00),A` at
    `0x0100` (`ROM01:0D3B`); type-1 only as
    `{D7,bank,addr}`; unobserved (OPEN). Earlier
    scan missed bulk copy (no per-address xref);
    source `ROM00:7DFA` 20 words en bloc (no
    per-address xref by design). No `D7` thunk
    writes observed even with COM loaded; runtime
    patching remains **mechanically possible and
    unobserved (OPEN)** — do not claim without
    witnessed `D7` write + `--dump-mem` capture.

* **TASKS.md:** updated the emulator plan —
   marked Phase 2 DONE with the vtable decode
   (big-endian, entries, evidence, retain
   mapping) and Phase 3 DONE with the boot-copy
   finding + correction (bulk-copy blind spot,
   writer PCs, no `D7` observed, OPEN patch);
   fixed the earlier EE00 framing correction
   (now superseded) and the top `RESOLVED
   ram:EE00-EE4F` entry to the bulk-copy wording;
   updated `Minor / deferred` retain notes:
   `ROM01:1177` reachable (Phase 1) and
   `156F`/`1664`/`168E`/`16B8` are vtable entries
   (retain notes record slot role); refreshed
   Phase 2/Phase 3 harness/acceptance notes to
   DONE; updated sequencing note to report the
   bulk-copy conflict as corrected.

* **Docs updated in this pass:**
   `research/TASKS.md` (emulator plan Phase 2 DONE
   + Phase 3 DONE + correction + `Minor / deferred`
   retain notes + sequencing note + two historical
   EE00 entries corrected/superseded + this entry),
   `reference/commstar-api.md` (both Entry points
   passages corrected to ROM boot bulk-copy
   `D6D6`/`D736`/`D73B`/`D73E`/`D740`, no `D7`
   observed, OPEN patch),
   `research/gap-analysis.md` (Retained (10) and
    Item C updated — `ROM01:1177` reachable,
    `156F`/`1664`/`168E`/`16B8` are vtable entries,
    big-endian at `ROM01:7C80`/`ram:D130`).
    No Ghidra edits; no new inference; evidence
    tags preserved; ~70-col wrapping. `mkdocs
    build --strict` (site_dir `site-mkdocs`) run —
    see below.

### 2026-09-19 — vtable readers unlocated;
 boot-copy plate corrected; thunk-write mechanism
 identified (docs only, no Ghidra, no new
 inference; parent-verified, Ghidra saved)

* **Finding 1 — vtable readers not yet located
   (CONFIRMED zero-xref; reader SUSPECTED) —
   static search exhausted.**
   There are **zero xrefs** to `ROM01:7C80` and
   to `ram:D128`/`D12A`/`D130`; only `ram:D100`
   in that area has xrefs (6, in
   `Dialog_IdleRelease`,
   `Session_AdvanceStageOnZero`,
   `Session_HelperRouter11E5`). Byte-pattern
   search for the little-endian pointer to
   `D128` (`28 d1`) found only two hits —
   `ROM01:2A22` and `ROM01:3412` — and both are
   **false positives** (CONFIRMED, byte-verified):
   the bytes are the tail of `CALL 28FE`
   followed by `POP DE` (`CD FE 28 D1 …`), not
   a pointer. `search_instructions` for
   `d128`/`d130` operands also returned zero
   (CONFIRMED), so there is no `LD HL,(D128)`,
   no immediate base, and no data pointer to
   the table in the ROM. The dispatcher cannot
   be located statically — it must reach the
   table by a **computed address** (e.g. a
   pointer chain or a base computed at runtime),
   or by direct execution out of the RAM copy
   per the coroutine model (OPEN). The static
   lead `Session_HelperRouter11E5`
   (`ROM01:11E5`) is **not** supported by a
   table reference (its plate documents a
   different, 6-byte-stride table at `ram:D108`
   plus the `ram:D100` scratch buffer). Facts
   (CONFIRMED, byte-verified): table is **43
   big-endian 16-bit entries, `FFFF`-terminated
   at `ROM01:7CD8`**; RAM copy at `ram:D128`
   diverges at entries 3–6 (`1577`/`11B1`/
   `13BB`/`13D8` vs ROM's `156F`/`15D8`/
   `1512`/`1664`) — i.e. runtime-patched;
   `ram:D130 = D128+8` is an alternate entry
   point, not a separate table. Plates added at
   `ROM01:7C80` and `ram:D128` (Ghidra saved).
   Recorded as an **OPEN** item;
   **discriminating observation now:** an
   **emulator read-trace** of `ram:D128`/
   `ROM01:7C80` (execution watching the table
   addresses) or a computed-address/
   pointer-chain trace, since byte/xref search
   is exhausted.

* **Finding 2 — boot copy corrected
   (CONFIRMED, byte-verified).**
   `Kernel_InitCopyData` (`ram:D6C0`, entered
   `ROM00:7039` via `CopyKernelDispatchBlock`):
   at `D6C9` copies the 4-byte template
   `21 01 00 C9` from `D6D7` to `ED1C`; at
   `D6D4` an `LDIR` copies `0x460` bytes
   `ED1C`→`ED20`, filling `ED20-F17F`
   **including the `EE00-EE4F` stub arena**
   (CONFIRMED, byte-verified). The old plate
   claim "does NOT touch `EE00`/`F100`" was
   **wrong** and is corrected; EOLs added at
   `D6D1`/`D6D4` (Ghidra saved).

* **Finding 3 — thunk-write mechanism, both
   mechanically possible (CONFIRMED mechanics;
   unobserved in emulator runs so far).**
   (i) **DIP type-0 block:** loader takes the
   destination address from descriptor bytes
   [4:5] (`ROM01:0ED1` → `D36A`) with **no
   range check**, so a DIP file with
   `dest_addr = EE00` writes there. (ii) **COM
   program:** loaded at `0x0100` (`ROM01:0D3B`)
   and runs with full RAM access, so
   `LD (EE00),A` / `LDIR` overwrites the arena.
   Type-1 blocks can also target `EE00` via
   `image_base + bank_offset` but only produce
   `{D7,bank,addr}` stubs. Matches owner's note
   (DIP record/block target or COM overwrite).
   Runtime thunk-patching by loaded software is
   therefore **mechanically possible and
   unobserved** in the emulator runs so far.

* **TASKS.md:** updated emulator-plan notes
   (Phase 2 reader OPEN with SUSPECTED
   `ROM01:11E5` + 43-entry `FFFF` at `7CD8` +
   `D128` divergence + `D130 = D128+8`; Phase 3
   boot-copy mechanism `D6C9`/`D6D4` + thunk
   mechanism DIP-type-0 / COM; Minor/deferred
   retain notes) and appended this session
   entry.

* **Docs updated in this pass:**
   `research/TASKS.md` (emulator plan + this
   entry), `research/gap-analysis.md` (Retained
   vtable reader OPEN + boot-copy + thunk
   notes), `reference/memory-map.md` (boot-copy
   `D6C0`/`D6C9`/`D6D4` correction + thunk
   mechanism), `reference/commstar-api.md`
   (thunk mechanism). No Ghidra edits; no new
   inference; evidence tags preserved;
   ~70-col wrapping. `mkdocs build --strict`
   (site_dir `site-mkdocs`) run — see below.

### 2026-09-19 — vtable reader: static search
 exhausted (no pointer; 28 d1 = CALL 28FE/POP DE)
 (docs only, no Ghidra, no new inference;
 parent-verified)

* **The `ROM01:7C80` / `ram:D128` vtable has no
  static reference at all (CONFIRMED).**
  Byte-pattern search for the little-endian
  pointer to `D128` (`28 d1`) found only two
  hits — `ROM01:2A22` and `ROM01:3412` — and
  both are **false positives** (CONFIRMED,
  byte-verified): the bytes are the tail of
  `CALL 28FE` followed by `POP DE`
  (`CD FE 28 D1 …`), not a pointer.
  `search_instructions` for `d128`/`d130`
  operands also returned zero (CONFIRMED). So
  there is no `LD HL,(D128)`, no immediate
  base, and no data pointer to the table in
  the ROM.

* **Conclusion (OPEN):** the vtable
  reader/dispatcher cannot be located
  statically — it must reach the table by a
  **computed address** (e.g. a pointer chain
  or a base computed at runtime), or by direct
  execution out of the RAM copy per the
  coroutine model. This remains **OPEN**; the
  static lead `Session_HelperRouter11E5`
  (`ROM01:11E5`) is **not** supported by a
  table reference (its plate documents a
  different, 6-byte-stride table at `ram:D108`
  plus the `ram:D100` scratch buffer).

* **Discriminating observation now:** an
  **emulator read-trace** of `ram:D128`/
  `ROM01:7C80` (execution watching the table
  addresses) or a computed-address/
  pointer-chain trace, since byte/xref search
  is exhausted.

* **TASKS.md:** updated the vtable-reader OPEN
   item (both `28 d1` hits falsified as
   `CALL 28FE`/`POP DE`; zero operand refs;
   static search exhausted; next tool = emulator
   read-trace) and appended this entry. No Ghidra
   edits; evidence tags preserved; ~70-col
   wrapping. `mkdocs build --strict` (site_dir
   `site-mkdocs`) run — see below.

### 2026-09-19 — vtable reader located
 (UI_FormExitDispatchNext via ram:D081 pointer
 table; --watch-read added) (Ghidra saved;
 emulator read-trace; docs only in this pass,
 no new inference; parent-verified)

* **Vtable reader LOCATED (CONFIRMED, emulator
  `--watch-read`).** Session-object callback
  table is read by `UI_FormExitDispatchNext`
  (`ROM01:06D3`-`0720`). It increments
  `g_formIdxW` (`ram:D2DE`), rejects at
  `index >=5` via `CALL 0xE0E7`, indexes
  5-entry word-pointer table at `ram:D081`
  (`LD DE,0xD081; ADD HL,DE` at `ROM01:06EF`),
  double-indirects to callback slot
  (`ROM01:06F7`-`06FA`), calls via
  `CALL 0xD828` (`g_pUserCallbackTrampoline`
  indirect-call tramp).

* **Callback slots (CONFIRMED, emulator
  `--watch-read` + byte-verified):** base
  `ram:D12F`, stride `0x0E`; first word of each
  slot is little-endian ROM01 address. Observed
  `D12F/D130=0x1177`, `D13D/D13E=0x156F` — i.e.
  retained session-object stubs. `ram:D081`
  entries are word pointers
  `0xD0F0/0xD13D/0xD121/0xD12F/0xD14B`
  (NULL-terminated) into `D12F`-based records.

* **Why no static xref (CONFIRMED):** reader
  reaches table by double indirection (base
  `D081` indexed by RAM counter, then pointer to
  callback slot), so byte/xref search could not
  see it — why earlier static hunt failed.
  Manual DATA xref `ROM01:06EF` → `ram:D081`
  added; plates at `ROM01:06D3` (reader),
  `ram:D081` (index table), `ram:D12F`
  (callback-slot base, repeatable) (Ghidra
  saved).

* **Harness gained `--watch-read` `LO:HI[,...]`
  (CONFIRMED, tested).** `analysis/boot_hw.py`
  now supports inclusive read-watch mirroring
  `--watch-mem` (reports value + reading PC +
  SP + bank; per-range cap
  `--watch-read-limit`, default 24; totals at
  exit). Entry in `--help`. This is what
  located the reader.

* **TASKS.md:** closed vtable-reader OPEN item
   wherever it appeared — `Minor / deferred`
   retain notes, Phase 2 reader bullet, and
   `gap-analysis.md` retained sections marked
   **RESOLVED** with reader + `D081`/`D12F`
   facts; residual OPEN is only the witnessed
   `D7` stub-patch (DIP/COM) — **OPEN as a
   harness-instrumentation gap (CONFIRMED,
   emulator `analysis/boot_hw.py`):**
   `--watch-mem` (and by extension `--watch-read`)
   not observing loaded-program stores (control
   `E000` shows only boot writes
   `pc-after=D723x4`); `EE00:EE4F` run showed 160
   boot-bulk writes
   (`pc-after=D6D6/D736/D73B/D73E/D740`) and no
   bank-2 PC write of `D7 00 BF 48`; patch
   *mechanism* stays **CONFIRMED possible** (DIP
   type-0 dest with no range check; COM
   overwrite); witness needs watch armed for the
   loaded-program run + `--dump-mem` capture.

* **Docs updated in this pass:**
   `research/TASKS.md` (closed OPEN + this
   entry), `research/gap-analysis.md` (retained
   sections RESOLVED + reader facts), and
   `analysis/README.md` (harness `--watch-read`
   docs). No Ghidra edits in this docs pass
   beyond the saved plates/xref above; no new
   inference; evidence tags preserved; ~70-col
   wrapping. `mkdocs build --strict` (site_dir
   `site-mkdocs`) run — see below.

### 2026-09-19 — D7 patch witness blocked by harness
 scope (loaded-program writes unwatched) (emulator
 `analysis/boot_hw.py`; docs only, no Ghidra, no
 new inference; parent-verified)

* **Attempt to witness `D7` stub-patch failed for a
   harness reason, not an analysis reason
   (CONFIRMED, emulator `analysis/boot_hw.py`).**
   A crafted 15-byte COM
   (`LD HL,0xEE00; LD (HL),0xD7; INC HL;
   LD (HL),0x00; INC HL; LD (HL),0xBF; INC HL;
   LD (HL),0x48; RET`, i.e. writes thunk
   `D7 00 BF 48` into `EE00`-`EE03`) was uploaded
   via `--upload` with `--watch-mem EE00:EE4F`.
   The upload ran (`upload_status=succeeded`,
   `execution entered bank 2 at 0100`) but **no
   write from the loaded program was observed** —
   the arena's 160 writes all came from the boot
   bulk copy (`pc-after=D6D6/D736/D73B/D73E/D740`),
   none from a bank-2 PC.

* **Control confirms the harness gap (CONFIRMED).**
   A minimal COM writing `0xAA` to `E000`
   (`LD HL,0xE000; LD (HL),0xAA; RET`) run with
   `--watch-mem E000:E003` likewise shows only the
   boot writes (`pc-after=D723x4`) — **the loaded
   program's stores are not seen by `--watch-mem`**.
   So the watch is not active (or not applied)
   during the post-load `Run` execution of the
   loaded COM in this harness.

* **Conclusion (OPEN as a harness-instrumentation
   gap).** The witnessed `D7` patch remains **OPEN
   as a harness gap**: `--watch-mem` (and by
   extension `--watch-read`) needs to be
   armed/scoped so it observes writes/reads during
   the loaded-program run, not just the boot phase.
   The patch *mechanism* stays **CONFIRMED possible**
   (DIP type-0 dest with no range check; COM
   overwrite); only the witness is blocked. This
   does **not** affect any Ghidra annotation.

* **TASKS.md:** updated the residual `D7`-patch OPEN
   item to record the harness gap (watch not
   observing loaded-program stores; control at
   `E000`) as the blocker.

* **Docs updated in this pass:** `research/TASKS.md`
    (residual OPEN updated + this entry). No Ghidra
    edits; no new inference; evidence tags preserved;
    ~70-col wrapping. `mkdocs build --strict`
    (site_dir `site-mkdocs`) run — see below.

### 2026-09-19 — D7 stub patch witnessed (loaded COM
 writes `EE00`-`EE03`; marker artifact corrected)
 (emulator `analysis/boot_hw.py`; docs only, no
 Ghidra, no new inference; parent-verified)

* **The `D7` stub patch is now WITNESSED
    (CONFIRMED, emulator `analysis/boot_hw.py`).**
    Crafted COM writes thunk `D7 00 BF 48` into
    `EE00`-`EE03`
    (`LD HL,0xEE00; LD (HL),0xD7; INC HL;
    LD (HL),0x00; INC HL; LD (HL),0xBF; INC HL;
    LD (HL),0x48; LD A,0xA5; LD (0x0200),A; RET`)
    uploaded via `--upload` with
    `--upload-marker 0200:A5` and
    `--watch-mem EE00:EE4F`. Result:
    `execution entered bank 2 at 0100`,
    `marker 0200=A5 observed`,
    `upload_status=succeeded`; arena totals **164
    writes** with writing PCs `D6D6×80 D736×20
    D73B×20 D73E×20 D740×20` (boot bulk copy)
    **plus `0105×1 0108×1 010B×1 010E×1`** — the
    loaded program's four stores into `EE00`-`EE03`
    (CONFIRMED). So a loaded COM can and does
    overwrite the stub arena at runtime (CONFIRMED).

* **CORRECTION of the previous conclusion — the
    earlier failure was a test-marker artifact, not
    a harness gap (CONFIRMED).** The first attempt
    used `--upload-marker 0100:21`, which is the
    COM's **own first opcode** (`LD HL,…` = `0x21`
    at `0100`), already present at load time — so
    `run_loaded_program` saw the marker immediately
    and returned **before executing the COM**. Choosing
    a marker the program *writes after* the patch
    (`0200:A5`) makes it run. Therefore `--watch-mem`
    / `--watch-read` **were** active during the
    loaded-program run; the previous "watch not active
    during loaded-program Run" / "harness-
    instrumentation gap" conclusion is **wrong** and
    is corrected here. `0200:A5` vs `0100:21`
    discriminates it.

* **TASKS.md:** closed the residual `D7`-patch OPEN
    item wherever it appeared — `Minor / deferred`
    retain notes, Phase 3 arena section (both the
    `RESOLVED + CORRECTION` bulk-copy block and the
    thunk-write mechanism), and the Phase-3 harness
    note — all marked **RESOLVED/WITNESSED
    2026-09-19 (CONFIRMED, emulator)** with byte
    values `D7 00 BF 48`, store PCs
    `0105/0108/010B/010E`, totals `164` and the
    marker correction (`0100:21` early-return →
    `0200:A5`). Practical lesson noted: for future
    `--upload` runs pick a marker the program writes
    *after* the effect under test, not an opcode byte
    present at load.

* **Docs updated in this pass:** `research/TASKS.md`
    (residual OPENs closed + mark RESOLVED/WITNESSED
    + marker-artifact CORRECTION + this entry),
    `research/gap-analysis.md` (retained `FUN_*`
    notes — residual `D7` now RESOLVED/WITNESSED),
    `reference/commstar-api.md` (both "unobserved
    (OPEN)" wordings → RESOLVED/WITNESSED with
    `D7 00 BF 48` / `0105×1` etc. + CORRECTION),
    `reference/memory-map.md` (§2.1 thunk-patching —
    "mechanically possible, unobserved (OPEN)" →
    RESOLVED/WITNESSED with same bytes/PCs +
    CORRECTION). No Ghidra edits; no new inference;
    evidence tags preserved (`CONFIRMED`/`CORRECTION`);
    ~70-col wrapping. `mkdocs build --strict`
    (site_dir `site-mkdocs`) run — see below.
### 2026-09-19 — extended coverage of the unhit
 retains (0904/441b/d937 unhit in four run types
 → LIKELY dead) (emulator `analysis/boot_hw.py`,
 exit 0, bounded; docs only, no Ghidra, no new
 inference; parent-verified)

* **Extended coverage of the three unhit retains
   (CONFIRMED, emulator `analysis/boot_hw.py`,
   exit 0, bounded).** `--watch-pc
   0904,1177,441b,d937` across four run types:
   boot + `--drive-serial` `1177=2, others 0`;
   `--trace-session-transaction 4` `1177=2,
   others 0`; `--upload hello.com
   --upload-marker 0200:A5` (real COM load path)
   `1177=13, others 0`; `--upload hello.com
   --commstar-peer` (commstar session attach)
   `0904=0 441B=0 D937=0` (peer saw no requests
   — test COM does not hold a commstar session).
   So `ROM01:1177` reachable in every run (now
   up to 13 hits); `ROM01:0904`, `ROM00:441B`,
   `ram:D937` unhit in all four.

* **Conclusion (CONFIRMED static status +
   extended coverage).** Combined with static
   status — `ROM01:0904` is `NOP; NOP; RET`
   alignment padding (not a real routine),
   `ROM00:441B` and `ram:D937` have **zero xrefs**
   — these three are **dead/unreachable in every
   exercised path** (boot, session transaction,
   COM load, commstar attach). Retained (plates)
   rather than deleted: could still be reached by
   other loaded software or the one unexercised
   path (barcode scan). Tag **SUSPECTED dead →
   LIKELY dead** (zero xrefs + unhit in four run
   types); only the barcode-scan capture remains
   unexercised.

* **TASKS.md:** updated the minor/deferred retain
   block with the four-run coverage table and the
   **LIKELY dead** conclusion (only barcode path
   unexercised), and refreshed the Phase 1
   coverage block from partial (2 runs, SUSPECTED)
   to extended (4 runs, LIKELY dead).

* **Docs updated in this pass:** `research/TASKS.md`
    (minor/deferred block + Phase 1 block + this
    entry), `research/gap-analysis.md` (both
    retained-`FUN_*` sections — `0904`/`441B`/`D937`
    upgraded to **LIKELY dead** with four-run
    coverage, `1177` to up to 13 hits). No Ghidra
    edits; no new inference; evidence tags preserved
    (`CONFIRMED`/`LIKELY`); ~70-col wrapping.
    `mkdocs build --strict` (site_dir `site-mkdocs`)
    run — see below.
### 2026-09-19 — callback xrefs linked; barcode path
 armed but not triggered (Ghidra saved; emulator;
 docs only, no Ghidra, no new inference;
 parent-verified)

* **Callback xrefs linked (CONFIRMED).** The
   `ram:D081` 5-entry pointer table (read by
   `UI_FormExitDispatchNext`) points to callback
   slots whose first word is a little-endian
   ROM01 callback address (CONFIRMED, byte-verified
   slot contents). Byte-verified slot contents and
   manual DATA xrefs added: `ram:D0F0`→`ROM01:0A67`,
   `ram:D121`→`ROM01:1177`, `ram:D12F`→`ROM01:1177`,
   `ram:D13D`→`ROM01:156F`, `ram:D14B`→`ROM01:156F`.
   So the `D081` entries
   `0xD0F0/0xD13D/0xD121/0xD12F/0xD14B` select
   callbacks `0x0A67`/`0x156F`/`0x1177`/`0x1177`/
   `0x156F`; `ROM01:1177` is reached by the dispatch
   via slots `D121` and `D12F` (both entries), and
   `0x156F` via `D13D`/`D14B`. Plates updated at
   `ram:D081` (entry→callback listing) and `ram:D12F`
   (slot base + observed callbacks; Ghidra saved);
   function list unchanged.

* **Barcode-scan path attempted but not exercised
   (CONFIRMED; trigger identified 2026-09-19).**
   Two bounded harness runs with
   `--barcode-scan A1 --barcode-probe
   --watch-pc 0904,441b,d937` — (a) a plain
   boot+scan, (b) the harness's documented expect
   flow (`--expect "Enter the
   Workstation:\r12345678\r" --expect "Main Menu"`
   then scan) — both ended `barcode_status=pending`
   with `0904=0 441B=0 D937=0`. So the wand was
   armed but never triggered. **Plus third
   whole-path run** `--barcode-scan A1
   --barcode-decode --barcode-bdos --barcode-expect
   A1 --watch-pc 0904,441b,d937` also ended
   `barcode_status=pending` with
   `0904=0 441B=0 D937=0` (CONFIRMED). **Why
   (CONFIRMED, `analysis/boot_hw.py` ~3094):**
   harness drives capture only when
   `BARCODE_ENABLED and barcode_status=="pending"
   and "Main Menu" in fb_txt and not pending_keys
   and (no expect steps or expect steps exhausted)`;
   in these `--barcode-*` runs `"Main Menu"` never
   appears in captured LCD text (grep empty), so
   trigger never met — plain boot *does* reach
   `"Main Menu"` but barcode-enabled runs do not.
   `BARCODE_ENABLED = BARCODE_WIDTHS is not None`,
   so option does arm the wand; gap is
   reaching/keeping Main Menu under barcode flags.
   The three retains remain **LIKELY dead** and
   discriminator **still unexercised for this
   concrete trigger reason**, not a firmware
   dead-end; next step is harness reaching
   `"Main Menu"` with barcode flags set (or owner
   real scan). Earlier "flow did not reach a
   barcode-entry field" wording is **superseded**
   by this Main Menu trigger finding.

* **TASKS.md:** recorded the 5 callback xrefs in the
   vtable/reader notes (minor/deferred header and
   Phase 2 reader bullet — byte-verified slot
   contents, `D081`→callback mapping, `ROM01:1177`
   via `D121`/`D12F`, `0x156F` via `D13D`/`D14B`,
   plates updated), and updated the retain block:
   barcode path attempted (two flows) →
   `barcode_status=pending`, retains still **LIKELY
   dead**, discriminator unexercised, next step is a
   barcode-entry field before scan — **now updated
   with third whole-path run and Main Menu trigger
   finding** (see next entry). No Ghidra edits in
   this docs pass beyond the saved plates above; no
   new inference; evidence tags preserved
   (`CONFIRMED`/`LIKELY`); ~70-col wrapping.

* **Docs updated in this pass:** `research/TASKS.md`
    (vtable/reader notes + retain block + this
    entry), `research/gap-analysis.md` (both
    retained-`FUN_*` sections — callback xrefs
    linked with `D081`→callback mapping and barcode
    armed but not triggered with two flows — **now
    superseded by three-flow + trigger detail,
    and by the exercised `--drive-serial` run
    (see next entry)**). No Ghidra edits; no new
    inference; evidence tags preserved; ~70-col
    wrapping. `mkdocs build --strict` (site_dir
    `site-mkdocs`) run — see below.

### 2026-09-19 — barcode whole-path also pending
 (Main Menu not reached under --barcode flags)

* **Third barcode attempt also pending
   (CONFIRMED, emulator `analysis/boot_hw.py`):**
   whole-path `--barcode-scan A1 --barcode-decode
   --barcode-bdos --barcode-expect A1 --watch-pc
   0904,441b,d937` also ended
   `barcode_status=pending` with
   `0904=0 441B=0 D937=0`. **Why (CONFIRMED,
   ~3094):** harness drives capture only when
   `BARCODE_ENABLED and barcode_status=="pending"
   and "Main Menu" in fb_txt and not pending_keys
   and (no expect steps or expect steps exhausted)`;
   in barcode-enabled runs `"Main Menu"` never
   appears in captured LCD text (grep empty), so
   trigger never met — plain boot *does* reach
   `"Main Menu"` but `--barcode-*` runs do not.
   `BARCODE_ENABLED = BARCODE_WIDTHS is not None`,
   so option does arm the wand; gap is
   reaching/keeping Main Menu under barcode flags.
   Discriminator remains **unexercised for this
   concrete trigger reason**, not a firmware
   dead-end; retains remain **LIKELY dead**; next
   step is to make the harness reach `"Main Menu"`
   with barcode flags set (or owner real scan).

* **TASKS.md:** updated retain/barcode note with
   third whole-path run and trigger detail
   (Main Menu not reached under `--barcode-*`
   flags; `BARCODE_ENABLED` arms wand, gap is
   reaching Main Menu), and appended this
   one-line session entry. No Ghidra edits; no
   new inference; evidence tags preserved
   (`CONFIRMED`/`LIKELY`); ~70-col wrapping.

* **Docs updated in this pass:** `research/TASKS.md`
    (retain/barcode note + this entry). No Ghidra
    edits; no new inference; evidence tags preserved;
    ~70-col wrapping. `mkdocs build --strict`
    (site_dir `site-mkdocs`) run — see below.
    **Superseded 2026-09-19 (see next entry):**
    the `barcode_status=pending` / "Main Menu not
    reached" explanation was the missing
    `--drive-serial`; barcode path is now
    exercised (CONFIRMED).

### 2026-09-19 — barcode path exercised
 (--drive-serial); three retains dead across
 all five paths (emulator `analysis/boot_hw.py`,
 exit 0, bounded; docs only, no Ghidra, no new
 inference; parent-verified)

* **Barcode path is now exercised (CONFIRMED,
   emulator `analysis/boot_hw.py`).** The missing
   piece was `--drive-serial`:
   `--drive-serial --barcode-scan A1
   --barcode-probe --watch-pc 0904,441b,d937`
   reaches `[40320] Main Menu reached; driving
   barcode capture`, installs the probe hook,
   and reports `barcode_status=succeeded` — hook
   reached `PC=9000 AF=0042 BC=0000 DE=0000
   HL=9000 IX=FA03 IY=FB65 SP=D611 bank=00`,
   stack `1468 FBB9 F691 FFFF DFDB 7213`,
   `FBB9..FBBC = b5f92700` (table `F9B5`, count
   39), returned count 0 (probe rejects, capture
   re-armed). So the earlier
   `barcode_status=pending` was simply the missing
   `--drive-serial` (Main Menu was never reached);
   the previous "Main Menu not reached under
   --barcode flags" explanation is **superseded**
   by this exercised run (CONFIRMED).

* **The three retains are dead (CONFIRMED-unhit
   across every exercised path).** With
   `--watch-pc 0904,441b,d937` the barcode run
   again gives `0904=0 441B=0 D937=0`. Combined
   with the earlier four run types (boot+serial,
   session-transaction, COM load, commstar-peer),
   `ROM01:0904` (`NOP; NOP; RET` padding),
   `ROM00:441B` (zero xrefs) and `ram:D937` (zero
   xrefs) are unhit in **all five** exercised
   paths. Upgrade **LIKELY dead → dead
   (unreachable in every exercised path; zero
   xrefs; not a real routine for `0904`)**. They
   remain retained with plates (a firmware path
   not yet discovered could still reach them),
   but no ROM caller exists (CONFIRMED).

* **TASKS.md:** recorded the exercised barcode run
   (the `--drive-serial` fix, the hook contract
   facts), superseded the "Main Menu not reached"
   explanation, and upgraded the three retains to
   dead-across-all-paths (see minor/deferred and
   Phase 1). Appended this session entry.

* **Docs updated in this pass:** `research/TASKS.md`
   (this entry + minor/deferred + Phase 1),
   `research/gap-analysis.md` (both retained
   `FUN_*` sections — "two flows" wording to
   exercised result, three retains upgraded to
   **dead**). No Ghidra edits; no new inference;
   evidence tags preserved (`CONFIRMED`/`dead`);
   ~70-col wrapping. `mkdocs build --strict`
   (site_dir `site-mkdocs`) run — see below.
