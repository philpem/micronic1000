# Gap analysis — Micronic 1000 (documentation / annotation coverage)

Status: 2026-08-29 (10th audit, synthetic builder + loader finalize), firmware
`micron1.bin` (overlay spaces `ROM00`/`ROM01`, `ram` resident kernel).
This is a **documentation-coverage** audit: which functions have *we* named
and commented, versus the auto-named `FUN_*` that Ghidra merely detected.

## Headline

| Space | Functions | Auto `FUN_*` (undocumented) | Named/non-`FUN_*` |
|-------|-----------|------------------------------|-------------------|
| ROM00 | 521 | **81** | 440 |
| ROM01 | 208 | **67** | 141 |
| ram | 186 | **11** | 175 |
| EXTERNAL | 1 | **0** | 1 |
| **Total** | **916** | **159** | **757 (82.6 %)** |

**Refreshed directly from Ghidra on 2026-08-29 (guarded 916).** Deferred
analysis re-instantiated previously named/symbolized bodies and the new
finalizer `Program_FinalizeInput` (`ROM01:1002`) was created. The current
inventory is strictly additive over the captured prior addresses: 67
re-instantiated functions were preserved rather than deleting documented
work, so the `FUN_*` count rose with the recovered bodies. The only
intentionally new function in this pass is `Program_FinalizeInput`.
The prior audit reported 849 total / 142 `FUN_*` / 707 named (83.3 %);
the increase to 916 / 159 / 757 reflects recovered bodies plus the one
new finalizer. These 159 auto-named functions are the remaining analysis
backlog, not completed coverage.

The three internal address spaces contain 915 functions. Ghidra's guarded
total also includes the existing external import `EXT_FUN_ram_0010` at
`EXTERNAL:00000001`, which accounts for the remaining named function.

Plate completeness was not recomputed in this pass. The loader functions
and the new `Program_FinalizeInput` carry plates; the 159 auto-named
functions remain undocumented by definition.

Earlier audits (480/88, 668/58, 686/1, 689/0, 750/0, 849/142) are history.

## Notes

- Numbers can drift with deferred auto-analysis; re-run the
  `search_functions FUN_` check after any run_analysis and delete/
  name real code and delete only byte-verified artifacts rather than
  recording either class as completed coverage.
- RAM02 overlay exists (owner-created): uninitialised block 0000-7FFF
  over `ram`; MCP cannot read uninit overlay bytes - load a hardware
  RAM dump in the GUI to visualise a RAM bank page.
- Loader docs are now closed for file format (see
  `manual/program-formats.md`); the **open item is the upstream
  physical/session provider** — `ram:D370` is
  `g_pProgramLoaderContinuation` (`Coroutine_SwapContinuation` `ram:D9F9`),
  not an input-provider pointer, and the complete Commstar provider/session
  semantics remain **OPEN**.

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
