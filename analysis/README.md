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
- **`comms_tx_test.py`** — directed verification of the TX path:
  seed the link state + FDEA `{count, ptr}` descriptor, call
  `LinkTransferService` (2F86), capture port-4Dh bytes, compare
  against `micronic.proto`. **MATCH** (prelude + payload).
- **`comms_rx_test.py`** — verify the RX path: feed a frame via the
  port-4Eh input callback into `LinkBlockRx`/RX dispatcher (2FBD),
  capture the 4A strobe handshake. Confirms `proto.Link.rx()`
  mirrors the firmware (4Eh gated on 4Bh bit0).

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