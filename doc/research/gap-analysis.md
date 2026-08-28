# Gap analysis — Micronic 1000 (documentation / annotation coverage)

Status: 2026-08-28 (7th audit, runtime DIP/COM loader closed), firmware
`micron1.bin` (overlay spaces `ROM00`/`ROM01`, `ram` resident kernel).
This is a **documentation-coverage** audit: which functions have *we* named
and commented, versus the auto-named `FUN_*` that Ghidra merely detected.

## Headline

| Space | Functions | Auto `FUN_*` (undocumented) | Named/non-`FUN_*` |
|-------|-----------|------------------------------|-------------------|
| ROM00 | 394 | **62** | 332 |
| ROM01 | 172 | **66** | 106 (incl. the new `Program_*` loader functions) |
| ram   | 261 | **10** | 251 |
| **Total** | **827** | **138** | **689 (83.3 %)** |

**Refreshed directly from Ghidra on 2026-08-28.** The 2026-08-28 loader pass
added/renamed ROM01
functions in `0A67-10CE` (`Program_PrepareLoadGeometry` 0A67,
`Program_GenerateBlockChecksums` 0957, `Program_VerifyBlockChecksums` 09C2,
`Program_LoadByName` 0B82, `Program_ConsumeInputChunk` 0BAC,
`Program_LoadDipOrCom` 0CE7, `Program_ReportLoadError` 0CCB,
`Program_RunByName` 106F, `Program_NormalizeLoadRange` 0AE3) plus
`ram:D7F0` `RunLoadedProgram` and `ram:D081` `g_apScreenHandlerTables` /
`ram:D0F0` `g_apLoadRunHandlers` labels. Current function count is **827**;
`search_functions_enhanced` reports **138** auto-named functions (62 ROM00,
66 ROM01, 10 ram). These are the remaining analysis backlog, not completed
coverage.

Plate completeness was not recomputed in this pass. The loader functions
named on 2026-08-28 carry plates; the 138 auto-named functions remain
undocumented by definition.

Earlier audits (480/88, 668/58, 686/1, 689/0, 750/0) are history.

## Notes

- Numbers can drift with deferred auto-analysis; re-run the
  `search_functions FUN_` check after any run_analysis and delete/
  name real code and delete only byte-verified artifacts rather than
  recording either class as completed coverage.
- RAM02 overlay exists (owner-created): uninitialised block 0000-7FFF
  over `ram`; MCP cannot read uninit overlay bytes - load a hardware
  RAM dump in the GUI to visualise a RAM bank page.
- Loader docs are now closed for file format (see
  `manual/program-formats.md`); the **open item is the physical
  input-provider path** (coroutine/provider around `0C12`/`0CE7`/
  `ram:D370`), not the on-disk layout.

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
