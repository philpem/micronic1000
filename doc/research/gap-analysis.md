# Gap analysis — Micronic 1000 (documentation / annotation coverage)

Status: 2026-08-30 (11th audit, bounded form-4 service-33/link IRQ transaction), firmware
`micron1.bin` (overlay spaces `ROM00`/`ROM01`, `ram` resident kernel).
This is a **documentation-coverage** audit: which functions have *we* named
and commented, versus the auto-named `FUN_*` that Ghidra merely detected.

## Headline

| Space | Functions | Auto `FUN_*` (undocumented) | Named/non-`FUN_*` |
|-------|-----------|------------------------------|-------------------|
| ROM00 | 524 | **81** | 443 |
| ROM01 | 208 | **67** | 141 |
| ram | 186 | **11** | 175 |
| EXTERNAL | 1 | **0** | 1 |
| **Total** | **919** | **159** | **760 (82.7 %)** |

**Refreshed directly from Ghidra on 2026-08-30 (guarded 919).** Increase
from 916 is the recovered labelled state-machine body at `5A81`
(`SessionRxStateMachine`, via thunk `5A63` `Session_RxStateMachineThunk`
which already existed) plus the two new confirmed callback functions at
`2E72` (`Device_Service33Timeout`) and `2E85`
(`Device_Service33Complete`, via `ram:FDD2` `g_pSvc33Callback`). Ghidra
saved. The prior audit reported 916 total / 159 `FUN_*` / 757 named
(82.6 %); earlier audits (849/142, 935, etc.) are history. The 159
auto-named functions are the remaining analysis backlog, not completed
coverage. Renames in this pass: `Lib_MaxS16` -> `Lib_MinS16` at
`ROM00:5944`; `UiDialogCommitPair` -> `Program_StreamChunkCallbacks` at
`ROM01:0741` (128-byte callback-driven copy, `D2E2` state, mechanics-only);
`UiDialogDrawBlock` -> `Program_BridgeHandlerTables` at `ROM01:07EE`
(seven-slot handler-table bridge into `D0F0`, mechanics-only); `5A81`
plate corrected. Do not assert a service-33 provider link.

The three internal address spaces contain 918 functions. Ghidra's guarded
total also includes the existing external import `EXT_FUN_ram_0010` at
`EXTERNAL:00000001`, which accounts for the remaining named function.

Plate completeness was not recomputed in this pass. The loader functions,
`Program_FinalizeInput`, `Device_Service33Timeout`/`Complete`, and the
recovered `SessionRxStateMachine` carry plates; the 159 auto-named
functions remain undocumented by definition.

Earlier audits (480/88, 668/58, 686/1, 689/0, 750/0, 849/142, 916) are history.

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
