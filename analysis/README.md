# Micronic 1000 analysis tools

Everything for reverse-engineering and emulating the Micronic 1000.

## Reusable protocol model — `micronic/`

A self-contained Python package you can import to build an IR link
adapter or host program:

* `micronic.rtc.RTC146818` — HD146818 model; the **periodic tick
  cadence** follows Register A's RS nibble (1024 Hz default), exactly
  as the firmware programs it.
* `micronic.proto.Frame` — the wire payload: `[type][cmd_hi][cmd_lo]
  [data...]`.
* `micronic.proto.Link` — the 4x transport: `tx()` emits
  `[link_id&0x1F]` prelude + payload via an `on_tx` callable, gated
  on `on_st() & 0x80` (TX empty); `rx()` reads from `on_rx` gated on
  `on_st() & 0x01` (RX full).
* Verified **byte-for-byte** against the firmware (`comms_tx_test.py`).

## Emulator harnesses (Python `z80` module)

Requires the `z80` python module in `venv/`.

- **`boot_hw.py`** — boot the firmware to kernel/self-test with a
  MAME-accurate I/O stub and an **RTC-model-driven periodic INT**.
  Proves the HD146818 write path live; writes a full I/O trace to
  `/tmp/opencode/micronic_boot_io.txt`. Uses `micronic.rtc`.
- **`boot_hw_serial.py`** — extends boot_hw.py with paced keyboard injection
  at the 16C9 HALT wait (FBC9 bit2 / FFA8) to drive past the banner and the
  "Enter serial" prompt. `--drive-serial` / `--serial TEXT` queue ENTER + serial + ENTER.
- **`boot_hw_visible.py`** — extends boot_hw_serial.py with **LCD rendering**,
  an **expect DSL**, and **multi-bank RAM**. This is the user-visible harness.
  `timeout 300 analysis/venv/bin/python3 analysis/boot_hw_visible.py --help` prints full usage.
- **`comms_tx_test.py`** — directed verification of the TX path:
  seed the link state + FDEA `{count, ptr}` descriptor, call
  `LinkTransferService` (2F86), capture port-4Dh bytes, compare
  against `micronic.proto`. **MATCH** (prelude + payload).
- **`comms_rx_test.py`** — verify the RX path: feed a frame via the
  port-4Eh input callback into `LinkBlockRx`/RX dispatcher (2FBD),
  capture the 4A strobe handshake. Confirms `proto.Link.rx()`
  mirrors the firmware (4Eh gated on 4Bh bit0).

### `boot_hw_visible.py` — visible harness details

**Memory safety:** single process, `timeout 300`, bounded `--max-slices`, 200k I/O log ring, `gc.disable()` + manual `collect`.

**LCD:** framebuffer at `FC06–FCA5` (160 bytes, 20 cols × 8 rows, ASCII). `LcdRefreshScreen` (ROM00:1E27) via `lcd_putc` (1F79) ports 23h/03h; `lcd_clear_spaces` writes 0xA0 spaces to FC06. Rendered with `\\x1b[H` home-cursor when changed or every `--lcd-rate` slices. Escape/CR/LF shown as space.

**Multi-bank RAM:** port `47h` (`BANK_SEL`, shadow `F791`) selects the 32K window `0000–7FFF`: `0=ROM0`, `1=ROM1`, `2..N=RAM pages` (32K each). Fixed RAM `8000–FFFF` is always present (32K). Totals: `128K=32K+3×32K (banks 2..4)`, `256K=32K+7×32K (banks 2..8)`, `512K=32K+15×32K (banks 2..16)`. Save/restore on `47h` write (only for installed banks). **Non-present banks read `0xFF` (open bus) and writes are discarded** — required for correct RAM sizing. The firmware walks banks `0x41..0x01` in `Boot_BankWalkInit` regardless of installed RAM; sizing is done by `contig_ram_map_test` (267A) and `ram_page_test_4banks` (2530), with `DelayCountUp` (271F) computing `FEAB = FEA9 * 0x20` (FEA9 = count of present pages) displayed as `Ram: NN K.B.` on the banner. With `--ram 256` the banner must show 256K (not 2016K = 63*0x20).

**Options:** `--ram` / `--ram-size` (128|256|512), `--drive-serial` / `--serial TEXT`, `--max-slices N`, `--dump-bank N`, `--lcd` / `--no-lcd` / `--lcd-rate N`, `--expect SPEC` (repeatable), `--expect-file FILE`, `--expect-timeout N`, `-h`/`--help`.

**Expect DSL:** `match:keys` — wait until `match` substrings appear in LCD text, then inject `keys` via the keyboard ring (paced exactly like the `16C9` HALT wait, `FBC9` bit2, `FFA8==1`). Multiple `--expect` steps run in order.

- `match` may be empty (immediate) or a list joined by `,` or `&` meaning **AND** (all substrings must be present). Example: `"Ram:,K.B."` waits for both `"Ram:"` and `"K.B."`. For no-comma ambiguity use JSON list via `--expect-file`: `{"match":["Ram:","K.B."],"keys":"\\r"}`.
- `keys` escape sequences: `\\r`, `\\n` → `0x0D` (ENTER; `\\n` is mapped to `\\r`), `\\t` → `0x09`, `\\e`/`\\E` → `0x1B`, `\\\\` → `\\`, `\\xNN` → byte, `\\uNNNN` → unicode (via `unicode_escape`). Example: `--expect "To Continue Press>>:\\r"`.
- Separator variants: `match:keys`, `match::keys`, `match|keys` all split match from keys; first `:` is the delimiter (so `:` inside keys is safe if split on first colon).

**Examples:**
```sh
timeout 300 analysis/venv/bin/python3 analysis/boot_hw_visible.py --lcd --max-slices 300000
timeout 300 analysis/venv/bin/python3 analysis/boot_hw_visible.py --lcd --expect "To Continue Press>>:\\r" --expect "Serial:\\r12345678\\r" --expect "Main Menu:1"
timeout 300 analysis/venv/bin/python3 analysis/boot_hw_visible.py --ram 512 --expect-file /tmp/steps.json --dump-bank 2
# steps.json: [{"match":"To Continue Press>>","keys":"\\r"},{"match":["Ram:","K.B."],"keys":"\\r"},{"match":"Main Menu","keys":"1"}]
```

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
- `micronic/README.md` — full reusable-protocol docs.
- `../ghidra_scripts/FillBatteryRam.java` — loads the session modules
  into Ghidra RAM for static analysis.