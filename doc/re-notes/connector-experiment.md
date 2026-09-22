# Connector experiment — outputs and input together

The target is the owner's eight-contact right-side scanner connector. Power
and ground were already known at the start; six contacts required mapping. This image
provides manual port control without the barcode API or background OS code.
It continuously samples `EXTBUS_EDGE` (port `2Dh`) while generating selected
output patterns and showing raw input bytes on the LCD.

**Current image: connector v2.** It adds **F** to control `CTL_LATCH_2C`
bit 5, a state that v1 held high even though stock barcode setup clears it.
All other controls and reset baselines are retained. V1 is preserved for
reproducing the measurements below.

**Hardware status:** v1 boots on the owner's handheld, with heartbeat,
contrast and a non-inverted output on red/pin 1 established. The owner has
now mapped black to input port `2Dh` bit 0 with v2: at `2A=22h` and
`2C=00h` or `02h`, black high/released reads `23h`, black low reads `22h`
(CONFIRMED: owner measurements). Yellow now maps to `2Ah` bit 0 with
sink/release behaviour, as detailed below; its scanner-side purpose remains
unknown. Only ROM00
(`micron1.bin`, DIP1) is replaced; leave ROM01 (`micron2.bin`, DIP2)
unchanged. This dedicated diagnostic does not run normal menus. It writes
scratch RAM and the RAM NMI vector; use the normal stock-ROM restoration
and restart procedure afterwards.

## Image and transfer checks

File:

```text
/home/philpem/Micronic-1000/analysis/rom_exerciser/releases/connector-v2/micron1_connector_v2.bin
```

| Check | Value |
|---|---|
| Size | 32768 bytes |
| MD5 | `68f303e274b7d7d80e43b7e07c5b1176` |
| Additive 16-bit | `9429` |
| Additive 24-bit | `379429` |
| SHA-256 | `db5be1c812865b63e23071ff614870045134148bec3abe9ffcaa02351e38af30` |

Both additive checksums mean **sum every unsigned byte**, then mask with
`FFFFh` or `FFFFFFh`. They are not word sums or complemented checksums.
The adjacent JSON manifest records the source and original-ROM hashes too.

Rebuild from the repository root:

```sh
analysis/venv/bin/python analysis/rom_exerciser/connector.py --version 2
analysis/venv/bin/python -m pytest -q analysis/test_connector_probe.py
```

The builder refuses any original ROM other than the pinned 32K image.
It redirects the cold-boot entry before OS initialisation and reclaims a
bounded part of the now-unreachable session code. The release regression
compares the exact burn file, manifest and fresh build, so stale artifacts
cannot pass the release check.

### V1 archive

The existing v1 file remains at
`analysis/rom_exerciser/releases/connector-v1/micron1_connector_v1.bin`:
MD5 `261e828ef2008264e58d8d3db08fb86a`, sum16 `9568`, sum24 `379568`.
`connector.py` without `--version 2` still builds v1 for reproducibility.
V1's assembly and published binary/manifest are unchanged.

## V2: test the missing barcode configuration

1. After burning v2, check the banner says **CONNECTOR PROBE 2**.
2. Press and release **R, F, SPACE, B, SPACE**. Check **`2A=20`, `2C=02`**.
   This retains `CTL_LATCH_2C` bit 5 low and its bit 1 high, matching those
   two stock presence-probe control bits. It does not reproduce the whole
   stock API or establish either bit's electrical gating function.
3. Record idle `2D`/`OR`/`AND`. Repeat the black released / 500 Ω-to-ground
   comparison, checking actual contact voltage and the complete input byte.
4. Release black. Repeat yellow through 10 kΩ to ground and then separately
   through 10 kΩ to orange/Vcc, recording contact voltage and input byte.
5. To compare C high, press **C, SPACE** without resetting. The bytes should
   now be **`2A=22`, `2C=02`**. Repeat the same input comparisons.

**R restores `2C=20`, including bit 5 high.** After any R, repeat the full
F/SPACE/B/SPACE setup before interpreting a bit-5-low test. Use **F, SPACE**
to retain the low baseline: **F, L** only forces it low temporarily and
switching candidates restores its saved baseline.

Additional comparisons in the same burn:

| Sequence | `2A` | `2C` | Purpose |
|---|---|---|---|
| **R, F, SPACE** | `20` | `00` | `2Ch` bit 5 low, `2Ch` bit 1 low |
| **R, F, SPACE, B, SPACE** | `20` | `02` | `2Ch` bit 5 low, `2Ch` bit 1 high |
| **R, F, SPACE, B, SPACE, C, SPACE** | `22` | `02` | Also set `2Ah` bit 1 |

These are controlled comparisons. Even negative results do not establish
that a contact is unconnected or that the connector carries no other input.

## First bench run

You need the handheld, the programmed ROM00 and the scope for the first pass.
The Arduino IR sketch is not needed to identify which connector contacts
respond to the ROM's output controls.

1. Validate the copied image against the checksums above, fit ROM00/DIP1,
   and start the handheld. It enters the diagnostic directly; no ENTER or
   menu selection is needed.
2. Check for `CONNECTOR PROBE 2`, `2A=20 2C=20`, and
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
| **F** | Select `CTL_LATCH_2C` bit 5 (`2Ch/20h`), v2 only |
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
CONNECTOR PROBE 2
2A=20 2C=20 2D=FF 01
SEL=2C/01 MODE=S
IN OR=FF AND=FF
A-F:PIN P/T:PULSE
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

**Stronger pull-down:** owner used **500 Ω** and measured **0.056 V**, still
with `2D=23h`. The contact is near ground, so inadequate pull-down is no
longer a useful explanation for this negative result. Gating, a different
input path or another contact function remain unresolved.

### Input-configuration gap in connector v1

**CONFIRMED, fresh stock listing:** common barcode setup clears
`CTL_LATCH_2C` bit 5 at `ROM00:1229–1231`, and clears `CTL_LATCH_2A` bit 1 at
`ROM00:1233–123B`. A selector-specific branch sets `CTL_LATCH_2A` bit 1 at
`ROM00:1242–124A`; that branch skips the other route's direct presence probe.
The presence-probe route raises `CTL_LATCH_2C` bit 1 at `ROM00:128A–1292`,
then reads port `2Dh` at `ROM00:1299`.

Connector v1 resets `2Ch=20h` and exposes only `2Ch` masks `01h/02h`, so
**it cannot clear `CTL_LATCH_2C` bit 5**. Every test so far retained that bit
high. The diagnostic deliberately preserved the IR-selection state, but that
also prevents reproducing this part of the stock barcode configuration.
Whether that bit gates this connector input is **SUSPECTED**: the decisive
comparison requires its low state. No v1 key sequence produces it. V2 now
adds that control as candidate F; the comparison remains to be performed.

**V1 comparisons performed:** change `CTL_LATCH_2A` bit 1,
with `CTL_LATCH_2C` bit 1 low and high. This is a mode comparison, not a
claim that candidate C is an input enable.

| Key sequence | Expected `2A` | Expected `2C` |
|---|---|---|
| **R, C, SPACE** | `22` | `20` |
| **R, B, SPACE, C, SPACE** | `22` | `22` |

**Owner's C-high results:** **R, C, SPACE** gives `2D=OR=AND=20h`.
**R, B, SPACE, C, SPACE** gives `2A=22h`, `2C=22h`, `2D=20h`. The owner confirms
black was **released** for both readings, making `20h` the C-high idle
baseline. Port `2Dh` bits 0 and 1 are low; this does not yet establish a
black-contact input response.

**Owner's grounded-black follow-up:** black grounded also gives
`2A=22h`, `2C=20h`, `2D=20h` after **R, C, SPACE**, and
`2A=22h`, `2C=22h`, `2D=20h` after **R, B, SPACE, C, SPACE**. Thus the
C-high released and grounded results agree in both B states. C changes the
idle readback, but these tests have not shown a black-contact response.
The untested `CTL_LATCH_2C`-bit-5-clear state remains a limitation.

**Owner's yellow result:** after **R, B, SPACE**, yellow connected to
blue/ground measures **0 V**, and yellow connected to orange/Vcc measures
**5.3 V**. `2D=23h` in both cases. Blue is the owner's identified ground
contact. This test was requested with 10 kΩ, one resistor path at a time;
no yellow input response was observed under the v1 baseline.

**Next comparison:** clear `CTL_LATCH_2C` bit 5 and repeat the held-level
input tests. V1 cannot do this. V2 adds candidate F for that
specific bit; the previous results remain valid observations of v1's
bit-5-high configurations, not a complete test of the barcode input path.

From baseline `23h`, a change to `22h` means port `2Dh` bit 0 cleared; `21h`
means its bit 1 cleared; `03h` means its bit 5 cleared. Record the complete
byte even if it differs from these examples. `OR`/`AND` can differ briefly
while a display window includes the transition; steady held levels should
subsequently be visible in `2D`. The next comparison changes the previously fixed control state.

## V2 hardware observations — 2026-09-22

The owner reports **R, F, SPACE, B, SPACE** gives **`2A=20h`, `2C=02h`,
`2D=23h`**. Taking black and yellow high/low does not change `2D`. Numeric
pin voltages for this v2 run were not supplied. This tests
`CTL_LATCH_2C` bit 5 low with its bit 1 high and `CTL_LATCH_2A` bit 1 low;
that state alone has not exposed either contact as a readable input.

**C-high result:** pressing **C, SPACE** gives **`2A=22h`, `2C=02h`,
`2D=23h`**. Pulling black low changes `2D` to **`22h`**. Yellow high/low
still causes no observed change.

**B-low result:** then **B, SPACE** gives **`2A=22h`, `2C=00h`**. Black
floating or high reads **`2D=23h`**; black low reads **`2D=22h`**.

**CONFIRMED (owner measurements):** black controls port `2Dh` bit 0
without inversion in both tested `2A=22h`, `2C=00h/02h` configurations.
`CTL_LATCH_2C` bit 1 need not be high for this response. These observations
establish configuration-dependent visibility, not the internal gate topology
or behaviour under arbitrary other latch values. No numeric pin voltages
were supplied for these v2 comparisons.

| ROM | `2A` | `2C` | `2D`, black released/high | `2D`, black low |
|---|---|---|---|---|
| v1 | `20` | `22` | `23` | `23` |
| v1 | `22` | `20` | `20` | `20` |
| v1 | `22` | `22` | `20` | `20` |
| v2 | `20` | `02` | `23` | `23` |
| v2 | `22` | `02` | `23` | `22` |
| v2 | `22` | `00` | `23` | `22` |

**C-low follow-up:** the owner then pressed **C, SPACE** and reported
`2A=2-`, `2C=00`, `2D=23`, with grounding black producing no change.
The sequence should produce `2A=20h`; the literal `2-` report is retained
as an ambiguous transcription, not a verified complete output byte.

**Simultaneous output and input (CONFIRMED: owner measurements):**
**C, SPACE** restores `2A=22h`, `2C=00h`. **E, P** pulses red with an
approximately **400 ms period**. With black grounded, `2D=22h` remains
constant under **E/P**, **E/L** and **E/H**. The low input state therefore
remains readable with the output pulsing or held in either state. This is
an observed period for this run, not a precision timing specification.

**Released-input follow-up (CONFIRMED: owner measurements):** released
black reads **`2D=23h` throughout E/P, E/L and E/H**. Both held input levels
therefore remain distinguishable across all three tested red-output modes.

| Red output mode | `2D`, black released | `2D`, black grounded |
|---|---|---|
| E/P, approximately 400 ms period | `23` | `22` |
| E/L, held low | `23` | `22` |
| E/H, held high | `23` | `22` |

This establishes a candidate pair for Arduino feedback: red/pin 1 carries
handheld output, and black supplies handheld input via port `2Dh` bit 0.
To reproduce from reset, use **R, F, SPACE, C, SPACE**, verify `2A=22h`,
`2C=00h`, then **E, P** (or E/L, E/H). No further burn is needed for this
connector-only comparison.

**Next:** integrate the mapped pair with the Arduino after choosing the
electrical interface from the measured voltage levels. Then measure usable
pulse timing and check coexistence with IR operation. The standalone test
does not establish short-pulse capture, arbitrary-state independence or
compatibility with the latch states used by the IR controller.

Yellow is mapped below. The remaining contacts are owner-identified as
**pin 2 brown, pin 4 violet and pin 7 green**; their functions remain
unknown. Brown's first negative tests are recorded below.

## Yellow: sink/release output and remaining tests

**Black's observed working condition:** `CTL_LATCH_2A` bit 1 high and
`CTL_LATCH_2C` bit 5 low. `CTL_LATCH_2C` bit 1 can be low or high; red's
`CTL_LATCH_2A` bit 4 can be low, high or pulsing. These are bench conditions,
not a determination of the internal gate circuit. **R, F, SPACE, C, SPACE**
reaches the tested `2A=22h`, `2C=00h` baseline.

**CONFIRMED (owner measurements): yellow responds to `CTL_LATCH_2A` bit 0**
with `CTL_LATCH_2C=00h`, `CTL_LATCH_2A` bit 1 high and its bit 4 low.
With a 10 kΩ pull-up to orange/Vcc, D/P produces a yellow waveform with
approximately 400 ms period while `2A` alternates `22h/23h`. The owner
then reports **H pulls yellow low, L floats it**:

| Command | `2A` | `2C` | Yellow behaviour |
|---|---|---|---|
| D/L | `22` | `00` | Released/floating; external resistor sets voltage |
| D/H | `23` | `00` | Pulled low |
| D/P | `22/23` | `00` | Alternates release/sink, approximately 400 ms period |

This is an active-low, sink/release output in the tested configuration.
Open-collector/open-drain topology is **SUSPECTED**, not established by
these observations alone; an equivalent switched or tri-stated driver is
not excluded. The scanner-side purpose and numeric held output voltages
remain unreported. Earlier held-level tests alone did not establish this
output behaviour.

1. **Input comparison:** reset/setup with **R, F, SPACE, C, SPACE**;
   verify `2A=22h`, `2C=00h` and leave black released. Pull yellow through
   **10 kΩ** to blue/GND, then separately through **10 kΩ** to orange/Vcc.
   **Completed (CONFIRMED: owner measurements):** yellow measures **0 V**
   with the ground connection and **5.22 V** with the Vcc connection;
   **`2D=OR=AND=23h` in both cases**. No held-level response was observed
   through port `2Dh` in this configuration. This does not rule out
   an input under other conditions.
2. **Output comparison:** leave a **10 kΩ pull-up** from yellow to
   orange/Vcc, observe yellow on the scope, then **D, P**. Candidate D
   controls `CTL_LATCH_2A` bit 0; expect `2A=22h/23h`, `2C=00h`.
   **Completed:** the waveform and sink/release polarity are recorded
   above. **D, L** and **D, H** still allow numeric held voltage measurements.
3. **Pull-down check completed (CONFIRMED: owner measurements):** with
   the 10 kΩ resistor moved from orange/Vcc to blue/GND, yellow remains
   **near 0 V in both D/L and D/H**. This supports release rather than
   high drive in L under this load. Exact voltages were not supplied;
   no transistor topology is established.
4. **Other red baseline completed (CONFIRMED: owner observation):**
   after an accidental reset, the owner restored the 10 kΩ pull-up and
   used **R, F, SPACE, C, SPACE, E, SPACE, D, P**. In response to the
   requested `2A=32h/33h`, `2C=00h` test, the owner confirms yellow again
   produces the approximately 400 ms waveform with red held high.
   Yellow therefore pulses with red retained either low or high in the
   tested configurations; general independence is not established.
5. **Black input during yellow output (CONFIRMED: owner observations):**
   during the requested yellow-pulsing test with red retained high, black
   floats high when released; grounded black gives **`2D=22h` steadily**.
   The owner subsequently confirms **`2D=23h` steadily when black is
   released**. Both held input states therefore remain distinguishable
   throughout yellow pulsing with red retained high. Numeric released
   voltage was not supplied for this run. Short-pulse capture and combined
   IR operation remain untested.

The pull-up tests a specific blind spot: an open-drain output can release
its pin instead of driving high, so an external resistor supplies the high
state ([TI, pull-up/pull-down selection](https://www.ti.com/lit/an/slva485/slva485.pdf)).
The owner's sink/release observation is consistent with that behaviour,
but does not identify the internal transistor circuit. The pull-down
comparison tests for drive in the opposite direction.

**CONFIRMED, fresh stock listing:** ROM00:1537–1541 sets `CTL_LATCH_2A`
bit 0 while clearing its bit 4; ROM00:1548–1550 subsequently sets its bit 4.
ROM00:14E8–14F2 sets that latch's bit 4 while clearing its bit 0. This makes
candidate D worth testing alongside the physically mapped E output; none
of these bytes identifies yellow or establishes a scanner-side purpose.
Tracing yellow's PCB connection or observing a working scanner would help
establish the electrical circuit or scanner-side purpose; neither follows
from the output-bit mapping alone.

## Interpreting the scanner controls

The owner identifies **black as pin 5** and proposes black=data,
red=scanner enable, yellow=power control/scan trigger. Brown/pin 2 has no
observed input effect in the requested 22h/00h and 20h/02h comparisons;
its unloaded voltage is near zero with AC hum. These are owner observations.
Brown appearing floating is **SUSPECTED**, not proof of an unused contact
or absence of every possible bias path. Exact driven voltages and input
bytes were not supplied for brown.

**Black/pin 5 as barcode data is CONFIRMED by the combined evidence:**
the owner mapped black to `EXTBUS_EDGE` bit 0, and the stock capture loop
reads precisely that bit at ROM00:13CB–13CD and 13ED–13F2 to time signal
levels before passing widths to the decoder. This identifies a barcode
level/timing input; actual scanner waveforms have not yet been captured.

The selector-`2Ah` control sequence provides a useful distinction between
red and yellow. The saved selector is a device-route value, not a port read
or the input-classification result. Fresh listing at ROM00:1500–1505 selects
this branch; ROM00:12FF calls it before reading the data input at 1302.

| Stage | `CTL_LATCH_2A` bit 0 / yellow | `CTL_LATCH_2A` bit 4 / red | Evidence |
|---|---|---|---|
| Stop/deassert state | Clear: released | Set: high | ROM00:14E8–14F2 |
| Begin activation | Set: sinks low | Clear: low | ROM00:1537–1541 |
| After startup delay | Remains set: sinks low | Set: high | ROM00:1543–1550 |
| Later stop/deassert | Clear: released | Remains set: high | ROM00:14DE–14F5 |

The startup red-low interval is approximately **7.65 ms**, calculated from
ROM00:35CE's delay loop and intervening instructions at the owner-stated
3.6864 MHz clock, assuming no wait states (28,218 T-states between output
writes). This is a calculated stock-ROM interval, not the diagnostic's
measured approximately 400 ms waveform period. Yellow is not released by
the end of this short red pulse; the deassert routine releases it later.
The polling path can call that routine at ROM00:130B and 134E;
ROM00:14C8–14D6 also schedules it as a delayed callback.

**SUSPECTED roles, consistent with that sequence:**

- Yellow is a sustained active-low scan enable/trigger or a power-control
  signal. Its assertion at activation and release at stop fit the owner's
  power/scan hypothesis. They do not distinguish a logic enable from an
  actual supply/return switch.
- Red is a startup pulse, potentially trigger/reset or temporary inhibit.
  A simple level-held enable is a weaker fit: red is high both after the
  startup pulse and in the deasserted state. The existing tests also show
  red is not required to gate black's input in the tested configurations.

The recorded yellow test used a 10 kΩ pull-up, demonstrating only about
0.5 mA of load. The owner's high-current description has no quantified
current or transistor identification in this record; high-current capacity
must not become evidence for power switching without that measurement.
Open-drain-like behaviour alone does not resolve the role: dedicated
active-low trigger inputs also exist (for example the unrelated modern
[Zebex Z-5212 Plus manual, pin definition](https://www.zebex.com/uploads/files/Z-5212_Plus/Z-5212_Plus_UserManual.pdf)).
That example establishes plausibility only, not a Micronic pin assignment.

**Discriminating observations:** trace yellow's driver and the original
scanner connection, or observe scanner supply current/illumination while
holding yellow asserted with red high, then applying the short red-low
pulse. A supply/return connection supports power switching; an already
powered scanner starting acquisition supports a control/trigger role.
Capture black at the same time to relate the control sequence to data.
Without the original scanner, retain the measured signal names and test
violet/4 and green/7 next; brown's negative result is not an NC assignment.

## Remaining contacts: brown 2, violet 4, green 7

**CONFIRMED (owner-supplied numbering/colours):** the three remaining
contacts are pin 2 brown, pin 4 violet and pin 7 green. These are the
owner's connector labels, not an assumed standard mini-DIN pinout. No
physical contact can yet be assigned to the candidates below.

| Register candidate | CONFIRMED ROM mechanics, freshly checked | Physical interpretation |
|---|---|---|
| `EXTBUS_EDGE` / `2Dh` bit 1 | ROM00:1299–12A9 first tests `2Dh` bit 0. If clear, it tests `2Dh` bit 1 and selects software class 1 when set or class 2 when clear. | Strongest remaining input candidate; a connector presence/type signal is SUSPECTED. It could instead be internal status. |
| `CTL_LATCH_2C` / `2Ch` bit 0, key A | ROM00:1511–1528 sets then clears this bit around a delay, after setting `2Ch` bit 1. | A further connector output is SUSPECTED; the register pulse does not establish physical routing. |
| `CTL_LATCH_2C` / `2Ch` bit 1, key B | ROM00:127B–1292 clears then sets it before the input probe; ROM00:1507–150F sets it before the bit-0 pulse. | Another output/control candidate, but an internal enable is equally unresolved. |

The probe and `2Ch` pulse are on the route where the saved selector is
not `2Ah`. ROM00:1233–124A leaves `CTL_LATCH_2A` bit 1 clear on that route;
the selector-`2Ah` route sets it and bypasses the two-input classification
at ROM00:1269–1278. This argues for testing both control states, not for
assuming another contact must follow black's observed gate conditions.
The inspected capture loop uses only `2Dh` bit 0 (ROM00:13CB–13CD and
13ED–13EF); it supplies no evidence for a separate barcode clock pin.
The displayed `2Dh` bit 5 being high is not a physical pin assignment.

Suggested tests, one contact at a time:

1. Measure unloaded voltage, then compare the contact through 10 kΩ to
   ground and separately through 10 kΩ to Vcc. Begin at **R, F, SPACE,
   C, SPACE** (`2A=22h`, `2C=00h`), with black released and yellow stopped.
   Record voltage and full `2D`/OR/AND. If only `2Dh` bit 1 clears from
   `23h`, the result is `21h`; do not require that particular result.
2. If no response, repeat at **R, F, SPACE, B, SPACE** (`2A=20h`,
   `2C=02h`), which matches the inspected probe's relevant control bits.
   The diagnostic continuously reads the full `2Dh` byte, so the stock
   code's bit-0 test does not prevent observing bit 1 here.
3. For output candidates, scope each contact with a 10 kΩ pull-up, then
   if necessary a pull-down. **R, F, SPACE, B, SPACE, A, P** gives
   `2A=20h`, `2C=02h/03h` (A pulses with B retained high).
   **R, F, SPACE, B, P** gives `2A=20h`, `2C=00h/02h` (B pulses).
   Repeat with C/SPACE included before selecting the pulsed candidate
   to compare `2A=22h`. Record complete output bytes for every run.

These are **SUSPECTED contact links**, not a three-pin/three-bit mapping.
A negative result could reflect internal routing, different gating or an
unused contact. Firmware alone cannot choose among brown, violet and green;
held-level or waveform correlation, or PCB continuity, is required.

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
pin-mapping interface. Red and black now provide a tested output/input pair
for developing Arduino feedback; electrical interfacing, timing and combined
IR operation remain to be implemented and checked.

The IR fixes include absolute phase scheduling, timestamp-ordered edges,
terminal stuffing, malformed-stuffing rejection and reply-window receive
masking. `emit_late_max` reports emitter deadline lateness on the actual Uno.
Scope-check the emitted waveform before interpreting another response sweep.
The repaired stock hooks then distinguish poll completion from actual
received bytes; physical receive framing remains unresolved.

## Reading the assembly

The current source is `analysis/rom_exerciser/connector_v2.asm`;
`connector.asm` preserves v1. Their routine
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
