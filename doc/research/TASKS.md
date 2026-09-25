# Task list — Micronic 1000 reverse-engineering

State: continuously updated as work progresses.

> Historical session log: see [`session-log.md`](session-log.md).

## IR review follow-up — 2026-09-24

The [v4 handover and test plan](../re-notes/stock-context-v4-handover.md)
is ready for the next agent. Review fixes: callback-memory regression
repaired; reset/resume and BDOS reset routes covered; diagnostic boot
identity added; raw stock receive A/F displayed after the first return;
exact F7 and silent HEX artifacts archived. 69 project-environment tests
pass, and the canonical accelerated boot reaches Main Menu.

Pending: owner installs the new ROM, confirms physical coldstart and
5.45-ms boot witness, then matched silent/F7 V24 trials. No hardware
interaction occurred during preparation; last verified Uno state remains
LISTEN_ONLY. F7's earlier 34 carry-set markers are useful evidence, but
return framing is not confirmed. Optical arrival is owner-confirmed;
no more internal probing or alignment sweeps are requested.

## Low-power standby / wake — 2026-09-24

* **Matrix scan is 6 columns.** The normal keyboard scan drives COLUMNS
  on `KBD_DRIVE` bits 0-5, one at a time, and senses ROWS on `KBD_SENSE`
  (io:0000, low 6 bits). The Kbd_ScanMain loop uses a column counter
  `B=06h` with a mask stepped by `SLA` from `01h` → `02h` → `04h` →
  `08h` → `10h` → `20h` (ROM00:190D-1920), and reads rows as `AND 3Fh`;
  the key index is `row*6+col`. `3Fh` = drive all 6 columns at once
  (the `Kbd_SenseAllColumns` prescan, ROM00:1A42-1A51). CONFIRMED.
* **`KBD_DRIVE` bit 6 is not a matrix column.** It is only ever set on
  the NMI suspend/wake path: the RAM NMI prologue forces `f782=40h`
  (ram:F602, F628) and `Power_DownSuspend` drives `48h` when set vs
  `3Fh` when clear (ROM00:175E-176B). **LIKELY** that bit 6 enables a
  keyboard→NMI wake circuit: the suspend busy-spin runs `DI` and polls
  nothing (the spin's `IN A,(05h)` result is overwritten by `LD A,3` at
  ROM00:1795), so only NMI can wake the unit; a key closure must
  therefore assert NMI. Note the reduced wake drive is `48h`
  (bit 6 + bit 3) — **not** the all-columns value, which is `3Fh`
  reached when bit 6 is clear.
* **Discriminating test** to confirm the bit-6 NMI-wake hypothesis:
  probe the NMI line (and the `KBD_DRIVE`/`KBD_SENSE` lines) during the
  `48h` wake scan and press a single key; if the key closure drives NMI
  low, that is the mechanism. Also confirm the exact bus decode of the
  two wake drives (`48h` vs `3Fh`) — the ROM alone cannot say whether
  bit 6 set encodes "one selected column" or "all columns + wake
  enable" at the hardware.

## IR instrumentation and connector handoff — 2026-09-22

[PR #21](https://github.com/philpem/micronic1000/pull/21) is merged and contains the fixes
and bench record. See the [audit](reviews/ir-protocol-audit-2026-09-22.md)
for defect evidence and the [connector guide](../re-notes/connector-experiment.md)
for the full measurements, controls and rebuild/checksum instructions.

Completed instrumentation repairs:

- `rxb2` follows the destination pointer, records raw return A/F and received
  count, and bounds its preview to the first descriptor. Errors show dashes.
- Arduino phase scheduling, terminal stuffing, strict destuffing, startup
  ordering and RX masking have adversarial tests; all 13 configurations
  were compiled for Elegoo Uno R3.
- The bit-6 hook preserves the stock 620-iteration poll, adding 10 T-states
  before its first sample and 107 T-states after the loop.
- The witness skips arm after a bit-4 timeout and separates teardown writes.
- The peer replays unacknowledged replies without advancing policy state.

The `06 00 E4` payload/framing interpretation is withdrawn. Recorded LCD
observations remain; physical return framing/controller check bytes remain
OPEN. Emulator byte queues do not settle them.

**CONFIRMED (owner bench measurements and recorded ROM evidence):**

| Contact | Mapping / result |
|---|---|
| Orange/pin 3; blue/pin 8 | Vcc; ground respectively |
| Black/pin 5 | Barcode timing input, `2Dh` bit 0; working gate has `2Ah` bit 1 high and `2Ch` bit 5 low |
| Red/pin 1 | Non-inverted output, `2Ah` bit 4; reported high 5.6 V |
| Yellow/pin 6 | Sink/release output, `2Ah` bit 0; owner measured 200 mA sink current, not a characterised rating |
| Brown/2, violet/4, green/7 | Unassigned; no owner-detected diode paths to either rail. Brown's held-input tests produced no effect. Further mapping deferred. |

Both black input levels are readable while red pulses and while yellow
pulses with red held high in the tested connector configurations. The
owner also confirms **R/D/P**: yellow pulses with `2A=20h/21h`, `2C=20h`,
the relevant top-V24 shared-latch settings. This does not run the IR
controller or prove optical coexistence.

**Current IR round:** stock-context v3 **revision 2** is the reviewed next
ROM00 burn. Its guarded patch wraps the existing `Link_BlockRx` call with a
post-return yellow pulse. The stock worker's `LINK_STATUS` decision remains
unchanged. A passive Uno D8 interrupt logger permits
silent, free-running and handheld-paced comparisons without further ROM
changes. See the [stock-context test plan](../re-notes/ir-feedback-protocol.md#current-handoff-stock-context-v3-bench-trial).
The [v3 audit](reviews/feedback-v3-audit-2026-09-23.md) records the ROM,
Arduino real-time and logging defects found and fixed. Use
`micron1_stock_context_v3_r2.bin`, MD5 `bf518ce09083d420332fd02748f6bbef`,
byte sums `076F` / `38076F`; the old `37D9B7` image is superseded.
Require the new ~3.637-ms initialization pulse in LISTEN_ONLY before
interpreting absent receive markers. RX pulses are ~0.918/1.828 ms with
~0.46-ms release guards. Physical role/drive inversion and fixed candidate
settings are now available in the stock Uno builds without another burn.
The follow-up adds independent emitted-bit stuffing modes, optional closing
flag and fixed `00 00 FF FF 96` diagnostic content. Use explicit stuffing
rather than the legacy automatic rule to discriminate hypotheses. Start
with phase -2/8 or +2/8 for setup/hold around the first or second logical
clock edge respectively; inverted dark-idle boundaries remain a confound.
See the [discrimination sequence](../re-notes/ir-feedback-protocol.md#discriminating-the-receive-convention).
The [round-one worksheet](../re-notes/stock-context-v3-round1.md)
is the current capture record; PRs #22–#24 merged the feedback-v1, v2 and
v3 instrumentation in order.
**Current bench result:** owner installed revision-2 ROM00. C0 recorded the
3,636-us initialization marker and a V24 attempt, but its main log missed
the Uno boot banner. Fixed F0/F1 LED-role trials both captured handheld
outgoing bursts and no stock-RX return marker; the owner saw
`8000 (238/001)` / `8040 (238/001)` errors. The +2/8-cell timing path
was found distorted on the scope before any handheld phase-3 trial;
its Uno scheduler was repaired, and the replacement GPIO waveform is now
scope-qualified with yellow on pod D4. Details and raw captures are in
the [round-one worksheet](../re-notes/stock-context-v3-round1.md).
The first phase-3 V24 attempt had no RX return marker and ended with
`8000 (238/001)` / `8040 (238/001)`. The repeated F2S attempt used
100 handheld-triggered scope segments spanning both groups of about
50 retries. Uno D2/D3 activity appears in 24 segments; four 916–920-us
yellow lows follow Uno transmissions and match the instrumented
`Link_BlockRx` carry-set return path. The owner still saw `8000
(238/001)` then `8040 (238/001)`, "Line Failure". The scope caught
one yellow fall after the Uno data emission. This is a receive-call
return, not proof of a valid frame or session. The [round-one worksheet](../re-notes/stock-context-v3-round1.md)
has the raw capture filenames and timings.
**C1 silent control complete:** a verified LISTEN_ONLY build captured
100 handheld retries in two groups of 50, with no yellow pulse or
event drop. The matching scope CSV shows all 100 handheld bursts, zero
Uno D2/D3 rises and no yellow D4 low sample. The owner again saw
`8000 (238/001)`, "Plinth not connected", then `8040 (238/001)`,
"Line failure". The four F2S receive-return markers are therefore
associated with the transmitting condition in this comparison.
**OPEN:** discriminate optical role/level and return framing. The
current candidate has no demonstrated accepted frame; the intermittent
carry-set returns do not identify which bits, if any, were received.
An F3 trial inverted only the Uno clock output level at phase +2/8-cell.
The scope verified data setup/hold around the opposite physical clock
edge, then recorded 100 handheld retry segments with 21 showing Uno
output and no yellow pulse. The owner saw the same errors. F2S had
four carry-set markers with 18 complete post-burst Uno transmissions;
F3 had none with 14. This suggests clock polarity matters but does not
resolve a sparse, free-running comparison. A handheld-paced fixed
candidate using the F2S polarity is the next timing discriminator.
The F4 paced run requested 4 ms after each handheld burst. Its 100
ordinary replies had no yellow marker. One anomalous reply after a
short burst fragment started 32.58 ms after the last handheld edge and
was followed by a 916-us carry-set marker. The scope saw the second
transmission begin about 36.4 ms after its handheld trigger; the
predicted yellow return was beyond the 45-ms post-trigger window.
This suggested a later response window as a testable timing hypothesis,
without establishing an accepted frame. F5 then gave 100 regular
30-ms replies and F6 swept 30–36 ms across 100 replies; each requested
delay was achieved 14–15 times. Neither run produced a yellow marker
or a change from `8000` / `8040`. Scope captures independently show
regular late Uno output and no D4 low. **Discard delay alone as the
explanation** for the F2S/F4 markers. Free-running emission, the
abnormal F4 transition, and receive state still need discrimination;
none of these is established as the cause.
F7 tested sparse pacing directly: the Uno replied 33 ms after every
third handheld burst, sending 34 replies during 100 retries. All 34
reply segments produced a 916–924-us yellow carry-set marker, while
the handheld still displayed `8000` then `8040`. The scope independently
recorded 34 Uno outputs and 34 yellow lows in 100 trigger segments.
This F7 run showed a receive-call return, but an exact-binary repeat
in round two produced zero yellow markers. **Withdraw the claim that
sparse pacing makes the marker repeatable.** The 35-ms outlier pulse
also requires separate interpretation. See both worksheets.
F8 retained the sparse cadence and effective stuffing mode 1 while
changing the opening flag to `81`. It produced 34 timed optical replies
in 100 handheld-triggered segments but no yellow return marker; the
owner saw the same errors. The flag-choice causal inference is
withdrawn because the later exact F7 binary repeat also had zero
markers. Do not infer that either flag yields a valid frame.
F9 (stuffing mode 0) and F10 (mode 2) each sent 34 sparse replies with
no yellow low; the scope independently found 34 Uno output segments
and zero yellow lows in each 100-trigger run. The owner reported the
same `8000` / `8040` errors. The mode-1 causal inference is withdrawn:
the later exact F7 binary repeat also had zero markers. Do not promote
the original marker to frame acceptance.
F11 added a closing `7E` flag and saw 50 short one/two-cell fragments
alongside 100 normal handheld bursts. Those fragments shifted the
original every-third counter to 50 replies, with no yellow marker.
F11b ignored fragments shorter than 9 cells, restoring 34 replies
across 100 normal bursts; the scope also found 34 output segments and
zero yellow lows. The owner reported the same errors. Under the
restored cadence, F11b had zero yellow markers. The claim that closure
caused this is withdrawn because the later exact F7 binary repeat also
had zero. The origin of the short fragments is unresolved.
**Current blocker:** re-establish a positive receive-return control
under a verified V24 ADAPTOR selection and a stable, current-limited
LED drive before resuming content inference. Round-two C1 (`03h`)
and C2 (`00 00 FF FF 96`) were negative, but the interleaved type-2
baseline and exact F7 binary repeat were negative too. The owner
found PLINTH selected and cannot date the switch, so the port choice
for earlier negative runs is unverified. Coldstart independently
produced a 3,636-us yellow pulse on Arduino D8 and scope D4, clearing
the yellow measurement path for that event. An exact F7 repeat with
PLINTH selected and LEDs adjusted at the top V24 window yielded
8/34 return markers, all on the first eight replies. A later run
after further LED and power changes yielded 0/33, with its port
choice unconfirmed. The owner briefly bypassed the LED series
resistors and fed lab +5 V to the USB-connected Arduino 5-V terminal,
then restored the original 220-ohm resistor for each LED and removed
lab +5 V. A later
exact F7 run with V24 ADAPTOR confirmed had 34 Arduino replies and
zero yellow lows, but the matching scope capture had no D3 rises and
only 1–4 D2 rises in 31 segments instead of the expected 93 per
reply. The owner explains the digital-input symptom as the LED forward
voltage staying below the MSO digital threshold while the series
resistors were bypassed. The recorded restoration precedes C0e, so
the precise transition responsible for that capture is unclear.
An Arduino-only free-running check immediately afterward had four
complete output segments (88 D2 and 16 D3 rises each). The owner
initially reported alignment sensitivity within a few millimetres.
See the
[round-two worksheet](../re-notes/stock-context-v3-round2.md).
C0f swept alignment during a V24 attempt: 100 handheld bursts,
34 complete Arduino output segments, no yellow low on Arduino D8 or
scope D4, and the same `8000`/`8040` errors. A FREE_TX build repeats clock/data bursts
every 250 ms. The owner reports that IR reaches the handheld and that
alignment is less critical than first thought. They confirmed arrival
by probing the IR sensor amplifier output inside the handheld; the
probe was then removed. That does not establish payload decoding or
acceptance; the handheld
display during this check remains to be recorded. A 10-second Arduino log
contains 41 free-running transmissions, 50 handheld bursts and no
yellow event. The yellow marker reports a `Link_BlockRx` return, so
its absence does not distinguish a missing receive-dispatch call from
a receive call that did not return during the attempt. A guarded
one-shot receive-dispatch ROM image is prepared at
`analysis/rom_exerciser/releases/stock-rx-entry/`; it shows `I ss rr`
at `LinkRxDispatcher` entry and redirects the verified ROM warmstart
jumps at `ROM00:01A3` and `ROM00:3812` into cold initialization.
The RAM-resident wake route has not been validated on hardware.
Next compare a silent Uno V24 attempt
with the archived F7 reply under that ROM, with no further physical
probing. Content
inference remains suspended pending evidence of a decoded or accepted
reply.
The scope sampling audit qualified the edge-timing claims separately:
the long F5/F6 128-segment setup acquired at 78.1 kSa/s and exported
at 50 us/row, so use it for millisecond placement and yellow-event
presence only. New short F2/F3 acquisitions measured 20/10 MSa/s
and reproduced the earlier GPIO setup/hold ranges on a 2-us CSV
grid. See the worksheet's scope sampling audit and the saved SCPI
profile before comparing any future bit-edge measurements.

**Previous IR round:** feedback-v2 is burned and has completed its first
P/H/J/K handheld run. It retains v1 W/R/P/G and adds H/J/K controller-state
capture. See the [v2 bench procedure](../re-notes/ir-feedback-protocol.md#feedback-v2-receive-state-diagnostic-build-and-bench-procedure),
the command sheet at `analysis/trials/feedback-v2-state-1-13.txt`, and the
release manifest at `analysis/rom_exerciser/releases/feedback-v2/micron1_feedback_v2.json`.
The image MD5 is `a9966a607f672d75031113528b7c6ea3`; byte sums are
`903E`/`37903E`. The first attempted silent P handshake timed out waiting
for yellow ACK because the handheld had not yet cold-booted. After the
owner discharged backup power and confirmed the v2 banner, P returned
ROM sequence 1/error 0. The following H/J/K matrix returned ROM sequences
2–13/error 0 with no `LINK_STATUS` bit-4 or bit-0 sample in any trial;
each capture held a constant `80h` or `C0h` status byte. K's watcher-hit
byte stayed zero. See the [first v2 result](../re-notes/ir-feedback-protocol.md#first-feedback-v2-bench-result-2026-09-23),
`analysis/captures/feedback-v2-probe-2-clean.jsonl`, and
`analysis/captures/feedback-v2-state-3-14.jsonl`. The question is whether
`LINK_STATUS` bit 4 differs across high/low/watcher-like `LINK_CTRL`
bits-6/7 drive under matched IR stimuli. Even a positive correlation would
not identify optical LED roles or a complete IR frame by itself.

The corrected v2 physical-level matrix (host IDs 33–50, ROM sequences
32–49) covered all remaining `clk_inv dat_inv` settings for H/J/K and
both role assignments; all 18 valid captures again had constant `80h`
or `C0h` status, no `LINK_STATUS` bit 4/bit 0, and no K watcher hit.
The first attempt (IDs 15–32) did **not** vary levels because a 17-field
repeat-command parser branch dropped both inversion fields. This defect is
fixed and regression-tested; see the [v2 bench result](../re-notes/ir-feedback-protocol.md#first-feedback-v2-bench-result-2026-09-23).
**The question now assigned to v3:** can the earlier stock V24 pending-bit
observation be reproduced with the live TX/session/worker path, and does
stock `Link_BlockRx` return carry-clear after the selected optical
stimulus? Avoid further broad standalone 7Eh sweeps until that context is
isolated.

**Previous v1 round:** feedback-v1 implements black command handshakes, yellow
markers, stock-order witness and bounded raw RX in one standalone ROM. Fresh
`Link_PortSelect` bytes still clear `2Ah` bit 1 and top V24 sets `2Ch` bit 5,
so the harness restores the known black gate only after teardown. The canonical
contract is [IR feedback harness interface](../re-notes/ir-feedback-protocol.md).
Host validation includes 32 ROM tests and 2 UART tests. **CONFIRMED (owner
bench report, 2026-09-23):** feedback-v1 boot and the first direct-TTL silent
P request passed: sequence 1/error 0, valid 30-byte result checksum, status
C0h, LCD agreement, and return to READY. See the [raw bench record](../re-notes/ir-feedback-protocol.md#first-hardware-result-2026-09-23).
The silent W witness (host ID 2) also returned valid feedback: error 6,
LINK_STATUS bit-4 poll passed, arm executed, bit-6 poll timed out. Raw
probe/before/after status is A0h/80h/C8h; LCD agrees. Matched X stimulus
(host ID 3) returned valid feedback with the same poll/arm/timeout outcome;
probe/before/after A0h/C0h/C8h. **Historical timing concern (resolved for
the tested waveform in trial 6):** Uno reported maximum event lateness
110 us against a 122 us cell, repeated in successful ID 4.
The owner corrected wrongly labelled scope channels; the apparent
D6-before-D5 onset is withdrawn. **CONFIRMED (trial 5 scope CSV):** all 13
candidate clock and six data pulses are present, and sampled bits read 7Eh,
but early lead-clock intervals are about 90 us, later ones mostly 130 us,
and pulse widths are shorter than requested. This withdraws the earlier
"only first lead pulse clipped" possibility. Physical scope-pod D2/D3 to
Uno D5/D6 correspondence is inherited from earlier captures and needs
confirmation for this setup. The USB-loadable Uno emitter now dispatches
256 us before the first edge and has a queue-free path for the current phase.
Host tests and direct-TTL Uno build pass; **physical waveform remeasurement
was completed with trial 6.** Owner-confirmed scope D2→Uno D5 and
D3→Uno D6 produced 13/6 pulses, sampled 7Eh,
clock periods 117.5–127.5 us and widths within the stated targets;
`emit_late_max=7`. Trial-5 and trial-6 source CSVs are tracked at
`analysis/captures/feedback-trial{5,6}-keysight.csv`. W still returned
error 6 after arm; W did not attempt RX, so framing and physical LED roles
remain OPEN. Trial 7's swapped W/S emitted nothing as intended; trial 8's
swapped W/X was correctly timed (scope D3 proposed clock, D2 proposed data,
13/6 pulses, sampled 7Eh, Uno max lateness 3 us), but W still returned
error 6. Both trial-7/8 feedback records have valid checksums; W does not
call RX. Forced-RX matched trials 9/10 returned identical valid error
records: `A=EEh`, `F=6Dh` (carry), wrapper error 7, no saved DE/preview.
The stock RX byte-ready loop has a roughly 30.0 ms bound and likely overlaps
the trial-10 burst near START+7 ms; `EEh` can follow a first or later byte
timeout, while the wrapper hides partial bytes on error. Matched
receive-pending-gated G/S and G/X pair IDs 11/12 also returned identical
error 8 (`LINK_STATUS` bit-4 pending timeout); neither called RX. Their
different probe/before bytes were sampled before optical emission and do
not demonstrate a stimulus response. G/S and G/X with `swap=0`, IDs 13/14,
also returned error 8 with identical A0h/80h/80h probe/before/after bytes.
Trial 14 reported 10 us maximum lateness, but no new scope capture; the
flag-only candidate has not raised pending status in either software role.
Matched G/S and G/X IDs 15/16 added one `03h` payload byte after `7Eh`,
with `swap=0` and unchanged timing/framing; both timed out at the
`LINK_STATUS` bit-4 gate (error 8), with identical `E0h/C0h/C0h`
probe/before/after status. Trial 16 reports 3 us software lateness, but
there is no scope trace. Its exact stimulus was repeated as ID 17 with the
scope connected. That repeat returned error 8 with `E0h/C0h/C0h`, but its
tracked Keysight CSV verifies 21/21 clock and 8/8 data pulses on scope
D2/D3, sampled cells `7Eh 03h`, within digital timing targets. The
owner confirms the trial-17 pod map remained D2→Uno D5 and D3→Uno D6;
optical light is unmeasured. Matched G/S and G/X IDs 18/19 then tested the full frame
complemented (`pol=1`), as specified in the
[canonical interface](../re-notes/ir-feedback-protocol.md). Those trials
also returned error 8 with identical A0h/80h/80h status; the silent trial
emitted nothing, the stimulus reported 3 us maximum software lateness,
and neither entered stock RX. No trial-19 scope capture was supplied.
Mode-R matched silent/stimulated IDs 20/21 preserved the ID-19 candidate
and invoked stock RX directly. Both returned `A=EEh`, `F=6Dh`, wrapper
error 7. Trial 20 probe/before/after was E0h/C0h/C0h; trial 21 was
A0h/80h/C0h. Its `LINK_STATUS` bit 6 rose across stock RX, but the
different pre-stimulus baselines and stock RX timeout prevent attribution
to optics. No trial-21 scope trace was supplied. Matched mode-R
IDs 22/23 then used START+60 ms, normally after the no-byte RX timeout/status
sample, as a late-stimulus control. Both returned the same `EEh`/carry
and identical A0h/C0h/C0h probe/before/after status; trial 23 emitted
with 9 us maximum scheduler lateness. Since bit 6 was already set before
RX in both, this pair does not explain trial 21's rise. Next: test the
optical output at the top V24 receive window with the previously documented
SFH213 photodiode probe before more framing sweeps. This verifies light
at the target plane, not internal detector receipt. The owner clarified
the SFH213 is now built into the Arduino transponder, not separately
movable. Early R/X ID 24 repeated ID 21's A0h/80h/C0h status and
`EEh`/carry result with 3 us maximum software lateness. Since all
reported R trials have `after=C0h`, this does not prove an optical
response. The owner reports that the USB-only `V 1` camera check lights
the IR LEDs (CONFIRMED owner observation); this verifies emission at the
LEDs, not light at the handheld detector. Next: check alignment and
optical delivery at the top V24 window before further framing sweeps.
With geometry fixed, the next ROM-controlled pair was G/S host ID 25 then
G/X host ID 26, `swap=1`, candidate `7Eh 03h`, using the exact commands
in `doc/re-notes/ir-feedback-protocol.md`. This is the missing combination:
earlier `swap=1` G used `7Eh` alone, while the `7Eh 03h` payload was
tested only with `swap=0`.
**Completed (owner report):** both IDs 25/26 returned error 8, with
`LINK_STATUS` probe/before/after A0h/C0h/C0h and E0h/C0h/C0h respectively;
neither entered stock RX. With LED ballast resistors bypassed, the owner
observed `V 1` as low about 10%/high about 90% at a Micronic
photodiode-amplifier output. Later owner report confirms the signal still
reaches the Micronic IR receiver with the limiting resistors fitted. This
does not establish earlier short-burst delivery or the polarity/threshold
at the controller input. The owner's polarity
question concerns physical IR clock/data levels. Sketch `pol=1`
complements serialized data bits but leaves clock pulses unchanged, so it
does not answer that question. Retain deliberate LED current limiting.
A simultaneous D5/D6 and amplifier capture would directly establish
physical edge level and phase if practical.
Owner reports that probing the Micronic photodiode amplifier for the short
burst is difficult; no new scope trace accompanied resistor-limited G/S
ID 27 and G/X ID 28. Both valid records had error 8 and identical
`LINK_STATUS` probe/before/after A0h/80h/80h; ID 28 scheduled emission
with at most 3 us lateness. The direct short-burst waveform remains open.
The Uno sketch now implements optional `clk_inv dat_inv` trailing `T` fields
(old syntax defaults 0/0) and drives both outputs low before/after each X
burst. The connected Uno was uploaded and verified; exact uppercase `V 1`
completed normally. Resistor-limited G/S and G/X IDs 29–44 covered both
`swap` assignments and all four LED-drive-level combinations, each
against a silent control. All 16 returned error 8. ROM counters advanced
32–47, and stimulated trials reported at most 8 us scheduler lateness.
The historical-like `7Eh` + zero-stuffed `1Fh`, no-lead, START+3-ms
candidate in both assignments (IDs 45–48) also returned error 8, ROM
counters 48–51. These G results do not reproduce the old stock-ROM
positive `LINK_STATUS` bit-4 observation. The old tests used stock
receive/session context and burst-relative reply timing; negative G
results do not refute them. **Stop broad G sweeps** until that context
difference is understood. Timestamped logs are in `analysis/captures/`;
no new Micronic amplifier scope trace exists. No new EPROM burn was used.
**Timing audit:** the feedback ROM's 50-ms guard precedes yellow START;
G begins reset/select and polling about 2 ms after START, not 52 ms
after it. Discard the contrary early-stimulus explanation. G polls bit 4
only about every 5 ms; a brief, nonlatched indication could fall between
samples (SUSPECTED, latch behaviour unknown). A targeted 5/6-ms delay
test with explicit `7Eh 1Fh`, no lead (IDs 49–54, both `swap` roles) still
returned error 8 in all six valid records, ROM sequences 52–57. The
first serial-open attempt had malformed `REASYNC` and sent no trial;
the 4-s-startup retry succeeded. Both logs are archived. Further G
variation has diminishing value until stock-vs-feedback receive setup
and pending-bit lifetime are resolved.
The connected Uno was then updated with bounded repeat bursts (no handheld
EPROM change). Matched G/S, single-X, and three-X trials IDs 55–60 used
the explicit `7Eh 1Fh` candidate in both role assignments; repeats were
scheduled at START+5/28/51 ms. All six valid raw records were mode 4/error
8, ROM sequences 58–63. The two repeated stimuli spanned about 48.6 ms
from first software dispatch to last completion. Trial 58's human-readable
`release_us` text was garbled, but the raw record checksummed. This weakens
a single unlucky 5-ms polling phase as an explanation, without proving
that G's idle/finished controller state can detect the optical burst.
**Next discriminating ROM work:** compare `LINK_CTRL` finished bits 6/7
high against the stock IRQ watcher's cleared-bit state under matched
stimulus, with a faster bounded `LINK_STATUS` history. Avoid further broad
USB-only G waveform sweeps before that comparison.
The updated Uno sketch provides a sustained low-duty output self-test:
`V 1` from idle: A/D5 then B/D6 at 10% PWM for 1.5 s each, with black
released and ROM trial IDs unchanged. Repeating `V 1` after completion is
allowed. A rejected idle command, including a repeated trial ID, no longer
desynchronises the updated sketch; send the next higher trial ID directly.
An in-flight error still requires `R`. Direct TTL is now the sketch source
default for the owner's installed wiring. This needed a USB upload but no
EPROM burn. Earlier conn10 role-dependent retries did not prove physical
LED mapping or framing. R
preserves the last accepted host ID.

**Owner clarification:** Arduino LED clock/data assignment is unknown and
`7Eh` as a receive flag is SUSPECTED. Test both optical channel assignments;
software names are not physical identification. Prioritise one reusable ROM
burn: payload, candidate framing, channel roles and timing should be adjustable
on the USB-programmable Arduino without dismantling the handheld again.

The [IR feedback automation plan](../re-notes/ir-feedback-test-plan.md) keeps
the control rationale and bench worksheet; its linked canonical interface
defines the current feedback-v1 procedure. Arduino LED roles and `7Eh` remain
SUSPECTED until bench evidence discriminates them.

---

## Done (verified vs docs + Ghidra + byte-level traces)


1. Map syscall table at ram:d6f4 (3 loader primitives + hidden terminator)
2. Kernel installers -> Kernel_KernelToRam (ROM00:02FE),
   CopyKernelDispatchBlock (ROM00:3BAA)
3. ROM00 gap analysis; ROM01 gap pass 1
4. Boot load scripts CLOSED (decode_chains.py; grammar fn=0/1/2/FFFF)
5. Deferred-call queue / transfer-vector table SOLVED
   (queue ED1C-F17F doubles as task list AND UI vtable targets)
6. Template builder / object system decoded (ROM01:0271)
7. Warm restart path decoded
8. Diagnostic monitor entry verified as a returning stub (`Debug_MonitorHookStub` at `ROM00:3513`,
    `XOR A; RET`, rechecked 2026-09-20; now `Debug_MonitorHookStub`, formerly `Monitor_Enter`). Prior built-in-monitor and
   service-key monitor-boot claims withdrawn. External monitor/ICE use
   remains SUSPECTED; resolve with alternate-ROM/debugger evidence or an
   interception trace. See [debug facilities](../re-notes/os-diposb.md#debug-facilities).
9. Keyboard matrix fully decoded (H+L+P = HELP service key;
   drive(02)=col bit, sense(00)=row bit, index=row*6+col)
10. Interrupt architecture fully decoded (IM1 -> 0038 -> F5F3 -> F64D ->
    polled fd84 event table; NMI -> 0066 -> F5F6)
11. Clock self-test decoded (Clock_SelftestTickWindow ROM00:2828)
12. Session/Commstar reference data located (ROM00:6A50-6E90)
13. **RTC RESOLVED: 08h/28h indexed pair IS the HD146818** (address
    latch / data). Register map proven from firmware sequences:
    regs 00,02,04,06,07,08,09 = time file; 0A/0B = status/ctrl;
    0C = interrupt flags. See internals/rtc.md. The 4x
    latch cluster (4A/4B/4D/4F) is NOT the RTC (owner-confirmed).
14. **Documentation coverage:** current counts and their scope are maintained
    only in [gap-analysis.md](gap-analysis.md). See the historical pass log
    for earlier baselines; they are not the current state.
15. **CP/M implementation comparison** (doc/internals/cp-m-comparison.md):
    BDOS dispatch table ROM00:3708→ram:F1EB; fns 00-24h = CP/M 2.2
    semantics, with DIPOS extensions & stubs. Annotated ~30 `Bdos*`
    functions (dispatch handlers + FCB machine 0824/068D/06C1/09CA/
    0D79) and the extension stubs (0742/115E). Deviations documented:
    no disk BIOS (RAM storage), version=0x23, stub'd allocation/DPB/
    write-protect fns, device-routed console I/O, 16 drives.
16. **DIPOS-B extension fns IDENTIFIED + DOCUMENTED**: special fns
    2D(banked-call wrapper F55A)/2E(dir-search 0D79)/30(1893)/
    62(dir-integrity 0742)/68-69(no-op 115E), and the 13-word wrapped
    table ROM00:36EE→ram:F1D1 (fn F3-FF): F3 no-op, F4 RST28, F5 delay,
    F6 get-device, F7 SetActiveConsoleDevice, F8/F9/FA/FB FE83/FE93
    config read/write + device-pair, FC/FD set/get RTC time,
    FE/FF RTC alarm. All renamed+plate-commented in Ghidra.
17. **DIPOSB programmer's guide** (doc/manual/programmer-guide.md):
     self-contained doc to read alongside a CP/M 2.2 guide. Covers the
     BDOS call interface, RAM file system (A/B drives, 16-drive select,
     stubbed alloc/DPB fns), device-routed console I/O, the F3-FF
     extension fns (device/config/RTC/alarm/delay), banked calls (RST2),
     and a practical differences/avoid table.
18. **Runtime DIP/COM Load/Run loader — file format CLOSED (2026-08-28)**:
     `ROM01:0A67-10CE` via `ram:D081` (`g_apScreenHandlerTables`, was
     `g_tblFieldTypeRecPtrs`) → `ram:D0F0` (`g_apLoadRunHandlers`),
     `UI_FormExitDispatchNext` (ROM01:06D3) double-dereference. Ghidra
     names: `Program_PrepareLoadGeometry` 0A67, `Program_LoadByName` 0B82,
     `Program_ConsumeInputChunk` 0BAC, `Program_LoadDipOrCom` 0CE7,
     `Program_RunByName` 106F, `Program_GenerateBlockChecksums` 0957,
     `Program_VerifyBlockChecksums` 09C2, `Program_NormalizeLoadRange`
     0AE3, `Program_ReportLoadError` 0CCB, `Program_LoadedProgram` ram:D7F0
     (final transfer at 10C6). **No BDOS execute function** — BDOS
     open/read/search are generic FCB services; source bytes via
     coroutine/provider around `0C12`/`0CE7`/`ram:D370`, exact physical
     source-reader remains open — do not claim identified. DIP is
     **distinct from boot record dispatcher `ram:D6DB`** (`fn=0/1/2/FFFF`
     grammar is boot-only, not DIP). DIP grammar (LE, CONFIRMED): 14-byte
     header `{magic 0xC8C9 (C9 C8), system ID 0/0x00E5, entry-bank, image
     size clamped 0x8000, run-bank, entry addr, blockCount max 5}` then
     blocks `{u16 type, u16 dest bank off, u16 dest addr, u16 payload
     count}+payload`; type 0 direct copy, type 1 = 4-byte `{bank off,
     addr}` → `{0xD7, resolved bank, addr LE}` RST10 trampolines; only
     types 0/1 accepted (other type → default/next logic only if
     applicable, phrased explicitly). 8→10-byte
     `DIP_LoadedBlockDescriptor` expansion — `0957` writes additive
     checksum at `+8`, `09C2` recomputes, mismatch `0x2332` (9010),
     "Program corrupt." = **loaded memory changed** (not file checksum). COM
     fallback if first chunk `<14` or first word `!=0xC8C9` → copy to
     `0x0100`, run-bank `0`, entry `0x0100`. Errors: `0x232B` (9003),
     "Bad DIP file." = short/truncated 8-byte header or payload (not bad
     magic); `0x2331` (9009), "Program not built for this system." = ID
     mismatch; `0x2334` (9012), "DIP file has too many blocks." = count>5;
     `0x232A` (9002), "DIP file too big." = dest+payload over boundary;
     `0x232C` (9004), "COM file too big." = raw COM over capacity.
     `ram:ECDA` max entry-bank offset is **LIKELY** only. `ram:D681` is
     the kernel dispatch/boot-loader block, **not** the runtime loader
     (ROM01 separate). Supersedes old header-open / funnel-into-D6DB
     / `g_tblFieldTypeRecPtrs` device-mapping claims.
     Docs updated: program-formats.md (rewritten), programmer-guide.md
19. **Set Debug mode / status-device investigation — CLOSED (2026-09-25):**
    `g_bDebugRunEnabled` (`ram:ECC7`) enable byte and `g_bDebugRunDeviceIndex` (`ram:ECC8`) device index are CONFIRMED with
    dedicated initialisers (`ROM01:069A`/`06A1`) and consumers
    (`ROM01:038C`/`0393`). The `EF4C`/`EF34` callback pair moves
    Diagnostics menu selection (`EC6F`), not debug state. The activation
    chain through `g_wDebugRunActive` (`EB18`) transient gate → `EF18`/`EF24` → vector 13h →
    `F32F` → `Debug_MonitorHookStub` (`3513`, `XOR A; RET`) is CONFIRMED. No IR output, debug
    print, or persistent config write occurs. The earlier ephemeral-only
    claim from a bounded watch is corrected. Labels
    `g_bDebugRunEnabled`, `g_bDebugRunDeviceIndex`, `g_wDebugRunActive`
    installed in Ghidra (2026-09-25). `g_wMonitorDeviceSelector` (`E2F8`)
    remains **PROPOSED** (not installed).
    Docs updated: monitor-and-debug.md, memory-and-io-evidence.md,
    forms-ui.md.

## In progress

- **Plinth shadow-peer divergence — RESOLVED (2026-09-20):** bisected to
  `e5baacf`; root cause was that the synthetic route pushed the program object
  peer-initiated (on its internal-state oracle/timer), so the request→reply
  peer could not predict it. The route is now **request-driven** (it answers
  the handset's repeated state-`0044` block request) and the shadow peer serves
  the program via `ProgramDownloadPolicy`, giving
  `agreed=14 differed=0 unsolicited=0`. `CommstarShadowPeerTest` passes on both
  routes. See the session log for the full bisection and fix.

- **Documentation consistency corrections (2026-09-20):** current summaries
  reconciled; see `doc/review.md` for implementation status. The local-only
  storage conclusion was overturned by fresh BDOS `2Eh` tracing and review.
  Still open: routed per-operation pointer/request contracts and successful
  peer replies; capture these before claiming operational B:/C:/D: storage.

- **Session modules loaded into Ghidra** (MCP inline script; also in
  FillBatteryRam.java). Module A (D893-E0F3), Module B (D081-D2CA),
  A2 (E104-E233), params (E0F4), misc (E22D), page-zero (E2FA),
  disassembled.
   * `ram:da13` = session-to-BDOS bridge
     (RESOLVED 2026-09-19, CONFIRMED, byte-verified)
     — copies function number → C and argument → DE
     from the session register file (`E0FE`/`E100`,
     populated from the stack by `ram:D86E`), issues
     `CALL 0005`, returns BDOS A zero-extended in HL
   * `ram:e0b2` = command dispatcher (walks inline {cmd->handler})
  * `ram:d86e` = stack-param->E0FE copy then jump
  * `e06a/e085` = 16-bit comparison helpers
  * session RX loop `FUN_ROM00_59fb`, TX loop `FUN_ROM00_5f58`
- **Full emulator boot to a live link I/O** (updated 2026-08-28):
  * The 16C9 HALT-wait is the **keyboard event wait**, not just the
    tick: kernel EI/LD A,1/LD (FFA8),A/HALT at 16C3-16C9, wake checks
    fbc9&fbca; measured fbca=07 → caller 1105 = keyboard read waiting
    for fbc9 bit2. tick => fd4f/fbca recompute, but exit needs an
    event bit that no emulated source ever posts.
  * **Timebase fixed:** `boot_hw.py` uses 3400-tick slices and derives RTC
    phase from the measured `SLICE_TICKS - ticks_to_stop` execution budget.
    It calls `rtc.push_tick()` for each elapsed RTC period, then offers INT
    only when `FFA8 != 0`; thus breakpoints/watchpoints cannot make the RTC
    run faster than the emulated CPU.
  * **Events verified:** when PC parks in 16C9-16D2 with `FFA8=1`, the harness
    writes one queued byte through the FBF0 keyboard ring and sets FBC9 bit2.
    The serial-driven boot enters the Main Menu. Matrix injection via ports
    00/02 is not viable because firmware does not scan them during this wait.
  * Both directions now run end to end against real firmware: program
    download to the handheld and RECORD upload from it. The synthetic peer
    can now replace its internal RAM/PC receive-arm oracle with a tested
    completion-relative 500 ms delay. Physical timing remains unverified.

- **Decode Commstar session/frame layer** — the validated envelope, numeric
  type-2/3/4 exchange, program-download blocks, RECORD upload stream, and
  principal session transitions now run against real firmware in bounded
  emulation. The state-`0000` exchange formerly called the builder preflight
  is now characterised and regression-tested. Remaining: replace the
  diagnostic receive-arm oracle as the normal peer policy after physical
  validation, recover still-unknown object fields, and establish the physical
  return handshake.

## Next (priority order)


*No analytic work remains — §12 FINAL PASS fully CLOSED 2026-09-19 (items 1,2a,2b,3,4,5,6 DONE), `ram:DA13`/`ram:D36A`/`ram:D837`/`ram:EE00-EE4F`/vtable reader/barcode path all RESOLVED/WITNESSED, 4 `FUN_*` retains documented as dead/reachable-unknown. The only remaining work is owner/hardware-dependent (below). Historical §12/RESOLVED details are in the Detailed backlog; do not re-add analytic items here.*

### Hardware-dependent priorities (unchanged)

1. **Phase 0 gate:** run the `2609` record-stream build and/or the stock-order witness (`2F71` — 861 bytes, SHA-256 `dbc44a715eafba1443fcf3fc56155fb8db9291792dce4ba7dcba3e6cee325c14`, md5 `e83687ea027b9a0d341a071ef8d9c427`) and read `LINK_STATUS` bit 6 behaviour with no peer.
   * **Result run 1 (2026-09-20, CONFIRMED observation):** `2609` burned
     (md5 `6a1ff31fd0a3ba2ef98afcb760aec499`); after ENTER the error row is
     `EE 04 58 13 02` (stage 04, fresh `LINK_STATUS=58h` = TXRDY clear,
     HSBUSY set, RX-pending set; `CTRL_SHADOW=13h` = arm ran; 2 data bytes
     written). LIKELY the peer-handshake-survives arm, but the record stream is
     never reached. Details in
     `doc/re-notes/exerciser-test-plan.md` (Phase 0 hardware result).
   * **Result run 2 (old witness `2E3E`, 2026-09-20):** LCD `W C8 C8 00 00 C8 A0`
     (`OR=AND=ARMD=C8h`, `ISRC=IRQN=0`), but it **emits nothing** on the top
     port. Static comparison: the old replay omitted stock's
     `LINK_STATUS` bit-4-clear poll (`ROM00:32B8`) and bit-6-clear poll
     (`ROM00:32F0`) and raised `LINK_CTRL` 6/7 µs after the arm. Superseded.
   * **Run 3 (stock-order witness `2FFF`, owner 2026-09-20):** LCD
     `W D8 40 10 00 00 00 C8 7F` = `P4=10` (bit4 poll cleared), `P6=00` (bit6
     poll **timed out**), `OR=D8`/`AND=40` (bit 6 set in every sample),
     `ARMD=C8`, `ISRC=IRQN=00`. **Phase 0 verdict: bit 6 does not clear with
     no peer — peer-handshake survives → Phase 2.**
   * **Run 4 (teardown witness `308E`, owner 2026-09-20):** LCD unchanged
     (`W D8 40 10 00 00 00 C8 xx`), **still no burst** — the teardown write
     alone is not sufficient.
   * **Run 5 (front-end strobe witness `2F71`, owner 2026-09-20):** LCD
     unchanged (`W D8 40 10 00 00 00 C8 3D`), **still no burst** — `48h=03h`
     before the arm alone is not sufficient.
   * **Run 6 (front-end init + early probe witness `3351`, owner 2026-09-20):**
     the stock I/O log shows a **teardown** after the bit6 poll (drop
     `LINK_CTRL` bit4/bit0, `ROM00:3361-3376`) and three latches the
     boot-replacing exerciser never set: `48h` (`STATUS_DRIVE`) = `03h`
     (`Session_SystemInit` `ROM00:0359`), `07h` (`CTRL_07`) = `00h`
     (`RTC_DayChangeWatcher` `ROM00:24A5`), `04h` (`IRQ_MASK`) = `E0h` (`ROM00:22F2`); it also moves `LinkProbe` to
     boot (settling). LCD `W D8 40 10 00 D3 C4 C8 55`, **still no burst**.
   * **Run 7 (6/7 idle-state witness `3072`, owner 2026-09-20):** set
     `LINK_CTRL` 6/7 at boot (`early_init` in a reclaimed `01BE-024F` region)
     and cleared them at TX entry. **The LCD went blank — hard regression.**
     CONFIRMED (owner): raising 6/7 at boot kills the display, so 6/7 gates
     more than the link (display power/mode, or it hangs). New evidence for the
     Provisional 6/7 reading (open questions A/B). **Reverted to the known-good
     run-6 image `3351`** (`006e0a37…`, 872 bytes); 67 tests pass.
   * **Stock-ROM hook instrument (CONFIRMED, 2026-09-20) — Phase 0 CLEARED.**
     `analysis/rom_exerciser/stock_instrument.py` patches the STOCK ROM (boot
     unchanged) to sample `LINK_STATUS` in `Link_BlockTx`'s bit6 wait and print
     the result on the LCD. Hooks: `32F0` bit6 poll → `CALL hook6`, `3356`
     error entry → `JP show` (`show` prints `O xx A xx Bx` and halts). Code
     lives in the free `7E96-7FF9` gap — **NOT** the exerciser's `0250-02FD`,
     which is the stock boot's own continuation and crashed the first attempt
     (TESTING banner then blank). Image `micron1_stockhook.bin`: sum16 `EA30`,
     SHA-256 `cda7cf2d2c26d7673812c5ea46e8049d09fb191c4799a9c09b4edc6ace204a70`,
     md5 `afd177f12b080e93afc82aad3f331616`.
     **Owner result `O C8 A C8 B1`: during the stock bit6 wait `LINK_STATUS`
     was exactly `C8h` in every sample (OR = AND, bit 6 set, bit 7 set).
     CONFIRMED with the stock sequence and environment — `LINK_STATUS` bit 6
     does NOT clear with no peer; the peer-handshake reading survives.** The
     exerciser's replay gave the same answer; the TX anomaly is separate. A
     RAM-test speed-up patch (`26C8` `41h`→`09h`) was tried and **removed** —
     it hung the batteries-out cold boot (the RAM test initialises RAM).
     Reusable framework for future unknowns (add a hook, sample to RAM, print
     on LCD; triggers: UI, keyboard, RTC, side port `2Dh`). 3 hook tests pass.
2. **Phase 2 (RX path) — instrument built, not yet burned.** The stock-ROM
   hook set `rx` (`stock_instrument.py --hook rx`) patches `LinkRxDispatcher`
   entry (`ROM00:2FBD`) to `JP hook_rx`: when the link IRQ (source 2) finds
   `LINK_STATUS` bit 4 set, it prints `I ss rr` (`LINK_STATUS`, and `LINK_RXD`
   if bit 0 says byte-ready) and halts. Image `micron1_stockhook_rx.bin`:
   sum16 `DAA6`, SHA-256
   `5365bd1127656ae9f7e7f7a8cc7511dd9479f4abb7deee716c638f92a7630010`, md5
   `e4573f3e2cd9d925e7b64c2700baa7db`. Procedure: boot, then run the Arduino
   `FREE_TX` mode (`m1000_ir_probe.ino`, `FREE_TX 1`, all else `0`) — one swept
   burst every 250 ms with no handheld burst, probing the idle receiver
   directly (flag sense `{0x81,0x7E}`, polarity, ±1/8 ±1/4-cell phase,
   content); the last `# TX` line records the candidate configuration present
   when the hook froze. That observation does not identify the handheld's
   receive convention. A frozen burst displays `I ss rr`; no burst leaves the
   normal error path.
   `micronic.peer.CommstarPeer` covers the session layer above it.
   * **Result (owner, 2026-09-20, first run):** with the Arduino `FREE_TX`
     free-running and a V24 connect started, the hook fired and the handheld
     froze on **`I 98 00`** — `LINK_STATUS=98h` (**bit 4 receive-pending SET**,
     bit 7 set, **bit 6 clear**, bit 3 set), `LINK_RXD=00h` (bit 0 clear, no
     byte yet). First positive receive signal. **Confound:** it fired during
     the transfer, so it may be crosstalk/self-reception from the handheld's
     own TX (open question D) rather than the Arduino's burst. **Control
     needed: repeat with the Arduino emitters disabled (LISTEN_ONLY build); if
     `I 98 00` still appears, it is self-reception.** The Arduino's own RX log
     also shows `NO DATA-LINE ACTIVITY` (its `DAT_IN` sees no data line), so
     its receive wiring is incomplete.
   * **Control (owner):** with `LISTEN_ONLY` (Arduino silent) the unit does
     **not** stop → the receive is genuinely the Arduino's burst, **not
     crosstalk**. CONFIRMED: the controller accepts a return burst.
   * **Handheld-paced sweep (owner, RX_SWEEP, reply per burst):** the hook
     halted on **`I 90 00`** (`LINK_STATUS=90h`: bit 4 receive-pending set,
     bit 7 set, bit 6 clear; `LINK_RXD=00h`) at the Arduino's last line
     **`flag=7E phase=-2/8cell pol=0 content=2 delay=3000/3000us`** (content 2
     = flag + stuffed `1Fh`). This records the candidate Arduino stimulus that
     preceded the observation; it does not confirm `7E` as a return flag,
     polarity, phase, or either LED-to-detector assignment. `bit 4` set but
     `bit 0`/`RXD` clear = a pending receive, no byte yet. The reply was at
     3 ms (old sketch). **Next (built, not yet run):** Arduino `RX_NARROW`
     holds candidate settings while varying one axis (`RX_NARROW_AXIS`: 0 =
     phase, 1 = polarity, 2 = content), reply per burst at 4 ms; the rx hook
     is to be extended to wait for bit 0 and capture the frame.
   * **Narrowed run (RX_NARROW axis 0 = phase, owner 2026-09-20):** with the
     candidate `flag=7E` row fixed, the hook fired on the **first** reply
     (phase −4), giving `I 90 00` again (bit 4 set, bit 0/RXD clear). This is
     a repeated observation under that candidate stimulus. It does not settle
     the return flag, physical channel roles, phase requirement, or the cause
     of bit 4; the data convention and byte delivery remain open.
   * **Decision (owner) + `rxb` hook built.** Hold the data lead at the
     handheld's own TX convention (−2/8 cell) rather than sweeping it; sweep
     polarity next (`RX_NARROW_AXIS 1`), then content. New hook set `rxb` is
     the byte-capture version: `LinkRxDispatcher` entry → `hook_rxb`, which
     waits (bounded ~16 ms/byte) for `LINK_STATUS` bit 0 and captures up to 3
     bytes from `LINK_RXD`, printing `I ss n b0 b1 b2` (`n=0` = flag seen, no
     byte → data convention wrong). Image `micron1_stockhook_rxb.bin`: sum16
     `F818`, SHA-256
     `820a16ad70abe32440c48194bb0360fa756e26af76706b60f7556a69757b7528`, md5
     `a8e7dad5ad45949c089a501f46d055f9`. 9 hook tests pass.
   * **Stuffing sense (candidate hypothesis, implemented 2026-09-20):** if
     candidate flag `7E` uses normal HDLC, the candidate data stream requires
     **zero-stuffing** (a 0 after five 1s), not the Micronic's inverted
     one-stuffing. The Arduino zero-stuffs when its flag axis selects `7E`.
     This is adjustable stimulus generation, not receive-direction evidence.
     `content=2` (`1Fh`) ends in five 1s, so it exercises terminal
     zero-stuffing before a closing candidate flag. Content 4 (`7Fh`) tests a
     longer 1-run within the candidate stream.
   * **Byte capture result (owner, `rxb` hook, 2026-09-20):** the `rxb` hook
     halted on **`I 98 03 DF FF FF`** — `LINK_STATUS=98h` (bit 4 set), **n=3
     bytes captured** (`DF FF FF`). This shows that `rxb` read three bytes
     after its candidate stimulus, not that it identified return framing. The
     captured values do **not** match the sent `1Fh`: this hook reads `LINK_RXD`
     (4Eh) **without the stock arm sequence** (`Link_BlockRx` arms at
     `ROM00:33A6` before reading), so the bytes may be misaligned/raw, from a
     different source, or otherwise unrelated to the candidate framing. Next:
     mimic the stock arm (or hook the stock dispatcher's exit) to capture the
     frame cleanly, and add a `7Fh` content to exercise candidate zero-stuffing.
   * **`rxb2` hook built (2026-09-20):** instead of reading `LINK_RXD` itself,
     it calls the stock `Link_BlockRx` (`ROM00:3378`) so the full RX arm runs
     first, then prints `I ss a b0 b1 b2` (`ss` = post-call CTRL shadow, `a` =
     `Link_BlockRx` return code, `bN` = frame bytes). Image
     `micron1_stockhook_rxb2.bin`: sum16 `ECA2`, SHA-256
     `63c9072732db0f010601c2c942ef7791033ef589804041611efa5438f0a7c189`, md5
     `17f3d1275e2c7a8b7bd9f093ab11c0bc`. 10 hook tests pass.
   * **`rxb2` result (owner, 2026-09-20):** halted on **`I 08 EC 06 00 E4`** —
     post-call `LINK_CTRL` shadow `08h` (bit 3 — odd, the firmware never writes
     it), **`Link_BlockRx` return `A=EC` = protocol error** (from
     `ROM00:341C`: LINK_STATUS bit 3 set, or a length mismatch), buffer bytes
     `06 00 E4`. The hook result does not identify a received flag, frame, or
     payload; the earlier descriptor-as-payload interpretation is withdrawn.
     `content=2` was a candidate bare `1Fh` after the candidate flag. Next:
     send a complete candidate frame — `content=6` = flag + address `03h` +
     `ACK_FRAME` body + flag (`RX_NARROW_AXIS 2` sweeps contents 0/1/2 → maps
     `{flag, flag+03h, flag+03h+frame}`).
   * **Narrowed content run (owner, axis 2, 2026-09-20):** the hook did
     **not** fire — the handheld kept polling. But note the content map:
     `rxContentMap = {0,1,6}`, so the log's `content=2` **is `buildReply(6)`**,
     i.e. the full candidate frame (flag + `03h` + `ACK_FRAME` + flag). The
     differing outcomes in similar candidate-stimulus runs leave the cause of
     the hook observation open. Also: `Link_BlockTx`/`Link_BlockRx` contain no
     observed software FCS/checksum accumulation. That does not rule out
     controller-level wire check bytes or identify the cause of `EC`; physical
     return-frame check bytes remain OPEN. **Two things to fix:
     (a) reliable latch — phase-lock the reply to the handheld's cell grid
     (`sweepClock=1`); (b) frame must mirror the firmware's own frame
     (address + length + body), which should be taken from the harness's own
     initial TX (`03 15 00 01 01 7f ... 05`).
   * **Lead-in + handshake candidate built (2026-09-20).** The Arduino reply
     copies the handheld-transmit capture's **4-5 clock-only lead-in** before
     its candidate flag (`RX_LEAD_CELLS 5`; the handheld's bursts carry it too
     — its framer's pipeline flush). Content index 2 builds a **candidate
     Commstar type-2 control ack** (`buildReply(7)`): wire = flag `7E` +
     zero-stuffed(`00 07 00 02 01 43 00 00 02 01`), i.e. frame
     `[u16 len=7][type=2][seq=1][id=43h][spare][payload 00]` + trailer `02 01`.
     This is a candidate for the return handshake `Link_BlockTx` waits for;
     the receive convention remains unconfirmed. Sketch: `RX_NARROW 1`, axis
     2, flag `7E`, phase −2/8, pol 0, lead-in 5. All mode configs pass the host
     `-fsyntax-only` check.
   * **Transport trace (2026-09-20) — what reacts to which bit.** `Link_BlockTx`
     (`ROM00:3277`) gates on `LINK_STATUS`, in order: bit 7 `TXRDY` (flag write, prelude
     write, and every payload byte), **bit 4 `RXBUSY` clear** (`32B8`, before
     the arm — timeout `EBh`), **bit 6 `HSBUSY` clear** (`32F0`, after the arm —
     timeout `EEh`), then bit 6 again after the closing flag, then bit 5
     (`ECh`). The link IRQ (`31B6`): **bit 4 set → `LinkRxDispatcher`
     (receive); bit 4 clear → re-arm `LINK_CTRL` 6/7 (idle)**. The candidate
     `7E` stimulus coincided with bit 4, but cannot assign that result to a
     flag or identify the receive path's physical convention. **`bit 6` is the
     TX handshake and the cause of its clearing is still OPEN.** The type-2
     ack remains a candidate frame; the RX validator's structural requirements
     do not establish that this stimulus meets them. **Right instrument for
     the handshake: the `bit6` hook (`micron1_stockhook.bin`) plus adjustable
     Arduino stimuli** — it shows directly whether bit 6 clears.**

3. **Phase 3:** bidirectional payload with `micronic.peer.CommstarPeer`.

4. **Keep the existing remaining hardware items** (4Bh/4Ah electrical mapping, complementary port state + EXT STORAGE ADAPTER attachment point — owner confirmation — banked-RAM dump, Z80-bus fallback).

Process: `docs/static-analysis` (PR #15) merged to `master` 2026-09-20; the documentation-review follow-ups (PR #16, #17) also merged. `ir/8-transmit-arm` (PR #14) rebased to code-only (3 commits, `analysis/` only, tests pass) and awaiting merge.

### Detailed and historical backlog

The items below retain evidence and completion history. They are not the
current priority order; the concise lists above are authoritative.
5. **Examine the queued work-item system** — **DONE (2026-08-25,
   delegated analysis, applied + saved).** The FD5C queue is a 10-slot
   countdown-timer/callback table serviced from the RTC wake path, not
   an IRQ dispatcher: RTC_WakeReasonFetch (2206) → Comms_WorkItemSweep
   (224C) → Comms_WorkItemDispatch (2275); register/cancel =
   Comms_WorkItemRegister (2189, CY=full) / Comms_WorkItemCancel (21BA;
   listing shows 3 INC IX but bytes are 4 — stride is 4, do not
   "fix"). ExtBus_BusQueueWorkItem (135C, re-arming poll timer f9ae → 5
   ticks) / ExtBus_BusPoll (12EC; no-edge path has an OPEN weird DI
   fallthrough at 1328). RtcAlarmRegWorkItem → RTC_AlarmSleep (21EC,
    pure-timer + HALT-poll on FD4D, caller Bdos_InternalTimedWait 1129).
   FUN_ROM00__35c9 → Sound_Off (2Bh write; quiet-bus before 2Dh
   timing, LIKELY). Plus created RTC_AlarmDateMatches (223E, formerly
  `Link_StatusCompare_FD4B`) and
   Update remaining OPEN bits: meaning of fd84/RegB runtime bits;
   fbc9 bit0 → fn03 staging link; whether the alarm handler also
   writes FD4D directly.
   Also named from the repair batch + loaded-symbol recovery: the ROM01
   UI survivors (see item 6) and UI_PostDescriptor (6633, posts
   descriptor's first byte as command id into ram:e0b2).
6. **Define the orphaned ROM01 code gaps as functions** — **DONE
   (2026-08-25, all three ranges, diff-guarded).** 03C3-0740: bogus
   0465/052f/05dc removed, 06d3 discovered. 1D79-2115: two
   no-return-continuation guards (inline cmd tables after `CALL
   ram:e0b2` SessionCommandDispatch at 1F96/6B40/6E64) cleared via a
   listing script before the repair; discovered 1E0A, 1FB5 (+thunks
   1E9E/1ECB), 2047; one named loss (UiOpenSaveDialog 1ADD) restored
   with a recovery plate; noise "SessionCommandDispatch" function
   auto-created at 1F96 deleted. 67CA-6F28: bogus 67ca removed;
   discovered 6B53, 6B9B, 6CB2, 6E77; ram losses da4c/dc69 restored.
   NEXT: name the survivors (research/gap-analysis.md lists them).
7. **ROM01 / UI survey for `fbc5` and `fbc2` writers** (review §6.3) and
   **`fbc7/fbc8` consumers** (§6.4, BDOS fn F9 presets) — likely a
   "device" settings screen in ROM01. **CLOSED 2026-08-24 (§6.2)**: the
   reader-completion event bit is `fbc9` bit0, posted by
   `ExtBus_BusComplete`(14A3)→`Link_ResetSession`(30BD); that wakes the
   fn-03 `Link_WaitForLink` HALT (see manual/barcode-reader.md).
8. **Residual inverted-dispatcher doc claims — CLOSED 2026-08-28.** Active
   documentation now uses the corrected model: fn <25h -> F1EB; F3h-FFh ->
   F1D1 wrap via DEC B; unmatched 25h-F2h -> wild pointer, nothing rejected.
8a. **6e77 inline-data repair — DONE 2026-09-17.** The four inline operand
    spans in `Session_EvalRecordSteps` (`ROM01:6E77`) are now defined as
    `uint` data and labelled `tbl_corstep_0`..`3` (`ROM01:6E81`, `6EA5`,
    `6EB4`, `6ED1`); flow resumes correctly at `6E85`/`6EAA`/`6EB8`/`6ED5`.
    The inline bytes are the operands of the `CALL DC37`/`DC23`/`DC30`
    frame-op idiom (consumed 4-byte parameters).  Function count unchanged
    (1101) and the program was saved.  See the 2026-09-17 session entry.
8b. **ram:pending compiler-runtime page — label + plate DONE 2026-09-17.** All
    helpers are already labelled (`Lib_And16` `e023`, `Lib_Not16` `e02b`,
    `Lib_Or16` `e033`, `Lib_Xor16` `e03b`, `Lib_Lnot16` `e043`, `Lib_Eq16`
    `e04b`, `Lib_Ne16` `e05a`, `Lib_SignedLe16` `e06a`, `Lib_SignedGe16`
    `e06b`, `Lib_SignedGt16` `e085`, `Lib_SignedLt16` `e086`, `Lib_Neg16`
    `e09f`, `Lib_Sub16` `e0a9`, `Lib_Unsigned*` `e0d9`/`e0da`/`e0e7`/`e0e8`,
    memmove at `ram:d9a0`).  Plates added for the two that had none
    (`Lib_Not16`, `Lib_Neg16`); the trivial logic ops carry SHORT-form plates.
    **RESOLVED 2026-09-19 (CONFIRMED):** `ram:DA13`
    session-to-BDOS bridge closes the `6A36`
    constructor / `6AA9` stream-reader mapping;
    former `da13` OPEN superseded (see Next
    priorities and 2026-09-19 session entry).
8c. **Static writers of d2dc/d2de (06d3 globals)** and of the EA14/
    EA1C chunk-state blocks — not in defined code post-repair;
    re-check after the thunk-sweep and get_callers pass.
9. **Stale manual/barcode-reader.md leftovers** — **DONE (verified 2026-08-27):**
   manual/barcode-reader.md H1 and the "What a symbology decoder does" section
   no longer carry the stale "(was ...)" / "(if this is a light-pen)"
   wording. NOTE: protocol/commstar.md §400 still titles the external-device
   bus "(was "barcode/light-pen")" and §434 asserts "no barcode strings" —
   that predates the owner adjudication and needs a separate review pass.
10. **Name `FUN_ROM00__35c9`** (the quiet-bus helper in the capture
     path, review §2.3) during the work-item-queue analysis (item 5).
11. **Decode the error-screen format** — **DONE (2026-08-27, see
     protocol/commstar.md "Error / status screen format").** Owner observed
     "Error 8000 (238/001) Plinth not connected". CONFIRMED: 8000 = major
     error qualifier (literal 0x1F40, or 0x1F41=8001 for the 0x0009 case),
     NOT the e488 code (6); the "(238/001)" pair = RCV1/RCV2 session
     status fields from e701/e6ff (3-digit zero-padded), template at
     ROM00:7310 (tbl_sess_status_fmt) with field names RCV1/RCV2/SEND/
      LOAD/PROG/TIME/ENDC. Open: runtime meaning of RCV1/RCV2 (SUSPECTED
      receive counters; writer trace agent looped - still open) +
      FileSearchNextCb renamed Lib_DecU16 (2026-08-27, below).

### 12. FINAL PASS — complete annotation + naming cleanup (defer
    until the reverse-engineering is done; owner-decision
    2026-08-27)

    One coordinated sweep at the end, not piecemeal ad-hoc
     patches. Baseline 2026-08-27: 935 functions, 131 still
     `FUN_*`, 27 dispatch tables. Status 2026-09-19
      (Ghidra saved; raw-address cites migrated —
      137 + 127 rewrites, missing-label scan 99 → 90
      created; no new inference in this docs pass):

    1. **Name + plate every `FUN_*` — DONE** (see
       `research/gap-analysis.md`; 914 internal / 915
       guarded, 4 retained `FUN_*` with plates and
       documented open questions; 99.6 % named).
    2. **Rename wrong or grandfathered names**
       a. **Grandfathered `Module_Name` churn —
          DONE 2026-09-19 (590 names → 31-module
          taxonomy; 588 applied in Ghidra + 2
          already-renamed collisions; word-boundary
          doc sync across 24 files, commit
          `993a45d`; CONFIRMED):** canonical 31
          modules `Session_` `Bdos_` `Fs_` `Lib_`
          `Link_` `UI_` `Syscall_` `Field_`
          `RegFile_` `Lcd_` `Program_` `Disk_`
          `Tty_` `RTC_` `ExtBus_` `Diag_` `Kernel_`
          `KernelImage_` `Kbd_` `Device_` `Dialog_`
          `Text_` `Comms_` `Clock_` `Power_` `Util_`
          `Coroutine_` `Monitor_` `SelfTest_`
          `Sound_` `Fcb_` `Form_` `Boot_`
          `Barcode_`; normalizations `Kern*`→
          `Kernel_`, `Rtc*`→`RTC_`, `Ui*`→`UI_`
          (owner choice, uppercase per AGENTS.md
          §7), `lcd_*`→`Lcd_`, `tty_*`→`Tty_`,
          `dialog_*`→`Dialog_`,
          `session_*`→`Session_`,
          `Coro*`→`Coroutine_`,
          `Keyboard*`/`Key*`→`Kbd_`,
          `Reg*`→`RegFile_`, `Self*`→`SelfTest_`;
          reassignments `Banked*`→`Kernel_`,
          `Console*`→`Device_`, `Delay*`→`Util_`,
          `Str*`/`Arith*`/`Bcd*`/`Checksum*`/
          `Format*`/`Num*`/`Pack*`/`Table*`→`Lib_`,
          `BlockAlloc*`/`FileSearch*`→`Fs_`,
          `StateWord*`/`CmdDispatch*`→`Session_`,
          `ServiceCall*`/`thunk_*`→`Syscall_`,
          `Nop*`→`Diag_`, `TemplateBuilder`→`Form_`,
          `Port2b*`→`Sound_`,
          `ExtDecodeHook*`→`ExtBus_`,
          `Descriptor*`→`UI_`; do-not-regress
          identities preserved (`RTC_`, `Link_`,
          `Session_`, `ExtBus_`); protected exact
          names kept (`BankedRst08/20/28/30/38`,
          `Rst2Dispatch`/`Rst4IrqPoll`/
          `Rst5FatalScreen`/`Rst6ZeroRet`/
          `Rst7IrqPoll`, `ColdStartSelfTestBanner`,
          `LinkRxDispatcher`).
       b. **Wrong names — DONE 2026-09-19 (5, byte-
          verified, docs synced):** `ROM00:3BB8`
          `Coroutine_TaskSwitch` → `Coroutine_IndexedLookup_6A4A`
          (indexed lookup into table at `6A4A`; real
          `Coroutine_Enter` is `ram:D837` — duplicate
          mis-name corrected; `ram:D837` later renamed
          `Coroutine_Enter` 2026-09-19), `ROM00:3BD0`
          `Coroutine_SessionMul16` →
          `Coroutine_IndexedLookup_6B67` (into `6B67`),
          `ROM00:7C14` `Session_Cmp16Bit` →
          `Session_CmpLeU16` (HL=1 iff HL<=DE unsigned),
          `ROM00:7C22` `Session_Cmp16BitB` →
          `Session_CmpGtU16` (HL=1 iff HL>DE unsigned),
          `ROM01:6F29` `Syscall_Call_Id2Byte` →
          `ServiceCall_BdosFn2` (calls `Session_BdosCall`
          `ram:DA13` with fn 2). Grep confirms 0 stale
          mentions in `doc/`.
     3. **Plate-quality pass — DONE 2026-09-19
        (CONFIRMED, Ghidra saved; function list
        unchanged; plate coverage 100 %):**
        - **Unplated functions — DONE 2026-09-19:** all 144
          functions with `plateLen=0` now carry plates (46
          `ram` — mostly `SessionOpStub_*`/`Lib_*`/`RegFile_*`,
          notable `Fcb_ParseFilename` CP/M FCB parser,
          `Kernel_RunStagedCall` — 33 `ROM00`, 65 `ROM01`);
          no function renamed/created/deleted in that batch;
          plate coverage is now **100 %** (no function lacks
          a plate; CONFIRMED).
        - **Short plates — DONE 2026-09-19:** all 141 plates
          <120 chars reviewed against §8 — **82 KEEP**
          (genuinely trivial — math primitives,
          comparators, simple port I/O, single-RET stubs,
          RST vectors, constant-return helpers, simple
          RAM-cell setters, no-op coroutine stubs) and
          **59 UPGRADE** to the full form
          (brief/mechanics/In-Out-Clobbers/evidence tag,
          ~70 cols, multi-line ASCII; 59 applied in Ghidra;
          function list unchanged; saved). Typical
          upgrades: `Lib_MemMove`, `Bdos_PreparedCall`,
          the `RegFile_*` 32-bit math, `Lib_Mulu16`/
          `Mul16Mod16`, session buffer ops
          (`Session_TxFlush`, `Session_RxRefill`,
          `Session_TxAppendByte`, `Session_RxConsumeByte`),
          TTY key handlers, LCD helpers, message-box
          displays, link init/timeout, clock repack, UI
          descriptor-chain ops. **Item 3 is now DONE** —
          plate coverage 100 %, no SHORT-form plate
          remains that §8 would reject (CONFIRMED).
        Fix plates that contradict their own names and
        re-flow to ~70 cols was done as part of that
        review.
     4. **Comment-style pass — CLOSED 2026-09-19
        except one OPEN label (CONFIRMED; no new
        inference):** of 895 instruction comments, 356
        carried raw-address-like tokens — 137 REWRITE
        (first pass, RAM cell / I/O port cited by
        numeric address → descriptive label; all 137
        applied in Ghidra; function list unchanged;
        0 new labels needed) and 219 KEEP (value/mask,
        legitimate cross-reference, or label already
        present). Second pass found **127** further
        comments still containing a numeric address
        cite resolving to a labelled address
        (secondary cites left by the first pass plus
        others) — all 127 rewritten: every address
        cite replaced with its descriptive label,
        remaining magic numbers / bit masks decoded
        in place, opcode-restating text dropped;
        function list unchanged; saved; no new
        labels needed. Missing-label scan found
        **99** distinct descriptive labels cited in
        comments with no Ghidra symbol; **95**
        resolved to concrete addresses (from
        referencing instructions +
        `memory-map.md`/`unbanked-ram-map.md`);
        **90** created as labels in Ghidra (6 already
        present); function list unchanged; saved
        (CONFIRMED). **Residual closed 2026-09-19
        (CONFIRMED, Ghidra saved):** 3 of the 4
        SUSPECTED labels pinned — `g_bRxRingHead`
        already at `ram:F954` (verified, skipped;
        supersedes `g_bEchoChar` SUSPECTED at same
        address), `g_bLinkCmdShadow` created at
        `ram:F796` (port `4Ch` `LINK_CMD` shadow;
        supersedes `g_bIrStrobeShadow` SUSPECTED at
        same address), `g_bOutputCount` created at
        `ram:FEA3` (supersedes `g_bOutputCount`
        SUSPECTED `F998` — correct address is `FEA3`
        per byte-verified reference);
         `g_wCoroutineStepResult` — **RESOLVED
          2026-09-19 (CONFIRMED): not a fixed RAM
          address.** It names the buffer pointed to by
          `g_pCoroutineStepResultBuf` at `ram:EA24`;
          one writer `ROM01:6DF6 LD (0xEA24),HL` (HL
          from `ROM01:6909` → `Coroutine_Enter`)
         and six readers in `Fs_SeekByteOffset`
         (`ROM01:6DDF-6EED`); layout `+1` = 16-bit
         step-1 result, `+3` = 16-bit step-2 result,
         `+0` unreferenced; `ram:E73E` has zero refs
         program-wide — E73E hypothesis **refuted**
         (CONFIRMED). `g_pCoroutineStepResultBuf` at
         `ram:EA24` carries a repeatable comment and
         four EOLs at `ROM01:6E8F`/`6E9E`/`6EBB`/`6ED8`
         now use the `[*(g_pCoroutineStepResultBuf)+N]`
         form; no function renamed; saved.
         **`Boot_entry+1` bug — FIXED
        (CONFIRMED):** 7 comments corrected at
        `ROM01:1ea1`, `1f96`, `28bb`, `2b7b`, `2c95`,
        `3acb`, `ram:d777` — each cited `Boot_entry+1`
        to mean `0001h` (wrong; `Boot_entry` is
        `ROM00:014b`, so `Boot_entry+1 = 014c`);
        rewritten to `0001h` (intended page-zero cell;
        note CP/M IOBYTE is at `0003h`, not `0001h`).
        3 non-buggy uses of `Boot_entry` retained
        (range marker / state name). **Magic numbers
        — 5 decoded (CONFIRMED):** applied at
        `ROM00:15c4`, `02e5`, `02f1`, `0f37` (PRE) and
        one more — `0x80` = local-console flag, `10h`
        = 16-drive guard, `12h`/`01h` = key scan codes,
        coroutine step-zeroed slots (per-site as
        applied); 12+ comments kept as already
        adequately explained; one intended fix at
        `ROM01:6e8b` had no comment present — skipped
         (CONFIRMED absent). `bdos_entry_impl`
         proposal for `ROM00:F180` — **REJECTED**
         (CONFIRMED, byte-verified): `ROM00:0005` is
         `C3 80 F1` = `JP F180` outside `ROM00`'s
         `0000h..7FFFh` window → target is `ram:F180`
         (`Bdos_DispatchFn`, existing label); phantom
         `ROM00:bdos_entry_impl` was wrong-space; comment
         now `JP Bdos_DispatchFn (ram:F180) vectors
         into the DIPOS kernel (battery RAM)` — not a
         §12 item and now closed (Ghidra saved).
         **CAUTION (CONFIRMED):** 2-digit hex in
        RTC contexts is ambiguous — RTC register index
        (`01h`/`03h`/`05h`/`07h`) is not I/O port `07h`
        = `CTRL_07` (`RTC_ADDR`/`RTC_DATA` are
        `08h`/`28h`); both passes corrected these
        manually — note this hazard for any future
        comment edit. **Review note (CONFIRMED):**
        comment at `ROM00:0178` said "keyboard scan
        init" but the confirmed plate at `Lcd_Init`
        (`ROM00:1EEC`) says LCD subsystem init, so
        the old comment was factually wrong and was
         corrected. **Item 4 is now fully CLOSED**
         — no OPEN labels remain; items 1, 2a, 2b, 3,
         5, 6 are DONE (CONFIRMED). The
         `g_wCoroutineStepResult` pointer-indirected
         buffer is the final closure; E73E hypothesis
         **refuted**.
     5. **Data-typing backlog — DONE 2026-09-19
        (CONFIRMED, Ghidra saved; function list
        unchanged — 915; no new inference).** Types +
        labels created: `ROM01:7545` `ushort[4]`
        `tbl_UiCfgRegionPrefix`; `ROM01:757F`
        `ushort[6]` `tbl_UiCfgNamePointers` (5 name
        pointers + `0000` terminator — the earlier
        `ushort[136]` estimate was corrected);
        `ROM01:758B`/`75EB`/`760D` each typed
        `UiCfgHeader` (new 20-byte struct:
        `EC EF F8 F0 98 EF D8 EF` magic +0..+7,
        fields, LE backlink +12h) as
        `tbl_UiCfgTemplateHeaders` (non-contiguous,
        so individual items); `ROM01:79F4`
        `char[1547]` `str_cfg_option_pool` (existing
        label kept); `ROM00:7C30` `byte[256]`
        `tbl_FontCharWidth` (note `7C50` is offset
        +0x20 within it, not a separate table);
        `ROM00:7D80` `ushort[4]` `tbl_StubTablePrefix`;
        `ROM00:7D88` `ushort[60]`
        `tbl_SessionRuntimeStubSources` (renamed);
        `ROM00:7E50` `ushort[34]`
        `tbl_FnPtrDispatch7E50` (FFFF-terminated);
        `ram:E105` `byte[256]` `g_abFontCharWidth`;
        `ram:D0E0` `byte[448]` `g_abErrorStringTable`;
        41 dispatch-table labels created (16 `ROM01` +
        25 `ROM00`), all `tbl_Dispatch_<name>` —
        previously only 1 of 41 sites had a `tbl_`
        label; 11 plate/repeatable comments set.
        Function list unchanged (915); saved. The
        `ushort[136]` estimate for `757F` and the
        `7C50` separate-table claim are superseded.
     6. **Refresh `research/gap-analysis.md` — DONE
        2026-09-19** (single coverage tracker; headline
        914/915, 99.6 % named; plate coverage updated
        2026-09-19; data-typing + annotation tail
        refreshed 2026-09-19).

    Sequencing: one Ghidra-writing agent at a time,
    `save_program` between, and diff-guard the function
    list each batch (§11). Hold until the remaining open
    items are resolved, so we annotate the final picture
    rather than a moving target.

        **Remaining scope after 2026-09-19 (§12 FINAL
          PASS fully CLOSED):** **no OPEN items remain.**
          Items 1, 2a, 2b, 3, 4, 5, 6 are **DONE** — the
          `g_wCoroutineStepResult` pointer-indirected
          buffer (`g_pCoroutineStepResultBuf` at
          `ram:EA24`, `+1`/`+3` 16-bit results; E73E
          **refuted**, zero refs) was the final OPEN
          label. The `bdos_entry_impl` proposal for
          `ROM00:F180` was a non-§12 item and is now
          **REJECTED** (CONFIRMED) — `ROM00:0005` is
          `C3 80 F1` = `JP F180` outside `ROM00`'s
          `0000h..7FFFh` window → `ram:F180`
          (`Bdos_DispatchFn`, existing label); phantom
          `ROM00:bdos_entry_impl` was wrong-space; Ghidra
          comment now `JP Bdos_DispatchFn (ram:F180)
          vectors into the DIPOS kernel (battery RAM)`;
          no new label needed — §12 remains fully
          CLOSED and the page-zero cleanup below did not
          reopen it.


## Owner corrections to honor


- 4x ports (4A/4B/4C/4D/4F cluster) are NOT the RTC (twice-confirmed)
- No serial EEPROM; serial number is user-entered at banner after
  battery removal, stored at FEAB
- Hardware only has 08/28 as an obvious address+data latch pair.


## Do not regress


- 08/28 device is the RTC: keep Rtc* names (RTC_RegWrite/RTC_RegRead/
  RTC_Init/RTC_WriteTime/RtcSetTimeFromBuffer/RTC_ReadRegisterFile).
- 4x cluster is the external data link: keep Link* names
  (Link_BlockTx/Link_BlockRx/Link_TransferService/Link*). No RTC or
  "comms" naming there.
- RST vector 0010 = Rst2Dispatch (banked dispatch), 0020/0038 =
  Rst4IrqPoll/Rst7IrqPoll, 0028 = Rst5FatalScreen, 0030 = Rst6ZeroRet.
  ROM01 0008/0020/0028 = BankedRst08/BankedRst20/BankedRst28.
  Cold start 01BE = ColdStartSelfTestBanner; 2FBD = LinkRxDispatcher.
- RAM 32-bit session math opcodes keep Session* names (SessionAdd32/
  SessionNeg32/SessionTestCarry/...); empty dispatch slots keep
  SessionOpStub_<addr>.
- External-device bus naming (2026-08-24): port 2Dh = `EXTBUS_EDGE`;
  the 120F-14EE handlers stay `ExtBus*` (ExtBus_BusArm/ExtBus_BusAcquireEdge/
  ExtBus_BusComplete/...). The user **decode-hook socket** keeps neutral
  labels: `fbc0` = RST10 stub, `fbc1` = bank byte, `fbc2` = hook ptr;
  `ExtBus_DecodeHookInstall` (156E) / `ExtBus_DecodeHookDiscard` (1567)
  default it. **SUPERSEDED by owner adjudication (2026-08-24, AGENTS.md
  §3): the side port was used with a barcode pen; the 2D edge-capture
  subsystem IS the barcode reader front end, and `Barcode_` is the
  module prefix for NEW names there.** Existing `ExtBus*` names are
  grandfathered until a deliberate rename pass; do NOT flip back to
  `Reader*`, and do NOT reassign the disproven "EXT STORAGE ADAPTER"
  identity. `Bdos_ReaderInChar` (1080) is genuinely the CP/M fn-03 RDR
  path either way.
18. **Annotation coverage tracker**: **593/593 (100%) named** (Pass A
    complete as of this session). All ROM00 + ROM01 + RAM kernel stubs
    carry meaningful names. Highlights of the closing batch:
    RST vectors ROM00 0010/0020/0028/0030/0038 = Rst2Dispatch/
    Rst4IrqPoll/Rst5FatalScreen/Rst6ZeroRet/Rst7IrqPoll; ROM01 banked
    thunks BankedRst08/20/28; cold start ROM00:01BE =
    ColdStartSelfTestBanner; link RX ROM00:2FBD = LinkRxDispatcher;
    ROM01 field/dialog layer = Field_SelectWalk/Field_ConfigLoad/
    Session_FieldEditLoop/Lib_ToNumberParse/Lib_Accumulate/
    Lib_TableLookup/TextOut*; RAM dispatch slots SessionOpStub_*.
    The only auto created `FUN_ram_8c0c` was a false positive over a
    zero buffer (spurious CALL from a jump-table byte) — deleted.
19. **DIP program format documented** (manual/programmer-guide.md §7b +
    internals/os-diposb.md): DIP = block-structured loader-record stream, same
    grammar as the boot chain (fn 0 copy / 1 move / 2 queue-banked-call
    / FFFF term, bank-tagged); COM = plain single image. Advantages
    (multi-bank, init calls, streamable, diagnostics) vs. .COM; exact
    DIP on-disk header left as live-capture item. Loader primitives
    (D6FA/D713/D727/D7F0/D800) annotated to Pass A+B incl. record-walk
    inline comments + Kernel_DispatchEntry plate.
20. **Pass A COMPLETE (100%)**: all 593 functions named. Pass B
    (inline comments) started: io:00xx ports labelled + repeatable
    comments; RTC/LCD/link hardware EOL+pre comments use datasheet
    names (Reg B PIE/SET/24h, Reg A DV/RS, LINK_CTRL/LINK_STATUS bits).
    **Comment style rules (audited + enforced)**:
      * Short single-fact notes stay EOL.
      * Multi-clause/register-list/para explanations go in **Pre**
        comments, width-wrapped (~70 cols), one bit/field per line.
      * All long EOL comments converted to Pre (82 -> 0): HELP-key
        decode (018E), reset vector block 0000-0044, cold/warm restart
        entries, RTC Reg A/B bit-breakdowns, delay/monitor/TTY routing,
        link frame-validate/command-lookup/slot/descriptor functions.
    Further Pass B coverage this session (Pre comments, datasheet
    names): BDOS entry dispatcher (36A0 + specials 2D/2E/30/62/68/69),
    console device I/O (0DE9/0E00/0F37/1166/1170), CP/M line editor
    (117B), Tty_out_char control dispatch (1BEB), select-disk (15B3),
    DMA set (0CEC), RTC get-time (113E), alarm work-item queue
    (2189/21BA), date-rollover (222E/223B), drive valid (0824).

* Structural model 2026-09-18: inline-switch `JP(HL)` cases are blocks,
  not functions — do not re-split the Part B merges.
* Hybrid label model 2026-09-18 (ROM01 14 + ROM00 25 sites,
  CONFIRMED): inline-switch cases are basic blocks of the owning
  routine kept as one function; navigation via labels (not
  functions) — do not re-create case blocks as functions.
* Superseded names above (`3a1c`/`3b53`/`3b7a`/`581f`/`5991`/`62a9`/
  `62b6`/`62ca`/`66ec`/`6707`/`6b0d`/`6b53`) were case blocks; do not
  recreate as functions. The `257f` handlers (`2569`/`2572`/`257b`/
  `2593`) are blocks of `254b` → `257c` → `2593` → `2658`; do not
  recreate.
* `ROM01::3add` `FieldPadValue` is a mid-instruction banking artifact
  (`ROM01::0044` → `ROM00::3add`), not a ROM01 function — do not
  recreate.
* ROM00 dispatch owners (CONFIRMED, 2026-09-18): 23 routines
  `3ede-3f1f`, `3f20-4009`, `4563-46e8`, `46e9-47f5`, `47f6-48be`,
  `48bf-4973`, `4974-4a24`, `4a25-4adf`, `4ae0-4d28`, `4d75-4e6c`,
  `4e6d-4f59`, `4f5a-5033`, `5034-50ec`, `50ed-5178`, `5179-51eb`,
  `51ec-52a4`, `52a5-5427`, `5469-54e4`, `5542-5668`, `56e7-573c`,
  `573d-578e`, `578f-5829`, `59fb-5b57`, `5f58-606b`; sites 8+9 and
  17+18 share owners as above; site-1 is `3f20` (not `3ede`);
  residual `FUN_*` = `2da5`, `4333`, `441b`, `44ed`, `450d`
  (deferred) — do not re-split or recreate the ~89 absorbed
  case-block functions.
* Process — Ghidra function-body extension (CONFIRMED, 2026-09-18):
  `create_function` cannot extend a body past a computed jump;
  body extension must use Ghidra's `Function.setBody(AddressSet)`
  (script), and `FunctionManager.removeFunction` takes an entry
  **Address**, not a Function. The ROM00 pass was saved only after
  a manual `setBody` completion — the annotate stage had left
  owners as 6-byte shells and 2 epilogue functions were briefly
  lost, then recovered by the extension. Do not use
  `create_function` to grow a hybrid owner.


## Open questions

> Historical/resolved open questions have been moved to
> [`session-log.md`](session-log.md) (see `## Resolved open questions`).

* **Remaining (OPEN) — updated 2026-09-20:** analytic work is
  complete — §12 FINAL PASS fully CLOSED 2026-09-19. **4 retained
  `FUN_*`** (ROM00 1, ROM01 2, ram 1) carry plates and are
  documented as dead or reachable-unknown; see
  [`gap-analysis.md`](gap-analysis.md) for the current coverage
  figures and [`session-log.md`](session-log.md) for the resolution
  history. All remaining work is owner/hardware-dependent — see
  *Hardware-dependent priorities* above.

---

Historical session log: see [`session-log.md`](session-log.md).
