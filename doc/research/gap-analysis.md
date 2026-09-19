# Gap analysis — Micronic 1000 (documentation / annotation coverage)

Status: 2026-09-19 (19th audit — §12 FINAL PASS
fully CLOSED + data-typing backlog applied:
`ROM01:7545` `ushort[4]`, `757F` `ushort[6]`
(corrected from `ushort[136]`), `758B`/`75EB`/
`760D` `UiCfgHeader` 20 B, `79F4` `char[1547]`,
`ROM00:7C30` `byte[256]` (7C50 is +0x20), `7D80`
`ushort[4]`, `7D88` `ushort[60]`, `7E50`
`ushort[34]`, `ram:E105` `byte[256]`, `ram:D0E0`
`byte[448]`, 41 `tbl_Dispatch` labels, 11
comments; 3 labels pinned, 7 Boot_entry fixes, 5
magic numbers decoded, `g_wCoroutineStepResult`
RESOLVED pointer-indirected at `ram:EA24`, E73E
refuted; no OPEN items; plate coverage 100 %,
no SHORT-form remains that §8 would reject),
firmware
`micron1.bin` (overlay
spaces `ROM00`/`ROM01`, `ram` resident kernel). This is
a **documentation-coverage** audit: which functions have
*we* named and commented, versus the auto-named `FUN_*`
that Ghidra merely detected.

## Headline

| Space | Functions | Auto `FUN_*` (undocumented) | Named/non-`FUN_*` |
|-------|-----------|------------------------------|-------------------|
| ROM00 | 487 | **1** | 486 |
| ROM01 | 232 | **2** | 230 |
| ram | 195 | **1** | 194 |
| EXTERNAL | 1 | **0** | 1 |
| **Total (guarded)** | **915** | **4** | **911** |
| **Total (internal)** | **914** | **4** | **910 (99.6 %)** |

**Refreshed directly from Ghidra on 2026-09-18 — after
code-gap sweep complete (121 → 12; bodies extended,
914 internal / 915 guarded total)** — function counts
unchanged through 2026-09-19 (item 2b 5 renames, 144
unplated plated, item 3 short-plate review 82 KEEP /
59 upgraded, item 4 127 rewrites + 90 labels +
`Boot_entry+1` fixes + pointer-indirected
`g_wCoroutineStepResult`, and data-typing backlog
types + 41 `tbl_` labels — all plate/comment/data-
type-only, no function renamed/created/deleted
except the 5 item-2b renames, which do not change the
count). Auto `FUN_*` = 4
(ROM00 1, ROM01 2, ram 1); named = 910 internal
(99.6 %; 911 guarded). Previous audit was 914 / 4 /
910; dispatch-case absorptions (1002 → 915, −87) remain.
See session log 2026-09-19 (items 2b, unplated,
short-plate, comment-style, data-typing) and
2026-09-18 code-gap sweep and
`re-notes/inline-dispatch.md` for the structural model.

The three internal address spaces contain 914 functions. Ghidra's
guarded total also includes the existing external import
`EXT_FUN_ram_0010` at `EXTERNAL:00000001`, which accounts for the
remaining named function.

**Plate coverage (CONFIRMED 2026-09-19): 100 %** — every
function now carries a plate. The 144 functions that had
`plateLen=0` (46 `ram` — mostly `SessionOpStub_*`/`Lib_*`/
`RegFile_*`, notable `Fcb_ParseFilename` CP/M FCB parser,
`Kernel_RunStagedCall` — 33 `ROM00`, 65 `ROM01`) were
plated with no renames/creates/deletes. **Item 3
short-plate review DONE 2026-09-19 (CONFIRMED):** all 141
plates <120 chars reviewed against §8 — **82 KEEP**
(genuinely trivial — math primitives, comparators,
simple port I/O, single-RET stubs, RST vectors,
constant-return helpers, simple RAM-cell setters, no-op
coroutine stubs) and **59 UPGRADE** to the full form
(brief/mechanics/In-Out-Clobbers/evidence tag, ~70 cols,
multi-line ASCII; 59 applied in Ghidra; function list
unchanged; saved); plate coverage 100 %, no SHORT-form
plate remains that §8 would reject. Typical upgrades:
`Lib_MemMove`, `Bdos_PreparedCall`, the `RegFile_*`
32-bit math, `Lib_Mulu16`/`Mul16Mod16`, session buffer
ops (`Session_TxFlush`, `Session_RxRefill`,
`Session_TxAppendByte`, `Session_RxConsumeByte`), TTY key
handlers, LCD helpers, message-box displays, link
init/timeout, clock repack, UI descriptor-chain ops. See
`research/TASKS.md` §12 item 3. The 4 retained `FUN_*`
remain with plates but kept symbols (documented open
questions — see residual pass below).

Earlier audits (480/88, 668/58, 686/1, 689/0, 750/0, 849/142, 916, 919,
1093/109, 1028/42, 1001/42, 914/24) are history.

## Structural model (CONFIRMED for this codebase)

**Hybrid model — standard for this codebase (CONFIRMED).**
An inline-switch dispatch (`CALL ram:e0b2` `Kernel_TableDispatch` +
inline table + `JP(HL)`) case is a **basic block of the routine that
owns the table**, kept as **one function**; navigation is restored
with **labels** (not functions) at each case target and at the shared
continuation. Rationale: the case blocks have no prologue and use
the parent's frame, so naming them as functions asserts a false ABI;
labels give the greppable name without that.

Example (CONFIRMED): `3a04` `Session_FieldDispatch` runs its prologue,
computes the switch value, `JP 3b53` (dispatcher); table `3b56`
cases (`01→3acb`, `02/80→3a1c`, `04→3a99`, `08→3a40`, `10→3a75`,
`20→3a51`, `40→3ab2`) each `JP 3b7a` (the routine `RET`). So `3a04`'s
body legitimately spans `3a04-3b7a` and the cases are blocks. Part B
merges below and the ROM01 dispatch-case label pass apply this model;
see `TASKS.md` 2026-09-18 Part B and the 2026-09-18 dispatch-case
label pass for the full site lists. The earlier "audit `257f` OPEN"
item is now **resolved** under this model (see below).

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
  See `/tmp/opencode/rom01_dispatch_auditA.md` for the per-target
  label map.

* **Half B — 7 already-merged sites, 33 labels, no merges:**
  `3b53` `Session_FieldDispatch`, `45d1` `Session_RedrawField`,
  `4a2d` `Field_MatchPictureChar`, `581f` `Session_DispatchSub`, `5991`
  `Session_DispatchWrap`, `5e2e` `Field_FormatThreeAttempts`,
  `66ec` `UI_PostDescriptor`. `5e41` `CmdHandlerCount` renamed
  `FieldFormat_Default`. See
  `/tmp/opencode/rom01_dispatch_auditB.md`.

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
  question (see session log 2026-09-18 residual pass). Previous
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

Coverage after Items A–C is the headline above: auto
`FUN_*` = 4 (ROM00 1, ROM01 2, ram 1); named 910
(99.6 %).

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

## Model — do not regress (CONFIRMED)

Code gaps in this firmware are **truncated-body
continuations**; the correct fix is **body
extension** (`ExtendFunctionBody.java` /
`Function.setBody`), **never** creating functions
from the gap list.

Discriminator (CONFIRMED): gap start lacks the
`11 00 00 CD 37 D8` prologue → continuation; a
continuation may end in `RET` or a tail-`JP`.

## Remaining structural work

**No structural analysis items remain** beyond the
12 non-code gaps above and the 4 documented
`FUN_*` retains (ROM00 1, ROM01 2, ram 1) —
see residual pass. Dispatch models (ROM01 14 +
ROM00 25) and the code-gap sweep are closed.
Data-typing is typed (see above:
`ROM01:7545`/`757F`/`758B`/`79F4`,
`ROM00:7C30`/`7D80`/`7D88`/`7E50`,
`ram:E105`/`D0E0`, 41 `tbl_Dispatch` labels;
`ROM00:7409`/`7472` module-A images remain
deferred by design — no further action) and the
retains are expected (CONFIRMED).

Annotation tail per `research/TASKS.md` §12
(2026-09-19 — §12 FINAL PASS fully CLOSED; no
OPEN items remain):
plate coverage 100 % (closed — 144 unplated plated;
**item 3 DONE 2026-09-19 — 141 reviewed: 82 KEEP /
59 upgraded to full form; no SHORT-form remains
that §8 would reject**); comment-style pass —
of 356 flagged comments, 137 REWRITE (first pass,
RAM cell / I/O port by numeric address →
descriptive label, applied in Ghidra) and 219
KEEP (value/mask, legitimate cross-reference, or
label already present) (CONFIRMED; function list
unchanged; 0 new labels needed); second pass
127 REWRITE (secondary cites + others — every
address cite → label, magic numbers / bit masks
decoded, opcode-restating text dropped; function
list unchanged; saved; no new labels needed)
(CONFIRMED); missing-label scan found 99 distinct
labels cited with no Ghidra symbol, 95 resolved to
concrete addresses, 90 created (6 already present;
function list unchanged; saved) (CONFIRMED);
**residual closed 2026-09-19 (CONFIRMED, Ghidra
saved):** 3 of 4 SUSPECTED labels pinned —
`g_bRxRingHead` already at `ram:F954` (verified,
skipped; supersedes `g_bEchoChar` SUSPECTED at same
address), `g_bLinkCmdShadow` created at `ram:F796`
(port `4Ch` `LINK_CMD` shadow; supersedes
`g_bIrStrobeShadow` SUSPECTED at same address),
`g_bOutputCount` created at `ram:FEA3` (supersedes
`g_bOutputCount` SUSPECTED `F998` — correct address
is `FEA3` per byte-verified reference);
`g_wCoroutineStepResult` — **RESOLVED 2026-09-19
(CONFIRMED): not a fixed RAM address.** It names the
buffer pointed to by `g_pCoroutineStepResultBuf` at
`ram:EA24`; one writer `ROM01:6DF6 LD (0xEA24),HL`
(HL from `ROM01:6909` → `Coroutine_Enter`) and
six readers in `Fs_SeekByteOffset` (`ROM01:6DDF-6EED`);
layout `+1` = 16-bit step-1 result, `+3` = 16-bit
step-2 result, `+0` unreferenced; `ram:E73E` has
zero refs program-wide — E73E hypothesis **refuted**
(CONFIRMED). `g_pCoroutineStepResultBuf` at `ram:EA24`
carries a repeatable comment and four EOLs at
`ROM01:6E8F`/`6E9E`/`6EBB`/`6ED8` now use the
`[*(g_pCoroutineStepResultBuf)+N]` form; no function
renamed; saved. **`Boot_entry+1` bug — FIXED
(CONFIRMED):** 7 comments at `ROM01:1ea1`, `1f96`,
`28bb`, `2b7b`, `2c95`, `3acb`, `ram:d777` rewritten
`Boot_entry+1` → `0001h` (intended page-zero cell;
`Boot_entry` is `ROM00:014b`, so `Boot_entry+1 =
014c`; note CP/M IOBYTE is at `0003h`, not `0001h`);
3 non-buggy uses retained; **magic numbers — 5
decoded (CONFIRMED):** `ROM00:15c4`, `02e5`, `02f1`,
`0f37` (PRE) and one more — `0x80` local-console
flag, `10h` 16-drive guard, `12h`/`01h` key scan
codes, coroutine step-zeroed slots (per-site as
applied); 12+ kept as adequate; one intended at
`ROM01:6e8b` had no comment — skipped (CONFIRMED
absent). **`bdos_entry_impl` proposal for
`ROM00:F180` — REJECTED (CONFIRMED, byte-verified):
`ROM00:0005` is `C3 80 F1` = `JP F180` outside
`ROM00`'s `0000h..7FFFh` window → target is
`ram:F180` (`Bdos_DispatchFn`, existing label);
phantom `ROM00:bdos_entry_impl` was wrong-space;
comment now `JP Bdos_DispatchFn (ram:F180) vectors
into the DIPOS kernel (battery RAM)` — not a §12
item and now closed (Ghidra saved).**
**CAUTION (CONFIRMED):** 2-digit hex in RTC
contexts ambiguous
— register index `01h`/`03h`/`05h`/`07h` ≠ I/O port
`07h` = `CTRL_07`; `RTC_ADDR`/`RTC_DATA` are
`08h`/`28h` — both passes corrected manually;
**review note (CONFIRMED):** `ROM00:0178` "keyboard
scan init" corrected to LCD subsystem init per
confirmed plate at `Lcd_Init` (`ROM00:1EEC`). The
590-name `Module_Name` mass rename (31-module
taxonomy, 588 applied in Ghidra + 2 collisions,
docs synced across 24 files, commit `993a45d`) is
**DONE** (CONFIRMED). **Data-typing backlog — DONE
2026-09-19 (CONFIRMED, Ghidra saved; function list
unchanged — 915; no new inference; parent-verified):**
`ROM01:7545` `ushort[4]` `tbl_UiCfgRegionPrefix`;
`ROM01:757F` `ushort[6]` `tbl_UiCfgNamePointers`
(5 name pointers + `0000` terminator — the earlier
`ushort[136]` estimate was corrected);
`ROM01:758B`/`75EB`/`760D` each `UiCfgHeader`
(new 20-byte struct: `EC EF F8 F0 98 EF D8 EF`
magic +0..+7, fields, LE backlink +12h) as
`tbl_UiCfgTemplateHeaders` (non-contiguous, so
individual items); `ROM01:79F4` `char[1547]`
`str_cfg_option_pool` (existing label kept);
`ROM00:7C30` `byte[256]` `tbl_FontCharWidth` (note
`7C50` is offset +0x20 within it, not a separate
table); `ROM00:7D80` `ushort[4]`
`tbl_StubTablePrefix`; `ROM00:7D88` `ushort[60]`
`tbl_SessionRuntimeStubSources` (renamed);
`ROM00:7E50` `ushort[34]` `tbl_FnPtrDispatch7E50`
(FFFF-terminated); `ram:E105` `byte[256]`
`g_abFontCharWidth`; `ram:D0E0` `byte[448]`
`g_abErrorStringTable`; 41 `tbl_Dispatch` labels
created (16 `ROM01` + 25 `ROM00`), all
`tbl_Dispatch_<name>` — previously only 1 of 41
sites had a `tbl_` label; 11 plate/repeatable
comments set; function list unchanged (915); saved;
`ushort[136]` and `7C50` separate-table claims
superseded (CONFIRMED). **§12 FINAL PASS is now
fully CLOSED (CONFIRMED)** — no OPEN items remain
(items 1, 2a, 2b, 3, 4, 5, 6 done);
`g_wCoroutineStepResult` pointer-indirected buffer
was the final OPEN label, E73E hypothesis
**refuted**; data-typing supersedes the
`undefined[272]` view (CONFIRMED).

## Notes

- Numbers can drift with deferred auto-analysis; re-run the
  `search_functions FUN_` check after any run_analysis and delete/
  name real code and delete only byte-verified artifacts rather than
  recording either class as completed coverage.
- RAM02 overlay exists (owner-created): uninitialised block 0000-7FFF
  over `ram`; MCP cannot read uninit overlay bytes - load a hardware
  RAM dump in the GUI to visualise a RAM bank page.
- Loader docs are now closed for file format (see
  `manual/program-formats.md`); the upstream
  physical/session provider for the loader is
  **RESOLVED 2026-09-19 (CONFIRMED, byte-verified)**
  — the `ram:D36A` pointer protocol (loader sets
  `D36A`/`D36C`/`D368`/`D393`, yields via `ram:D370`,
  `Program_ConsumeInputChunk` `ROM01:0BAC-0C9A`
  copies `min(D36C,D393)` bytes FROM `D36A` TO
  `ECD8+D368`) with five staging targets:
  `ram:ECDC` (14 B DIP/COM header — primary;
  `0xD05`/`0xD18`/`0xD2F`), `ram:D39B` (8 B DIP
  block descriptor prefix — `0xE59`/`0xE6C`),
  descriptor[+4] (Type-0 payload — `0xEEC`),
  `ram:D372` (4 B Type-1 `RST 10h` expansion —
  `0xF6F`/`0xF94`), `0x0100+D399` (COM body —
  `0xDB8`) (see `re-notes/os-diposb.md`);
  **residual sub-question (OPEN, does not affect
  the WHAT):** no ROM00 code reads
  `D36A`/`D36C`/`ECDC`/`D372`/`D39B`; how the
  session peer learns these addresses (presumably
  via RAM scheduler `ram:D820`-`D85F` feeding
  `ROM00:7E00`) remains untraced.

## Known ghost: ram:8c0c

`FUN_ram_8c0c` is a **false positive over a zero buffer** (a spurious CALL
from a jump-table byte). It was deleted once (TASKS item 18) and RE-CREATED
by a later auto-analysis. Re-deleted 2026-08-24; if it reappears after any
`run_analysis`, delete it again and do not name it — it is not code.

Same class (deleted 2026-08-26): `FUN_ram_9cf0` = 16 NOP/zero bytes
(padding buffer) auto-created as a function. Watch the ram padding regions
for further instances.

## Method / how the numbers were produced

- `get_function_count` + `search_functions` (name_pattern `FUN_`) via Ghidra
  MCP, classifying `FUN_*` (and `thunk_FUN_*`) as "not annotated by us".
- `FUN_*` ≈ unannotated in practice: we rename what we document. Refresh this
  file after any pass that creates or renames functions — it is the single
  canonical coverage tracker (AGENTS.md §12; do not keep competing counts in
  TASKS.md or elsewhere).
