# Gap analysis — Micronic 1000 (documentation / annotation coverage)

Status: 2026-09-18 (12th audit, refreshed coverage after gated defines), firmware
`micron1.bin` (overlay spaces `ROM00`/`ROM01`, `ram` resident kernel).
This is a **documentation-coverage** audit: which functions have *we* named
and commented, versus the auto-named `FUN_*` that Ghidra merely detected.

## Headline

| Space | Functions | Auto `FUN_*` (undocumented) | Named/non-`FUN_*` |
|-------|-----------|------------------------------|-------------------|
| ROM00 | 574 | **21** | 553 |
| ROM01 | 329 | **145** | 184 |
| ram | 195 | **2** | 193 |
| EXTERNAL | 1 | **0** | 1 |
| **Total** | **1099** | **168** | **931 (84.7 %)** |

**Refreshed directly from Ghidra on 2026-09-18 — after final-sweep batch 2
(1099 total).** Auto `FUN_*` = 168 (was 252); named = 931 (84.7 %). Per-space
split: ROM00 21 (drop of 84, approximating the ~68 guidance), ROM01 unchanged
145, ram 2. The 168 auto-named functions are the remaining analysis backlog,
not completed coverage. Increase from the 2026-08-30 audit (919 total /
159 `FUN_*` / 760 named, 82.7 %) reflects functions defined since then, not
new coverage.

The three internal address spaces contain 1098 functions. Ghidra's guarded
total also includes the existing external import `EXT_FUN_ram_0010` at
`EXTERNAL:00000001`, which accounts for the remaining named function.

Plate completeness was not recomputed in this pass. The 252 auto-named
functions remain undocumented by definition.

Earlier audits (480/88, 668/58, 686/1, 689/0, 750/0, 849/142, 916, 919) are history.

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
