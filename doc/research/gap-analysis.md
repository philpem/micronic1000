# Gap analysis — Micronic 1000 (documentation / annotation coverage)

Status: 2026-09-18 (12th audit, refreshed coverage after gated defines), firmware
`micron1.bin` (overlay spaces `ROM00`/`ROM01`, `ram` resident kernel).
This is a **documentation-coverage** audit: which functions have *we* named
and commented, versus the auto-named `FUN_*` that Ghidra merely detected.

## Headline

| Space | Functions | Auto `FUN_*` (undocumented) | Named/non-`FUN_*` |
|-------|-----------|------------------------------|-------------------|
| ROM00 | 574 | **23** | 551 |
| ROM01 | 259 | **17** | 242 |
| ram | 195 | **2** | 193 |
| EXTERNAL | 1 | **0** | 1 |
| **Total (guarded)** | **1029** | **42** | **987** |
| **Total (internal)** | **1028** | **42** | **986 (95.9 %)** |

**Refreshed directly from Ghidra on 2026-09-18 — after final-sweep ROM01
Part B (1028 internal / 1029 guarded total).** Auto `FUN_*` = 42
(ROM00 23, ROM01 17, ram 2); named = 986 internal (95.9 %; 987 guarded).
ROM01 dropped 84 → 17. The 17 are the 12 Part-A `(retain)` entries plus
the 5 B1 `(retain)` shells. Part B completed the ROM01 cluster: 32
compiler-prologue shells (`LD DE,0 / CALL ram:d837`) extended to their
full bodies (27 named, 5 retained); 38 computed-dispatch blocks and 12
named interior fragments absorbed into parents and deleted;
`FUN_7599`/`FUN_7e14` deleted as data; `ROM01::3add` `FieldPadValue`
deleted as a mid-instruction banking artifact (`ROM01::0040`/`ROM00::0040`
both select bank 0, so `ROM01::0044`'s `JP 3ADD` resolves physically to
`ROM00::3add`). Guarded total 1093 → 1029 (−64; internal 1092 → 1028).
Increase from the 2026-08-30 audit (919 / 159 / 760, 82.7 %) reflects
functions defined since then, not new coverage. See session log
2026-09-18 Part B for the structural model and superseded names.

The three internal address spaces contain 1028 functions. Ghidra's
guarded total also includes the existing external import
`EXT_FUN_ram_0010` at `EXTERNAL:00000001`, which accounts for the
remaining named function.

Plate completeness was not recomputed in this pass. The 42 auto-named
functions remain undocumented by definition.

Earlier audits (480/88, 668/58, 686/1, 689/0, 750/0, 849/142, 916, 919,
1093/109) are history.

## Structural model (CONFIRMED for this codebase)

An inline-switch case reached via `CALL ram:e0b2`
(`InlineTableDispatch`) + `JP(HL)` is a **basic block of the routine
that owns the table**, not an independent function. Example
(CONFIRMED): `3a04` `SessionFieldDispatch` runs its prologue, computes
the switch value, `JP 3b53` (dispatcher); table `3b56` cases
(`01→3acb`, `02/80→3a1c`, `04→3a99`, `08→3a40`, `10→3a75`, `20→3a51`,
`40→3ab2`) each `JP 3b7a` (the routine `RET`). So `3a04`'s body
legitimately spans `3a04-3b7a` and the cases are blocks. Part B merges
below apply this model; see `TASKS.md` 2026-09-18 Part B for the full
cluster list and the open audit of Part-A's `257f` case targets.

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

**Flag for follow-up (OPEN):** Part A named dispatch-case targets of
table `257f` as separate functions (`Field_StepForward 2569`,
`Field_StepBackward 2572`, `Field_StepNoop 257b`, `Field_StepRender
2593`) and `Field_FlagHandler3a1c`. Under this model those are LIKELY
the same mis-split (Ghidra auto-functions at `JP(HL)` case targets) and
should be audited. Do NOT change them now; see `TASKS.md` open item
with discriminating check (whether the `257f` targets are `JP(HL)` case
blocks of a table-owning routine).

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
