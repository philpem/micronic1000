# IR feedback automation test plan

This is the bench worksheet and rationale for the implemented combined
feedback harness after [PR #21](https://github.com/philpem/micronic1000/pull/21).
The canonical command, timing and 30-byte result-record contract is
[IR feedback harness interface](ir-feedback-protocol.md). That interface,
rather than this historical design record, controls a burn.

## Scope

The feedback-v1 ROM and Uno controller provide one reusable trial controller:
explicit black-input
commands between IR trials, output markers during a trial, a positively silent
control, and LCD/serial/scope-correlated status and raw-RX observations. The
single burned image must not fix the Arduino stimulus framing, timing, payload
or LED roles; those are Arduino USB-configured hypotheses. Stock controller
ordering and bounded ROM wait times remain explicit constraints. First correlate stock-order
`LINK_STATUS` bit-4/bit-6 gates, then run bounded RX. Exclude peer/transfer automation.

## CONFIRMED starting facts

| Fact | Evidence to retain in the plan |
|---|---|
| The top V24 route has wire-ID bit 5 clear, `LINK_CTRL` bit 1 set, and port `2C` bit 5 set. | Existing ROM/emulator/owner evidence in [Commstar evidence](commstar-evidence.md). |
| The stock-order witness polls `LINK_STATUS` bit 4 before its arm and bit 6 after it; a bit-4 timeout skips the arm and its teardown is ordered. | Current witness documentation in [exerciser test plan](exerciser-test-plan.md). |
| No-peer stock-order testing left `LINK_STATUS` bit 6 set. | Owner hardware observation; it supports a peer-handshake question, not a controller identity. |
| Arduino source names D5 `CLK_OUT` and D6 `DAT_OUT`; their physical LED channels are unassigned. | Current sketch/README. Label physical channels A (D5) and B (D6) until scoped. |
| Black changes raw port-`2D` bit 0 with the tested gate: `2Ah` bit 1 high and `2Ch` bit 5 low, including `2A=22h`, `2C=00h/02h`. | Owner connector-v2 measurements. |
| Yellow is a `2A` bit-0 sink/release output; the owner reported 200 mA sink current. Red is `2A` bit 4 output. | Owner measurements in [connector experiment](connector-experiment.md). |

Stock `Link_PortSelect` clears port-`2A` bit 1 in both route states, sets
port-`2C` bit 5 for top V24, and preserves port-`2A` bits 0 and 4. Thus stock
IR selection destroys the known black gate. The combined ROM must restore the
black gate only after stock teardown completes, before an input command, and
release black again before the next IR arm. Port-`2A` bits 0 and 4 are candidate
marker controls; their use during IR remains a new bench test.

## SUSPECTED wire choices

`7E` is a candidate return stimulus, not an established flag. The physical LED
clock/data assignment is also unknown. Arduino trials must expose both channel
permutations: A=D5 as proposed clock/B=D6 as proposed data, and the reverse.
Every permutation starts with its own silent control. The serial record names
the physical channels, selected roles, line sense, timing and payload without
calling any of them accepted.

## Electrical boundary

The combined electrical interface has direct-TTL and NPN options documented
in the canonical interface guide. One direct-TTL silent probe has passed;
active IR coexistence remains untested. Red
has measured as high as 5.6 V, so it must not connect directly to an Uno input.
The proposed black command path uses a protected open-drain pull-low/release interface,
validated first at the connector with actual voltage and current measured.
Protection, references, and connector/optical coexistence remain open; the
standalone connector experiment does not prove optical coexistence.

## Implemented harness and validation boundary

`analysis/rom_exerciser/feedback.py` builds the standalone **feedback-v1**
ROM; it guards the stock input and patches only cold boot plus its reclaimed
private program. The ROM defaults to yellow released with the confirmed idle
black gate restored. It accepts black pulse modes W/R/P/G and keypad W/R/P/G,
uses the canonical START/cooldown/result sequence, and returns raw status and
bounded `Link_BlockRx` observations. It does not call any result a received or
accepted protocol frame.

The Uno configuration remains USB-selected hypothesis input. The legacy
`RX_NARROW` sweep records are historical evidence, not feedback-v1's trial
grammar. The host checks currently cover the ROM (32 tests) and result UART
timing/decoding (2 tests). The owner completed the first hardware boot and
direct-TTL silent P transaction on 2026-09-23; its valid result and LCD agree.
See the [raw bench record](ir-feedback-protocol.md#first-hardware-result-2026-09-23).
The subsequent silent W witness returned valid feedback after its arm and
bit-6 timeout. Stimulated W/X trials 3–5 produced the same timeout; trial 5
has a tracked digital scope capture. That capture exposed significant Uno
emitter timing distortion, so protocol conclusions remain pending. The
emitter has now been revised. Trial 6's physical scope capture meets all
stated digital timing targets, but W still returns bit-6 timeout/error 6 and
does not attempt RX. Trial 7's swapped silent control correctly emitted no
pulses; trial 8's swapped stimulus met digital timing targets but left the
same witness timeout. The next controlled comparison is a matched forced-RX
silent/stimulated pair. That pair (IDs 9/10) also returned identical errors:
stock RX `A=EEh`, `F=6Dh`, wrapper error 7. Because error records do not
preserve partial bytes, the next controlled comparison is mode G's
receive-pending gate with the same candidate and its own silent control.
G/S and G/X trials 11/12 with `swap=1` both timed out waiting for
`LINK_STATUS` bit 4. The subsequent comparison changed only to `swap=0`, again
with G silent/stimulated controls, because earlier matched experiments
showed a strong software-role-dependent reaction without identifying a
physical LED or accepted frame. Those unswapped controls (IDs 13/14) also
timed out with identical probe/before/after status A0h/80h/80h. The next
axis was one candidate `03h` payload byte after the opening `7Eh`, keeping
the same G mode, role, timing, stuffing and no closing flag. Matched trials
15/16 again timed out at the pending gate (error 8), with identical
`E0h/C0h/C0h` probe/before/after status. Trial 16 reports 3 us maximum
software lateness, but no scope trace was captured. The exact stimulus
was repeated as ID 17 with the scope connected. It again returned error 8
and `E0h/C0h/C0h`; its tracked Keysight
CSV shows the intended `7Eh 03h` cells at scope D2/D3, 21/21 clock pulses,
8/8 data pulses, with all digital timing targets met. The owner confirms
pod D2→Uno D5 and D3→Uno D6 were unchanged; optical delivery remains
unmeasured. The subsequent comparison was a matched G/S and G/X pair (IDs 18/19)
with `pol=1`, which complements the full frame after logical stuffing.
Both returned error 8 with identical `A0h/80h/80h` status and never reached
stock RX; no trial-19 scope trace was supplied. The next matched pair
(IDs 20/21) keeps this candidate but uses mode R to call stock RX directly.
This tests a different receiver path without changing the burned ROM. Both
returned `A=EEh`, `F=6Dh`, wrapper error 7. Trial 20's probe/before/after
was `E0h/C0h/C0h`; trial 21's was `A0h/80h/C0h`. Thus `LINK_STATUS` bit 6
rose during trial 21's RX call, but the before baselines already differed,
so attribution to optical output remains open. The subsequent matched
mode-R pair (IDs 22/23) delayed emission to START+60 ms as a late-stimulus
control.
Both returned the same `A=EEh`, `F=6Dh` error and identical
`A0h/C0h/C0h` probe/before/after status. Trial 23 scheduled emission at
START+59,808 us with 9 us maximum lateness; both trials began with
`LINK_STATUS` bit 6 set, so the pair did not test whether the bit can rise
without an in-window stimulus. R/X ID 24 repeated the early
START+7 ms complemented candidate and returned `A=EEh`, `F=6Dh`, error 7,
with `A0h/80h/C0h` probe/before/after status, matching ID 21. The
`after` status was C0h in every reported R trial, including silent and
late controls, so the bit-6 rise cannot yet be attributed to optics.
The optical path is the next useful check before more candidate-frame
sweeps. The SFH213 photodiode from the earlier optical capture is now
built into the Arduino transponder, not a separate movable scope probe.
The owner can inspect the LEDs with a camera; a USB-only sustained,
low-duty LED self-test is the next practical output check and needs no
new EPROM burn. The updated Uno sketch adds `V <visual_id>`: A/D5 runs
at 10% PWM for 1.5 s, then B/D6 for 1.5 s, with black released throughout.
It can run from idle without the handheld, and visual IDs do not consume
trial IDs. Upload the updated sketch, send `V 1`, and compare each labeled
interval with idle through a camera known to see IR. This checks emitter
light, not optical power at the handheld's internal detector.
The exact next commands and capture acceptance targets are at the top of the
[canonical handoff](ir-feedback-protocol.md#current-handoff-next-physical-trial).

## Original design, superseded by feedback-v1

The earlier M0--M2 proposal used abstract `SILENT`, `STIMULUS` and `IR_ARM`
states, plus Arduino burst telemetry that does not exist in the current burn.
It motivated the controls but is not an operational interface. Feedback-v1
uses only the concrete W/R/P/G requests defined by the canonical interface:

* **W** runs the stock-order witness and records its bit-4 and bit-6 poll
  outcomes, arm flag, raw status and ordered teardown facts.
* **R** resets/selects then calls the bounded private-descriptor wrapper around
  stock `Link_BlockRx`.
* **P** records the reset/select probe condition without claiming an optical
  stimulus or receive result.
* **G** performs the bounded bit-4-pending condition before the same raw RX
  wrapper.

Current ROM telemetry is the compact LCD result and the fixed yellow 30-byte
record: mode/counter/error, raw probe and status values, witness poll fields,
raw RX A/F/DE and bounded preview, plus final idle-gate shadows and a fresh raw
`2Dh` sample. It does not report a handheld optical-burst timestamp, Arduino
output transitions, scheduler lateness or protocol acceptance.

## Implemented connector commands and markers

The ROM accepts the bounded black pulse encoding defined in the
[canonical interface](ir-feedback-protocol.md) only between trials. After
ordered stock teardown it restores `2A` bit 1 high and `2C` bit 5 low before
permitting the selected Uno direct-TTL or NPN command interface. A physically stuck-low black
input prevents arming after the Uno releases its driver.
Record the complete `2A`/`2C` values, raw `2D`, command result and dwell time.
The concrete release, START and trial sequencing is defined only by the
canonical interface.

Owner-confirmed bridge evidence is limited to **R/D/P**: yellow pulses with
`2A=20h/21h`, `2C=20h`, the shared top-V24 latch values. It does not operate
the IR controller or prove optical coexistence.

Yellow is the implemented in-trial timing marker. Its ROM write changes only
the `2A` bit-0 value in the actual current IR latch shadow; it preserves every
other current `2A` bit and the current `2C` byte. It must not restore or retain
the black gate during an IR transaction. Record latch bytes before/after,
scope timestamp, trial ID and marker overhead. The marker is a correlation aid,
not a command channel or proof of wire ordering.

## Host checks and bench acceptance

Focused host checks now cover poisoned-RAM/NMI boot, idle gates, command
windows, release/stuck aborts, keypad release gate, stock-order witness, raw
RX bounds/errors and 30-byte checksums (32 ROM tests), plus 1200-baud 8N1
result decoding and receiver-clock tolerance (2 UART tests).

Before a burn, generate feedback-v1 and its manifest with `feedback.py`; the
canonical interface will carry the resulting image identity. Bench acceptance
still requires electrical validation, scope-correlated result records, a
silent Arduino control and selected USB-configured hypotheses for both
channel-role permutations. It excludes automatic session transfers and any
equation of controller status with accepted protocol data.

## Trial worksheet fields

For every run collect: sketch commit/build ID and `BLACK_USE_NPN` setting;
ROM image identity verified separately;
port and optical geometry; electrical protection used; controller trial ID and
mode; command timing; scope file and timebase; explicit scope pod-to-Uno D5/D6
map; marker and complete latch
bytes; LCD/UART result record; raw bytes/status; and the result category
(`silent control`, `gate change`, `RX pending`, `byte delivery`, `validated
frame`, or `inconclusive`).  Preserve negative and timeout runs beside the
positive run; they are the controls that make a claimed transition useful.
