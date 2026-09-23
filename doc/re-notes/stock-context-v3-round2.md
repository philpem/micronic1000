# Stock-context v3: content comparison and positive-control failure

Status: **Content inference suspended.** The original F7 build produced
34 yellow receive-return markers in round one, but an exact upload of
that binary later produced zero markers. The owner subsequently found
the handheld set to PLINTH rather than V24 ADAPTOR and cannot date
the change; the selected port for earlier negative runs is unverified.
The optical alignment is also owner-reported as critical. Completed
attempts ended with `8000`, "Plinth not connected", then `8040`, "line
failure". No valid frame or successful session has been demonstrated.

The [round-one worksheet](stock-context-v3-round1.md) contains the
ROM identity, wiring and earlier trials. Scope D0/D1 observed handheld
data/clock; D2/D3 observed Uno clock/data; D4 observed yellow. Yellow
was connected to Arduino D8, with black still on undriven D7. The
scope used an 80-ms window, left horizontal reference, DIG1 rising
trigger and 128-segment configuration for these handheld runs.

## Captures

| Run | Emitted content | Arduino log | Scope segments | Yellow lows |
|---|---|---:|---:|---:|
| C1 | Open `7E` + stuffed `03` | 100 full bursts, 2 short fragments, 34 replies | 100 handheld, 34 Uno | 0 |
| C2 | Open `7E` + stuffed `00 00 FF FF 96` | 100 full bursts, 34 replies | 100 handheld, 34 Uno | 0 |
| C0 | Open `7E` + stuffed type-2 candidate `00 07 00 02 01 43 00 00 02 01` | 100 full bursts, 34 replies | 100 handheld, 34 Uno | 0 |
| C0b | Exact archived F7 binary, same type-2 candidate | 100 full bursts, 34 replies | 100 handheld, 34 Uno | 0 |
| C0c | Exact F7 binary; PLINTH selected; LEDs adjusted near the top V24 window | 100 full bursts, 34 replies | 100 handheld, 34 Uno | 8 |
| C0d | Exact F7 binary; LEDs adjusted, series resistors bypassed, lab 5 V connected to USB-connected Uno before run; port choice unconfirmed | 100 full bursts, 33 replies | 100 handheld, 33 Uno | 0 |
| C0e | Exact F7 binary; owner restored series resistors and removed lab +5 V, confirmed V24 ADAPTOR | 100 full bursts, 34 replies | 100 handheld; D2/D3 output trace abnormal | 0 |
| C0f | Exact F7 binary; owner swept optical alignment during a V24 attempt | 100 full bursts, 34 replies | 100 handheld, 34 complete Uno output segments | 0 |

The first four runs requested and achieved 33-ms replies after every third
full handheld burst. The Arduino reported no yellow event or event
drop. The scope independently placed output at 33.00–33.04 ms after
the last handheld clock rise. C0 and C0b both emitted 93 Uno clock
cells per reply, matching F7's earlier scope count; C2 emitted 56.
The instrument measured 97.7 kSa/s after each acquisition, and each
2,000-row segment exports at 40 us/row. This resolves the roughly
916-us return marker and millisecond placement, not bit-edge setup.

The corresponding startup banners and live serial logs are
`analysis/captures/stock-v3-r2-c*-idle-uno.jsonl` and
`analysis/captures/stock-v3-r2-c*-handheld-20260923.jsonl`. Scope CSVs
are committed as the matching `*-keysight.csv.gz` files. C0b used
the archived `.cache/ir-arduino/pr25-f7-sparse33` binary verified on
upload, rather than recompiling the current sketch. Its startup
banner reports the original automatic stuffing selection, and sent
burst reports show `wire_stuff=1` and the original ten-byte payload.

## Correction to round-one inferences

CONFIRMED: F7's original run had 34 yellow lows in 34 reply segments.
CONFIRMED: the exact F7 binary repeat had zero yellow lows in 34 reply
segments. Its gross output length and 33-ms placement match F7 on
the saved scope exports. The cause of the difference is OPEN; the
scope's 40-us export grid does not rule out finer electrical or
optical differences.

Discard the earlier causal claims that changing the opening flag,
stuffing mode, or closing flag removed the return marker. Those runs
did have zero markers, but the nominal positive control was no longer
positive when repeated, and the handheld port choice for these runs
is unverified. C1 and C2 likewise cannot distinguish content until
the positive control reproduces in the same conditions.

## Yellow path and hardware changes

The verified LISTEN_ONLY build and a passive Arduino logger were armed
for a handheld off/on. The owner reported a backup-battery-low warning,
then a warm start through the comms error to the Load/Run screen. The
Arduino log contains no yellow pulse. The scope was armed for a D4
falling edge, but no captured waveform established a trigger; its
sample-rate readback after stopping may have been stale.

The owner then coldstarted the handheld. The Arduino logged a
3,636-us yellow low, and a newly triggered 20-MSa/s scope acquisition
independently showed 146 low D4 export rows at 25 us/row, a 3.625-ms
sampled span. The owner saw TESTING, then the main menu and Load/Run
screen. This confirms the yellow/D8/D4 measurement path worked for
that initialization event; it does not prove optical reply reception.
The owner confirms yellow remained connected to both D8 and D4 and
the LEDs faced the top V24 window, but reports alignment is critical.
The coldstart can reset the handheld's link selection to PLINTH, and
the owner later found PLINTH selected. The time of the change is
unknown.

An exact F7-binary repeat after LED adjustment (C0c) recorded eight
916–924-us yellow lows in its first eight reply segments, then none
in the remaining 26 replies. Scope data confirm 100 handheld bursts,
34 Uno output segments and eight yellow-low segments. The owner found
PLINTH selected for that attempt. Another exact-binary run (C0d)
recorded 100 bursts, 33 replies and no yellow low; the scope
independently showed 100 handheld and 33 Uno-output segments. Before C0d, the
owner adjusted the LEDs, bypassed their series resistors and connected
the Arduino to a lab 5-V supply while USB remained connected. The LED
current was then described as limited by the ATmega328P's maximum
`I_OH`, but that datasheet figure is a rating, not a current-limiting
element. The external supply fed the Arduino 5-V terminal directly
while USB was connected. Further transmitting runs are paused until
the series resistors and a defined power arrangement are restored.
The handheld port choice for C0d remains unconfirmed.
These observations keep geometry, drive circuit, supply and port
choice open as confounders; none is proven as the sole cause.

The owner then restored the original 220-ohm series resistor for each
LED and removed lab +5 V from the USB-connected Uno. The exact F7 binary in C0e was
run with V24 ADAPTOR selected, and the owner reports that useful LED
alignment changes within only a few millimetres. The Arduino logged
100 handheld bursts, 34 replies and zero yellow lows; the owner saw
`8000` then `8040`. The scope shows all 100 handheld triggers, but
the expected Uno D2/D3 waveform is abnormal: no D3 data rises and
only 1–4 D2 clock rises in 31 segments, rather than the earlier
93 D2 rises per complete reply. The owner explains the missing digital
highs as the LED forward voltage holding the MSO digital inputs below
their threshold when the series resistors were bypassed. This is an
owner-supplied explanation for the scope symptom. The recorded C0e
sequence places resistor restoration before this capture, so the exact
transition that produced its trace remains unclear; no protocol or
optical conclusion follows from the missing digital highs.

An Arduino-only free-running output check was then run with the
restored current-limited wiring and no handheld action. Each of four
scope segments has 88 D2 clock rises and 16 D3 data rises, at a
measured 5 MSa/s acquisition rate and 25-us CSV spacing. That
argues against a permanently failed D5/D6 output. The Uno was restored
to LISTEN_ONLY afterward.

Before another content trial, explicitly select V24 ADAPTOR and sweep
the LED alignment over the owner's reported few-millimetre range.
Reproduce a positive type-2 yellow return, then hold that position
fixed and interleave a content variant. If the control stays negative,
do not attribute the result to payload bytes.

C0f performed that sweep. The archived F7 binary logged 100 handheld
bursts, 34 replies and no yellow event. The 100-segment scope export
independently shows 34 output segments with D2 and D3 activity and no
D4 low sample. The acquisition reported 97.7 kSa/s and exported at
40 us/row, sufficient to distinguish the earlier roughly 920-us
yellow lows. The owner again saw `8000` then `8040`. Optical reception
has therefore not been re-established, and content inference remains
suspended. The owner then requested a continuous two-channel IR output
to check the handheld's receiver. A verified FREE_TX build was uploaded;
its USB reports show a repeated type-2 candidate burst every 250 ms on
D5 clock and D6 data. Its free-running phase setting is -2/8 cell,
distinct from F7's paced +2/8 cell. The owner reports that this IR
reaches the handheld and that alignment is less critical than first
thought. The means of observing reception has not yet been recorded;
this statement establishes neither payload decoding nor acceptance.
A 10-second USB log during the check contains 41 free-running
transmit reports, 50 handheld bursts and no yellow event. The owner
has not yet reported what the handheld displayed during this check.
