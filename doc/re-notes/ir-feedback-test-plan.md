# IR feedback automation test plan

This document plans the combined ROM/Arduino implementation after
[PR #21](https://github.com/philpem/micronic1000/pull/21). The draft currently
contains this plan and evidence corrections; the harness below is not yet
implemented. Further commits on `ir/automated-feedback-tests` will implement it.

## Scope

Build one reusable combined ROM/Arduino trial controller: explicit black-input
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

The combined electrical interface is still to be designed and validated. Red
has measured as high as 5.6 V, so it must not connect directly to an Uno input.
The proposed black command path uses a protected open-drain pull-low/release interface,
validated first at the connector with actual voltage and current measured.
Protection, references, and connector/optical coexistence remain open; the
standalone connector experiment does not prove optical coexistence.

## Current implementation boundary

The checked-in sketch defaults to `RX_NARROW=1`, `RX_NARROW_AXIS=2`; it
cycles candidate `7Eh` alone, candidate `7Eh` plus `03h`, and an open type-2
acknowledgement stimulus on successive handheld bursts. Fixed-stimulus trials
need explicit selection instead of this implicit cycle.
Its serial output reports activity, but has no serial command trigger or
operator-visible arm/disarm protocol. The implementation must document the grammar,
keep existing sweep modes, and make new Arduino hypothesis changes USB-only.

## Minimal staged design

### M0 — controlled silence and durable trial records

Add a small controller state machine, initially defaulting to `SILENT`:

* `SILENT` drives both return outputs low, starts no timer, and emits no reply
  after a handheld burst.
* An explicit command assigns a monotonically increasing trial ID, selects
  either `SILENT` or `STIMULUS`, and prints the complete effective
  settings before the trial starts.  Unknown, partial, or duplicate commands
  leave the controller silent and report an error.
* `BLACK_LOW` and `BLACK_RELEASE` are accepted only between trials, after the
  ROM has reported stock teardown and restored the tested black gate. The ROM
  must report the command result on the LCD/log. `IR_ARM` first releases black
  and restores the actual IR latch state before entering the stock arm path.
* A timeout, observed input-gap resynchronisation, command cancellation, or
  reset always returns the outputs to low and clears an armed reply.  Never
  leave a clock/data output asserted, an automatic reply armed, or black held
  low when a burst stalls.

Acceptance: scope, LCD and serial log show a silent trial with no return
optical activity, black low/release commands in the post-teardown state, clean
resynchronisation, and a second silent trial. The log contains trial ID,
command/teardown/arm times, observed burst start/end, output transitions and
scheduler lateness.

### M1 — USB-configured one-stimulus trials

Add named `STIMULUS` mode: exactly one Arduino-selected stimulus per explicit
arm, not the current content-axis cycle. A USB command chooses physical-role
permutation, line sense, timing and logical bytes; the burned ROM sees only
generic command/result, status and raw-RX fields. `7E` may be one logged
candidate byte pattern but is not described as a flag or acknowledgement.

Acceptance: for each A/B role permutation, a silent control precedes the
stimulus. Repeated armed trials retain their logged configuration and
scope-visible timing; unarmed bursts produce no reply. A stale arm expires before
an unrelated later burst, so a missed command cannot transmit later.

### M2 — stock-order gate, then RX

1. Run the stock-order witness with M0 `SILENT`; record the `LINK_STATUS`
   bit-4 outcome, whether the arm ran, its bit-6 outcome, ordered teardown, and the wire
   capture.  This is the baseline control.
2. For each channel permutation, repeat with one M1 USB-configured stimulus
   under the same placement and capture window. Do not conclude that `LINK_STATUS` bit 6 is
   a wire-level acknowledge merely because it changes.
3. Only after those paired runs, use the RX hook / `rxb2` path with the same
   USB-recorded stimulus. Record `LINK_STATUS`, return status, descriptor-
   bounded bytes, and the scope/serial trial ID together. Acceptance of a
   receive frame requires the stock result and expected bounded bytes, not
   just `LINK_STATUS` bit 4 or an IRQ.

## Combined connector commands and markers

The ROM accepts commands encoded on black between IR trials. After ordered stock
teardown it restores `2A` bit 1 high and `2C` bit 5 low, confirms the gate on
the LCD/log, then permits protected Uno open-drain `BLACK_LOW`/`BLACK_RELEASE`.
Specify a bounded pulse/command encoding, acknowledgement and idle-ready
marker before implementation; raw low/release controls alone are not a trial
command protocol. A physically stuck-low black input must prevent arming even
after the Uno releases its driver.
Record the complete `2A`/`2C` values, raw `2D`, command result and dwell time.
`IR_ARM` must release black before it restores stock IR selection and arms.

Owner-confirmed bridge evidence is limited to **R/D/P**: yellow pulses with
`2A=20h/21h`, `2C=20h`, the shared top-V24 latch values. It does not operate
the IR controller or prove optical coexistence.

Yellow is a proposed in-IR timing marker. Its future ROM write changes only
the `2A` bit-0 value in the actual current IR latch shadow; it preserves every
other current `2A` bit and the current `2C` byte. It must not restore or retain
the black gate during an IR transaction. Record latch bytes before/after,
scope timestamp, trial ID and marker overhead. The marker is a correlation aid,
not a command channel or proof of wire ordering.

## Future tests and PR acceptance

Add focused host tests before a burn:

* command parsing, default silence, both A/B role permutations, one-shot
  arming, cancellation, and stale-arm expiry;
* output-control writes: every terminal path drives clock/data low, and the
  selected stimulus produces the logged ordered transitions;
* protected black open-drain control: release-before-arm, reject black commands
  before teardown, and release on timeout, reset or stuck-low detection;
* a stuck input/high or missing-gap case: no reply while framing is uncertain,
  followed by bounded resynchronisation to a later valid burst;
* a silent-versus-stimulus trace fixture per role permutation proving no
  accidental emission and stable logged configuration; and
* hook/decoder regression coverage for the status row, timeout/teardown order,
  descriptor-preview bound, and a receive error.

Implementation acceptance requires one combined ROM image with reusable LCD/log
outcomes and generated checksum manifest (full filename, size, MD5, unsigned
additive 16- and 24-bit checksums, and SHA-256), a compiling Uno sketch, silent
controls for both role permutations, and one USB-configured stimulus. Before
this draft is ready for implementation review, it must contain ROM and Arduino
changes, focused tests and a bench worksheet alongside this plan. It excludes
automatic session transfers and any equation of controller status with
accepted protocol data.

## Trial worksheet fields

For every run collect: commit/build ID; ROM image identity verified separately;
port and optical geometry; electrical protection used; controller trial ID and
mode; command/arm/expiry times; scope file and timebase; observed handheld
burst timing; actual emitted timing/lateness; marker state and complete latch
bytes; witness or hook row; raw bytes/status; and the result category
(`silent control`, `gate change`, `RX pending`, `byte delivery`, `validated
frame`, or `inconclusive`).  Preserve negative and timeout runs beside the
positive run; they are the controls that make a claimed transition useful.
