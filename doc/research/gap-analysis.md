# Gap analysis — Micronic 1000 (documentation / annotation coverage)

Status: 2026-09-18 (14th audit, ROM00 InlineTableDispatch hybrid
pass), firmware `micron1.bin` (overlay spaces `ROM00`/`ROM01`, `ram`
resident kernel). This is a **documentation-coverage** audit: which
functions have *we* named and commented, versus the auto-named `FUN_*`
that Ghidra merely detected.

## Headline

| Space | Functions | Auto `FUN_*` (undocumented) | Named/non-`FUN_*` |
|-------|-----------|------------------------------|-------------------|
| ROM00 | 487 | **5** | 482 |
| ROM01 | 232 | **17** | 215 |
| ram | 195 | **2** | 193 |
| EXTERNAL | 1 | **0** | 1 |
| **Total (guarded)** | **915** | **24** | **891** |
| **Total (internal)** | **914** | **24** | **890 (97.4 %)** |

**Refreshed directly from Ghidra on 2026-09-18 — after ROM00
InlineTableDispatch hybrid pass (914 internal / 915 guarded total).**
Auto `FUN_*` = 24 (ROM00 5, ROM01 17, ram 2); named = 890 internal
(97.4 %; 891 guarded). Function count dropped because **~89**
dispatch-case functions were absorbed as **labels** (not a coverage
loss) — 12 from the audit Deletion List plus 77 interior blocks
identified by a prologue check. Guarded total 1002 → 915 (−87;
internal 1001 → 914); earlier ROM01 drop 84 → 17 (12 Part-A
`(retain)` + 5 B1 `(retain)`) remains. See session log 2026-09-18
ROM00 dispatch pass and `re-notes/inline-dispatch.md` for the
structural model, owner extents, and superseded names.

The three internal address spaces contain 914 functions. Ghidra's
guarded total also includes the existing external import
`EXT_FUN_ram_0010` at `EXTERNAL:00000001`, which accounts for the
remaining named function.

Plate completeness was not recomputed in this pass. The 24 auto-named
functions remain undocumented by definition.

Earlier audits (480/88, 668/58, 686/1, 689/0, 750/0, 849/142, 916, 919,
1093/109, 1028/42, 1001/42) are history.

## Structural model (CONFIRMED for this codebase)

**Hybrid model — standard for this codebase (CONFIRMED).**
An inline-switch dispatch (`CALL ram:e0b2` `InlineTableDispatch` +
inline table + `JP(HL)`) case is a **basic block of the routine that
owns the table**, kept as **one function**; navigation is restored
with **labels** (not functions) at each case target and at the shared
continuation. Rationale: the case blocks have no prologue and use
the parent's frame, so naming them as functions asserts a false ABI;
labels give the greppable name without that.

Example (CONFIRMED): `3a04` `SessionFieldDispatch` runs its prologue,
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

* `3a04` `SessionFieldDispatch` → `3b7a`
* `444f` `SessionRedrawField` → `463e`
* `576c` `CmdDispatchSub` → `5839`
* `583a` `CmdDispatchWrap` → `59a8`
* `6292` `Ui_PostKeyedEntry` → `62e4`
* `6633` `Ui_PostDescriptor` → `6759`
* `6aa9` `Ui_RecordMatchAndPost` → `6b6c`

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
  `Ui_FieldEditGetChoice 1D80-1FF2`, `SessionRxDispatch 2880-28FD`,
  `SessionConnectCheck 2B43-2C4E`, `SessionCmdWalkTable 2C4F-2CD2`.
  See `/tmp/opencode/rom01_dispatch_auditA.md` for the per-target
  label map.

* **Half B — 7 already-merged sites, 33 labels, no merges:**
  `3b53` `SessionFieldDispatch`, `45d1` `SessionRedrawField`,
  `4a2d` `Field_MatchPictureChar`, `581f` `CmdDispatchSub`, `5991`
  `CmdDispatchWrap`, `5e2e` `Field_FormatThreeAttempts`,
  `66ec` `Ui_PostDescriptor`. `5e41` `CmdHandlerCount` renamed
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
  `Session_ManualConnect 578f-5829`, `SessionRxByteLoop 59fb-5b57`,
  `SessionTxStringSender 5f58-606b`.

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

* **Residual ROM00 `FUN_*` = 5 (CONFIRMED deferred):** `2da5`,
  `4333`, `441b`, `44ed`, `450d` — left for a later pass; not
  InlineTableDispatch cases.

Guarded total 1002 → 915 (−87) because 89 case-block functions
were absorbed as labels — not a coverage loss.

## Remaining structural work

**ROM01 and ROM00 dispatch models are now both applied
(CONFIRMED).** No `CALL ram:e0b2` site remains unaudited (ROM01 14,
ROM00 25). Remaining coverage work is the **24 residual `FUN_*`**
(ROM00 5, ROM01 17, ram 2) plus the code-gap and data-typing tail —
same tail as before, now with both hybrid passes closed.

## Notes

- Numbers can drift with deferred auto-analysis; re-run the
  `search_functions FUN_` check after any run_analysis and delete/
  name real code and delete only byte-verified artifacts rather than
  recording either class as completed coverage.
- RAM02 overlay exists (owner-created): uninitialised block 0000-7FFF
  over `ram`; MCP cannot read uninit overlay bytes - load a hardware
  RAM dump in the GUI to visualise a RAM bank page.
- Loader docs are now closed for file format (see
  `manual/program-formats.md`); the upstream physical/session provider
  for the loader is now substantially advanced (see
  `re-notes/os-diposb.md`) — `ram:D370` is the loader's coroutine
  peer/rendezvous slot (`Coroutine_SwapContinuation` `ram:D9F9`), fed by
  the session program-data receive (`Session_ReadStreamChunk`
  `ROM00:3E6A`); only the exact staging cell/buffer the peer fills
  remains **OPEN**.

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
