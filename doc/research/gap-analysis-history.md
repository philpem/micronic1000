# Gap-analysis history — per-pass detail

Historical pass detail for the coverage tracker; current numbers are in
`gap-analysis.md`.

## Part B cluster merges (CONFIRMED)

Parents extended and their inline-switch case blocks absorbed; all 12
interior adjudications were **MERGE** (internal-only callers, no
external references):

* `3a04` `Session_FieldDispatch` → `3b7a`
* `444f` `Session_RedrawField` → `463e`
* `576c` `Session_DispatchSub` → `5839`
* `583a` `Session_DispatchWrap` → `59a8`
* `6292` `UI_PostKeyedEntry` → `62e4`
* `6633` `UI_PostDescriptor` → `6759`
* `6aa9` `UI_RecordMatchAndPost` → `6b6c`

Superseded Part-A names deleted as case blocks (12, none had external
callers and none are referenced in `doc/` — grep verified): `3a1c`
`Field_FlagHandler3a1c`, `3b7a`, `3b53`
`SessionCommandDispatchStub_3B53`, `581f`, `5991`, `62a9`, `62b6`,
`62ca`, `66ec`, `6707`, `6b0d`, `6b53`. The 38 computed-dispatch blocks
and these 12 fragments are not missing functions; they are blocks.

## ROM01 dispatch-case label pass (CONFIRMED, 2026-09-18)

**ROM01 audit complete — 14 sites = all ROM01 `CALL ram:e0b2`
sites.** Owners byte-verified (`11 00 00 CD 37 D8` prologue →
final `C9`); external xrefs `7571→0DEF` and `767D→10EF` were
descriptor-data misdecodes, not callers.

* **Half A — 7 owners, 27 case functions merged + labelled, 40
  labels + 37 EOL comments:** `Program_LoadDipOrCom 0CE7-0FE5`,
  `Field_ResetCounterDispatch 10CF-1176`,
  `Session_AdvanceStageOnZero 14CF-153D`,
  `UI_FieldEditGetChoice 1D80-1FF2`, `Session_RxDispatch 2880-28FD`,
  `Session_ConnectCheck 2B43-2C4E`, `Session_CmdWalkTable 2C4F-2CD2`.
  See `gap-analysis-history.md` Half-A summary for the per-target
  label map (ephemeral audit file removed from published references).

* **Half B — 7 already-merged sites, 33 labels, no merges:**
  `3b53` `Session_FieldDispatch`, `45d1` `Session_RedrawField`,
  `4a2d` `Field_MatchPictureChar`, `581f` `Session_DispatchSub`, `5991`
  `Session_DispatchWrap`, `5e2e` `Field_FormatThreeAttempts`,
  `66ec` `UI_PostDescriptor`. `5e41` `CmdHandlerCount` renamed
  `FieldFormat_Default`. See Half-B summary in `gap-analysis-history.md`
  (ephemeral audit file removed from published references).

Guarded total 1028 → 1001 internal (1002 guarded) because 27 case
functions were absorbed as labels — not a coverage loss.

**Superseded Part-A `257f` handlers — RESOLVED (CONFIRMED):**
`Field_StepMode1 2569`, `Field_StepMode2 2572`,
`Field_ApplyStepMode 2593` (and `Field_StepNoop 257b`) are blocks of
the routine at `254b` (prologue `11 00 00 CD 37 D8` → `JP 257c`
dispatcher → `2593` shared continuation → `RET 2658`). The earlier
"audit `257f` OPEN" item is closed; the functions were absorbed and
labelled under the Half-A model (owner `14CF`/`10CF` region — exact
owner/labels in the Half-A audit file above).

## ROM00 dispatch label pass (CONFIRMED, 2026-09-18)

**ROM00 audit complete — 25 sites = all ROM00 `CALL ram:e0b2`
sites, hybrid model applied (CONFIRMED).** Each site audited and
converted to **one function per prologue-delimited routine +
labels** at case targets and shared continuations. Total owners
**23 routines** (two shared: sites 8+9 share `Session_CmdCommand
4ae0-4d28`, sites 17+18 share `Session_CmdEndTx 52a5-5427`). All
owners byte-verified (`11 00 00 CD 37 D8` prologue → final `C9`);
interiors discriminated by that prologue check.

* Owners extended: `Session_TxAppendString 3ede-3f1f`,
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
  `Session_TxStringSender 5f58-606b`.

* **Site-1 owner correction (CONFIRMED):** the audit first named
  `3ede` as owner of the `3fec` dispatcher, but `ROM00::3f20`
  (`Session_CoroJumpTx`) is itself a prologue entry
  (`11 00 00 CD 37 D8`) with real external callers (`5346`, `4c3a`,
  `ROM00::7dbe` vector, `ram:ed88`). Corrected: `3f20` is the
  owning routine (`3f20-4009`); `3ede` is a separate routine ending
  at `3f1f`.

* **Absorbed:** ~89 case-block functions deleted (12 from the audit
  Deletion List + 77 interior blocks found by a prologue check).
  Discriminator: only real routine entries start with
  `11 00 00 CD 37 D8`; among interiors only `3f20` did — all
  others were blocks (no external callers). ~113 labels created at
  case targets.

* **Residual ROM00 `FUN_*` now = 1 (CONFIRMED retained):**
  `441b` — zero xrefs, dead coroutine yield; documented open
  question (see `gap-analysis-history.md` residual pass). Previous
  5-deferred set resolved: `2da5`, `4333`, `44ed`, `450d` renamed
  (see below).

Guarded total 1002 → 915 (−87) because 89 case-block functions
were absorbed as labels — not a coverage loss.

## Residual `FUN_*` pass — 14 renamed, 10 retained (CONFIRMED,
2026-09-18)

**24 targets: 14 renamed + plates, 10 retained with plates and
kept symbols.** All byte-verified; Ghidra saved.

* **Renamed (14):** `Session_ConfigShow` (`ROM00:2DA5`),
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

* **Correction (CONFIRMED):** the
  `Field_ValidateAlwaysPass*` name/evidence was wrong — the
  pointers sit at odd offsets (`ROM01:7E87`/`7E8B`/`7E8D`), so the
  names were changed to the mechanics
  `Field_ReturnOneStub1/2/3` and the table described as the
  `ROM01:7E87` pointer table. The "7E85 vtable" claim is
  **withdrawn**; the validator role is **SUSPECTED** only.

* **Retained (10) with documented open questions
     (CONFIRMED retained, plates set, symbols kept;
     updated 2026-09-19 — vtable reader LOCATED +
     barcode path exercised (--drive-serial);
     three retains dead across all five paths):**
     `ROM00:441B` (zero xrefs, **dead
     (unreachable in every exercised path; zero
     xrefs)** — unhit in all five bounded runs:
     boot, session-transaction, COM load,
     commstar attach, barcode probe
     (`--drive-serial --barcode-scan A1
     --barcode-probe --watch-pc 0904,441b,d937`
     reaches `[40320] Main Menu reached; driving
     barcode capture`, `barcode_status=succeeded`,
     hook `PC=9000 AF=0042 BC=0000 DE=0000
     HL=9000 IX=FA03 IY=FB65 SP=D611 bank=00`,
     stack `1468 FBB9 F691 FFFF DFDB 7213`,
     `FBB9..FBBC = b5f92700` (table `F9B5`, count
     39), returned 0 (probe rejects); previous
     `barcode_status=pending` was missing
     `--drive-serial`, superseded; `0904=0
     441B=0 D937=0` (CONFIRMED));
     `ROM01:0904` (alignment padding
     `NOP; NOP; RET`, not a real routine,
     zero xrefs, **dead (unreachable in every
     exercised path; zero xrefs; not a real
     routine)** — same five runs unhit);
     `ROM01:1177` (trivial stub, **CONFIRMED
     reachable** in every run via extended
     `boot_hw.py --watch-pc` — up to 13 hits;
     identity remains unknown) /
    `156F`/`1664`/`168E`/`16B8` (**CONFIRMED
    session-object vtable entries (methods)** at
    `ROM01:7C80` / `ram:D128` — 43 big-endian entries,
    `FFFF` at `ROM01:7CD8`; `ram:D130 = D128+8`
    alternate entry; `ram:D128` diverges at entries
    3–6 — see Phase 2; retain notes record vtable
    slot role; **reader LOCATED (CONFIRMED,
    emulator `--watch-read`):** `UI_FormExitDispatchNext`
    (`ROM01:06D3`-`0720`) increments `g_formIdxW`
    (`ram:D2DE`), rejects `index >=5` via
    `CALL 0xE0E7`, indexes 5-entry word-pointer
    table at `ram:D081` (`LD DE,0xD081; ADD HL,DE` at
    `ROM01:06EF`), double-indirects to callback
    slot (`ROM01:06F7`-`06FA`), calls via
    `CALL 0xD828` (`g_pUserCallbackTrampoline`);
    callback slots base `ram:D12F`, stride `0x0E`,
    first word little-endian ROM01 callback
    address (CONFIRMED, byte-verified slot
    contents): `D12F/D130=0x1177`,
    `D13D/D13E=0x156F`; `ram:D081` entries
    `0xD0F0/0xD13D/0xD121/0xD12F/0xD14B`
     (NULL-terminated) select callbacks
    `0x0A67/0x156F/0x1177/0x1177/0x156F`
    (CONFIRMED) — byte-verified slot contents
    and manual DATA xrefs added:
    `ram:D0F0`→`ROM01:0A67`,
    `ram:D121`→`ROM01:1177`,
    `ram:D12F`→`ROM01:1177`,
    `ram:D13D`→`ROM01:156F`,
    `ram:D14B`→`ROM01:156F` (so `ROM01:1177`
    reached via slots `D121` and `D12F`,
    `0x156F` via `D13D`/`D14B`); no static xref
    by double indirection — manual DATA xref
    `ROM01:06EF` → `ram:D081` added; plates
    updated at `ram:D081` (entry→callback
    listing) and `ram:D12F` (slot base + observed
    callbacks; Ghidra saved); function list
    unchanged); residual
    **RESOLVED/WITNESSED 2026-09-19 (CONFIRMED,
    emulator):** `D7` stub-patch **WITNESSED** —
    COM writes `D7 00 BF 48` into `EE00`-`EE03`
    (`0105/0108/010B/010E`, `0200:A5` marker;
    `164 writes` `D6D6×80 D736×20 D73B×20 D73E×20
    D740×20` boot plus COM stores; `0100:21`
    artifact corrected));
    `ROM01:4D86`/`4E79` (text-buffer builders;
   compiler-frame args `SP+0x0E`–`0x16` undecoded);
   `ram:D937` (zero xrefs, **dead (unreachable in
   every exercised path; zero xrefs)** — same five
   runs unhit).

## Data-typing — `ROM01:7545`/`757F`/`758B`/
`75EB`/`760D`/`79F4` + `ROM00:7C30`/`7D80`/`7D88`/
`7E50` + `ram:E105`/`D0E0` + 41 `tbl_Dispatch`
labels (CONFIRMED, 2026-09-19 — Ghidra saved;
function list unchanged — 915; no new inference;
parent-verified)

Previously `ROM01:757F-768E` was `undefined[272]`
with `tbl_UiCfgTemplates` etc. (2026-09-18). Now
superseded by typed data (CONFIRMED, byte-verified):

* **Types + labels created (CONFIRMED, Ghidra
   saved; function list unchanged — 915):**
  `ROM01:7545` `ushort[4]` `tbl_UiCfgRegionPrefix`;
  `ROM01:757F` `ushort[6]` `tbl_UiCfgNamePointers`
  (5 name pointers + `0000` terminator — the
  earlier `ushort[136]` estimate was corrected);
  `ROM01:758B`/`75EB`/`760D` each typed
  `UiCfgHeader` (new 20-byte struct:
  `EC EF F8 F0 98 EF D8 EF` magic +0..+7, fields,
  LE backlink +12h) as `tbl_UiCfgTemplateHeaders`
  (non-contiguous, so individual items);
  `ROM01:79F4` `char[1547]` `str_cfg_option_pool`
  (existing label kept); `ROM00:7C30` `byte[256]`
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
  `7C50` separate-table claim are superseded
  (CONFIRMED).

* **Structure (CONFIRMED mechanics):** the three
  `UiCfgHeader` items share the 20-byte header
  `EC EF F8 F0 98 EF D8 EF` + fields + LE
  self-backlink at `+12h`; their string pointers
  reference the shared option pool at `79F4`
  (`"PLINTH"`, `"V24 ADAPTOR"`, `"LOCAL LINK"`,
  baud rates, `ON`/`OFF`). Referenced from
  `Field_ConfigLoad` (`ROM01:05E0-06B0`) at `0620
  LD HL,0x758B`, `0658 LD HL,0x75EB`,
  `066A LD HL,0x760D`. The five-node
  `757F-768E` description above is superseded by
  the three typed headers (the earlier
  `tbl_UiCfgNode3/4` etc. were the same region
  under the old `undefined[272]` view).

* **Unresolved (OPEN/SUSPECTED — minor):** the
  `E1` prefix at `757F`, the `F479` header
  pointer (**SUSPECTED** bank-qualified), exact
  field semantics, and the end boundary above
  `768E` remain as before — no new inference
  here, only the typing/labels above were
  applied.

## Tail — compiler-runtime plates, module-A images, retained
stubs resolved (CONFIRMED, 2026-09-18)

**Item A — compiler-runtime plates `ram:e020-e0aa`
(CONFIRMED).** 7 plates added: `Lib_And16` (`e023`),
`Lib_Or16` (`e033`), `Lib_Xor16` (`e03b`), `Lib_Lnot16`
(`e043`), `Lib_SignedLe16` (`e06a`), `Lib_SignedGe16`
(`e06b`), `Lib_SignedLt16` (`e086`). 6 others in the range
were already plated. Ghidra saved.

**Item B — module-A ROM images (CONFIRMED).**
`ROM00:7409` and `ROM00:7472` are compiled-C prologues
(`11 00 00 CD 37 D8`) with zero `ROM00`-space xrefs that
reference `ram`-space addresses (`ram:d837`, `ram:e104`) —
i.e. module-A code destined for battery RAM. Labelled as
data (`tbl_ModuleA_RomImage_7409`,
`tbl_ModuleA_RomImage_7472`); **no functions created**.
Deferred by design (wrong address space if created in
`ROM00`).

**Item C — retained `FUN_*` resolved (CONFIRMED;
updated 2026-09-19 — vtable reader LOCATED; callback
xrefs linked, barcode path exercised
(--drive-serial); three retains dead across all
five paths).**
6 renamed: `ROM01:156f`→`Session_Obj_Method_6784`,
`1664`→`Session_Obj_Method_6b6d`,
`168e`→`Session_Obj_Method_6c84`,
`16b8`→`Session_Obj_Method_696f` (each prologue → `CALL` a
work function → tail-call `ROM01:1548`); **these
four are CONFIRMED session-object vtable entries
(methods) at `ROM01:7C80` / `ram:D128` (43 entries,
`FFFF` at `ROM01:7CD8`; `ram:D130 = D128+8`; big-
endian hi-first, Phase 2)** — retain notes record
the vtable slot role; **reader LOCATED (CONFIRMED,
emulator `--watch-read`):** `UI_FormExitDispatchNext`
(`ROM01:06D3`-`0720`) increments `g_formIdxW`
(`ram:D2DE`), rejects `index >=5` via `CALL 0xE0E7`,
indexes 5-entry word-pointer table at `ram:D081`
(`LD DE,0xD081; ADD HL,DE` at `ROM01:06EF`),
double-indirects to callback slot
(`ROM01:06F7`-`06FA`), calls via `CALL 0xD828`
(`g_pUserCallbackTrampoline`); callback slots base
`ram:D12F`, stride `0x0E`, first word little-endian
ROM01 callback address (CONFIRMED, byte-verified
slot contents): `D12F/D130=0x1177`,
`D13D/D13E=0x156F`; `ram:D081` entries
`0xD0F0/0xD13D/0xD121/0xD12F/0xD14B`
    (NULL-terminated) select callbacks
`0x0A67/0x156F/0x1177/0x1177/0x156F` (CONFIRMED)
— byte-verified slot contents and manual DATA
xrefs added: `ram:D0F0`→`ROM01:0A67`,
`ram:D121`→`ROM01:1177`, `ram:D12F`→`ROM01:1177`,
`ram:D13D`→`ROM01:156F`, `ram:D14B`→`ROM01:156F`
(so `ROM01:1177` reached via `D121` and `D12F`,
`0x156F` via `D13D`/`D14B`); no static xref by
double indirection — manual DATA xref
`ROM01:06EF` → `ram:D081` added; plates updated
at `ram:D081` (entry→callback listing) and
`ram:D12F` (slot base + observed callbacks;
Ghidra saved); function list unchanged; residual
    **RESOLVED/WITNESSED 2026-09-19 (CONFIRMED,
    emulator):** `D7` stub-patch **WITNESSED**
    (`D7 00 BF 48` into `EE00`-`EE03`,
    `0105/0108/010B/010E`, `0200:A5` marker;
    `0100:21` artifact corrected);
`4d86`→`Session_Obj_BuildTextBuf1`,
`4e79`→`Session_Obj_BuildTextBuf2` (text-buffer builders,
`COMPUTED_CALL` from `ROM01:7f1d`/`7f1f`). 4 retained with
plates: `ROM01:1177` (trivial stub, **CONFIRMED
reachable** in every run via extended
`boot_hw.py --watch-pc` — up to 13 hits; identity
remains unknown), `ROM00:441b` (zero-xref dead,
**dead (unreachable in every exercised path; zero
xrefs)** — unhit in all five runs: boot,
session-transaction, COM load, commstar attach,
barcode probe (`--drive-serial --barcode-scan A1
--barcode-probe --watch-pc 0904,441b,d937` gives
`0904=0 441B=0 D937=0`; barcode path exercised
with `barcode_status=succeeded`, hook `PC=9000
AF=0042` etc., superseded pending; CONFIRMED);
sibling `443c` used),
`ram:d937` (zero-xref bit-flag dispatcher over
`ram:e104`, **dead (unreachable in every exercised
path; zero xrefs)** — same five runs unhit),
`ROM01:0904` (alignment padding `NOP; NOP; RET`,
not a real routine, zero xrefs, **dead
(unreachable in every exercised path; zero xrefs;
not a real routine)** — same five runs unhit).

Coverage after Items A–C is the headline in
`gap-analysis.md`: auto `FUN_*` = 4 (ROM00 1, ROM01 2,
ram 1); named 910 (99.6 %).

## Code-gap sweep complete — 121 → 12 (CONFIRMED,
2026-09-18)

`find_code_gaps` dropped **121 → 12** gaps. The 121
were overwhelmingly **truncated-body continuations**
of compiled routines — Ghidra stopped at the
non-returning `CALL ram:d837` (`LD DE,0 /
CALL ram:d837` prologue is `11 00 00 CD 37 D8`) and
left a 6-byte prologue shell — **not** new
functions.

Applied (Ghidra saved, count unchanged):

* **209 shells extended** to their continuation
  (gap ends in `RET`, no prologue inside) via
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

Remaining **12 gaps — all non-code, expected**
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
  (descriptors/strings/tables, typed:
  `tbl_UiCfgRegionPrefix` at `7545` (`ushort[4]`),
  `tbl_UiCfgNamePointers` at `757F` (`ushort[6]`),
  `tbl_UiCfgTemplateHeaders` at `758B`/`75EB`/
  `760D` (`UiCfgHeader` 20 B each),
  `str_cfg_option_pool` at `79F4` (`char[1547]`),
  etc.; `ROM00:7409`/`7472` module-A images
  are separate and deferred by design).

These are data/vector regions, not missed code,
and `find_code_gaps` flags uncovered executable
memory including data.