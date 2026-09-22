# IR feedback harness interface

Implementation contract for the combined diagnostic ROM and Elegoo Uno R3.
The connector mappings are owner measurements; this command/result protocol
is new test firmware, not a discovered Micronic protocol.

## Contacts and polarity

* Uno D7 drives an external NPN base through a resistor; emitter goes to
  common ground and collector to black/pin 5. D7 high sinks black; D7 low
  releases it. Add a base-emitter pull-down so reset releases the line.
* Uno D8 senses yellow, with an external 10 kOhm pull-up to Uno 5 V.
  Yellow low means ROM port `2Ah` bit 0 set (sink); high means release.
  D8 is always an input. The Uno never drives yellow.
* D5 is physical optical output A, D6 output B. Clock/data roles are
  hypotheses selected on the Arduino. Both outputs low means silent.
* Blue is common ground. Do not join orange handheld Vcc to Uno 5 V.
  Red is unused by this harness; its measured 5.6 V must not enter an Uno pin.

Validate levels and transistor orientation with the connector probe before
connecting the harness. Yellow's measured 200 mA sink current is not a rating.

## Command and trial timeline

The ROM defaults to idle with yellow released and the black gate restored:
port `2Ah` bit 1 high, port `2Ch` bit 5 low. No trial runs automatically.
Only one request may be outstanding. LCD/key work is allowed while idle;
black must remain low until acknowledgement, so LCD gaps cannot lose a request.

1. Uno requires yellow high for at least 100 ms, then asserts black.
2. ROM detects black low and sinks yellow as ACK. No LCD/key work occurs
   during pulse measurement. Uno must observe ACK within 1500 ms or release
   black, cancel the trial and report an error without optical emission.
3. From observed ACK, Uno holds black for 100 ms (mode 1, witness), 300 ms
   (mode 2, forced RX), 500 ms (mode 3, probe), or 700 ms (mode 4,
   pending-gated RX), then releases it. ROM measures
   from its ACK using approximately 5 ms sampled ticks. Inclusive accepted
   tick windows: 15..30 for witness, 50..70 for RX, 90..110 for probe,
   and 130..150 for pending-gated RX.
   All other durations are invalid. 160 ticks low is a stuck-input abort.
4. ROM requires six consecutive released samples (about 30 ms). Any low
   sample aborts the request. Black must be released before IR gate changes.
5. For an accepted command, ROM releases yellow for 50 ms. Uno recognises
   START only on a following falling edge preceded by at least 40 ms high
   while waiting for this accepted request. A 1000 ms start deadline applies
   after black release. Error records are decoded in this state too.
6. ROM sinks yellow at START and waits 2 ms before the trial body. This
   deliberate delay makes the marker detectable even for an immediate error.
   Arduino stimulus delay is measured from observed START, not from an
   optical burst. Record the marker observation time and actual dispatch
   lateness. Do not log over Serial inside a timed optical emission.
7. ROM runs a bounded witness, RX or probe trial. It performs ordered stock
   teardown, then holds yellow low for another 100 ms before restoring the
   black gate. This lets the permitted Arduino stimulus (at most 60 ms delay
   plus 24 ms emission) finish before result transmission even if the trial
   exits immediately. No input commands are accepted
   while the IR configuration is active. The trial/result deadline is 6000 ms
   from START; expiry releases black and switches both optical outputs off.
8. ROM releases yellow for 20 ms, emits the result below, and leaves yellow
   released. This 20 ms result lead-in is deliberately shorter than the
   40 ms START qualifier. Result UART data cannot produce a 40 ms high run.
   A result must be received before another host trial is allowed; after a
   timeout require an explicit resynchronisation command and a fresh idle
   interval. Never automatically re-arm a stale stimulus.

Malformed and stuck-low requests emit an error result after the 20 ms
lead-in, without a 50 ms pretrial guard or START. A sustained UART break is
not a byte: the receiver requires a valid stop bit and resets on framing error.
If black is physically stuck low, the ROM must wait for release before it
can acknowledge another request. Manual keypad trials use the same START,
teardown and result path; the host must not confuse them with a pending request.

## Result record

Yellow is idle-high, **1200 baud, 8 data bits LSB first, no parity, one stop
bit**. Low is sink and high is release. The ROM sends exactly 30 bytes;
there is no optional text or newline. The Uno scans for the magic/version,
validates length, checksum, mode and sequence, and logs a complete record.
A timeout, framing error or checksum failure is an invalid result, never
successful test completion.

| Offset | Meaning |
|---:|---|
| 0..1 | Magic `A5 5A` |
| 2 | Format version `01` |
| 3 | Mode: 0 invalid request, 1 witness, 2 forced RX, 3 probe, 4 pending-gated RX |
| 4..5 | ROM trial counter, little-endian; increment once per accepted trial, including keypad trials |
| 6 | Error code, table below |
| 7 | Controller probe result |
| 8..9 | `LINK_STATUS` before and after trial |
| 10 | `LINK_STATUS` bit-4 poll result: `10` clear, `00` timeout, `FF` not run |
| 11 | `LINK_STATUS` bit-6 poll result: `40` clear, `00` timeout, `FF` not run |
| 12 | TX arm executed: 0/1 |
| 13..14 | RX raw return A and F (zero when RX was not run) |
| 15..16 | RX count, little-endian (zero when RX was not run) |
| 17 | Preview length, 0..8; zero on RX error |
| 18..25 | First descriptor's received bytes, bounded by count and descriptor capacity; unused bytes zero |
| 26..27 | Final port `2Ah` and `2Ch` shadows after idle gate restoration |
| 28 | Raw port `2Dh` sample after gate restoration |
| 29 | Check byte: unsigned sum of all 30 bytes modulo 256 equals zero |

Error codes: 0 completed diagnostic (not protocol acceptance), 1 invalid
command width, 2 stuck black low, 3 unstable release, 4 TX-ready timeout,
5 bit-4 timeout, 6 bit-6 timeout, 7 RX routine error, 8 receive-pending timeout.
Local Arduino timeout,
framing, checksum and cancellation errors are serial-log events, not fabricated
ROM records. Not-run fields are reset every trial; old RX bytes must not leak.

RX uses a private 134-byte descriptor. The count field is the successful
stock routine's returned DE value, which subtracts two from the consumed
byte count. Those two bytes have not been assigned a wire-level meaning.
The count is not a claim of a validated frame.
Mode 2 arms the stock receive routine directly. Mode 4 enables the idle
receiver and waits at most about 100 ms for `LINK_STATUS` bit 4 before calling
that same routine. Both arming hypotheses are available in the same burn.

The host trial ID and ROM counter are distinct. Log both. Once synchronised,
an accepted automatic trial must advance the ROM counter by one modulo 65536;
otherwise report a sequence mismatch. A first record establishes a baseline
and cannot prove that no earlier/manual trial occurred. A ROM reset requires
explicit host resynchronisation before another stimulus trial.

## USB commands and first bench sequence

The Uno runs at 115200 baud with newline-terminated ASCII commands. The
feedback build powers up silent. `R` releases black, turns both LEDs off,
prints `SYNC`, and reports `READY` after a fresh 100 ms yellow-high interval.
After any transport error, resynchronise explicitly rather than retrying.

```text
T id W|R|P|G S|X swap flag|-- stuff close pol phase lead delay_us payload
C id
R
B id L|R
```

`id` is a strictly increasing decimal host ID, starting at 1. Trial modes are witness `W`,
forced RX `R`, reset/probe `P`, and receive-pending-gated RX `G`. `S` is silent;
`X` sends one stimulus. Probe mode requires `S`.

| Parameter | Values |
|---|---|
| `swap` | 0: D5 proposed clock, D6 proposed data; 1: reverse |
| `flag` | Exactly two hex digits, or `--` for raw payload without a start byte |
| `stuff` | 0 none; 1 insert zero after five ones; 2 insert one after five zeros |
| `close` | 0 none; 1 append the selected unstuffed candidate flag |
| `pol` | 0 normal candidate data sense; 1 complement it |
| `phase` | Decimal -4..4, data rise minus clock rise in eighths of a cell |
| `lead` | 0..16 proposed-clock-only cells before the stimulus |
| `delay_us` | 0..60000 from observed yellow START; log actual scheduling lateness |
| `payload` | Up to 16 bytes as contiguous hex, or `-` for no payload |

The initial implementation uses 122 us cells, 61 us proposed clock pulses,
and 76 us proposed data pulses, MSB-first bytes. These are trial settings,
not established receive requirements. Changes beyond the current USB ranges
require only an Arduino sketch update, within the ROM's documented deadlines.
With `flag=--`, `stuff` and `close` must both be zero. Neither a software
`flag` label nor a controller-status change establishes a received flag.

`C id` silences the Arduino and abandons its active trial; it cannot undo a
ROM trial already started. Cancellation is serviced during the scheduled
delay, or after an optical emission completes (at most 24 ms). In particular, releasing black during a command
can leave a valid shorter pulse. Observe the returning result/idle state and
resynchronise before proceeding. `B id L` and `B id R` are idle-only bench
controls for the black transistor; a held low starts the ROM's command
measurement and eventually its stuck-input error. Use the automatic `T`
handshake for experiments, not manual pulse timing.

1. Validate the connector interface with the already-tested connector ROM:
   D7 low releases black, D7 high pulls it low; verify yellow at D8 stays
   within 0..Uno 5 V. Use a 10 kOhm base resistor and 100 kOhm base-emitter
   pull-down for the external NPN. Check the chosen transistor's pinout.
2. Install the feedback ROM in ROM00 only and upload the matching sketch.
   Leave ROM01 stock. Power up with black released and both optical outputs
   off. This standalone diagnostic replaces normal startup and uses scratch
   RAM; it does not run the normal barcode API or session menus.
3. Send `R`, wait for `READY`, then perform a silent probe trial:

   ```text
   T 1 P S 0 -- 0 0 0 -2 0 0 -
   ```

4. Capture yellow, D5 and D6 on the scope. Run a silent witness, then one
   candidate stimulus under the same optical placement:

   ```text
   T 2 W S 0 7E 1 0 0 -2 5 7000 -
   T 3 W X 0 7E 1 0 0 -2 5 7000 -
   ```

   Wait for `RESULT` and a fresh `READY` between commands. Repeat with `swap=1`
   and new IDs, including its own silent control. `7E` is one candidate byte,
   not an accepted flag. Keep timeout and negative records.
5. Repeat controlled comparisons with `G`, then `R`. Change one Arduino
   parameter at a time. Correlate raw status, return flags/count and preview
   with the scope. Successful diagnostic completion does not mean a valid
   IR frame. A checksum error means the yellow feedback channel needs fixing
   before interpreting the IR experiment.

For a durable host log, put explicit `T` lines in a text file (comments start
with `#`) and run from the repository root:

```sh
python3 analysis/ir_feedback.py --port /dev/ttyACM0 \
  --commands trials.txt --log trial-results.jsonl
```

The POSIX runner needs no third-party Python package. It records UTC and
monotonic timestamps for every line, waits for matching results/readiness,
and stops on a transport error or unexpected result without replaying a
trial. It exclusively creates the log, so rerunning cannot overwrite
measurements. Close any Arduino Serial Monitor before opening the same port.
A ROM diagnostic timeout is recorded as data and does not abort a batch.

## LCD and keypad

The LCD refreshes after each completed trial; it does not continuously poll
IR status. YES/NO adjust contrast. W, R, P and G run the corresponding manual
trial after checking black is released. Space has no action in this ROM.
These controls differ from the earlier connector-probe ROM. Do not operate
manual trials during an automated batch; resynchronise the Uno afterwards.

The four 20-column rows contain hexadecimal values (mode is a single digit):

```text
M2 S0000 E00 B34A56
Q=121040EC010400
D08=0001020304050607
A22C00IFE
```

* Row 1: mode, ROM sequence, diagnostic error, status before and after.
* Row 2 (`Q=`): seven bytes, probe status, bit-4 poll result, bit-6 poll
  result, raw RX A, raw RX F, returned DE low byte, returned DE high byte.
* Row 3: preview length then eight byte positions, unused positions zero.
* Row 4: final port 2Ah, port 2Ch and raw port 2Dh, labelled A, C and I.

For example `0400` at the end of row 2 means DE=0004h. Refer to the error
table above before interpreting a zero count or preview. The USB result is
the full machine-readable record, including the TX-arm flag omitted on LCD.

## Build and copy verification

Run from the repository root:

```sh
analysis/venv/bin/python analysis/rom_exerciser/feedback.py \
  -o analysis/rom_exerciser/releases/feedback-v1/micron1_feedback_v1.bin \
  --manifest-out analysis/rom_exerciser/releases/feedback-v1/micron1_feedback_v1.json
```

The image is **32768 bytes**, for ROM00 only. It patches cold boot and a
private diagnostic area; ROM01 stays stock. Generated binaries are ignored
by git; the adjacent JSON manifest pins the reproducible image and source.

Full burn-image path on the development PC:

```text
/home/philpem/Micronic-1000/analysis/rom_exerciser/releases/feedback-v1/micron1_feedback_v1.bin
```

| Check | Value |
|---|---|
| MD5 | `815db5763ad1f0b9910620a7dd83ed7c` |
| Additive 16-bit, hex | `A1FA` |
| Additive 24-bit, hex | `37A1FA` |
| SHA-256 | `23572b77763cfba2d64a069cfe0b1e42a034b542fcf97c607461465b73e4f93c` |

Additive checksums sum every unsigned image byte, modulo 2^16 or 2^24,
without complement. These values are for feedback-v1, not either connector
probe image. Verify the copied file on the programmer PC before burning.

Rsync the entire existing Arduino directory:

```text
/home/philpem/Micronic-1000/analysis/arduino/m1000_ir_probe/
```

Open `m1000_ir_probe.ino`; the neighbouring `feedback_harness.h` is required.
Select Arduino Uno / Elegoo Uno R3. The default build is feedback mode;
remove old compile-time sweep flags when compiling this experiment.

## Validation and limits

Automated checks execute the assembled ROM with simulated port reads,
exercise the actual Arduino sketch through its serial/feedback interface,
and decode the ROM's yellow output using an independent 1200-baud receiver.
They cover malformed commands, bounds, timeouts, raw RX results, LCD output,
marker timing, UART framing/checksum, and silent/stimulated operation.
The ROM UART cell measured 3067 Z80 T-states against nominal 3072; decoding
also passes at receiver clock offsets of plus/minus 2 percent.

The feedback build and all 13 legacy configurations compile for the Uno.
Physical connector/IR coexistence, the feedback link on this board and actual
IR reception still require the bench sequence above. `7Eh` and the physical
LED roles remain hypotheses. Stock poll bodies and ordering are retained,
but wrapper call overhead, markers and disabled maskable interrupts make
this a diagnostic environment, not an exact replay of the running OS.
