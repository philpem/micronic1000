# Connector experiment — one ROM, outputs and input together

The target is the owner's eight-contact right-side scanner connector. Power
and ground are already known; six contacts remain to be mapped. This image
provides manual port control without the barcode API or background OS code.
It continuously samples `EXTBUS_EDGE` (port `2Dh`) while generating selected
output patterns and showing raw input bytes on the LCD.

**Hardware status:** emulator-tested; this particular image has not yet run
on the physical handheld. Its power/LCD startup reuses the previously working
exerciser sequence. Only ROM00 (`micron1.bin`, DIP1) is replaced; leave ROM01
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
