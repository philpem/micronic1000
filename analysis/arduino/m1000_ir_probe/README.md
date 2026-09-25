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

Upload it and confirm `MODE: LISTEN ONLY` and
`STOCK_CONTEXT_V3 width_us=32 drops=16`. Start logging, reset the Uno to
capture that banner, then cold-restart the handheld with the **v3 revision 2**
ROM. Require the initialization pulse near **3637 us** before interpreting
any absent receive marker. The pulse also occurs on a stock warm restart;
it does not prove a complete battery-RAM reset.
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
axis. `RX_NARROW_AXIS=3` alternates LED role assignments instead. FREE_TX
and RX_NARROW are separate builds; do not enable them together.
For a fixed repeat of the old pending-observation candidate, append
`-DSTOCK_FIXED_CANDIDATE=1` to either transmitting build's flags. The
fixed defaults are `7E`, phase `-2/8`, serialized polarity 0, content index
2, and a 4000-us RX_NARROW reply delay. Each startup and TX report states
the physical role/inversion configuration; verify those echoes.

These additional build flags allow exact replay without changing ROM:

| Flag | Values / meaning |
|---|---|
| `STOCK_TX_SWAP` | 0 or 1; exchanges physical D5/D6 roles (default 0) |
| `STOCK_CLOCK_INVERT`, `STOCK_DATA_INVERT` | 0 or 1; invert the corresponding LED level during emission; idle stays dark |
| `STOCK_FLAG_IDX` | 0 = `81h`, 1 = `7Eh` |
| `STOCK_PHASE_IDX` | 0..4 = -4, -2, 0, 2, 4 eighths of a cell |
| `STOCK_POL_IDX` | 0 or 1; complements serialized bits, not clock electrical level |
| `STOCK_CONTENT_IDX` | 0 = flag only, 1 = flag + `03h`, 2 = type-2 control acknowledgement, 3 = diagnostic `00 00 FF FF 96` (fixed mode only) |
| `STOCK_STUFFING_MODE` | -1 = historical flag-dependent choice (default); 0 = off; 1 = insert zero after five ones; 2 = insert one after five zeros; explicit modes describe emitted serialized bits |
| `STOCK_CLOSE_FLAG` | 0 = open (default), 1 = append a raw closing flag after terminal stuffing |
| `STOCK_CLOSE_BYTE` | -1 = disabled (default); 0..255 appends that raw MSB-first closing marker after terminal stuffing, independent of the opening flag; cannot combine with `STOCK_CLOSE_FLAG=1` |
| `STOCK_PREFIX_BYTE` | -1 = disabled (default); 0..255 prepends that raw MSB-first byte immediately before the opening flag in fixed type-2 ACK mode |
| `STOCK_ZERO_PAYLOAD` | 0 = normal type-2 ACK payload (default); 1 = replace it with ten zero bytes (80 data-low cells) |
| `STOCK_REPLY_DELAY_US` | 500..60000; fixed RX_NARROW delay from last observed outbound clock edge |
| `STOCK_REPLY_DELAY_STEP_US`, `STOCK_REPLY_DELAY_COUNT` | Fixed RX_NARROW only: cycle `COUNT` delays, starting at `STOCK_REPLY_DELAY_US` and adding `STEP_US` after each reported burst; defaults 0 and 1; maximum resulting delay 60000 us |
| `STOCK_REPLY_EVERY_N` | Fixed RX_NARROW only: transmit on qualifying bursts 1, N+1, 2N+1, ... of at least 9 clock cells; shorter fragments do not advance the counter. Default 1, range 1..32. Each burst report includes `reply_sent=1/0`. |

For a timing sweep with the same emitted frame, set fixed RX_NARROW and
add `-DSTOCK_REPLY_DELAY_US=30000 -DSTOCK_REPLY_DELAY_STEP_US=1000
-DSTOCK_REPLY_DELAY_COUNT=7`. The startup banner identifies the sweep;
each `burst` line prints `delay_req=requested/achieved` in microseconds.
For a sparse fixed reply comparable to the 250-ms free-running cadence,
use `-DSTOCK_REPLY_DELAY_US=33000 -DSTOCK_REPLY_EVERY_N=3` and leave
`STOCK_REPLY_DELAY_COUNT=1`. Skipped bursts report `reply_sent=0`,
achieved delay 0, and no `tx_start_us`.

For independent framing tests, always specify `STOCK_STUFFING_MODE=0`, `1`
or `2`: the compatibility default `-1` couples stuffing to flag choice.
Explicit stuffing mode describes the emitted serialized stream after `pol`;
the builder compensates its internal run counter for complement. `pol=1`
complements the emitted flag too (`7E` becomes `81`); the configured flag
alone is not the emitted value. Content 3 exercises both run senses across
byte boundaries and includes an asymmetric byte; it is a diagnostic pattern,
not a valid Commstar message. It is excluded from the legacy 60-row sweep.
`STOCK_CLOSE_BYTE` emits a raw closing delimiter outside the stuffed data
region. It is useful for testing a closing marker independently of the
opening marker; it does not model an FCS, which would belong in the stuffed
data region.
`STOCK_PREFIX_BYTE` is also outside the stuffed payload. A prefix of `7E`
followed by the configured `7E` opening flag emits two adjacent flags; a
prefix of `00` emits eight data-low cells before the same opening flag.
Both retain the default five clock-only lead cells unless another mode
changes that setup.
For the matched 101-cell control, combine prefix `7E` with
`STOCK_ZERO_PAYLOAD=1`: five lead-low cells, two `7E` bytes, then 80 zero
payload cells. The zero payload option changes only fixed type-2 ACK content;
the default payload remains unchanged.

Start with phase index 1 (-2/8): data pulses lead the first logical clock
edge by 30 us and hold for 46 us. To test the second logical clock edge,
use index 3 (+2/8), with 31-us setup and 45-us hold. Clock inversion swaps
physical rising/falling meanings; it does not shift the events. These are
nominal software timings, not established handheld requirements. Inverted
clock drive adds boundary transitions when leaving/returning to dark idle;
these are not payload clocks and can affect acquisition. Phase 0
has no setup margin at the first edge. See the
[staged discrimination plan](../../../doc/re-notes/ir-feedback-protocol.md#discriminating-the-receive-convention)
for controls and limits.

For example, append these flags to the FREE_TX build above for one fixed,
open diagnostic candidate (repeat with stuffing 0 and 2, changing nothing
else):

```text
-DSTOCK_FIXED_CANDIDATE=1 -DSTOCK_FLAG_IDX=1 -DSTOCK_PHASE_IDX=1 -DSTOCK_POL_IDX=0 -DSTOCK_CONTENT_IDX=3 -DSTOCK_STUFFING_MODE=1 -DSTOCK_CLOSE_FLAG=0 -DSTOCK_TX_SWAP=0 -DSTOCK_CLOCK_INVERT=0 -DSTOCK_DATA_INVERT=0
```

Candidate indices and reply delay apply with `STOCK_FIXED_CANDIDATE=1`.
Test both physical role assignments and record actual drive levels; defaults
alone do not cover these unknowns. A full FREE_TX sweep has 60 rows and takes
15 seconds, longer than one roughly five-second handheld retry batch.
Use repeated V24 attempts overlapping the desired rows, or fixed candidates
for matched repetitions. Repeat a positive candidate and an interleaved
silent control before assigning cause.
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
window are reported as unmatched; missing TX evidence does not establish a
silent control. Startup banners separate Uno clock epochs. Initialization
pulse candidates are excluded from IR TX association. Malformed JSON records
make analysis fail explicitly rather than silently losing evidence.

The event ring holds seven pending pulses. If it fills while the Uno is busy,
some events are dropped and reported as `# STOCK_YELLOW_DROPS N`; a capture
with drops is incomplete. New captures retain 32-bit widths and use a
saturating 16-bit drop count. The initial rise from a pin already low when
capture starts is ignored because its falling edge was not observed.
Legacy captures with capped 65535-us widths are flagged and not correlated.
This marker records timing at the Uno input pin. It does not decode a yellow
serial record, identify which stock-ROM routine caused the pulse, or prove
that the optical signal reached the handheld receiver. Confirm optical
waveforms independently when interpreting a negative result.

Expected revision-2 low pulses are about 918 us (stock RX carry set),
1828 us (carry clear), and 3637 us (initialization). Width classification
is a candidate interpretation; later frame validation is not instrumented.
The ROM holds high guards about 460 us on each side of an RX pulse, including
instruction overhead, even if yellow originally was held low.

INT0 still triggers on D2 rising edges; its callback samples D4 directly
from `PIND` before calling `micros()` or applying debounce. D8 PCINT,
Timer0 and UART interrupts remain enabled during optical emission. Do not
wrap the emitter in `noInterrupts()`: that can lose D8 edges and Timer0
overflow counts. Yellow records are queued by the ISR and written one
complete line at a time only when the UART buffer has room. Both optical
timing metrics are software observations: `emit_late_max` is sampled before
GPIO and `emit_applied_late_max` after GPIO (a conservative upper bound
subject to 4-us resolution and intervening interrupts). Check D5/D6 and D8
together on the scope. Ring drops cannot reveal interrupt-flag coalescing.

### V7 single-bit payload probe

`STOCK_PAYLOAD07_TO06=1` changes only the second byte of the normal
fixed ten-byte payload from07h to06h; default0 preserves the baseline.
It has no effect when STOCK_ZERO_PAYLOAD selects the separate zero array.
Archived09: `analysis/arduino/releases/stock-v7-framing/09-double7e-payload06/`.
Two raw7E bytes plus payload00060002014300000201,101cells including5lead
zeros. Host validation checks the sole changed cell36 and candidate
window35..42=80h; physical ASIC interpretation remains untested.

`STOCK_PAYLOAD00_TO80=1` changes only the first normal payload byte00h
to80h. Default0 preserves historical images; combining with zero-payload
or07-to06 controls is rejected. Variant10 is archived under
`analysis/arduino/releases/stock-v7-framing/10-double7e-payload80/`.
Exact-stream host gate verifies onlycell21 changes,101cells retained,
and candidate flag/payload window18..25 changesC0->D0.
