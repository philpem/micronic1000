# Gap analysis — Micronic 1000 (documentation / annotation coverage)

Status: 2026-09-19 (19th audit — §12 FINAL PASS fully CLOSED).
Historical per-pass detail has been moved to
[`gap-analysis-history.md`](gap-analysis-history.md).

This is a **documentation-coverage** audit: which functions have
*we* named and commented, versus the auto-named `FUN_*`
that Ghidra merely detected.

## Headline

| Space | Functions | Auto `FUN_*` (undocumented) | Named/non-`FUN_*` |
|-------|-----------|------------------------------|-------------------|
| ROM00 | 487 | **1** | 486 |
| ROM01 | 231 | **2** | 229 |
| ram | 196 | **1** | 195 |
| EXTERNAL | 1 | **0** | 1 |
| **Total (guarded)** | **915** | **4** | **911** |
| **Total (internal)** | **914** | **4** | **910 (99.6 %)** |

**Refreshed directly from Ghidra on 2026-09-19 (verified:
`get_function_count` = 915 guarded, `search_functions FUN_` = 4 at
`ROM01:0904`/`ROM00:441B`/`ram:D937`/`ROM01:1177`, `DumpFunctions.java`
= 914 internal: ROM00 487, ROM01 231, ram 196; guarded 915 incl.
`EXTERNAL:00000001`)** — after code-gap sweep complete (121 → 12;
bodies extended, 914 internal / 915 guarded total); counts
unchanged through 2026-09-18 → 2026-09-19 (item 2b 5 renames, 144
unplated plated, item 3 short-plate review 82 KEEP / 59 upgraded,
item 4 127 rewrites + 90 labels + `Boot_entry+1` fixes +
pointer-indirected `g_wCoroutineStepResult`, and data-typing backlog
types + 41 `tbl_` labels — all plate/comment/data-type-only, no
function renamed/created/deleted except the 5 item-2b renames, which do
not change the count). Auto `FUN_*` = 4 (ROM00 1, ROM01 2, ram 1);
named = 910 internal (99.6 %; 911 guarded). Previous audit was 914 / 4
/ 910; dispatch-case absorptions (1002 → 915, −87) remain. See session
log 2026-09-19 (items 2b, unplated, short-plate, comment-style,
data-typing) and 2026-09-18 code-gap sweep and
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
questions — see `gap-analysis-history.md` residual pass).

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
merges and the ROM01/ROM00 dispatch-case label passes apply this model;
see `gap-analysis-history.md` for the full site lists. The earlier "audit
`257f` OPEN" item is now **resolved** under this model.

Historical per-pass detail has been moved to
[`gap-analysis-history.md`](gap-analysis-history.md).

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
12 non-code gaps and the 4 documented
`FUN_*` retains (ROM00 1, ROM01 2, ram 1) —
see `gap-analysis-history.md` residual pass. Dispatch models (ROM01 14 +
ROM00 25) and the code-gap sweep are closed.
Data-typing is typed (see above:
`ROM01:7545`/`757F`/`758B`/`79F4`,
`ROM00:7C30`/`7D80`/`7D88`/`7E50`,
`ram:E105`/`D0E0`, 41 `tbl_Dispatch` labels;
`ROM00:7409`/`7472` module-A images remain
deferred by design — no further action) and the
retains are expected (CONFIRMED). One minor OPEN
residual remains (loader session-peer address discovery, does not affect
coverage; see Notes below).

Annotation tail per `research/TASKS.md` §12
(2026-09-19 — §12 FINAL PASS fully CLOSED; one
minor OPEN residual remains — loader session-peer address discovery,
does not affect coverage; see Notes below):
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
fully CLOSED (CONFIRMED)** — items 1, 2a, 2b, 3, 4, 5, 6 done; one minor
OPEN residual remains (loader session-peer address discovery, see Notes
below);
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
