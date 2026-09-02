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
* `micronic.commstar.SyntheticWorkflow` — application-owned adapter policy
  for a selected source, opaque scan uploads, optional validated COM/DIP
  download/run, feedback, and safe-removal. It is not a recovered command
  grammar.
* `test_proto.py` covers the raw queue/latch API and the confirmed logical
  header checks.
* `micronic.barcode` — the barcode/edge-capture side: a `Wand` model of
  the port-2Dh level source, a Code 39 encoder and reference decoder, and
  a **Code 39 decode hook written in Z80** for installation at the
  firmware's `FBC2` hook vector (`decoder_source()` / `assemble_decoder()`),
  plus a hook **probe** that records the machine state it is entered with.
  Every width is in the unit the capture loop records; the module carries
  the firmware limits it enforces (`MIN_WIDTH` 8, `MAX_WIDTH` 0x17FF,
  `MAX_ELEMENTS` 128) with the instruction that imposes each.
* `micronic.z80asm` — a small two-pass Z80 assembler, so payloads injected
  into the emulator live in the repository as readable source rather than
  hex blobs. It implements the subset those payloads use and raises
  `AsmError` on anything else rather than emitting something wrong.
* `test_barcode.py` covers the Code 39 table invariants, the codec, the
  wand's off-by-one against a Python model of the capture loop, the
  assembler, the Z80 decoder on a bare CPU, and — under
  `MICRONIC_RUN_EMULATOR_TESTS=1` — the whole path through the real ROM.

## Emulator harnesses (Python `z80` module)

Requires the `z80` python module in `venv/`.

- **`boot_hw.py`** — the single canonical harness. Boots the firmware to
  kernel/self-test with a MAME-accurate I/O stub and an **RTC-model-driven
  periodic INT** (proves the HD146818 write path live), and adds paced
  keyboard injection (`--drive-serial`/`--serial`), LCD rendering
  (`--lcd`/`--no-lcd`/`--lcd-rate`), an expect DSL (`--expect`/
  `--expect-file`/`--expect-timeout`), multi-bank RAM (`--ram`/`--ram-size`,
  `--dump-bank`), snapshot dumps (`--dump-mem`/`--snapshot`), and
  execution/memory watches (`--watch-pc`, `--watch-mem`, `--fill-mem`).
  `--help` prints full usage. Writes a full I/O trace to
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

**Options:** `--ram` / `--ram-size` (128|256|512), `--drive-serial` / `--serial TEXT`, `--max-slices N`, `--dump-bank N`, `--lcd` / `--no-lcd` / `--lcd-rate N`, `--expect SPEC` (repeatable), `--expect-file FILE`, `--expect-timeout N`, `--upload PATH` (drive real loader via `Program_LoadByName`/`Program_ConsumeInputChunk`/`Program_FinalizeInput` below Commstar — not a Commstar peer; `--upload-name NAME` defaults to the input basename, `--upload-bank N` defaults to 2, `--upload-max-bytes N` defaults to 65535, optional `--upload-marker ADDR:VAL`, `--upload-no-run` stops after finalize/state 3), `--trace-session-builder 4|5` (bounded synthetic builder trace; bypasses only the separate preflight), `--trace-session-transaction 4` (bounded harness: runs builder form 4 through the actual service-33/link IRQ path, bypassing only the already documented separate preflight as builder trace 4 does; payload/command semantics remain OPEN), `--trace-loadrun-source plinth|v24 --trace-loadrun-v24-mode 0..3` (the V24 mode selector is an experimental trace control, not a V24 peer), `--synthetic-loadrun FILE` (serves a validated COM/DIP file as raw state-44 program data after the confirmed PLINTH control path; a 126-byte chunk is regression-tested but not a proven maximum), `--synthetic-workflow FILE` (manifest wrapper for the tested PLINTH image path; `run_after_load` invokes the real ROM run path while records, feedback, and safe removal remain adapter policy), optional `--synthetic-loadrun-finalize` (adapter policy: calls the real loader finalizer with success after the final payload; not a claimed Commstar EOF frame), and `--trace-loadrun-debug` (bounded diagnostics for a stalled state-44 reply), `-h`/`--help`.

**Watching execution and memory:** three instruments, all usable together and all reported again at exit.

- `--watch-pc A[,B,...]` — a real breakpoint at each hex address; prints the registers on each hit (first `WATCH_REPORT_LIMIT` = 4 hits per address) and the per-address totals at exit. Unlike sampling the PC between slices, it misses nothing.
- `--watch-mem LO:HI[,...]` — every memory write landing in an **inclusive** hex range, reported with the address, the value, the PC, `SP` and the current bank. Note the asymmetry with `--dump-mem`, which takes `ADDR:LEN`. It hooks the CPU's write callback, so it sees `PUSH` and `LDIR` stores as well as `LD (nn),r`; host-side pokes (`host_write`) deliberately bypass it. The printed PC is the address of the instruction **after** the writing one (verified against a known `LD (nn),HL` and a `PUSH`). Printing stops at `--watch-mem-limit` per range (default 24) but counting does not, so a hot region cannot flood the log; the exit summary gives the write count, the distinct writing PCs with counts, and the lowest and highest address touched. Because stack pushes are ordinary writes, a range placed below a stack top measures how far that stack descends.
- `--fill-mem LO:HI[,...]` — seed an inclusive range of fixed RAM once, at the point the destructive power-on RAM test would have finished (`ram_page_test_4banks`, ROM00:2530), which is the earliest point a marker can survive. The default pattern is address-derived, `mem[a] = (a ^ (a >> 8)) & 0xFF`, so neither a zero-fill nor a constant write can hide in it; `--fill-mem-value NN` substitutes a constant when you want to run a fill and its complement. At exit each range reports how many bytes still hold the marker and the lowest and highest that do not — the survival/low-water mark. Filling live cells (the port shadows at `F780`-`F799`, say) will break the run.

Example — prove a span is untouched while measuring how deep the system stack really goes:

```sh
timeout 420 analysis/venv/bin/python3 analysis/boot_hw.py --no-lcd \
    --expect "To Continue Press>>:\r" --expect "serial number:\r12345678\r" \
    --expect "Main Menu:3" --expect "Version" \
    --watch-mem f68d:f77f,ffa9:ffff --fill-mem f68d:f819
```

See `doc/re-notes/unbanked-ram-map.md` for the results this produced.

**Barcode wand (`--barcode-*`):** a model of whatever the firmware reads on `EXTBUS_EDGE` (port `2Dh`) bit 0, so a scan can be driven end to end. Before this the harness returned a constant `FFh` for that port, the edge-detect loops at `ROM00:13CB`/`13ED` never saw a transition, and nothing on the capture path had ever executed.

- **Width unit.** Widths are the numbers the firmware records. The capture loop starts each element at `HL=1` and pre-increments before every poll (`ROM00:13E5`/`13E8`), so an element held for *N* samples is pushed as *N+1*; the model holds each level for `width-1` samples so that what goes in on the command line is what lands in the table at `F9B5`. Limits, all byte-verified: minimum 8 (`ROM00:13FA` `SUB 8` / `JR C` restarts the whole capture below it), maximum 6143 (`ROM00:13EA` `CP D` with `D=18h` ends the capture — this is what the trailing quiet zone does), and at most 128 elements (`ROM00:140F` `CP 80h`, the point at which the reverse copy from `FBB3` downward would collide with the destination at `F9B5`).
- **Only the capture loop draws samples.** The wand answers with the quiet line unless the PC is at one of the two `IN A,(2Dh)` sites inside the capture (`13CB` arming, `13ED` timing). The presence probe at `12A3` and the idle polls at `1302`/`1317`/`132E`/`1370` therefore cannot eat samples out of a scan and shift every recorded width.
- `--barcode-widths W1,W2,...` feeds raw element widths, alternating bar, space, bar, … starting with a bar (the capture arms on the 0→1 edge, so element 0 is always the first dark bar). `--barcode-scan TEXT` encodes TEXT as Code 39 instead, with `--barcode-narrow`/`--barcode-wide` (default 12/30) and `--barcode-idle` for the leading quiet zone.
- `--barcode-probe` installs a hook that records the registers, stack, bank shadow and parameter block it was entered with, then rejects the scan. `--barcode-decode` installs the Code 39 decoder; `--barcode-hook HEX` installs arbitrary bytes. `--barcode-hook-at` (default `9000`, free upper TPA) and `--barcode-hook-bank` (default 0) control where the `FBC0` thunk points.
- `--barcode-bdos` reads the scan back the way a program would — `CALL 0005h` with `C=03h`, repeatedly. Without it the capture is driven directly (`DI`, `CALL 13B8`) and the run stops at `ROM00:30BD`, because the delivery tail jumps through the device callback at `FDD2` and never returns to its caller.

Acceptance run — widths in, matching table out:

```sh
timeout 550 analysis/venv/bin/python3 analysis/boot_hw.py --no-lcd \
    --max-slices 60000 --expect-timeout 45000 \
    --expect "To Continue Press>>:\r" \
    --expect "Enter the,Workstation:\r12345678\r" --expect "Main Menu" \
    --barcode-scan A1 --barcode-probe --watch-mem f9b5:fbb4
```

Whole path — Code 39 hook installed, scan read back through BDOS `03h`:

```sh
    ... --barcode-scan A1 --barcode-decode --barcode-bdos --barcode-expect A1
# [barcode] fn 03h returned 1b024131  b'\x1b\x02A1'
```

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
- **`test_boot_upload.py`** — opt-in emulator integration (bounded, requires `z80`): `MICRONIC_RUN_EMULATOR_TESTS=1 analysis/venv/bin/python3 analysis/test_boot_upload.py` runs nine tests covering COM/DIP loading, maximum-size COM validation, the bounded form-4 service-33 transaction, single- and multi-chunk synthetic PLINTH streams, workflow manifest run behavior, V24 mode-counter editing, and a bounded mode-1 V24 loader trace. The synthetic peer exercises confirmed control and raw payload paths; command grammar and EOF envelope remain compatibility assumptions. One emulator process at a time under `timeout`.

## Decode scripts (static)

- `decode_chains.py` — decode the boot-load chains (fn=0/1/2 records)
  -> the src/dst/len of every module copy.
- `disasm_modules.py` — disassemble the chain-loaded module blobs.
- `trace_io.py` — chronological I/O trace of boot/RTC window.
- `watch_queue.py` — find the deferred-call queue consumer.
- `hunt_rtc.py` — (historical) early RTC scan.

## Ghidra scripts (`ghidra/`)

- `AnalyseMicronicRom.java` — **the one to run.** Consolidated,
  self-contained, idempotent listing repair, in seven ordered passes:
  reconstructs the battery-RAM image (pass 0, absorbed from
  `FillBatteryRam.java`), clears the wrong no-return flag on the `ram:D837`
  frame helper, types both banks' boot-load chains and links their
  deferred-call targets, types `RST 10h` inline operands, defines the
  `InlineTableDispatch` tables, creates functions at every compiler frame
  prologue, and links all 281 runtime stub slots to the routines they stand
  for. No arguments. Documented in `doc/re-notes/ghidra-repair-script.md`.
- `DefineInlineTables.java` — the standalone version of just the
  `InlineTableDispatch` pass (see `doc/re-notes/inline-dispatch.md`).

## Other

- `BootTrace.java`, `BootTrace.pending.java` — Ghidra-side boot
  trace experiments.
- `micronic/README.md` — full reusable-model documentation.
- `~/ghidra_scripts/FillBatteryRam.java` — the standalone battery-RAM
  loader. **Folded into `ghidra/AnalyseMicronicRom.java` as pass 0**, with
  two corrections: the `ram:E104` copy length (`0129h` from the chain
  record, not the hardcoded `0130h`, which over-ran into `ram:E22D`), and a
  much tighter phantom-function predicate — the original deleted every
  `ram` function at or above `F100`, which on the current database would
  destroy the whole resident kernel. Prefer the consolidated script; the
  standalone copy is kept for reference.
