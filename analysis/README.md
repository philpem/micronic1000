# Micronic 1000 analysis tools

Everything for reverse-engineering and emulating the Micronic 1000.

## Reusable firmware models — `micronic/`

A Python package of evidence-scoped models and harness helpers. The link
scaffold is not sufficient to build an interoperable Commstar adapter:

* `micronic.rtc.RTC146818` — HD146818 model; the **periodic tick
  cadence** follows Register A's RS nibble (1024 Hz default), exactly
  as the firmware programs it.
* `micronic.proto.Link` / `micronic.proto.LinkPeer` — raw
  byte-latch scaffold for the 4x transport: queues `LINK_RXD`,
  captures `LINK_TXD`, records `LINK_CTRL`/`LINK_CMD`/`LINK_PROBE`
  writes, and synthesizes `LINK_STATUS` polls. No frame grammar,
  checksum, or session roles are implemented; numeric types `2,3,4`
  and reply words are observed numeric triggers only.
* `micronic.program` — host-side COM/DIP image validator (CONFIRMED grammar
  from `doc/manual/program-formats.md`): classifies by first-chunk rule
  (`<14` bytes or first word != `C9 C8` → COM), validates DIP 14-byte LE
  header (magic `C9 C8`, system ID `0`/`E5 00`, block count ≤5), parses
  blocks, checks payload lengths and type-1 `len % 4 == 0`, enforces COM
  max `0xCF81`; error identifiers match the loader catalogue
  (`0x232B`/`0x2331`/`0x2334`/`0x232C`) where applicable and clamps image
  size at `0x8000` without rejection.
* `test_proto.py` covers the raw queue/latch API and the confirmed logical
  header checks.

## Emulator harnesses (Python `z80` module)

Requires the `z80` python module in `venv/`.

- **`boot_hw.py`** — the single canonical harness. Boots the firmware to
  kernel/self-test with a MAME-accurate I/O stub and an **RTC-model-driven
  periodic INT** (proves the HD146818 write path live), and adds paced
  keyboard injection (`--drive-serial`/`--serial`), LCD rendering
  (`--lcd`/`--no-lcd`/`--lcd-rate`), an expect DSL (`--expect`/
  `--expect-file`/`--expect-timeout`), multi-bank RAM (`--ram`/`--ram-size`,
  `--dump-bank`), and snapshot dumps (`--dump-mem`/`--snapshot`). `--help`
  prints full usage. Writes a full I/O trace to
  `/tmp/opencode/micronic_boot_io.txt`. Uses `micronic.rtc`.
- **`comms_tx_test.py`** — directed verification of the TX path:
  seed the link state + FDEA `{count, ptr}` descriptor, call
  `LinkTransferService` (2F86), capture port-4Dh bytes, compare
  against `micronic.proto`. **MATCH** (prelude + payload).
- **`comms_rx_test.py`** — exploratory RX strobe trace: queue bytes through
  the port-4Eh callback into `LinkBlockRx`/RX dispatcher (2FBD) and capture
  the 4A handshake. It does not verify frame acceptance because the two
  controller bytes excluded from the returned count remain **OPEN**.
- **`comms_duplex.py`** — reusable `proto.LinkPeer` regression: bridges the
  queue/latch interface to the actual firmware byte pumps for two directed
  raw-byte tests. It does not verify a Commstar exchange, controller framing,
  or electrical bit identities.

### `boot_hw.py` — visible harness details

**Memory safety:** single process, `timeout 300`, bounded `--max-slices`, 200k I/O log ring, `gc.disable()` + manual `collect`.

**LCD:** framebuffer at `FC06–FCA5` (160 bytes, 20 cols × 8 rows, ASCII). `LcdRefreshScreen` (ROM00:1E27) via `lcd_putc` (1F79) ports 23h/03h; `lcd_clear_spaces` writes 0xA0 spaces to FC06. Rendered with `\\x1b[H` home-cursor when changed or every `--lcd-rate` slices. Escape/CR/LF shown as space.

**Multi-bank RAM:** port `47h` (`BANK_SEL`, shadow `F791`) selects the 32K window `0000–7FFF`: `0=ROM0`, `1=ROM1`, `2..N=RAM pages` (32K each). Fixed RAM `8000–FFFF` is always present (32K). Totals: `128K=32K+3×32K (banks 2..4)`, `256K=32K+7×32K (banks 2..8)`, `512K=32K+15×32K (banks 2..16)`. Save/restore on `47h` write (only for installed banks). **Non-present banks read `0xFF` (open bus) and writes are discarded** — required for correct RAM sizing. The firmware walks banks `0x41..0x01` in `Boot_BankWalkInit` regardless of installed RAM; sizing is done by `contig_ram_map_test` (267A) and `ram_page_test_4banks` (2530), with `DelayCountUp` (271F) computing `FEAB = FEA9 * 0x20` (FEA9 = count of present pages) displayed as `Ram: NN K.B.` on the banner. With `--ram 256` the banner must show 256K (not 2016K = 63*0x20).

**Options:** `--ram` / `--ram-size` (128|256|512), `--drive-serial` / `--serial TEXT`, `--max-slices N`, `--dump-bank N`, `--lcd` / `--no-lcd` / `--lcd-rate N`, `--expect SPEC` (repeatable), `--expect-file FILE`, `--expect-timeout N`, `--upload PATH` (drive real loader via `Program_LoadByName`/`Program_ConsumeInputChunk`/`Program_FinalizeInput` below Commstar — not a Commstar peer; `--upload-name NAME` defaults to the input basename, `--upload-bank N` defaults to 2, `--upload-max-bytes N` defaults to 65535, optional `--upload-marker ADDR:VAL`, `--upload-no-run` stops after finalize/state 3), `--trace-session-builder 4|5` (bounded synthetic builder trace; bypasses only the separate preflight), `--trace-session-transaction 4` (bounded harness: runs builder form 4 through the actual service-33/link IRQ path, bypassing only the already documented separate preflight as builder trace 4 does; payload/command semantics remain OPEN), `-h`/`--help`.

**Expect DSL:** `match:keys` — wait until `match` substrings appear in LCD text, then inject `keys` via the keyboard ring (paced exactly like the `16C9` HALT wait, `FBC9` bit2, `FFA8==1`). Multiple `--expect` steps run in order.

- `match` may be empty (immediate) or a list joined by `,` or `&` meaning **AND** (all substrings must be present). Example: `"Ram:,K.B."` waits for both `"Ram:"` and `"K.B."`. For no-comma ambiguity use JSON list via `--expect-file`: `{"match":["Ram:","K.B."],"keys":"\\r"}`.
- `keys` escape sequences: `\\r`, `\\n` → `0x0D` (ENTER; `\\n` is mapped to `\\r`), `\\t` → `0x09`, `\\e`/`\\E` → `0x1B`, `\\\\` → `\\`, `\\xNN` → byte, `\\uNNNN` → unicode (via `unicode_escape`). Example: `--expect "To Continue Press>>:\\r"`.
- Separator variants: `match:keys`, `match::keys`, `match|keys` all split match from keys; first `:` is the delimiter (so `:` inside keys is safe if split on first colon).

**Examples:**
```sh
timeout 300 analysis/venv/bin/python3 analysis/boot_hw.py --lcd --max-slices 300000
timeout 300 analysis/venv/bin/python3 analysis/boot_hw.py --lcd --expect "To Continue Press>>:\\r" --expect "Serial:\\r12345678\\r" --expect "Main Menu:1"
timeout 300 analysis/venv/bin/python3 analysis/boot_hw.py --ram 512 --expect-file /tmp/steps.json --dump-bank 2
# steps.json: [{"match":"To Continue Press>>","keys":"\\r"},{"match":["Ram:","K.B."],"keys":"\\r"},{"match":"Main Menu","keys":"1"}]
```

## Program image validator

- **`validate_program.py`** — CLI for COM/DIP validation (no hardware): reads
  a file (or stdin), classifies via first-chunk rule, validates per
  `doc/manual/program-formats.md`, prints human or `--json` output.
  Exit `0`=valid, `1`=invalid, `2`=error. Example:
  `analysis/venv/bin/python3 analysis/validate_program.py prog.dip --json`
- **`test_program.py`** — self-contained golden regression tests for
  `micronic.program` (stdlib only, 35 tests). Run with
  `analysis/venv/bin/python3 analysis/test_program.py` or
  `python3 analysis/test_program.py` or `python3 -m unittest analysis.test_program`.
- **`test_boot_upload.py`** — opt-in emulator integration (bounded, requires `z80`): `MICRONIC_RUN_EMULATOR_TESTS=1 analysis/venv/bin/python3 analysis/test_boot_upload.py` runs 4 tests — COM Hello World, one-block DIP Hello World, maximum-size `0xCF81` COM load/byte verification (checks bytes through `D080` and loader state 3), and the bounded form-4 service-33/link IRQ transport transaction (exact wire bytes, controller queues, type-3 reply, and zero-payload receive object; mechanically valid only — command/payload meaning and peer realism remain OPEN). All 4 passed serially in verification; `test_program.py` 35/35 and `test_proto.py` 3/3 also passed. One emulator process at a time under `timeout`; uses the real loader callbacks below Commstar. Example bounded transaction: `analysis/venv/bin/python3 analysis/boot_hw.py --trace-session-transaction 4`.

## Decode scripts (static)

- `decode_chains.py` — decode the boot-load chains (fn=0/1/2 records)
  -> the src/dst/len of every module copy.
- `disasm_modules.py` — disassemble the chain-loaded module blobs.
- `trace_io.py` — chronological I/O trace of boot/RTC window.
- `watch_queue.py` — find the deferred-call queue consumer.
- `hunt_rtc.py` — (historical) early RTC scan.

## Other

- `BootTrace.java`, `BootTrace.pending.java` — Ghidra-side boot
  trace experiments.
- `micronic/README.md` — full reusable-model documentation.
- `../ghidra_scripts/FillBatteryRam.java` — loads the session modules
  into Ghidra RAM for static analysis.
