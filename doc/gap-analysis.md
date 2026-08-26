# Gap analysis — Micronic 1000 (documentation / annotation coverage)

Status: 2026-08-26 (5th audit), firmware `micron1.bin`
(overlay spaces `ROM00`/`ROM01`, `ram` resident kernel). This is a
**documentation-coverage** audit: which functions have *we* named and
commented, versus the auto-named `FUN_*` that Ghidra merely detected.

## Headline

| Space | Functions | Auto `FUN_*` (undocumented) | Named by us |
|-------|-----------|------------------------------|-------------|
| ROM00 | 394 | **0** | all named |
| ROM01 | 164 | **0** | all named |
| ram   | 192 | **0** | all named |
| **Total** | 750 | **0** | **100 %** (naming) |

**PASS A COMPLETE (2026-08-25), re-verified 2026-08-26**: zero `FUN_*`
remain. Deferred auto-analysis keeps resurrecting a few `FUN_*` shells;
each reappearance is triaged and either named (if real code) or deleted
(if a NOP/zero-buffer artifact) in the same pass — see the 2026-08-26
session entries in TASKS.md. The naming invariant is `FUN_* == 0`.

**Plate debt (separate from naming):** 299 named functions still carry no
plate comment (ROM00 238, ROM01 61; ram saturated). Tracked in TASKS.md
"plateless tranches". 13 thunks are intentionally excluded.

Earlier audits (480/88, 668/58, 686/1, 689/0) are history.

## Notes

- Numbers drift ±3 with deferred auto-analysis; re-run the
  `search_functions FUN_` check after any run_analysis and delete/
  name any new 1-byte artifacts rather than recording them as coverage.
- RAM02 overlay exists (owner-created): uninitialised block 0000-7FFF
  over `ram`; MCP cannot read uninit overlay bytes - load a hardware
  RAM dump in the GUI to visualise a RAM bank page.

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