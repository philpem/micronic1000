# M1000 IR probe

This sketch targets an Elegoo Uno R3 (`arduino:avr:uno`). Build it with the
Arduino CLI or IDE and open the serial monitor at **115200 baud**.
For the current direct-TTL bench connection, compile from the repository root:

```sh
arduino-cli compile --fqbn arduino:avr:uno \
  --build-property compiler.cpp.extra_flags=-DBLACK_USE_NPN=0 \
  analysis/arduino/m1000_ir_probe
```

Direct TTL is also the source default, so an IDE upload uses the current
bench wiring. Upload the same build to the Uno. The
[current physical-test handoff](../../../doc/re-notes/ir-feedback-protocol.md#current-handoff-feedback-v2-bench-trial)
gives the next ID, scope setup, measurements and result fields.

## Combined feedback harness (default)

The default build is now `FEEDBACK_HARNESS=1`. It boots **silent** and accepts
explicit one-shot USB commands. The matching ROM provides witness (`W`),
forced receive (`R`), reset/probe (`P`), and receive-pending-gated receive (`G`)
trials in one burn. Feedback-v2 adds H/J/K receive-state captures; see the
complete [wiring, command and result guide](../../../doc/re-notes/ir-feedback-protocol.md).

### Choose black interface before uploading

At the top of `m1000_ir_probe.ino`, select exactly one black-command wiring:

```cpp
#define BLACK_USE_NPN 0  // direct 5 V TTL: D7 -> black / pin 5
// #define BLACK_USE_NPN 1  // external NPN transistor instead
```

`BLACK_USE_NPN=1` selects the alternative NPN interface:
D7 low releases black and D7 high commands it low. `BLACK_USE_NPN=0` is the
direct 5 V TTL option: wire **D7 directly to black / pin 5**, omit the NPN and
its base resistors, and use D7 high for idle/released and D7 low for command.
The sketch prints `BLACK: NPN` or `BLACK: DIRECT_TTL` at startup and after
`R`; verify that banner before a trial. The 74LS input suggestion remains
SUSPECTED; this selection is a bench wiring choice, not an identity claim.

### Wiring to the handheld

Power the Uno from USB and the handheld from its batteries. Use the tested
scanner cable's **blue, black and yellow** wires:

| Connection | Wiring |
|---|---|
| Common ground | Handheld **blue / pin 8** to **Uno GND**; also NPN **emitter** when selected |
| Command to handheld | Handheld **black / pin 5** to NPN **collector** (`BLACK_USE_NPN=1`) or directly to **D7** (`=0`) |
| NPN drive, optional | **D7 -> 10 kOhm -> base**; **100 kOhm base-to-emitter** (`=1` only) |
| Feedback from handheld | Handheld **yellow / pin 6** to **D8**; **10 kOhm yellow-to-Uno-5-V** pull-up |
| Optical stimulus | Keep existing IR LED drivers/channels **A on D5**, **B on D6**, facing the top V24 window |

Leave orange/Vcc, red, brown, violet and green disconnected and insulated.
Remove the earlier connector tests' yellow-to-orange and black-to-ground
resistors. Do not join handheld Vcc to Uno 5 V. In direct-TTL mode, power the
Uno before the handheld; switch the handheld off before unplugging Uno USB.
Check the actual transistor's B/C/E pinout when using NPN mode. Connector pin
numbers and wire colours are owner-confirmed (2026-09-22).

See the [complete wiring diagram and power-up checks](../../../doc/re-notes/ir-feedback-protocol.md#connect-the-handheld-to-the-uno).
D7 polarity follows the selected banner: NPN high commands/low releases;
direct TTL low commands/high releases. D8 is input-only. D2/D4 optical
monitoring is unused in feedback mode. The D5/D6 clock/data assignment is
unknown; `swap` selects the proposed roles without rewiring.

Open the serial monitor at 115200 baud, confirm the expected `BLACK:` banner,
send `R`, and wait for `READY`. Then:

```text
T 1 P S 0 -- 0 0 0 -2 0 0 -
```

This silent probe checks command/result communication before emitting IR.
Wait for `RESULT` and fresh `READY` before each new trial. `C 1` cancels the
Arduino side; send `R` to resynchronise after a transaction error. A ROM
diagnostic error is recorded as data and does not establish IR framing.
With the updated sketch, a rejected idle command (including a repeated
trial ID) starts no handheld transaction and does not require `R`: send
the next command with a greater trial ID. Errors after a transaction begins
still say `send R to resynchronise` and require that step.

To check that the IR emitters produce light visible to a camera, send `V <id>`
(for example, `V 1`). You can repeat the same ID any number of times. It runs
from idle over USB without a handheld transaction or a READY handshake. The
Uno pulses channel A on D5 at 10% PWM for 1.5 seconds, then channel B on D6
for 1.5 seconds, and turns both off. Point the camera at the emitters during each
serial-labeled interval. Send `C <id>` to stop early; completion or cancellation
returns to quiet operation and prints `READY` after the normal idle settling
period when the yellow input is high. Visual IDs do not consume ROM trial IDs.
This check does not assert BLACK or contact the ROM.

For physical clock/data polarity tests, `T` accepts two optional final
fields after the payload: `clk_inv dat_inv`, each `0` or `1`. Old commands
without them remain `0 0`. These invert the **LED output levels during the
short X burst only**, after `swap` assigns the clock/data roles; both LED
drive pins return low when the burst ends. The separate `V` command can
still pulse them on request. These fields are separate from `pol`, which
complements serialized data bits while leaving clock pulses unchanged.
`S` trials do not emit even if inversion fields are `1`.
The next matched test matrix is
[`analysis/trials/feedback-optical-levels-29-36.txt`](../../trials/feedback-optical-levels-29-36.txt).
Keep the LED current-limiting resistors fitted.

For reproducible batches and timestamped JSONL logs, use
`analysis/ir_feedback.py` as documented in the guide. Keep this entire sketch
directory together when rsyncing; `feedback_harness.h` is part of the build.

## Legacy optical monitor and sweep modes

Set `FEEDBACK_HARNESS=0` to reproduce the older experiments. Explicit legacy
mode flags also select the legacy build unless `FEEDBACK_HARNESS` is supplied.
The feedback mode refuses conflicting legacy mode flags at compile time.

The pin assignments are defined at the top of the sketch:

| Signal | Uno pin | Direction |
|---|---:|---|
| `CLK_IN` | D2 | handheld clock input / interrupt |
| `DAT_IN` | D4 | handheld data input |
| `CLK_OUT` | D5 | physical return channel A; proposed clock |
| `DAT_OUT` | D6 | physical return channel B; proposed data |

**Receive conventions remain unconfirmed (owner clarification, 2026-09-22).**
The Arduino LED assignment to handheld clock/data receivers is unknown.
`CLK_OUT`/`DAT_OUT` name software roles, not established optical destinations;
both assignments need testing. `7Eh` as a receive flag is **SUSPECTED**.
These assumptions must remain adjustable on the Arduino, so testing them
does not require another handheld EPROM burn.

The input lines must be protected from the handheld voltage as described in
the sketch comments. The output channels should remain optically separated.

The legacy default (`FEEDBACK_HARNESS=0`) is `RX_NARROW=1`, with
`RX_NARROW_AXIS=2`. It sends a
reply to each completed handheld burst using candidate flag `7Eh`, baseline polarity and
phase `-2/8` (data rise 30 us before clock rise), while varying the content
axis. The three content trials are flag only, flag plus `03h`, and an open
type-2 control acknowledgement. The startup banner and each burst line state
the active settings; the per-burst `payload=` field is the logical payload
bytes actually passed to the wire builder.

Other modes are compile-time flags in the sketch (`LISTEN_ONLY`, `LOOPBACK_TEST`,
`PULSE_TEST`, `FREERUN_TEST`, `LADDER_TEST`, `RX_SWEEP`, `FREE_TX`, and related
axes). They are mutually checked with preprocessor errors. Set
`RX_NARROW=0` when enabling another mode. `LISTEN_ONLY=1` is the safe monitor
configuration and does not drive the return outputs.

The emitter defines phase as data-rise minus clock-rise and schedules absolute
timestamps on an eighth-cell grid. `emit_late_max` in a burst report is the
largest `micros()` deadline lateness observed while dispatching that emitted
burst. It measures software deadline lateness only; it does not measure LED,
detector, wiring, interrupt or scope timing, and a zero value is not a physical
waveform guarantee. The host event test is an ideal scheduler check. Confirm
the actual waveform and electrical levels with an independent scope.

The host-only emitter harness is outside this directory at
`analysis/test_ir_emitter.cpp`; keeping it outside the sketch directory avoids
Arduino builders compiling its mock API and `main()` as sketch sources.

## Stock-ROM context capture

This mode observes the stock receive path through handheld yellow / pin 6. It
uses the legacy optical connections, so connect the handheld clock and data
detector outputs to **D2 and D4** (each through its own **10 kOhm series
resistor**), and retain the existing separately driven optical LEDs on **D5
and D6**. Keep those LED channels optically separated and their current
limiting resistors fitted. Connect handheld **blue / pin 8** to Uno GND.
Connect handheld **yellow / pin 6** to **D8**, with a **10 kOhm pull-up from
D8/yellow to Uno 5 V**. Leave handheld **black / pin 5** and Uno **D7**
disconnected in these modes. Leave orange / pin 3 (handheld Vcc) disconnected:
share ground only, and do not join handheld Vcc to Uno 5 V.

First run a silent control with the stock-context event capture enabled. Build
from the repository root:

```sh
arduino-cli compile --fqbn arduino:avr:uno \
  --build-property 'compiler.cpp.extra_flags=-DBLACK_USE_NPN=0 -DFEEDBACK_HARNESS=0 -DLISTEN_ONLY=1 -DRX_NARROW=0 -DSTOCK_CONTEXT_EVENTS=1' \
  analysis/arduino/m1000_ir_probe
```

Upload it and confirm `MODE: LISTEN ONLY` and the stock-context D8 banner.
Run the same handheld operation that will be used for the transmitting
captures and record its yellow events. This is the control for yellow pulses
that occur without an Uno optical reply.

Then build and capture the free-running TX condition. It emits one swept
optical burst every 250 ms by default, independently of handheld traffic; it
is intended to exercise the stock instrument's idle receiver during its
connect attempt:

```sh
arduino-cli compile --fqbn arduino:avr:uno \
  --build-property 'compiler.cpp.extra_flags=-DBLACK_USE_NPN=0 -DFEEDBACK_HARNESS=0 -DLISTEN_ONLY=0 -DRX_NARROW=0 -DFREE_TX=1 -DSTOCK_CONTEXT_EVENTS=1' \
  analysis/arduino/m1000_ir_probe
```

For the handheld-paced condition, build RX_NARROW with its default content
axis (axis 2):

```sh
arduino-cli compile --fqbn arduino:avr:uno \
  --build-property 'compiler.cpp.extra_flags=-DBLACK_USE_NPN=0 -DFEEDBACK_HARNESS=0 -DLISTEN_ONLY=0 -DFREE_TX=0 -DRX_NARROW=1 -DRX_NARROW_AXIS=2 -DSTOCK_CONTEXT_EVENTS=1' \
  analysis/arduino/m1000_ir_probe
```

RX_NARROW replies after each handheld burst and varies the selected content
axis. FREE_TX and RX_NARROW are separate builds; do not enable them together.
For each build, run the passive logger before the handheld operation so its
startup and event lines are retained. It sends no commands, defaults to
`/dev/ttyACM0`, and refuses to overwrite an existing log:

```sh
python3 analysis/stock_context_log.py \
  --log analysis/captures/stock-context-control.jsonl --duration 60
python3 analysis/stock_context_log.py \
  --log analysis/captures/stock-context-free-tx.jsonl --duration 60
python3 analysis/stock_context_log.py \
  --log analysis/captures/stock-context-rx-narrow.jsonl --duration 60
```

Change `--port` if the Uno is not `/dev/ttyACM0`. Analyze each capture after
the run; the 250 ms default association window can be changed if needed:

```sh
python3 analysis/stock_context_log.py \
  --log analysis/captures/stock-context-control.jsonl --analyze
python3 analysis/stock_context_log.py \
  --log analysis/captures/stock-context-free-tx.jsonl --analyze
python3 analysis/stock_context_log.py \
  --log analysis/captures/stock-context-rx-narrow.jsonl --analyze \
  --association-window-ms 250
```

With `STOCK_CONTEXT_EVENTS=1`, the Uno timestamps D8 low-pulse starts and
records the pulse width when D8 rises. It prints events outside the pin-change
interrupt as `# STOCK_YELLOW rise_us=N low_us=W`; RX_NARROW reply reports and
FREE_TX reports also include their `tx_start_us=` and `swap=` fields for
timestamp correlation. The logger may therefore show an event line after a
later TX report even when the event's pulse started earlier. Analysis
correlates to the closest TX preceding the pulse fall using Uno's wrapping
32-bit microsecond clock, not line order. Events with no TX in the configured
window are reported as silent/control.

The event ring holds seven pending pulses. If it fills while the Uno is busy,
some events are dropped and reported as `# STOCK_YELLOW_DROPS N`; a capture
with drops is incomplete. Pulse widths above 65535 us are capped at 65535.
This marker records timing at the Uno input pin. It does not decode a yellow
serial record, identify which stock-ROM routine caused the pulse, or prove
that the optical signal reached the handheld receiver. Confirm optical
waveforms independently when interpreting a negative result.
