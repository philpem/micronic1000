# Connector experiment — one ROM, outputs and input together

The target is the owner's eight-contact right-side scanner connector. Power
and ground are already known; six contacts remain to be mapped. This image
provides manual port control without the barcode API or background OS code.
It continuously samples `EXTBUS_EDGE` (port `2Dh`) while generating selected
output patterns and showing raw input bytes on the LCD.

**Hardware status:** emulator-tested and first owner hardware trial recorded
2026-09-22: boot, heartbeat, single-press contrast adjustment and an E-selected
waveform on red/pin 1 work. The contact map and input path remain incomplete.
Its power/LCD startup reuses the previously working exerciser sequence. Only ROM00 (`micron1.bin`, DIP1) is replaced; leave ROM01
(`micron2.bin`, DIP2) unchanged. This is a dedicated diagnostic, so the normal
menus do not run. It writes scratch RAM and the RAM NMI vector; retain your
normal procedure for restoring the stock ROM and restarting afterward.

## Image and transfer checks

File:

```text
/home/philpem/Micronic-1000/analysis/rom_exerciser/releases/connector-v1/micron1_connector_v1.bin
```

| Check | Value |
|---|---|
| Size | 32768 bytes |
| MD5 | `261e828ef2008264e58d8d3db08fb86a` |
| Additive 16-bit | `9568` |
| Additive 24-bit | `379568` |
| SHA-256 | `b435f3bc2c6e14e55ed04579063a22231581c22426fd5ed19aba35647fb42f77` |

Both additive checksums mean **sum every unsigned byte**, then mask with
`FFFFh` or `FFFFFFh`. They are not word sums or complemented checksums.
The adjacent JSON manifest records the source and original-ROM hashes too.

Rebuild from the repository root:

```sh
analysis/venv/bin/python analysis/rom_exerciser/connector.py
analysis/venv/bin/python -m pytest -q analysis/test_connector_probe.py
```

The builder refuses any original ROM other than the pinned 32K image.
It redirects the cold-boot entry before OS initialisation and reclaims a
bounded part of the now-unreachable session code. The release regression
compares the exact burn file, manifest and fresh build, so stale artifacts
cannot pass the release check.

## First bench run

You need the handheld, the programmed ROM00 and the scope for the first pass.
The Arduino IR sketch is not needed to identify which connector contacts
respond to the ROM's output controls.

1. Validate the copied image against the checksums above, fit ROM00/DIP1,
   and start the handheld. It enters the diagnostic directly; no ENTER or
   menu selection is needed.
2. Check for `CONNECTOR PROBE 1`, `2A=20 2C=20`, and
   `SEL=2C/01 MODE=S`. The two-digit heartbeat should keep changing.
   Use **NO / YES** for contrast if necessary. The example `2D=FF` below is
   illustrative: the actual resting input byte is a measurement to record.
3. Draw the connector as seen looking into the handheld socket. Mark the
   known power and ground contacts and give the six unknown contacts local
   labels **U1–U6**. These labels are for this experiment; they do not assume
   a standard mini-DIN pin numbering or a view from the cable side.
4. Press and release **R, A, P**. `SEL=2C/01 MODE=P` should appear and `2C`
   should alternate between `20` and `21`. Find any contact carrying the
   corresponding slow waveform. **S** stops it; **L / H** hold its two states
   for voltage measurements.
5. Repeat from **R** for candidates **B** and **C**. Use the table below to
   record each result. **D/E** are additional candidates if needed. A latch
   may control an internal enable instead of appearing directly on a contact;
   record a negative result without treating it as proof of no connection.

At this point report the resting LCD input byte and the contacts that respond
for A/B/C, including low/high voltages and any inversion. If there is no
response, record that along with the displayed output bytes. The gating test
in the longer sequence below is the next useful comparison.

### Output worksheet

Begin each row with **R**, then the candidate key. **L / H** produce the
listed software latch values. Physical voltage/polarity is deliberately blank
until measured. Both complete latch bytes remain visible on the LCD.

| Key | Controlled latch bit | Selected latch at L / H | Contact(s) | Voltage at L / H | Notes |
|---|---|---|---|---|---|
| A | `CTL_LATCH_2C` bit 0 | `20 / 21` | | | |
| B | `CTL_LATCH_2C` bit 1 | `20 / 22` | | | |
| C | `CTL_LATCH_2A` bit 1 | `20 / 22` | | | |
| D | `CTL_LATCH_2A` bit 0 | `20 / 21` | | | |
| E | `CTL_LATCH_2A` bit 4 | `20 / 30` | | | |

For the gated **R, B, SPACE, A, P** experiment, record a separate row: the
complete `2C` output alternates `22 / 23`, with `CTL_LATCH_2C` bit 1 retained
high. Do not mix that result with the reset-baseline A row.

### Input observations

After identifying outputs, use the input procedure below on the remaining
contacts. Record the full `2A` and `2C` output bytes with every observation;
an enable setting may affect the input path.

| Contact | Stimulus / measured voltage | LCD `2A` / `2C` | LCD `2D` | `OR` / `AND` | Changed input mask |
|---|---|---|---|---|---|
| | | | | | |

Within one display interval, `OR XOR AND` identifies input bits that were
sampled in both states. For example, `OR=FF AND=FE` means port `2Dh` bit 0
was sampled both high and low. Constant `2D=FF` alone says nothing about
which contact owns that bit. Start with slow held levels so each state can
be read; brief activity during LCD/key work may be missed.

## Keys

Use the letter printed on the physical key, without MODE or Sun.
Selection initially is A (`2Ch` mask `01h`), **stopped**.

| Key | Action |
|---|---|
| **A** | Select `CTL_LATCH_2C` bit 0 (`2Ch/01h`) |
| **B** | Select `CTL_LATCH_2C` bit 1 (`2Ch/02h`) |
| **C** | Select `CTL_LATCH_2A` bit 1 (`2Ah/02h`) |
| **D** | Select `CTL_LATCH_2A` bit 0 (`2Ah/01h`), additional candidate |
| **E** | Select `CTL_LATCH_2A` bit 4 (`2Ah/10h`), additional candidate |
| **P** | Slow square-wave test, approximately 2 Hz |
| **T** | Faster square-wave test, approximately 25 Hz |
| **L / H** | Hold the selected bit low / high |
| **S** | Stop and restore the selected bit to its baseline |
| **SPACE** | Stop, toggle the selected bit in the retained baseline, and hold it |
| **R** | Stop and reset both complete baseline bytes to `2Ah=20h`, `2Ch=20h` |
| **NO / YES** | Adjust LCD contrast darker / lighter |

Selecting a different output stops the old waveform and restores the old
selection's baseline first. Press and release keys; holding a key does not
repeat its action. Unrecognised keys do nothing.

**P/T rate definition:** each half-cycle contains respectively 50 or 4
sampled dwell loops. A dwell reads the input 184 times and takes about 5 ms
at the owner-stated 3.6864 MHz CPU clock. Keyboard and display work add
jitter and lengthen the nominal periods. These are identifiable diagnostic
waveforms, not precision frequency references. Only the selected mask moves;
other latch bits retain their baseline values.

## LCD

The eight rows are:

```text
CONNECTOR PROBE 1
2A=20 2C=20 2D=FF 01
SEL=2C/01 MODE=S
IN OR=FF AND=FF
A-E:PIN P/T:PULSE
L/H:HOLD S:STOP
SPACE:BASE R:RESET
NO/YES:CONTRAST
```

- `2A` and `2C` are the complete last-written output bytes, mirrored in their
  software shadows. They are not hardware readback.
- `2D` is the latest raw `EXTBUS_EDGE` input byte in hexadecimal.
- The last two digits on row 2 are a rolling display heartbeat.
- `SEL` shows output port/mask, `MODE` is `S`, `P`, `T`, `L` or `H`.
- `OR` and `AND` accumulate input samples during the preceding display
  interval, then reset. A differing bit indicates sampled changes. They do
  not capture pulses occurring entirely during LCD/key work, and do not
  replace the scope for edge timing. Display updates roughly ten times/sec.

## Suggested measurement sequence

1. Reference the scope to known ground and label the six unknown contacts
   on a socket mating-face drawing. Keep the scanner/Arduino outputs
   disconnected during this initial output-observation pass.
2. Press **A, P**. Probe the six contacts for the slow pattern. Try **L/H**
   for voltage measurements and **T** for a faster identifying waveform.
   Record contact, selected mask, full latch bytes, voltage and polarity.
3. Repeat **B**, then **C**. **D/E** are available in the same burn if needed;
   their stock use is coupled, so test them deliberately and record the
   baseline. They are candidate controls, not identified general-purpose
   output pins. IR-selection and power/banking registers are not swept.
4. A negative output result may be gating. To hold `CTL_LATCH_2C` bit 1 high
   while pulsing bit 0, press **R, B, SPACE, A, P**. `2C` now alternates
   `22h/23h`. **S** returns it to `22h`; **R** restores `20h`. This also
   supplies an explicit alternate baseline for input tests if that bit is
   an enable. Every candidate can be retained high through SPACE in this way.
5. Once output contacts and electrical levels are understood, use **S** and
   slowly stimulate one candidate input with an interface appropriate to
   those measured levels. Watch `2D`, `OR` and `AND`. `EXTBUS_EDGE` bit 0 is
   the firmware's scan-timing input; its connector contact remains unknown.
   The display is live in stopped, held and waveform modes, so a waveform
   and input observation can be combined without a second ROM burn.

Keep the input stimulus slow initially so both states are visible. A wire
that mirrors an output is a useful correlation, but confirm direction and
conditioning before making it an Arduino command or feedback channel.
There is no automatic decision that an unknown contact is safe to drive.

## Hardware observations — 2026-09-22

Owner-reported results using connector v1, sum24 `379568`. Contact numbers
and wire colours below are the owner's labels, not an assumed standard DIN
pinout. These are the first physical observations; emulator coverage alone
was previously available.

| Observation | Evidence and interpretation |
|---|---|
| Diagnostic boots; heartbeat advances | CONFIRMED by owner observation. |
| Single YES/NO presses adjust contrast | CONFIRMED by owner observation. |
| **R, E, P** toggles pin 1 / red | CONFIRMED observed correlation with candidate E, `CTL_LATCH_2A` bit 4. Follow-up **R, E, L**, then **H** confirms red follows L=0/H=1 without inversion, and LCD `2A=20h/30h` respectively. **R** returns red low. Owner measured red at **5.6 V** with **R, E, H**; numeric low voltage remains unreported. |
| Pin 3 / orange connects directly to Vcc, with high current | Owner-reported power connection; no numeric current measurement supplied. Treat it as power, not a signal candidate. |
| Black has ESD-diode paths to Vss and Vcc, both about 0.6 V Vf | Owner-reported diode measurements; black returns to 5.1 V when the test resistor is disconnected. They do not yet establish input/output direction. |
| Yellow has an ESD-diode path to Vss, about 0.4 V Vf | Owner-reported diode measurement. Yellow appears high impedance with no defined pull-up/down state; direction and any Vcc-side diode remain unresolved. |
| Other candidates produce no detectable connector change | Owner clarified that the negative result concerns the connector, not the LCD controls. No A/B/C/D contact mapping is established. |
| **R, B, SPACE, A, P** produces no activity change on other contacts | Owner-reported negative result with `CTL_LATCH_2C` bit 1 retained high while its bit 0 pulses. This configuration did not expose another output; it does not establish that those latch bits have no internal function. |
| Input baseline after **R** and the **B, SPACE** comparison | Owner reports `2D=23h`, `OR=23h`, `AND=23h` in both configurations. Port `2Dh` bits 0, 1 and 5 are high; no changes were sampled in the reported display windows. |

**Black pull-down result:** owner reports **0.9 V** with **10 kΩ to ground**,
while LCD `2D` remains **23h**. Removing the resistor restores black to
**5.1 V**. This demonstrates a loaded voltage change without a corresponding
port-`2Dh` change in the tested state; it does not establish black's direction
or the threshold of any connected input.

**Next measurement:** repeat black-to-ground with **1 kΩ**, retaining
**R, B, SPACE** (`2C=22h`), and record contact voltage and `2D`. This checks a
lower level before interpreting the absent input response. Remove the
resistor afterwards and check recovery. Yellow stimulation is still pending.

From baseline `23h`, a change to `22h` means port `2Dh` bit 0 cleared; `21h`
means its bit 1 cleared; `03h` means its bit 5 cleared. Record the complete
byte even if it differs from these examples. `OR`/`AND` can differ briefly
while a display window includes the transition; steady held levels should
subsequently be visible in `2D`. Yellow stimulation is deferred until this
first controlled observation.

## Scope of the image

Interrupts remain disabled and the NMI target is a standalone return.
Keyboard and LCD access are polled. Output masks are deliberately limited
rather than walking power, bank-select, LCD or unknown control bits.
The IR controller is not exercised during mapping. A future combined IR
measurement can use a mapped marker/input once its shared-latch effects are
understood; this ROM does not assume that electrical independence.

## Arduino files and subsequent IR work

Rsync the existing sketch directory, including its `.ino` and README:

```text
/home/philpem/Micronic-1000/analysis/arduino/m1000_ir_probe/
```

The target is **Elegoo Uno R3**, board `arduino:avr:uno`, serial 115200 baud.
All 13 compile-time configurations build with the actual AVR toolchain. The
current default remains `RX_NARROW=1`, content axis 2; the README documents
pins and mode selection. It is an IR experiment sketch, not yet a connector
pin-mapping interface: first establish the six-contact map with the scope,
then choose measured input/output contacts for Arduino feedback.

The IR fixes include absolute phase scheduling, timestamp-ordered edges,
terminal stuffing, malformed-stuffing rejection and reply-window receive
masking. `emit_late_max` reports emitter deadline lateness on the actual Uno.
Scope-check the emitted waveform before interpreting another response sweep.
The repaired stock hooks then distinguish poll completion from actual
received bytes; physical receive framing remains unresolved.

## Reading the assembly

The diagnostic source is `analysis/rom_exerciser/connector.asm`. Its routine
comments describe the intended caller contracts and state transitions:

- `start` bypasses the normal OS, establishes scratch state and initialises
  the display; `main_loop` alternates input sampling and waveform progress.
- `sample_wait` collects raw input and window OR/AND; `reset_samples` starts
  a new display window. Startup, LCD and keyboard work are unsampled gaps.
- `wave_tick` advances the dwell counter. `apply_output` combines the chosen
  bit's current level with the retained baseline of its owning latch.
- `handle_key` changes selection/mode/baseline; `key_scan` maps the polled
  matrix into the ROM's base key codes. Held keys are suppressed until a
  different sampled key code appears; this is not a timed switch-debounce
  filter.
- `display` writes three complete status rows, with explicit padding to
  prevent old characters surviving a shorter field.

The baseline is the output state restored by **S** and by changing selection.
It can differ from `20h` after **SPACE**. **R** explicitly restores both
baseline bytes to `20h`; **L/H/P/T** temporarily override only the selected
bit. This distinction allows one candidate to stay high while another pulses.
