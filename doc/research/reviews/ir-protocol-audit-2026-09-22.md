# IR protocol, diagnostic ROM and scanner-port audit

Reviewed **2026-09-22**, including the existing uncommitted changes on
`7125508f6dbc319b736b06d5bac4a9f5c57c27d2`. This is a review and proposed
experiment plan. The findings below preserve the pre-fix evidence.

**Implementation follow-up (same day):** the descriptor preview, phase/event
scheduler, stuffing validation, bit-6 instrumentation timing and peer retry
defects have been fixed and regression-tested. The witness now stops before
arming on a bit-4 timeout and performs separate ordered teardown writes.
`rxb2` leaves the destination untouched before receive and displays only bytes
covered by both the returned count and the first descriptor; this supersedes
the original pre-fill suggestion below. The relocated bit-6 poll preserves
620 stock iterations, with a 10 T-state entry shift and 107 T-states after
the poll. Arduino configurations compile for the owner's Elegoo Uno R3.
See the [current ROM plan](../../re-notes/exerciser-test-plan.md) and
[one-burn connector experiment](../../re-notes/connector-experiment.md)
for the release image, checksums, controls and next measurements. The
physical return framing remains OPEN; subsequent measurements map three of
the six initially unknown connector contacts (see the connector guide).

**Owner clarification, 2026-09-22:** Arduino LED clock/data assignment is
unknown; `7Eh` as a receive flag is SUSPECTED, not confirmed by naming it a
flag in a stimulus. Test both channel assignments and candidate framing with
Arduino changes. The next ROM should support these tests with one burn.

**Main finding at audit time:** several remaining uncertainties are in the instruments
themselves. Fix and validate those before interpreting another convention
sweep. The existing captures and firmware tests remain valuable, but they
do not yet demonstrate a correct return frame or a working physical adapter.

**Connector decision:** a manual, output-first pin-mapping tangent is useful.
The owner identifies an **8-contact mini-DIN-like right-side scanner port**,
with **power and ground already known: six contacts remain unknown**.
Bypass the barcode API and control the latch writes directly. Once output
contacts are mapped, investigate the input contacts. This is the owner's
intended experiment, not a proposal to use the normal barcode reader API.

Evidence tags below distinguish **CONFIRMED** source/byte/test observations
from **LIKELY** interpretations and **SUSPECTED** physical explanations.
Nothing here assigns an unmeasured electrical function to a connector pin.

## Original findings (before repairs)

| Priority | Finding | Practical consequence |
|---|---|---|
| High | `rxb2` displays descriptor bytes as received data | The reported `06 00 E4` is not evidence of those bytes arriving over IR |
| High | Arduino phase labels and edge scheduling disagree | The nominal −2/8-cell setting actually gives about −4/8; extreme settings distort the waveform |
| High | The stock bit-6 hook more than doubles the wait | A successful response under this hook could miss the stock deadline |
| High | The peer advances a download on an unacknowledged duplicate request | A lost reply can skip program data despite the happy-path tests passing |
| High | Experiment configurations and conclusions have drifted | “content=2”, a mode name, or a sum16 alone is insufficient provenance |
| Medium | Stuffing, interrupt and waveform tests leave important gaps | Passing tests can preserve the wrong instrument behaviour |

### 1. `rxb2` reads the descriptor, not its destination

**CONFIRMED**, `analysis/rom_exerciser/stock_instrument.py:264-276`.
The hook loads `HL` from the active RX descriptor pointer, preserves it
across `Link_BlockRx`, and prints three bytes directly from that descriptor.
It never follows the destination pointer stored at descriptor offset +2.

Fresh Ghidra memory at `ROM00:2FBD` and the original ROM file agree:

```text
2A DC FD E5 CD 78 33 E1 38 49 23 23 7E 23 66 6F CD DC 30
```

After the stock receive call and carry check, the dispatcher advances twice,
loads the destination pointer, then calls the frame validator. The hook
omits that dereference and does not call the validator.

An adversarial Z80 run used a descriptor `06 00 00 90`, a distinct payload
buffer `AA BB CC DD EE FF`, and an error status permitting no payload read.
The hook displayed `IC2EC060000`: its supposed data was `06 00 00`, while
the payload buffer remained untouched. The only `LINK_RXD` read was the
stock dummy read. Reproduction: `/tmp/opencode/check_rxb2_descriptor.py`.

**Discarded inference:** the owner's `I 08 EC 06 00 E4` result does not prove
that the controller received those bytes, framed them, or rejected a short
logical frame. The saved control shadow and return code remain observations;
the descriptor-as-payload interpretation does not. An `ECh` return alone
does not identify which receive error path occurred.

**Next (original recommendation):** record descriptor metadata separately, dereference the real buffer,
and capture the number of bytes actually received, return flags/code and
error branch. Pre-fill the buffer so untouched bytes are recognisable.
Include successful and failed RX tests with different descriptor and buffer
sentinels. The current test at `analysis/test_stock_instrument.py:219-262`
uses an empty descriptor and only weakly checks the error display.

### 2. The phase sweep does not generate the advertised phase

**CONFIRMED**, `analysis/arduino/m1000_ir_probe/m1000_ir_probe.ino:667-680`.
Clock rise is already scheduled 30 µs after the unshifted data rise.
`txPhaseEighths` adds another shift to data; it is not an absolute
data-to-clock phase. Consequently the current “−2/8” setting adds −30 µs
and gives a **60 µs lead**, rather than the intended approximately 30 µs.

There is a second defect: events always execute in the order data-high,
clock-high, data-low, clock-low even when shifted deadlines require a
different chronological order. Past deadlines execute immediately.

| Printed setting | Source-derived waveform for consecutive pulses |
|---|---|
| −4 | Data falls immediately after clock rises; essentially no hold time; steady width about 61 µs |
| −2 | Data leads clock by 60 µs; pulse width 76 µs, hold about 16 µs |
| 0 | Data leads clock by 30 µs; original intended waveform |
| +2 | Data and clock rise consecutively; clock high expands to 76 µs |
| +4 | Clock itself is delayed; data and clock rise consecutively; clock high is 76 µs |

These are ideal-wait, zero-GPIO-overhead reproductions of the actual source
order, not physical scope measurements. AVR overhead and interrupt jitter
cannot restore the requested event ordering. Reproduction:
`/tmp/opencode/ir-review-emitter.cpp`.

**SUSPECTED:** the malformed setup/hold intervals contribute to intermittent
receive indications or wrong bytes. Confirm/refute with a scope trace of
the actual Arduino outputs and known data at every setting.

**Next (original recommendation):** define phase as data-rise minus clock-rise; schedule edges in time
order, including across cell boundaries. Test generated transitions against
independent expected timestamps, then verify the physical waveform. Changing
only the default to zero addresses the current nominal-phase error but does
not repair the general sweep.

### 3. Instrumentation changes the timing being measured

**CONFIRMED**, `stock_instrument.py:99-130` and fresh `ROM00:32F3-32FF` bytes.
The stock repeated failed poll takes 59 Z80 T-states; `hook6` takes 132.
Both use 620 iterations. At the owner-stated 3.6864 MHz, the approximate
wait changes from **9.92 ms to 22.20 ms**, excluding small entry/exit costs
and interrupts. Keeping the iteration bound does not preserve elapsed time.

The no-peer `O C8 A C8 B1` result remains useful: every sampled
`LINK_STATUS` value was `C8h`, including `LINK_STATUS` bit 6 set. It does
not establish the electrical identity of that bit, continuous behaviour
between samples, or an unchanged stock timing environment.

The `rxb` no-byte loop also lasts approximately **28.9 ms**, rather than the
documented 16 ms. OR/AND accumulation cannot recover events during LCD,
keyboard, settling or other unsampled intervals.

**Next (original recommendation):** publish cycle costs with the image manifest. Prefer recording the
stock branch outcome and a small number of samples, with output deferred
until after the measurement. Test time-varying statuses around the original
deadline. A peer response arriving at 15 ms must not be described as meeting
the stock 9.92 ms allowance merely because the instrument accepts it.

### 4. The session peer is not retry-safe

**CONFIRMED**, `analysis/micronic/peer.py:199,364-367,386-396`.
Every request invokes the stateful policy again. There is no in-flight
duplicate-response cache. After a command response has been acknowledged,
feeding the same block request twice without acknowledging the first yields:

```text
image = ABCDEFGHIJKL; chunk = 4; identical request sequence = 3
first response:  marker 0, ABCD
retry response:  marker 0, EFGH
policy offset:   8
```

Reproduction: `/tmp/opencode/ir-review-peer-retry.py`. A repeat of the initial
command-reply request can similarly change `OK` into program data. This
contradicts the idempotence requirement already documented in
`doc/protocol/commstar.md:433-454`.

**Next (original recommendation):** retain and resend the response for an outstanding transaction
without advancing application state twice. Model completion and sequence
reuse explicitly; a permanent cache keyed only by sequence is insufficient.
Add lost type-2 reply, lost type-3 acknowledgement, duplicate command/block
request and sequence-wrap tests, then fault-inject the real-ROM session test.
Happy-path interoperability remains established; reliable physical transfers
do not follow from it.

### 5. Configuration drift and overinterpretation obscure the remaining question

**CONFIRMED source/document conflicts:**

- RX `content=2` is an index, not a stable payload identity. Historical
  prose calls it `1Fh`; an earlier map selected builder case 6; the current
  `{0,1,7}` map selects a different acknowledgement. Serial output does not
  identify the exact bytes. Current `contentName(7)` still describes flag
  fill, while case 7 emits an acknowledgement.
- Current RX_SWEEP starts at 26 ms; older recipes say approximately 3 ms;
  RX_NARROW uses 4 ms. Current case 7 has no closing flag despite the banner
  promising a closed frame. Its sequence and link ID are fixed test values.
- The plan still recommends reverted witness `3072` at lines 572 and 600,
  although it records that image blanking the LCD. The tested witness is
  `3351`. A reply-on-handheld-burst mode cannot start from a witness that
  emits no burst without an independent trigger.
- Witness code is not a byte-for-byte stock I/O replay: it combines
  separate teardown writes and continues after a poll timeout where stock
  aborts. Different transitions of unknown latches are not established as
  equivalent. Their contribution to missing emission remains unresolved.
- TASKS says no analytic work remains, while these instrument defects and
  remaining controller questions plainly require analysis.

**Discarded inferences:** a pending receive indication alone does not settle
the complete receive convention; `DF FF FF` does not validate an expected
byte sequence that it fails to match; the descriptor readout in finding 1
cannot establish valid framing. Preserve the owner-observed displays and
silent-Arduino control. They demonstrate stimulus-dependent behaviour, not
yet a correctly decoded frame or a TX handshake acknowledgement.

**Next (original recommendation):** give each trial an immutable manifest: both ROM hashes, sketch
source and compiled-image hashes, all mode settings, exact emitted bytes and
bit count, actual measured phase, lead/trailer cells, trigger and delay,
trial number, LCD result, serial transcript and scope file. Log builder case
and payload, not just an index. Freeze one pair and alternate one fixed
stimulus with silence before resuming a sweep.

### 6. Additional test and interpretation gaps

**CONFIRMED source/test observations:**

- `1Fh = 00011111` does contain five consecutive ones. The assertion that
  it does not exercise normal zero stuffing is false. The sender inserts
  stuffing only before the next data bit: a final five-bit run followed by
  a raw closing flag omits the required intervening bit under the intended
  HDLC rule. Both normal `1Fh + 7Eh` and inverted `20h + 81h` reproduce
  this. The current acknowledgement ends `01h`, so that boundary defect
  does **not** explain its result. Receiver behaviour without a closing
  flag still needs measurement.
- The decoders discard any bit after five zeros without verifying the
  required stuffed one. Both valid `10000001000001011` and malformed
  `10000001000000011` decode as address 3. Add malformed-stuffing, terminal
  runs, byte-boundary runs and closing-flag fixtures independent of the
  sender implementation.
- FREERUN_TEST enables Timer2 before initialising the GPIO pointers the ISR
  dereferences (`.ino:870-878`). This is a startup race to remove, not a
  demonstrated explanation of any particular historical capture.
- Arduino `txActive` discards receive edges during the scheduled wait,
  emission and recovery. Its serial log therefore cannot prove that the
  handheld emitted nothing during those intervals. Use an independent scope.
- The ROM tests do not inject real interrupts through the installed vector
  during measurement and rendering. Fingerprints and constant-status tests
  do not establish I/O timing, IRQ behaviour or stock equivalence.
- The byte-latch emulator supplies controller statuses and bytes; it does
  not simulate optical reception or establish what clears physical
  `LINK_STATUS` bit 6. Shadow agreement also compares two software peers,
  rather than providing an independent physical protocol oracle.
- No software checksum in the examined ROM establishes only that software
  fact. It does not rule out a controller-generated/checked wire FCS.
  Keep the latter open pending full-frame physical evidence; this is not
  a recommendation to add an arbitrary CRC.
- Annotation coverage is not protocol correctness. Near-complete naming
  and passing docs builds do not close these engineering questions.

**Known:** 8192 bit/s is a strong nominal timing interpretation; the capture
measures about 122 µs per cell, a mismatch. The conn13 early/late separation
is real. Conn11 rules out a universal final-light-off deadline.

**Still open:** the divider/oscillator-source cause of the timing mismatch;
whether the conn13 content and duration variables are a complete factorial
comparison. This one is not established merely by the fit. Test
equal-duration valid/malformed stimuli before declaring content exploration
exhausted.

## What survives the review

- **CONFIRMED by independent rerun:** conn2 has the documented 50 segments
  and three burst families, decoding to the same `03h` prelude under the
  documented interpretation.
- **CONFIRMED by independent rerun:** conn13 has 163/163 early-dark reactions,
  0/221 late-dark reactions, 0/22 end-censored reactions and 0/76 silent
  reactions. The median populations differ by 15.624 ms.
- **CONFIRMED by independent rerun:** conn11 has 62/62 late-ending responses
  with a reaction, preserving the important exception to the simple cutoff.
  Its and conn13's archived hashes match the documentation.
- **Owner-observed:** silent Arduino control did not produce the receive-hook
  halt that active stimulus produced. Preserve this positive evidence while
  narrowing the claims attached to it.
- **CONFIRMED tests:** real ROM code completes bounded download/upload
  scenarios against the synthetic controller/peer. Patch-site guards,
  ROM bounds and image fingerprints are useful protections.

## Manual scanner-connector experiment: outputs first, then inputs

### Scope and known facts

Power and ground are already identified by the owner. Label the remaining
six contacts on a socket mating-face drawing with the key orientation shown;
use those physical labels in the measurement sheet. Older five-pin wording
is superseded by the current owner description; it is not evidence of a
different connector variant.

**CONFIRMED firmware mechanics:** `EXTBUS_EDGE` bit 0 is sampled for edge
timing. Its physical contact is not yet mapped. `EXTBUS_EDGE` bit 1 also
participates in classification; that does not prove it has a separate pin.
Do not assume a standard mini-DIN pinout or TTL voltage from the connector.

Fresh `ExtBus_BusArm` bytes show that normal barcode arming clears
`CTL_LATCH_2C` bit 5 and changes `CTL_LATCH_2A` bit 1 and
`CTL_LATCH_2C` bit 1. Fresh `Link_PortSelect` bytes show it also clears
`CTL_LATCH_2A` bit 1 and `CTL_LATCH_2C` bits 0/1. These identify background
writers to exclude from the manual experiment. They do not defeat the
proposed direct-port approach.

### Proposed output harness

1. Start from the known-working stock boot/LCD environment. Enter a small
   dedicated diagnostic mode after initialisation; do not call the barcode
   arm/capture API or initiate IR transactions during mapping. Prevent IRQ
   and deferred link/barcode work from rewriting the selected latches.
   With interrupts disabled, use direct polled keys and LCD access, not
   an OS key-wait that needs interrupts. Retain the working power/LCD latch
   state throughout the diagnostic mode.
2. Snapshot the latch shadows and establish a displayed baseline. For each
   chosen bit, explicitly clear and set it while preserving all unrelated
   bits and keeping its RAM shadow coherent. Hold each state until a key
   action, then restore baseline before selecting another bit. Display the
   port, mask and complete written byte; an optional slow repeat toggle can
   help identify a capacitively coupled or pulsed signal.
3. Start with **CTL_LATCH_2C bits 0 and 1**, then **CTL_LATCH_2A bit 1**:
   firmware already changes these around the scanner paths. They are
   candidate signals, not known connector outputs or guaranteed-safe GPIOs.
   Monitor all six unknown contacts with a high-impedance scope and record
   level, polarity, transitions and any coupled effect on LCD/IR/power.
4. Keep **CTL_LATCH_2C bit 5** at its baseline during this first pass because
   it also selects the IR configuration. Do not sweep `IRQ_MASK`, bank select,
   LINK_CTRL or every unknown latch bit indiscriminately. Expand the chosen
   masks only after reviewing their firmware use and observed effects.
   Failure of these first three candidates to reach a pin is an observation,
   not proof that no output exists. If an independently mapped enable gates
   an output, record a second explicit baseline with that enable held and
   repeat the one-bit test; keep the two baseline results separate.
5. Produce a table of contact ↔ port/mask ↔ baseline/low/high voltage ↔
   polarity ↔ static/pulsed behaviour. A changed voltage is a candidate
   mapping; confirm it repeatedly and distinguish logic from a switched
   supply or enable before attaching the Arduino input/interface.

This harness is a proposed small additional ROM hook. The current exerciser
README explicitly says its optional pin-walk is absent; the existing burn
does not already implement this experiment.

### Input pass and eventual IR feedback

After the output contacts are mapped, sample the raw `EXTBUS_EDGE` byte in
the diagnostic mode and show changes on LCD or store them in RAM. Apply a
slow, electrically appropriate bounded stimulus to one remaining candidate
contact at a time, starting with the scan-timing input. Correlate the contact
with **EXTBUS_EDGE bit 0**, then investigate other input bits. Do not run the
barcode decoder: its default hook discards captures, it repurposes SP during
capture, and its long busy waits are unnecessary for pin mapping.

**Expected benefit, conditional on mapping:** an isolated output can mark
“armed”, “wait exited” or “byte ready” for the Arduino/scope; an input can
select or trigger a trial. For richer logs, sample into RAM during the IR
operation and emit slowly afterward. Maintain the known IR selector and
other shared latch bits. Compare marker-enabled and marker-disabled runs:
manual OUTs still add time, and an internally shared output may still disturb
the controller even if it appears on the connector.

Stop after a bounded mapping pass if no useful independent signal emerges;
keypad/LCD plus scope remain sufficient to repair the present instrument
defects. A complete barcode or serial protocol is not required.

## Suggested order of work and success criteria

1. **Repair observation first:** correct `rxb2`, Arduino phase/event order,
   payload labels and stuffing boundaries. Pass sentinel-backed RX and
   independent timestamp/bit-vector tests before another burn.
2. **Add the manual latch mode:** map outputs on the six unknown contacts,
   then inputs. Success is a repeatable contact-to-bit table; useful debug
   output is a bonus rather than a prerequisite for the IR corrections.
3. **Repeat one frozen RX trial against silence:** scope emitted bits and
   timing, record trial ID/status/count/actual bytes. Success requires exact
   bytes and stock receive/validation outcome, not just a pending flag.
4. **Test TX handshake separately:** determine what makes `LINK_STATUS`
   bit 6 clear, then whether `LINK_STATUS` bit 7 permits the first payload
   byte, within the stock deadline. A session type-2 reply and the electrical
   TX turnaround are different observations.
5. **Only then widen the sweep:** vary polarity, lead-in, stuffing, closing
   flag and delay individually with equal-duration controls. Archive each
   build and run. Avoid first-hit-only conclusions about an entire axis.
6. **Harden the peer:** fix duplicate handling and inject losses before
   claiming reliable physical download/upload. Retain the existing
   successful emulator cases as regression coverage.

## Validation and review record

- ROM instrumentation: **77 passed** in the two targeted pytest modules.
- Other analysis tests, excluding ROM instrumentation and boot integration:
  **96 passed, 5 skipped, 71 subtests passed**; the five skips are opt-in
  barcode integration tests, tested separately below.
- Opt-in boot/session suite: **28 passed, 6 subtests passed**, 323.70 s.
- Opt-in barcode suite: **24 passed**, including all five previously skipped
  integration tests. Its read-driven, PC-gated stimulus model tests software
  contracts rather than asynchronous electrical timing or a connector pinout.
- Documentation-build results are recorded in the accompanying session entry.
- Reproductions were independently checked for descriptor readout, phase
  ordering, timeout arithmetic and duplicate request handling. A separate
  reviewer checked consequential conclusions against source and fresh ROM
  bytes. Cross-provider review was unavailable; the review used the
  available same-provider fallback.
- No ROM, Arduino or peer implementation was changed by this audit. Existing
  dirty changes were included and preserved. No hardware was operated.
- Four non-repeatable audit bookmarks were saved in Ghidra at the affected
  descriptor, timing and shared-latch routines; no functions were renamed.

Detailed investigator reports and runnable reproductions are in
`/tmp/opencode/ir-review-{rom,wire,barcode,verdict}.md`,
`check_rxb2_descriptor.py`, `ir-review-emitter.cpp`,
`ir-review-stuffing.cpp` and `ir-review-peer-retry.py`.

Reviewed artifact SHA-256 values:

```text
micron1.bin
6226dc1766933e193130112ee9a3304d916f503c57363cfcec00a4179aa66a6f
micron2.bin
2473697c45fe705d71a763e3391ffcbf7755784adaf64c653e3a930e0ff1f3f9
Arduino sketch
18fe05797eb2e39c301b461b2e0c710122e16f421d665471fcf4084886e7c4f6
stock_instrument.py
cd74baeea1cb77e431071ecbba3a26d92311fa43e2ffd8d6bd094852089eded2
exerciser.asm
a43d6a7aab3efd80e938c4e1c9d67bd63ab5fc5faeb4a93f19f318f42ab0ce8d
peer.py
e27533e779689a4a22238566270088c0a738758c0c67c6183589b3139090a68f
```
