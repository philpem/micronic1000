# micronic — reusable Micronic 1000 firmware models

A Python package containing evidence-scoped hardware models, image tools,
and external-link harness helpers for the Micronic 1000 / PARCON 1000. It
does not yet describe enough of the controller transaction or Commstar
session to build an interoperable link adapter.

```
micronic/
  __init__.py   package exports
  rtc.py        HD146818 register model (RTC tick cadence)
  proto.py      raw external-link byte-latch scaffold
  program.py    COM/DIP image validator (CONFIRMED grammar)
```

## rtc.py — the RTC / tick source

The M1000's CPU interrupts come from the HD146818 periodic output.
The firmware *programs* the rate by writing Register A's RS nibble;
a correct emulator/adaptor must therefore fire ticks at whatever the
firmware wrote, not a constant.

```python
from micronic.rtc import RTC146818
rtc = RTC146818()
rtc.reg_write(0x0A, 0x26)   # RS=6 -> 1024 Hz   (default running rate)
rtc.reg_write(0x0B, 0x40)   # PIE on
rtc.push_tick()             # drive the periodic output
assert rtc.reg_read(0x0C) & 0xC0   # IRQF+PF
```

Rate table is the standard MC146818 one (RS 1..15). Register C
read returns-and-clears the interrupt flags, exactly as firmware
uses it to ACK each tick.

## proto.py — the IR-link transport (raw byte-latch scaffold)

This module is a raw byte-latch scaffold, not a Commstar session
implementation. It models only directed reads/writes at the
M1000-facing latches as the firmware drives them:

| port | role |
|------|------|
| 4Ah | control latch (firmware drives bits 0/1/4/5) |
| 4Bh | status (firmware polls bits 7/4/6 for TX and 0-3 for RX) |
| 4Ch | latch (firmware writes 0x81 after a status-bit-7 poll) |
| 4Dh | TX data byte (write) |
| 4Eh | RX data byte (read) |
| 4Fh | probe (0x1F) |

ROM-visible buffer layout (CONFIRMED):

* RX logical buffer: `+0..1` LE embedded length, `+2` numeric type,
  `+3` sequence byte, `+4` active link id, `+5` unread by the
  examined ROM path, payload starts `+6`.
* TX prefix preparation (`LinkFramePrefixWrite` ROM00:316B) writes
  `+0..1` descriptor length, `+2` numeric type, `+3` sequence,
  `+4=0x7F`; the meaning of `0x7F` is **SUSPECTED**, and `+5` is
  untouched by that path.
* `LinkValidateFrameHeader` (ROM00:30DC) checks embedded length
  against the caller-supplied logical count and checks `+4` against
  the active link id; it does not inspect `+5`.
* Successful `LinkBlockRx` returns `DE=controller bytes consumed
  minus 2`; the identities of those two bytes are **OPEN**.
* The examined ROM transport/header path has no checksum; integrity
  inside unresolved loaded-session payloads remains **OPEN**.

Numeric types `2, 3, 4` and seven reply words `01EE, 02EE, 02E0,
04E0, 05E0, 01EF, 03EE` are observed triggers — treat as numeric
words/types, not named semantic commands unless the bytes prove a
meaning. Do not claim a `[type][16-bit big-endian command][payload]`
grammar, symmetric roles, payload checksums, filenames, or a verified
bidirectional Commstar exchange.

```python
from micronic import proto
peer = proto.LinkPeer()  # queues LINK_RXD, captures LINK_TXD
# Wire the peer callbacks into your harness:
# peer.write_tx / peer.read_rx / peer.firmware_status
# peer.write_control / peer.write_command / peer.write_probe
```

## Verification status

The **controller-facing TX sequence** was verified against the real
firmware by seeding the link state and calling `LinkBlockTx`-related
paths under emulation (`analysis/comms_tx_test.py`):

- first byte on port 4Dh = the **link-id prelude** (`link_id & 0x1F`)
- then bytes from the descriptor list at FDEA (`{count_lo, count_hi,
  ptr_lo, ptr_hi}` `{6 -> FDDE, 0}`, via `LinkReadBufferDescriptor`
  ROM00:3508), sent via `OUTI (4Dh)` gated on 4Bh bit7
- 4Ah control-latch mechanical drive, 4Ch = 0x81 after the
  status-bit-7 poll; electrical meanings remain unproven

`LinkBlockTx` outcomes: `EBh` if either pre-payload bit-7 wait or the
bit-4-clear wait times out; `EEh` if either bit-6-clear wait or a
payload/post-payload bit-7 wait fails; `ECh` if final status bit5 is
set; success `A=00h` carry clear. Initialized descriptor chains:
`FE0E {6->FDE4,3->FE38,0}`
(structurally mutable), `FE32 {9->FE3A,0}`, `FDEA {6->FDDE,0}`. Retry
scheduler: initial `fdd6=32h/fdd8=6`, later `fdd6=14h/fdd8=3`; the
caller reschedules without testing `A`/carry. `LinkProbe` (ROM00:348A)
writes `1Fh` to `LINK_PROBE`; physical effect is **OPEN**. `LinkBlockRx`
success returns `DE=bytes consumed minus 2` (identities **OPEN**).

`analysis/comms_duplex.py` bridges the reusable `proto.LinkPeer`
queue/latch interface to the firmware byte pumps. It validates
transport mechanics, not a live Commstar session or electrical bit
identities. Do not claim verified bidirectional Commstar exchange,
payload checksums, filenames, or symmetric protocol roles — none are
proven for the examined ROM path.

`proto.LinkPeer` is the reusable queue-and-latch peer: it captures
`LINK_TXD`, queues `LINK_RXD`, records latch writes, and has
configurable non-data status bits; it does not assign electrical names
to those bits. UI fields `E701`/`E6FF` are width-3 decimal RCV1/RCV2
status fields; runtime meaning is **OPEN** and they are not
transport-frame fields.

The default status policy matches the directed firmware traces: status
bit 7 is supplied for TX, bit 0 while queued RX bytes remain, and no
inferred completion bit. A future controller harness can set `status_bits` and
`completion_bits` only from its own observed hardware behaviour.

Note: the FDEA buffer is a *descriptor* `{count_lo, count_hi, ptr_lo,
ptr_hi}` (read by ROM00:3508), not a flat frame — the payload lives
at the pointer. Record/block *data contents* remain **OPEN**; the
examined ROM transport/header path has no checksum.

## program.py — COM/DIP image validator

Host-side validator for the runtime Load/Run Program loader (ROM01:0A67-10CE,
`Program_LoadDipOrCom` at `ROM01:0CE7`). Implements **only** the CONFIRMED
grammar from `doc/manual/program-formats.md`:

* **COM/DIP discrimination** by first-chunk rule: `<14` bytes or first word
  != `0xC8C9` (`C9 C8`) → COM, else DIP.
* **DIP header** exactly 14 bytes LE: magic `0xC8C9`, system ID `0` or
  `0x00E5`, image size clamped to `0x8000` (not rejected), block count `≤5`.
* **Blocks**: 8-byte header + payload; payload length validated; type-1
  payload must be multiple of 4; unknown types are allowed (ROM takes the
  default dispatch path).
* **COM** max `0xCF81` (`0xD081 - 0x0100`) bytes.
* Error identifiers match the loader catalogue where applicable:
  `0x232B` (9003) "Bad DIP file.", `0x2331` (9009)
  "Program not built for this system.", `0x2334` (9012)
  "DIP file has too many blocks.", `0x232C` (9004) "COM file too big.".
  Type-1 alignment uses validator-specific `DIP_TYPE1_ALIGN`.

```python
from micronic.program import validate, build_dip_file

# Build a minimal DIP for testing
data = build_dip_file(blocks=[(0, 0, 0x1000, b"hello")])
res = validate(data)
assert res.valid and res.kind == "DIP"

# Validate a file
from micronic.program import validate_file
res = validate_file("prog.dip")
print(res.valid, res.errors)

# CLI
# analysis/venv/bin/python3 analysis/validate_program.py prog.dip --json
```

Builders `build_dip_header` / `build_dip_block` / `build_dip_file` are
provided for host tooling and golden tests. The validator never invents
constraints not in the docs (e.g. it does **not** reject `image_size >
0x8000` — the loader clamps it).

## boot_hw.py — emulator harness

`analysis/boot_hw.py` boots `micron1.bin`/`micron2.bin` under the
z80-module emulator with MAME-correct I/O; it keeps a
`micronic.rtc.RTC146818` in sync with firmware port-08/28 writes and
fires the Z80 INT at the programmed period. It proves the HD146818
write path end-to-end and drops a full I/O trace to
`/tmp/opencode/micronic_boot_io.txt`.

`--upload PATH` drives the **real** loader (`Program_LoadByName`
`ROM01:0B82` → `Program_ConsumeInputChunk` `ROM01:0BAC` chunked by
request word `D36C` → `Program_FinalizeInput` `ROM01:1002` state 3 →
`Program_RunByName`/`RunLoadedProgram`) below Commstar — it does **not**
emulate a Commstar peer. Options: `--upload-name NAME` (input basename),
`--upload-bank N` (default 2), `--upload-max-bytes N` (default 65535),
optional `--upload-marker ADDR:VAL` (hex), `--upload-no-run` (stop
after finalize/verify). `--trace-session-builder 4|5` runs the bounded
synthetic builder traces described in `doc/protocol/commstar.md`.

Opt-in integration: `MICRONIC_RUN_EMULATOR_TESTS=1
analysis/venv/bin/python3 analysis/test_boot_upload.py` (3 tests: COM
Hello, DIP Hello, max-size COM byte verification). Run one emulator
process at a time under `timeout` (memory guidance in `analysis/README.md`).
