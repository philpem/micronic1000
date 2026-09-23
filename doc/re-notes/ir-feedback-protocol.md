# IR feedback harness interface

Implementation contract for the combined diagnostic ROM and Elegoo Uno R3.
The connector mappings are owner measurements; this command/result protocol
is new test firmware, not a discovered Micronic protocol.

## Current handoff: next physical trial

**Status 2026-09-23:** feedback-v1 ROM00 is already installed. Trials 6 and
8 validated digital timing for both proposed Uno clock/data assignments;
their source CSVs are tracked in `analysis/captures/`. Trial 7 was an
expected silent control. Both W stimuli retained the bit-6 timeout; W does
not attempt RX. Forced-RX silent/stimulated trials 9/10 both returned raw
`A=EEh`, `F=6Dh`, wrapper error 7. The stock RX byte-ready wait can return
that error after its 1785-count poll; the record hides partial bytes on
error. Matched G pairs 11/12 (`swap=1`) and 13/14 (`swap=0`) all timed out
waiting for `LINK_STATUS` bit 4 (error 8) with an opening `7Eh` alone.
The matched `swap=0` G trials 15/16 added candidate payload `03h`; both
again timed out with error 8 and `E0h/C0h/C0h` probe/before/after status.
Trial 16 has no scope trace. Its unchanged repeat, trial 17, also returned
error 8. The trial-17 Keysight CSV independently shows the intended
`7Eh 03h` candidate at scope D2/D3 with all digital timing targets met;
the owner confirms the pod wiring remained D2→Uno D5 and D3→Uno D6.
The complemented-wire matched G pair 18/19 also returned error 8 with
identical A0h/80h/80h status. No trial-19 scope trace was supplied. None
of these G trials entered stock RX.
Direct stock-RX matched IDs 20/21 both returned `EEh`/carry and wrapper
error 7. Trial 21's `LINK_STATUS` changed `80h→C0h` across the RX call,
but its pre-stimulus baseline differed from trial 20's `C0h`; neither
causation nor accepted receive framing is established.
The late-stimulus R pair 22/23 both began with bit 6 set (`A0h/C0h/C0h`)
and again returned `EEh`/carry. Trial 23 did schedule its burst at about
START+60 ms. This does not reproduce or explain trial 21's bit-6 rise.
**OPEN:** optical delivery, physical LED roles and receive framing remain
unproved. The one-burn ROM and USB sketch stay in place.
`emit_start_us` marks scheduler entry about 256 us before the first edge;
compare physical edges in CSV rather than software interval length.

1. Keep the tested sketch from branch `ir/automated-feedback-tests` and the
   present geometry/wiring. It is the direct-TTL `BLACK_USE_NPN=0` build for
   `arduino:avr:uno` (Elegoo Uno R3, 16 MHz). Confirm `BLACK: DIRECT_TTL`
   and LCD `IR FEEDBACK/W/R/P/G` if restarting. No EPROM or Uno code change
   is needed for the next comparison.
2. Check the **optical output at the handheld top V24 receive window**
   before changing frame parameters again. The owner previously used an
   SFH213 photodiode with cathode to **Uno 5 V**, anode through 100 kOhm
   to **Uno GND**, and a scope probe on the anode; light raises the anode
   ([optical front-end notes](ir-wire-protocol.md#the-slew-is-the-receivers-not-the-transmitters)).
   If that probe is still available, measure each Uno LED channel at its
   intended handheld receive aperture. Keep the LED drivers, current
   limiting, spacing and masks as used in trial 17. Scope Uno D5/D6 and
   the photodiode analogue output together over at least 4 ms; the owner
   confirmed scope pod
   D2→Uno D5, D3→Uno D6 through trial 17. Record which receive aperture
   the photodiode faces, its position relative to the handheld window,
   and whether each D5/D6 pulse train produces a distinct light waveform.
   This validates light at the target plane, not the internal detector.
3. Open serial at 115200 baud; send the standalone `R` resync command and
   wait for `READY`. For an optical capture, repeat the known ID-21 stimulus
   with the next unused ID, while recording the scope. For example:

   ```text
   T 24 R X 0 7E 1 0 1 -2 5 7000 03
   ```

   Use a new ID for each repeat; the standalone `R` does not reset host
   IDs. `stuff=1` builds the logical stream before `pol=1` complements
   the entire frame, yielding physical candidate `81h FCh`. If one
   photodiode must be moved between the two apertures, repeat with the
   next ID without changing Arduino settings. Preserve each full serial
   result but interpret this as an optical-path check, not a new protocol
   candidate. A photodiode trace at the window cannot itself prove that
   the handheld receiver decoded a frame.
4. The trial-17 source is archived at
   `analysis/captures/feedback-trial17-keysight.csv`. Reproduce its decoding
   with `python3 analysis/feedback_scope.py
   analysis/captures/feedback-trial17-keysight.csv --clock-bit 2
   --data-bit 3 --payload 03 --stuff 1`. Scope D2 carried **21** proposed
   clock pulses and D3 **eight** data pulses, with sampled candidate cells
   `0111111000000011` (`7Eh` followed by `03h`). Every clock rise
   interval should be within 8 us of 122 us, clock high within 8 us of 61 us,
   data high within 8 us of
   76 us, and `emit_late_max` below about 15 us; trial 17 met these targets.
   The trace cannot identify Uno header wiring, emitted IR light, or optical
   receipt. For the proposed optical check, the expected sampled cells are
   `1000000111111100` if the D2/D3 channel mapping is unchanged; the data
   pulse count remains eight. Decode its *physical* complemented cells with
   `--flag 81 --payload FC --stuff 2`; that decoder stuffing mode describes
   the wire sense, whereas the sketch uses `stuff=1` **before** complementing
   the frame. No stuffed cell occurs in this particular candidate. The
   analogue light signal should follow the appropriate digital pulse train.
   Do not infer a receiver frame merely from a matching optical waveform.

For each trial preserve the full serial `TRIAL`/`RESULT`/`READY` text, CSV,
scope pod-to-Uno map, geometry, sketch commit/build setting, and ROM identity.
The LCD need only be transcribed if it disagrees with the serial result or
serial feedback is missing. The installed ROM00 image is
`analysis/rom_exerciser/releases/feedback-v1/micron1_feedback_v1.bin`, MD5
`815db5763ad1f0b9910620a7dd83ed7c`, additive 16-bit `A1FA`, additive
24-bit `37A1FA`; ROM01 remains stock. See the detailed setup below.

## Connect the handheld to the Uno

Use **three wires from the right-side scanner connector: blue, black and
yellow**. Power the handheld from its batteries and the Elegoo Uno R3 from
USB. Join their grounds, but keep their positive supply rails separate.
The optical connection still uses the existing two IR LED channels.

Before uploading, set `BLACK_USE_NPN` in `m1000_ir_probe.ino` and wire black
to match it. `1` is the default external-NPN interface; `0` selects a direct
5 V TTL wire from D7 to black/pin 5. The startup and `R` output must say
`BLACK: NPN` or `BLACK: DIRECT_TTL` for the wiring actually fitted. The
suggestion that black may feed 74LS logic remains SUSPECTED; direct TTL is a
selected bench interface, not an established hardware identity.

The colours below refer to the owner's tested cable. They are not a standard
mini-DIN colour code. **CONFIRMED: owner pin-number identification,
2026-09-22:** black 5, yellow 6, blue 8, red 1, orange 3. No connector-face
view or plug/socket numbering orientation is implied by the wiring diagram.

| Handheld scanner-connector wire | Connect to | Purpose |
|---|---|---|
| **Blue / pin 8 / ground** | **Uno GND**; NPN emitter when selected | Common signal reference |
| **Black / pin 5** | NPN collector (`BLACK_USE_NPN=1`) or **Uno D7** (`=0`) | Uno command to handheld |
| **Yellow / pin 6** | **Uno D8**, and one end of a **10 kOhm** resistor | Handheld ACK/START/result output |
| **Orange / pin 3 / Vcc** | Leave disconnected and insulate | Handheld supply; do not connect to Uno 5 V |
| **Red / pin 1** | Leave disconnected and insulate | Unused output, measured up to 5.6 V |
| **Brown / pin 2, violet / pin 4, green / pin 7** | Leave disconnected and insulate | Unassigned contacts |

Complete the Arduino-side connections:

| Uno connection | Wire/component |
|---|---|
| **D7, NPN mode** | Through **10 kOhm** to transistor **base** |
| **D7, direct-TTL mode** | Directly to black / pin 5; no NPN/base resistors |
| **GND** | Handheld **blue / pin 8**; NPN emitter and one end of 100 kOhm resistor in NPN mode |
| Transistor **base, NPN mode** | Other end of the **100 kOhm** resistor |
| **5 V** | Other end of yellow's **10 kOhm** pull-up resistor |
| **D8** | Yellow/pull-up junction; configured as input |
| **D5** | Existing IR LED driver/channel **A** |
| **D6** | Existing IR LED driver/channel **B** |
| **D2, D4** | Not required for feedback mode; optical monitoring is disabled |

For **direct-TTL mode** (`BLACK_USE_NPN=0`), use this command connection:

```text
Uno D7 ------------------------------------------------ Black / pin 5
Uno GND ----------------------------------------------- Blue / pin 8 / ground
Uno 5 V ------[10 kOhm]-------+------------------------ Yellow / pin 6
                             |
Uno D8 ----------------------+
```

Power the Uno before the handheld. Switch the handheld off before unplugging
Uno USB; keep the Uno powered while the handheld is powered. The NPN and
its base resistors are not fitted in this mode.

For the optional **NPN mode** (`BLACK_USE_NPN=1`), B, C and E mean base,
collector and emitter:

```text
                 COMMAND: Uno -> handheld

Uno D7 -------[10 kOhm]-------+------- B
                             |        |  NPN transistor
                          [100 kOhm]  C------------- Black / pin 5
                             |        E
Uno GND ---------------------+--------+------------- Blue / pin 8 / ground


                 FEEDBACK: handheld -> Uno

Uno 5 V ------[10 kOhm]-------+--------------------- Yellow / pin 6
                             |
Uno D8 ----------------------+


                 OPTICAL STIMULUS

Uno D5 ------ existing LED driver A ---- IR light --> handheld top V24 window
Uno D6 ------ existing LED driver B ---- IR light --> handheld top V24 window
```

The transistor drawing is a **connection diagram, not a package pinout**.
Check the B/C/E arrangement for the actual transistor. Keep the existing IR
LED current limiting/drivers: D5/D6 are not wired to scanner-connector pins.
Their clock/data roles remain unknown; the USB `swap` setting reverses the
proposed roles without changing the wiring.

Assemble with power off. Remove any earlier test resistor connecting yellow
to **orange/Vcc** or to ground: this harness instead pulls yellow up to
**Uno 5 V** through 10 kOhm. Likewise remove the earlier black-to-ground test
resistor. In NPN mode, the NPN lets the Uno sink or release black without
receiving that voltage on D7; its 100 kOhm base-emitter resistor keeps it
released while the Uno resets. In direct-TTL mode, black connects directly to
D7 under the required power order above.

With power applied, yellow should sit near Uno 5 V when released and near
0 V when the handheld sinks it; verify that before connecting D8. In NPN mode, black
retains its handheld-side high level when the transistor is off; in direct
TTL mode, D7 drives the idle high.
Use the connector-probe checks in the bench sequence below to verify the
pull-low/release paths before running a stimulus.

**Signal polarity:** NPN mode uses D7 high to command black low and D7 low to
release it. Direct-TTL mode uses D7 low to command black low and D7 high for
idle. Yellow low means ROM port `2Ah` bit 0 is set (sink); high means
release through the Uno-side pull-up. D8 is always an input and never drives
yellow. The pull-up draws about 0.5 mA when yellow is low; yellow's
owner-measured 200 mA sink current is not a component rating.

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
controls for the selected black interface; a held low starts the ROM's command
measurement and eventually its stuck-input error. Use the automatic `T`
handshake for experiments, not manual pulse timing.

1. Select `BLACK_USE_NPN` before uploading and validate the connector
   interface with the already-tested connector ROM. For NPN mode, D7 low
   releases black and D7 high commands it low; use the 10 kOhm base resistor,
   100 kOhm base-emitter pull-down and verify the transistor pinout. For
   direct-TTL mode, D7 high releases black and D7 low commands it low; power
   Uno before handheld and switch handheld off before removing Uno USB.
   In either mode verify yellow at D8 stays within 0..Uno 5 V.
2. Install the feedback ROM in ROM00 only and upload the matching sketch.
   Leave ROM01 stock. Power up with black released and both optical outputs
   off. This standalone diagnostic replaces normal startup and uses scratch
   RAM; it does not run the normal barcode API or session menus.
3. Confirm the matching `BLACK:` banner, send `R`, wait for `READY`, then
   perform a silent probe trial:

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

## Recovering from a serial command rejection

The current sketch uses a generic `ERROR ... reason=command` for malformed
or empty command lines, non-increasing IDs, and requests made outside READY.
Its `id` is the last accepted trial ID; any `raw` bytes may be retained from
that completed trial. They are not a new handheld response and do not reveal
which input line was rejected. Inspect the preceding TRIAL/READY lines.

On 2026-09-23, after completed trial 3, the owner reported:

```text
ERROR id=3 reason=command raw=A55A0101030006A0C0C81000010000000000000000000000000022002378
```

The owner then confirmed resending the same ID-3 command to repeat the
trial. This explains the rejection: every trial, including an identical
repeat, needs a strictly greater host ID. The old bytes are not a new result.
To recover, select Newline in Serial Monitor, send `R` as a separate line,
wait for SYNC/wiring banner/READY, then send the intended trial 4 command
once. If it is rejected again, retain the exact transmitted text as well
as the response. R resets synchronisation, not the host-ID monotonic check.
The next accepted host ID must still exceed the last accepted ID.

## LCD and keypad

For routine bench reports, retain the complete TRIAL and RESULT lines (and
any ERROR), plus scope captures when requested. RESULT includes every LCD
field and additional data, so LCD transcription is unnecessary. Report LCD
contents when they disagree with serial, when no RESULT arrives, or when
debugging the display itself.

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

## First hardware result — 2026-09-23

**CONFIRMED (owner bench report):** feedback-v1 boots on the handheld,
and the Uno reports `BLACK: DIRECT_TTL; D7 HIGH=idle, LOW=command`.
Serial `R` produces `SYNC` and a fresh `READY`. The first silent probe
completed and returned to `READY`:

```text
T 1 P S 0 -- 0 0 0 -2 0 0 -
TRIAL id=1 mode=P kind=S swap=0 flag=-- stuff=0 close=0 pol=0 phase=-2 lead=0 delay_us=0 cell_us=122 order=MSB payload=-
RESULT id=1 rom_seq=1 mode=3 err=0 ack_us=68872424 release_us=69372424 start_us=69452424 emit_start_us=0 emit_end_us=0 emit_late_max=0 raw=A55A0103010000C0C0C0FFFF000000000000000000000000000022002379
READY
```

Owner-reported LCD:

```text
M3 S0001 E00 BC0AC0
Q=C0FFFF00000000
D00=0000000000000000
A22C00I23
```

Decoded independently from the supplied hex: exactly 30 bytes, byte sum
modulo 256 is zero; sequence 1, probe mode 3, diagnostic error 0. Probe,
before and after `LINK_STATUS` values are all C0h. The two witness poll
fields are FFh (not run), the TX-arm flag is zero, and RX return/count/preview
fields are zero (RX not run). Final latch values are `2Ah=22h`, `2Ch=00h`,
with raw `2Dh=23h`; all agree with the LCD.

The logged ACK-to-black-release interval is 500,000 us, matching P mode;
release-to-START is 80,000 us, consistent with the 30 ms release check plus
50 ms guard. These are Arduino observation times, not a scope measurement.
The zero emission timestamps are consistent with the selected silent mode.
This demonstrates one successful direct-TTL command and yellow result
transaction through the probe/reset/select path. It does not establish IR
receive framing, LED roles, or coexistence with active TX/RX trials.

## Silent witness, host ID 2 — 2026-09-23

**CONFIRMED (owner bench report):** the silent W trial returned a valid
result and READY. The following record preserves the original serial output:

```text
T 2 W S 0 7E 1 0 0 -2 5 7000 -
TRIAL id=2 mode=W kind=S swap=0 flag=7E stuff=1 close=0 pol=0 phase=-2 lead=5 delay_us=7000 cell_us=122 order=MSB payload=-
RESULT id=2 rom_seq=2 mode=1 err=6 ack_us=325261964 release_us=325361964 start_us=325446868 emit_start_us=0 emit_end_us=0 emit_late_max=0 raw=A55A0101020006A080C810000100000000000000000000000000220023B9
READY
```

LCD:

```text
M1 S0002 E06 B80AC8
Q=A0100000000000
D00=0000000000000000
A22C00I23
```

Independent decode: 30 bytes with sum modulo 256 zero; sequence 2, mode 1,
diagnostic error 6. Probe status A0h, before status 80h, after status C8h.
The bit-4 poll result is 10h (LINK_STATUS bit 4 cleared); the arm flag is 1;
the bit-6 poll result is 00h (LINK_STATUS bit 6 did not clear within the
bounded wait). No RX was attempted. The final gate/sample remain 22h/00h/23h,
and every displayed field agrees with the serial record.

ACK-to-release is 100,000 us; release-to-START is 84,904 us. The logged
emission timestamps remain zero as selected by S. This establishes a valid
feedback transaction after a silent stock-order witness, including the arm
and ordered teardown path. Error 6 is a measured controller-wait outcome,
not a feedback transport failure. No wire-level meaning is assigned to the
raw status values or the bit-6 wait by this result.

## First stimulus, host ID 3 — 2026-09-23

**CONFIRMED (owner bench report):** matched W/X trial, swap 0, candidate
7Eh, phase -2, five lead cells, requested delay 7000 us:

```text
T 3 W X 0 7E 1 0 0 -2 5 7000 -
TRIAL id=3 mode=W kind=X swap=0 flag=7E stuff=1 close=0 pol=0 phase=-2 lead=5 delay_us=7000 cell_us=122 order=MSB payload=-
RESULT id=3 rom_seq=3 mode=1 err=6 ack_us=520435732 release_us=520535736 start_us=520620640 emit_start_us=520627684 emit_end_us=520629540 emit_late_max=110 raw=A55A0101030006A0C0C81000010000000000000000000000000022002378
READY
```

LCD:

```text
M1 S0003 E06 BC0AC8
Q=A0100000000000
D00=0000000000000000
A22C00I23
```

Independent decode verifies all 30 bytes/checksum and LCD agreement. Like
silent trial 2, the LINK_STATUS bit-4 wait passed, the TX arm executed, and
the LINK_STATUS bit-6 wait timed out (error 6). Probe/after status remain
A0h/C8h; before status is C0h rather than trial 2's 80h. The before sample
precedes the scheduled stimulus; do not attribute that difference to the
emission. Final gate/sample are again 22h/00h/23h; RX was not attempted.

The Uno reports an emission dispatch 7044 us after its START observation,
with 1856 us between its emission start/end timestamps (including the
emitter's 300 us post-burst delay). Those timestamps do not themselves mark
physical LED edges. The reported maximum event lateness is **110 us**, close
to a 122 us cell. This is a stimulus timing concern, not a yellow-result
checksum failure. A maximum alone does not identify the affected edge(s).

**OPEN:** verify the actual D5/D6 waveform before interpreting this as a
negative framing/LED-assignment result. The host emitter tests verify event
ordering with a simulated clock; they do not model AVR execution costs. In
this sketch, queue setup begins after `sendFrame` has waited for the first
edge deadline. Whether setup cost explains the observed maximum, and how
much later cells are affected, requires edge timing evidence.

Next repeat the same stimulus as host ID 4, capturing D5 and D6:

```text
T 4 W X 0 7E 1 0 0 -2 5 7000 -
```

For this software configuration, the intended GPIO waveform is 13 proposed
clock pulses on D5 (five lead cells plus eight candidate-byte cells), at
122 us period and 61 us high time; six data pulses on D6 for the six one bits
of 7Eh, each 76 us high and rising 30 us before its corresponding clock.
These are requested timings, not yet measured outputs or confirmed handheld
receive conventions. Record first and later pulse spacing/widths separately,
plus the full serial result. Keep placement/settings fixed for this repeat.

## Stimulus repeat, host ID 4 — 2026-09-23

**CONFIRMED (owner report):** after R/SYNC/READY, trial 4 completed:

```text
TRIAL id=4 mode=W kind=X swap=0 flag=7E stuff=1 close=0 pol=0 phase=-2 lead=5 delay_us=7000 cell_us=122 order=MSB payload=-
RESULT id=4 rom_seq=4 mode=1 err=6 ack_us=1083669104 release_us=1083769104 start_us=1083854008 emit_start_us=1083861052 emit_end_us=1083862904 emit_late_max=110 raw=A55A0101040006A080C810000100000000000000000000000000220023B7
READY
```

Independent decode: 30 bytes, checksum zero; bit-4 poll 10h, arm 1, bit-6
poll 00h/error 6; probe/before/after A0h/80h/C8h. Final latch/input fields
remain 22h/00h/23h. No RX. Logged hold 100 ms, release/START 84.904 ms,
emission dispatch START+7044 us, emission interval 1852 us, maximum lateness
again 110 us. This repeats the timing concern without identifying its edge.

The owner initially reported D6 appeared to begin before D5, with activity
extending off the left side of the scope display, then identified incorrect
scope channel labels. **Correction:** withdraw the apparent pin-order
reversal; it is not evidence that the sketch drives the channels backwards.
This correction does not establish pulse widths or resolve the 110 us timing
concern. In the selected software roles, individual D6 data edges are
requested 30 us before their paired D5 clocks; the five lead cells plus
initial zero of 7Eh request the start of the D5 train about 702 us before
the first D6 rising edge. Check first and later pulses in a complete capture
with corrected channel labels.

Following successful trial 4, repeated R/SYNC/READY followed by ID 4 produced
`ERROR id=4 reason=command`, as expected: R preserves the last accepted host
ID. The last supplied log ends at READY; the next usable ID is 5.

Next capture: CH1 on Uno header D5, CH2 on D6, common ground; single-shot
rising-edge trigger on D6 at about 2.5 V, 200 us/div with 50% pre-trigger.
Arm before sending the same command with ID 5. This should include the
intended earlier D5 lead clocks and later data; if either end is clipped,
increase the capture span. Keep the waveform and full serial result.

```text
T 5 W X 0 7E 1 0 0 -2 5 7000 -
```

## Stimulus and scope capture, host ID 5 — 2026-09-23

**CONFIRMED (owner serial report):** trial 5 completed with valid feedback;
ROM mode 1/error 6 again means the LINK_STATUS bit-4 poll passed, TX arm
executed, and LINK_STATUS bit-6 wait timed out. The owner supplied this
Agilent/Keysight MSO-X3054A digital CSV as `/tmp/IR`:

```text
TRIAL id=5 mode=W kind=X swap=0 flag=7E stuff=1 close=0 pol=0 phase=-2 lead=5 delay_us=7000 cell_us=122 order=MSB payload=-
RESULT id=5 rom_seq=5 mode=1 err=6 ack_us=1438882328 release_us=1438982336 start_us=1439067220 emit_start_us=1439074288 emit_end_us=1439076116 emit_late_max=138 raw=A55A0101050006A0C0C81000010000000000000000000000000022002376
READY
```

**CONFIRMED (CSV, 2.5 us/sample):** `analysis/feedback_scope.py` finds 13
pulses on scope D2 and six on scope D3. These are scope pod labels; D2/D3
are treated as the Uno's proposed clock/data lines using the earlier capture
wiring, pending confirmation that the probes were unchanged for this trial.
The scope window contains all 13 pulses. Sampling D3 at the eight candidate
D2 clock rises yields `7Eh`, the requested candidate byte. This verifies the
digital stimulus at the probes, not that `7Eh` is the handheld's receive flag
or that the optical LED channels have the intended roles.

| Scope measurement | Requested | Observed |
|---|---:|---:|
| Initial lead clock rise spacing | 122 us | 90, 90, 90, 92.5 us (median 90) |
| Later clock rise spacing | 122 us | mostly 130 us; 137.5 and final 80 us also occur |
| Typical clock high width | 61 us | mostly 45–47.5 us |
| Data high width | 76 us | 55–57.5 us |
| Data rise before paired clock | 30 us (integer phase calculation) | 30–32.5 us |

**CONFIRMED:** the emitted clock period and pulse widths differ materially
from the requested settings. The previous suggestion that only the first
lead pulse might be clipped is withdrawn: all four initial lead intervals
are about 90 us, and later spacing varies. The reported maximum software
event lateness is 138 us; that number alone does not locate its affected
edge. The CSV cannot establish what reached the handheld's photoreceiver.

**LIKELY:** constructing and sorting a lazy event queue after the scheduled
first-edge deadline contributes to the timing distortion (see `sendFrame`
and `emitCells` in the Uno sketch), but the scope trace does not isolate AVR
runtime costs from other scheduling effects. Correct the USB-loadable Uno
emitter and re-scope the same candidate before treating another error 6 as
evidence against framing, LED assignment, or receive polarity. The one-burn
feedback ROM remains suitable for this repeat. The source capture is tracked
at `analysis/captures/feedback-trial5-keysight.csv`; its
SHA-256 is `16baa457c5cd74cbdf5650839d931b251db12785ee3e8f4954465748b6507e50`.

## Repaired stimulus and scope capture, host ID 6 — 2026-09-23

**CONFIRMED (owner serial report):** the repaired direct-TTL Uno sketch
booted and completed the same W/X stimulus:

```text
BOOT
MODE: FEEDBACK v1, SILENT until explicit T; D5=A D6=B D7=black driver D8=yellow input
BLACK: DIRECT_TTL; D7 HIGH=idle, LOW=command
READY
SYNC
BLACK: DIRECT_TTL; D7 HIGH=idle, LOW=command
READY
TRIAL id=6 mode=W kind=X swap=0 flag=7E stuff=1 close=0 pol=0 phase=-2 lead=5 delay_us=7000 cell_us=122 order=MSB payload=-
RESULT id=6 rom_seq=7 mode=1 err=6 ack_us=15928724 release_us=16028724 start_us=16113620 emit_start_us=16120424 emit_end_us=16122516 emit_late_max=7 raw=A55A0101070006A080C810000100000000000000000000000000220023B4
READY
```

The 30-byte result sums to zero modulo 256. Its probe/before/after status
is A0h/80h/C8h; `LINK_STATUS` bit-4 poll returned 10h, arm executed, and
`LINK_STATUS` bit-6 poll returned 00h with error 6. RX was not attempted in
mode W. ROM sequence 7 is not a host-ID mismatch: host ID and ROM sequence
are independent, and the ROM also counts accepted keypad trials.

**CONFIRMED (owner Keysight CSV):** the new `/tmp/IR` was copied to tracked
`analysis/captures/feedback-trial6-keysight.csv` (SHA-256
`baf9c8437e93a9ec39642f62a925e5664707ebd554b0b04e4675dc449051751f`).
At 2.5 us/sample the decoder finds 13 pulses on scope D2 and six on D3,
with `7Eh` sampled on the eight candidate clock rises. **CONFIRMED (owner
probe identification):** scope D2 was connected to Uno D5 and scope D3 to
Uno D6 in trial 6. For `swap=0`, Uno D5 carried the proposed clock and Uno
D6 the proposed data; the LED optical roles remain unconfirmed.

| Measurement | Trial 5 | Trial 6 | Requested |
|---|---:|---:|---:|
| Clock rise intervals | 90 us first lead; mostly 130 us later | 117.5–127.5 us, median 121.25 us | 122 us |
| Clock high width | mostly 45–47.5 us | 60–67.5 us | 61 us |
| Data high width | 55–57.5 us | 77.5 us | 76 us |
| Data rise before paired clock | 30–32.5 us | 27.5–35 us | 30 us |
| Uno `emit_late_max` | 138 us | 7 us | below about 15 us |

**CONFIRMED:** the repaired sketch meets every stated digital timing target
at the scope probes, so the trial-5 emitter defect is resolved for this
candidate. **SUSPECTED, still open:** optical channel assignment and `7Eh`
as a receive flag. Error 6 is the stock-order witness's bit-6 timeout; it
does not report a rejected receive frame. The planned swapped-role witness
comparison was subsequently completed as IDs 7 and 8 below; direct RX
controls are next. No further ROM burn is indicated.

## Swapped-role silent control and stimulus, IDs 7–8 — 2026-09-23

**CONFIRMED (owner serial report):** trial 7 was intentionally silent, so
the absence of a D5/D6 optical waveform on the scope is expected. Its
`emit_start_us`, `emit_end_us` and `emit_late_max` were all zero. Trial 8
used the same candidate timing but `swap=1`:

```text
SYNC
BLACK: DIRECT_TTL; D7 HIGH=idle, LOW=command
READY
TRIAL id=7 mode=W kind=S swap=1 flag=7E stuff=1 close=0 pol=0 phase=-2 lead=5 delay_us=7000 cell_us=122 order=MSB payload=-
RESULT id=7 rom_seq=9 mode=1 err=6 ack_us=11406636 release_us=11506644 start_us=11591544 emit_start_us=0 emit_end_us=0 emit_late_max=0 raw=A55A0101090006A080C810000100000000000000000000000000220023B2
READY
TRIAL id=8 mode=W kind=X swap=1 flag=7E stuff=1 close=0 pol=0 phase=-2 lead=5 delay_us=7000 cell_us=122 order=MSB payload=-
RESULT id=8 rom_seq=10 mode=1 err=6 ack_us=19929104 release_us=20029112 start_us=20113992 emit_start_us=20120796 emit_end_us=20122892 emit_late_max=3 raw=A55A01010A0006A0C0C81000010000000000000000000000000022002371
READY
```

Both 30-byte records have valid zero-sum checksums. Each passed the
`LINK_STATUS` bit-4 poll, executed the TX arm, then timed out on
`LINK_STATUS` bit 6 (error 6); W mode did not call RX. Trial 7's
probe/before/after status was A0h/80h/C8h and trial 8's A0h/C0h/C8h.
The before sample precedes optical emission; earlier unswapped X trials
showed both 80h and C0h before values. Thus this difference is not a
demonstrated response to the swapped stimulus.

**CONFIRMED (Keysight CSV):** trial 8's `/tmp/IR` was copied into tracked
`analysis/captures/feedback-trial8-keysight.csv` (SHA-256
`edb99fecab134c998958b1eda6179fce2fbfc79205d1319c0f8aec448f52abae`).
At 2.5 us/sample, scope D3 carries 13 proposed clock pulses and D2 six
proposed data pulses. Candidate sampling yields `7Eh`. Clock rise intervals
are 117.5–125 us, clock widths 60–67.5 us, data widths 75–77.5 us, and
data rises 27.5–35 us before paired clocks. This meets all digital timing
targets after `swap=1`. If the scope wiring stayed as owner-confirmed for
trial 6, D3 is Uno D6 and D2 is Uno D5; optical reception remains unmeasured.

**CONFIRMED:** swapping the proposed LED roles while keeping the W stimulus
settings produced no change in the witness outcome: bit-4 pass, arm, bit-6
timeout. This does not select an LED role or reject `7Eh`; the W witness does
not report received bytes. The mode-R comparison that followed is recorded
below.

## Forced-RX silent control and stimulus, IDs 9–10 — 2026-09-23

**CONFIRMED (owner serial report):** the matched R/S and R/X pair used the
same `swap=1`, candidate `7Eh`, phase and delay as the trial-8 stimulus.
The silent control correctly has zero emission timestamps. Both 30-byte
records have valid zero-sum checksums:

```text
TRIAL id=9 mode=R kind=S swap=1 flag=7E stuff=1 close=0 pol=0 phase=-2 lead=5 delay_us=7000 cell_us=122 order=MSB payload=-
RESULT id=9 rom_seq=11 mode=2 err=7 ack_us=2340066216 release_us=2340366224 start_us=2340446156 emit_start_us=0 emit_end_us=0 emit_late_max=0 raw=A55A01020B0007A0C0C0FFFF00EE6D00000000000000000000002200232E
READY
TRIAL id=10 mode=R kind=X swap=1 flag=7E stuff=1 close=0 pol=0 phase=-2 lead=5 delay_us=7000 cell_us=122 order=MSB payload=-
RESULT id=10 rom_seq=12 mode=2 err=7 ack_us=2348517424 release_us=2348817432 start_us=2348897388 emit_start_us=2348904188 emit_end_us=2348906284 emit_late_max=3 raw=A55A01020C0007A0C0C0FFFF00EE6D00000000000000000000002200232D
READY
```

Both have probe/before/after A0h/C0h/C0h, unused W poll fields FFh/FFh,
TX arm field zero, and stock RX return `A=EEh`, `F=6Dh` (carry set). The ROM
wrapper reports error 7. The RX count and preview fields are zero because
`rx_collect` does not save DE or call `preview_rx` on carry; they are **not**
proof that the controller delivered zero bytes before error. Trial 10's
emitter was dispatched about 6.8 ms after START and reported maximum software
lateness 3 us. No trial-10 scope capture was supplied, so its physical
waveform is inferred from identical settings and the independently scoped
trial-8 burst, not measured anew.

**CONFIRMED (stock bytes):** `Link_BlockRx` at `ROM00:3378` arms RX, then
at `ROM00:33CF–33EB` polls `LINK_STATUS` bit 0 for a byte or bit 1 for frame
end. If neither appears before the `06F9h` decrement bound, it returns
`A=EEh` with carry set. The no-byte path is 62 Z80 T-states per iteration,
so 1785 iterations take about 30.0 ms at the owner-stated 3.6864 MHz
clock when the wait runs to exhaustion. This is distinct from the 24.69 ms
transmit per-byte wait documented elsewhere. The RX loop resets its bound after
each byte, so `EEh` alone does not distinguish a first-byte timeout from a
later timeout. The ROM begins mode R after its 2 ms START marker; the
trial-10 burst near START+7 ms is therefore **LIKELY** inside the receive
window, but exact RX entry/return times were not instrumented. Do not
misidentify this `EEh` as the W witness's `LINK_STATUS` bit-6 timeout.

Mode G's separate receive-pending gate was tested next as IDs 11/12 below.
The current candidate has only an opening `7Eh` with no payload or closing
flag, so an unchanged RX result does not reject a complete-frame hypothesis.

## Receive-pending-gated silent control and stimulus, IDs 11–12 — 2026-09-23

**CONFIRMED (owner serial report):** the `swap=1` G/S and G/X pair kept
the same candidate and 7 ms delay. Both 30-byte result records have valid
zero-sum checksums:

```text
SYNC
BLACK: DIRECT_TTL; D7 HIGH=idle, LOW=command
READY
TRIAL id=11 mode=G kind=S swap=1 flag=7E stuff=1 close=0 pol=0 phase=-2 lead=5 delay_us=7000 cell_us=122 order=MSB payload=-
RESULT id=11 rom_seq=13 mode=4 err=8 ack_us=2871452436 release_us=2872152440 start_us=2872232476 emit_start_us=0 emit_end_us=0 emit_late_max=0 raw=A55A01040D0008A08080FFFF000000000000000000000000000022002304
READY
TRIAL id=12 mode=G kind=X swap=1 flag=7E stuff=1 close=0 pol=0 phase=-2 lead=5 delay_us=7000 cell_us=122 order=MSB payload=-
RESULT id=12 rom_seq=14 mode=4 err=8 ack_us=2878292156 release_us=2878992156 start_us=2879072192 emit_start_us=2879079000 emit_end_us=2879081088 emit_late_max=3 raw=A55A01040E0008E0C0C0FFFF000000000000000000000000000022002343
READY
```

The silent control's probe/before/after status is A0h/80h/80h; the
stimulated trial's is E0h/C0h/C0h. Each `before` sample precedes its own
optical emission, and each `after` equals its `before`: these between-trial
baseline differences are **not** an observed response to trial 12's burst.
Both trials timed out waiting up to about 100 ms for `LINK_STATUS` bit 4
to become set (ROM wrapper error 8), so neither called `Link_BlockRx`.
The W-only poll fields are FFh/FFh, TX arm field zero, and RX A/F/count/
preview fields zero because RX was not run. Trial 12 reports 3 us maximum
software event lateness. No trial-12 scope capture was supplied; the Uno
output settings match the independently scoped trial-8 swapped burst.

**OPEN:** neither G trial demonstrates controller receive-pending status.
This does not establish the optical LED roles or whether `7Eh` is the
return flag. Earlier controlled experiments found a strong response with
the *unswapped* software-role assignment and little with the swapped one
(`doc/re-notes/ir-wire-protocol.md`, conn10); that response was a timing/
retry effect, not decoded RX data. Therefore the next matched G pair changes
only `swap` to 0 (IDs 13/14 below), keeping candidate, delay, optical
placement and mode fixed.

## Unswapped receive-pending controls, IDs 13–14 — 2026-09-23

**CONFIRMED (owner serial report):** the `swap=0` G/S and G/X pair changed
only the proposed optical channel roles from IDs 11/12. Both 30-byte
feedback records have valid zero-sum checksums:

```text
READY
TRIAL id=13 mode=G kind=S swap=0 flag=7E stuff=1 close=0 pol=0 phase=-2 lead=5 delay_us=7000 cell_us=122 order=MSB payload=-
RESULT id=13 rom_seq=15 mode=4 err=8 ack_us=3212521996 release_us=3213222004 start_us=3213302040 emit_start_us=0 emit_end_us=0 emit_late_max=0 raw=A55A01040F0008A08080FFFF000000000000000000000000000022002302
READY
TRIAL id=14 mode=G kind=X swap=0 flag=7E stuff=1 close=0 pol=0 phase=-2 lead=5 delay_us=7000 cell_us=122 order=MSB payload=-
RESULT id=14 rom_seq=16 mode=4 err=8 ack_us=3221521628 release_us=3222221628 start_us=3222301664 emit_start_us=3222308468 emit_end_us=3222310560 emit_late_max=10 raw=A55A0104100008A08080FFFF000000000000000000000000000022002301
READY
```

Both probe/before/after triples are exactly A0h/80h/80h. Both timed out
waiting for `LINK_STATUS` bit 4 (wrapper error 8), so neither called
`Link_BlockRx`. Trial 13 was silent by design; trial 14 reported 10 us
maximum software event lateness, within the earlier target. No trial-14
scope capture was supplied, so do not claim its physical waveform was
remeasured. This matched pair shows no pending-state change for the
flag-only `7Eh` candidate with `swap=0` either. Earlier conn10 retry
reactions under a different program and timing do not override this direct
pending-gate observation.

**OPEN:** flag-only `7Eh` is not a complete candidate frame. IDs 15/16
below add one `03h` payload byte while keeping mode G, `swap=0`, delay,
phase, stuffing and polarity fixed. That byte is a candidate copied from
earlier response experiments, not a proven return address or acknowledgement.

## Candidate payload controls, IDs 15–16 — 2026-09-23

**CONFIRMED (owner serial report):** the matched silent/stimulated pair
carried `7Eh` plus one candidate `03h` byte, with no closing flag. Both
30-byte result records pass the zero-sum checksum:

```text
TRIAL id=15 mode=G kind=S swap=0 flag=7E stuff=1 close=0 pol=0 phase=-2 lead=5 delay_us=7000 cell_us=122 order=MSB payload=03
RESULT id=15 rom_seq=17 mode=4 err=8 ack_us=3489586108 release_us=3490286116 start_us=3490366152 emit_start_us=0 emit_end_us=0 emit_late_max=0 raw=A55A0104110008E0C0C0FFFF000000000000000000000000000022002340
READY
TRIAL id=16 mode=G kind=X swap=0 flag=7E stuff=1 close=0 pol=0 phase=-2 lead=5 delay_us=7000 cell_us=122 order=MSB payload=03
RESULT id=16 rom_seq=18 mode=4 err=8 ack_us=3500211264 release_us=3500911264 start_us=3500991300 emit_start_us=3500998104 emit_end_us=3501001172 emit_late_max=3 raw=A55A0104120008E0C0C0FFFF00000000000000000000000000002200233F
READY
```

Both probe/before/after triples are `E0h/C0h/C0h`; each `before`
precedes any optical emission, and `after` equals `before`. Both waited
for `LINK_STATUS` bit 4 until wrapper error 8; neither invoked stock RX.
The added byte therefore produced no measured receive-pending response.
Trial 15 emitted nothing by design; trial 16's reported maximum scheduler
lateness is 3 us. **No scope trace was captured for trial 16.** The
software telemetry does not measure D5/D6 edges or light reaching the
handheld. The `7Eh 03h` sequence and clock/data LED identities remain
SUSPECTED. Mode G tests the controller's post-`LinkFinish` pending gate;
it is not equivalent to the running OS receive path.

Trial 17 below repeats the trial-16 stimulus with a scope capture. Trial 15
remains the matched silent control. Earlier conn13 closing-flag tests found
no effect on a different retry-timing metric; they did not test this G-mode
pending gate.

## Scoped candidate-payload repeat, ID 17 — 2026-09-23

**CONFIRMED (owner serial report):** trial 17 repeated the G/X `swap=0`,
`7Eh 03h` candidate without a closing flag. Its 30-byte record passes the
zero-sum checksum:

```text
TRIAL id=17 mode=G kind=X swap=0 flag=7E stuff=1 close=0 pol=0 phase=-2 lead=5 delay_us=7000 cell_us=122 order=MSB payload=03
RESULT id=17 rom_seq=20 mode=4 err=8 ack_us=474918832 release_us=475618840 start_us=475698876 emit_start_us=475705680 emit_end_us=475708748 emit_late_max=3 raw=A55A0104140008E0C0C0FFFF00000000000000000000000000002200233D
READY
```

As in IDs 15/16, probe/before/after are `E0h/C0h/C0h`; the bounded
`LINK_STATUS` bit-4 pending wait expired (wrapper error 8), so stock RX
was not invoked. ROM sequence 20 advanced independently of host ID 17.
Software maximum scheduling lateness is 3 us.

**CONFIRMED (owner Keysight CSV):** `/tmp/IR` was copied to
`analysis/captures/feedback-trial17-keysight.csv`, SHA-256
`088613cc57d8b688ce7adaf8fbeb5316ae29d3865274578fbfb799a33375f1eb`.
At 2.5 us/sample, the decoder sees 21/21 proposed clock pulses on scope
D2 and 8/8 data pulses on scope D3. The sampled candidate cells are
`0111111000000011` (`7Eh 03h`). Clock rise intervals span 117.5–125 us;
clock widths 60–67.5 us; data widths 72.5–77.5 us; data rises 25–32.5 us
before its paired clock. All fall inside the established digital timing
limits. **CONFIRMED (owner):** the scope connections had not changed since
trial 6, so D2 was on Uno D5 and D3 on Uno D6 for trial 17. The CSV thus
verifies the intended digital waveform at those Uno headers. Neither the
CSV nor the error result measures IR light at the handheld detector. The
scoped repeat removes an Arduino edge-timing explanation at D5/D6 but
cannot distinguish wrong optical delivery from wrong receive framing or
a receive-gate mismatch.

## Complemented-wire candidate controls, IDs 18–19 — 2026-09-23

**CONFIRMED (owner serial report):** the matched `swap=0` G/S and G/X
pair kept the logical `7Eh 03h` candidate and `stuff=1`, and changed only
`pol=1` from IDs 15–17. The Arduino complements all built frame bits after
logical stuffing, making physical candidate bytes `81h FCh`. Both 30-byte
records pass their zero-sum checksums:

```text
TRIAL id=18 mode=G kind=S swap=0 flag=7E stuff=1 close=0 pol=1 phase=-2 lead=5 delay_us=7000 cell_us=122 order=MSB payload=03
RESULT id=18 rom_seq=21 mode=4 err=8 ack_us=993839528 release_us=994539532 start_us=994619568 emit_start_us=0 emit_end_us=0 emit_late_max=0 raw=A55A0104150008A08080FFFF0000000000000000000000000000220023FC
READY
TRIAL id=19 mode=G kind=X swap=0 flag=7E stuff=1 close=0 pol=1 phase=-2 lead=5 delay_us=7000 cell_us=122 order=MSB payload=03
RESULT id=19 rom_seq=22 mode=4 err=8 ack_us=1000614652 release_us=1001314656 start_us=1001394692 emit_start_us=1001401496 emit_end_us=1001404568 emit_late_max=3 raw=A55A0104160008A08080FFFF0000000000000000000000000000220023FB
READY
```

Both probe/before/after status triples are `A0h/80h/80h`. The silent
control emitted nothing, while the stimulus reported 3 us maximum
software scheduler lateness. Both timed out at the `LINK_STATUS` bit-4
pending gate (error 8) before stock RX. No trial-19 scope trace was
supplied; `/tmp/IR` still contains the archived trial-17 capture. The
pre-emission baseline changed from the E0h/C0h of IDs 15–17 to A0h/80h
for *both* IDs 18/19. That change is not a measured polarity response.
The matched pair shows no pending-gate response to this complemented
candidate, but does not establish optical delivery or reject the
physical `81h` flag as a receive convention.

**Next:** stop varying the frame inside G for now. G's bounded post-
`LinkFinish` bit-4 gate never opened in IDs 11–19, so stock RX was not
tested by those trials. Matched mode-R IDs 20/21 retain the ID-19 stimulus
settings and compare direct stock RX with and without optical output. Mode R
does not require the pending gate, but its wrapper suppresses partial-byte
evidence when stock RX returns carry. Their results are recorded below.

## Direct stock-RX matched pair, IDs 20–21 — 2026-09-23

**CONFIRMED (owner serial report):** both valid 30-byte records returned
mode 2/error 7 and stock RX `A=EEh`, `F=6Dh` (carry set):

```text
TRIAL id=20 mode=R kind=S swap=0 flag=7E stuff=1 close=0 pol=1 phase=-2 lead=5 delay_us=7000 cell_us=122 order=MSB payload=03
RESULT id=20 rom_seq=23 mode=2 err=7 ack_us=1198247732 release_us=1198547736 start_us=1198627672 emit_start_us=0 emit_end_us=0 emit_late_max=0 raw=A55A0102170007E0C0C0FFFF00EE6D0000000000000000000000220023E2
READY
TRIAL id=21 mode=R kind=X swap=0 flag=7E stuff=1 close=0 pol=1 phase=-2 lead=5 delay_us=7000 cell_us=122 order=MSB payload=03
RESULT id=21 rom_seq=24 mode=2 err=7 ack_us=1207358968 release_us=1207658972 start_us=1207738908 emit_start_us=1207745716 emit_end_us=1207748784 emit_late_max=3 raw=A55A0102180007A080C0FFFF00EE6D000000000000000000000022002361
READY
```

Trial 20 emitted nothing; trial 21 reported 3 us maximum scheduler
lateness. The silent trial's probe/before/after is `E0h/C0h/C0h`;
the stimulated trial's is `A0h/80h/C0h`. In trial 21, `LINK_STATUS`
bit 6 changed from clear in the `before` sample to set in the `after`
sample. These samples bracket the entire stock `Link_BlockRx` call,
including its timeout, so this change is **not yet attributable** to
optical output. The before sample and probe already differed between
the paired runs, before trial 21 emitted anything. Because the wrapper
records DE/preview only on a carry-clear return, their zero values cannot
rule out partial bytes before a later `EEh` timeout. No new trial-21
scope capture was supplied; `/tmp/IR` still held trial 17.

**Rationale for the following control:** compare a late silent/stimulated
mode-R pair, IDs 22/23, with
`delay_us=60000`. If RX times out in its first roughly 30 ms byte-ready
wait, its `after` status sample precedes this stimulus; a rise of
`LINK_STATUS` bit 6 in the late control would show that the bit can rise
without an in-window optical burst. If it does not rise, trial 21's
within-trial change remains only suggestive, because baselines already
differ and the records do not timestamp stock RX's return. Their results
are recorded below.

## Late-stimulus direct-RX control, IDs 22–23 — 2026-09-23

**CONFIRMED (owner serial report):** both 30-byte records pass the
zero-sum checksum, returning mode 2/error 7, stock RX `A=EEh`, `F=6Dh`
(carry set), and identical probe/before/after status `A0h/C0h/C0h`:

```text
BOOT
MODE: FEEDBACK v1, SILENT until explicit T; D5=A D6=B D7=black driver D8=yellow input
BLACK: DIRECT_TTL; D7 HIGH=idle, LOW=command
READY
SYNC
BLACK: DIRECT_TTL; D7 HIGH=idle, LOW=command
READY
TRIAL id=22 mode=R kind=S swap=0 flag=7E stuff=1 close=0 pol=1 phase=-2 lead=5 delay_us=60000 cell_us=122 order=MSB payload=03
RESULT id=22 rom_seq=25 mode=2 err=7 ack_us=17801224 release_us=18101224 start_us=18181184 emit_start_us=0 emit_end_us=0 emit_late_max=0 raw=A55A0102190007A0C0C0FFFF00EE6D000000000000000000000022002320
READY
TRIAL id=23 mode=R kind=X swap=0 flag=7E stuff=1 close=0 pol=1 phase=-2 lead=5 delay_us=60000 cell_us=122 order=MSB payload=03
RESULT id=23 rom_seq=26 mode=2 err=7 ack_us=26478664 release_us=26778672 start_us=26858624 emit_start_us=26918432 emit_end_us=26921496 emit_late_max=9 raw=A55A01021A0007A0C0C0FFFF00EE6D00000000000000000000002200231F
READY
```

Trial 22 emitted nothing. Trial 23's scheduler entered emission at
START+59,808 us, about 192 us before the nominal cell start and roughly
256 us before the first clock edge, and
reported 9 us maximum lateness. Its nonzero emission interval verifies
the Arduino did not cancel the late stimulus. Both trials already had
`LINK_STATUS` bit 6 set in the `before` sample, so their unchanged
`after` samples do **not** test whether bit 6 can rise during stock RX
without an in-window optical stimulus. The pair also supplies no
stimulus-dependent stock RX return. There was no new scope capture;
`/tmp/IR` still held the archived trial-17 CSV. The first-byte
`EEh` no-byte wait is about 30 ms, but this wrapper does not timestamp
the stock RX return or reveal whether earlier partial bytes preceded a
later timeout; `delay_us=60000` is therefore a likely late control, not
a measured guarantee that the burst followed RX.

## Validation and limits

Automated checks execute the assembled ROM with simulated port reads,
exercise the actual Arduino sketch through its serial/feedback interface,
and decode the ROM's yellow output using an independent 1200-baud receiver.
They cover malformed commands, bounds, timeouts, raw RX results, LCD output,
marker timing, UART framing/checksum, and silent/stimulated operation.
The ROM UART cell measured 3067 Z80 T-states against nominal 3072; decoding
also passes at receiver clock offsets of plus/minus 2 percent.

The feedback build and all 13 legacy configurations compile for the Uno.
The direct-TTL silent probe and W witness passed the diagnostic handshake.
Trial 5 identified the emitter timing defect; trials 6 and 8 verified
correctly timed digital stimuli for both proposed channel assignments, but
both W results retained bit-6 timeout. Direct RX controls 9/10 returned the
same `EEh` byte-wait error. G controls 11–19 all timed out waiting for
`LINK_STATUS` bit 4, including the unswapped `7Eh 03h` candidate in 15–17
and its complemented-wire counterpart in 18/19. Trial 17 verified its
candidate at Uno D5/D6. Direct-RX IDs 20/21 both returned `EEh`/carry;
trial 21 alone showed `LINK_STATUS` bit 6 clear before and set after the
stock RX call, with causal interpretation open.
Actual IR reception remains unproven. `7Eh` and the physical
LED roles remain hypotheses. Stock poll bodies and ordering are retained,
but wrapper call overhead, markers and disabled maskable interrupts make
this a diagnostic environment, not an exact replay of the running OS.
