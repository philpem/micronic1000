# micronic — reusable Micronic 1000 protocol model

A Python package modelling the hardware + IR-link protocol of the
Micronic 1000 / PARCON 1000, derived from firmware static analysis
and the runtime boot trace. Its purpose: give you a **reusable
protocol description** to build an infrared link adapter (or host
program) that talks to the M1000.

```
micronic/
  __init__.py   package exports
  rtc.py        HD146818 register model (RTC tick cadence)
  proto.py      Commstar IR-link frame/transport model
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

## proto.py — the IR-link transport

Models the *external* byte transport as the firmware drives it:

| port | role |
|------|------|
| 4Ah | control latch (bit1 = IR line select, bit6/7 = online) |
| 4Bh | status (bit7 TX empty, bit0 RX full) |
| 4Ch | command/ACK latch (0x81 = present) |
| 4Dh | TX data byte |
| 4Eh | RX data byte |
| 4Fh | probe (0x1F) |

Frame (little-endian, length prefixed):

```
[len][type][cmd-id-hi][cmd-id-lo][payload...]
```
types: 2 = session, 3 = answer/timeout, 4 = command.

Replies the unit can send (FE14 prefix words):
`EE01` idle, `02E0`, `02EE`, `04E0` ACK(connected), `05E0` ACK(cmd),
`01EF` rejected/bad-id.

```python
from micronic import proto
Link = proto.Link(
    port_out=lambda b: send_byte_to_hw(b),
    port_in=lambda: read_byte_from_hw(),
    port_status=lambda: read_status_port(),
    port_ctrl=lambda v: set_ctrl(v),
)
frame = proto.Frame(proto.TYPE_COMMAND, 0x4400, b"data")
Link.tx(frame)
rx = Link.rx()
```

## Verification status

The **physical TX prologue** was verified against the real firmware
by seeding the link state (fdd4/fdd5/fdd6) and calling
`LinkTransferService` (2F86) under emulation
(`analysis/comms_tx_test.py`):

- first byte on port 4Dh = the **link-id prelude** (`0x45 & 0x1F = 0x05`)
- then `count` bytes from a `{count, ptr}` descriptor at FDEA, sent
  via `OUTI (4Dh)` gated on 4Bh bit7
- 4Ah control-latch writes (0x02/0x03...), 4Ch = 0x81 after the status-bit-7
  poll; electrical meanings remain unproven

## Bidirectional exchange (verified)

`analysis/comms_duplex.py` drives a real bidirectional exchange
between the reusable model and the actual M1000 firmware over the
shared port bus:

* **M1000 -> model**: the firmware's `LinkTransferService` transmits
  `[05][04][44][00]"from-M1000"` on 4Dh; the model's `Link.rx()`
  parses it as `Frame(type=4, cmd=0x4400, "from-M1000")`.
* **model -> M1000**: the model builds an ACK
  `[05][03][04][E0]"reply-to-M"`, `Link.tx()` emits it, and the
  firmware's RX dispatcher consumes all 14 bytes.

Result: **BIDIRECTIONAL EXCHANGE OK**. `proto.LinkPeer` is the reusable
queue-and-latch peer for an M1000-facing transport implementation. It captures
`LINK_TXD`, queues `LINK_RXD`, records latch writes, and has configurable
non-data status bits; it does not assign electrical names to those bits.

```python
peer = proto.LinkPeer()

# M1000 I/O callbacks use peer.firmware_status(), peer.read_rx(),
# peer.write_tx(), peer.write_control(), peer.write_command(), and
# peer.write_probe().
adapter = peer.make_adapter_link(id_byte=0x45)
adapter.tx(proto.Frame(proto.TYPE_ANSWER, 0x04E0, b"reply"))
```

The default status policy matches the directed firmware traces: status bit 7
is supplied for TX, bit 0 while queued RX bytes remain, and no inferred
completion bit. A production adapter can set `status_bits` and
`completion_bits` only from its own observed hardware behaviour.

Note: the FDEA buffer is a *descriptor* `{count_lo, count_hi, ptr_lo,
ptr_hi}` (read by FUN_3508), NOT a flat frame - the payload lives at
the pointer. The record/block *data contents* at that pointer are the
only remaining runtime detail; the transport and framing are verified.

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
