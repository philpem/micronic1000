# Stock-context v8: active receive buffer readback

## Release and purpose

ROM00 image: `analysis/rom_exerciser/releases/stock-context-v8/micron1_stock_context_v8.bin`.
Programmer additive checksum: **387331** (16-bit sum `7331`), size 32768 bytes.
SHA-256: `57057f0a106a4608dc6675824315b44e67be93796b1052559ab3567f2c9e5dd5`.
**Leave ROM01 unchanged. Hardware validation is pending.**

The owner reported this v7 result after reset restored communication:

```text
R7IEC29:8A000600E4FD
X0EFEE5FD0000060005
```

CONFIRMED from the stock receive bytes and reviewed synthetic execution:
this descriptor advanced by one ordinary `INI`; `LINK_STATUS=8A` has
bit 2 clear, so no terminal `INI` occurred. V7's terminal `00` is invalid
and does not identify the ordinary byte. See
[receive evidence](commstar-evidence.md#v7-receive-diagnostics).

V8 reads the first two bytes of the active buffer after receive cleanup
and the yellow marker, with interrupts disabled. It retains v7's separate
terminal-byte capture. This tests whether the earlier ordinary read
returns the same value as the previously observed terminal `C0`.
That equivalence is SUSPECTED; a captured ordinary byte can support or
refute it, but cannot by itself establish optical byte provenance.

## Readout

```text
R8IaaFF:ssvvLLLLPPPP
XDDDDWWWWbbccTTTTRR 
```

| Field | Meaning |
| --- | --- |
| `aa`, `FF` | Receive return A and flags |
| `ss` | Captured terminal LINK_STATUS |
| `vv` | Terminal byte; valid only when LINK_STATUS bit 2 is set |
| `LLLL`, `PPPP` | Active descriptor length and buffer address |
| `DDDD`, `WWWW` | Active descriptor address and next-write pointer |
| `bb`, `cc` | First two active-buffer bytes, read after return |
| `TTTT`, `RR` | Requested total through active descriptor; residual B |

Words are displayed as raw little-endian bytes. The `bbcc` field replaces
v7's saved BC field. Both LCD rows remain 20 characters. For a non-EC
return, only the seven-character `R8IaaFF` prefix is meaningful; ignore
old text left elsewhere on the screen.

Decode both rows using:

```sh
analysis/venv/bin/python analysis/rom_exerciser/stock_context_v8.py \
  --decode 'PASTE BOTH R8 ROWS HERE'
```

The decoder checks pointer advancement against length, residual B and
terminal-read presence. Only covered sample slots are valid; other slots
are returned as `null`, even though raw stale bytes remain visible on
screen. A consistent one-byte advancement with LINK_STATUS bit 2 clear
makes `bb` the ordinary-byte readback and leaves `cc` invalid. With one
terminal read and no ordinary read, `bb` should match valid `vv`.

These are **post-return RAM contents**, conditional on descriptor stability
and no concurrent writer. The sample omits earlier descriptors and bytes
beyond the first two of the active descriptor. It does not prove packet
acceptance, wire framing, an FCS, or that a byte is payload.

## Implementation and verification

CONFIRMED by assembled image and emulator comparisons: the new 11-byte
RAM-copy sequence makes no extra LINK_RXD access. Receive I/O timestamps,
return registers, and yellow-marker timestamps match v7. The later display
output gains 73 T-states (about 19.8 microseconds at the owner-specified
3.6864 MHz); the first seven prefix characters are unchanged in timing.

The image ends at ROM00:7FF8 exclusive, leaving two bytes in the existing
cave. Stock reset routes and ROM01 are unchanged. Diagnostic scratch
remains C7E0–C7F2 in upper TPA, **assessed only for the controlled FOO
trial**. Upper TPA may contain loaded program data. Buffers and descriptors
must not overlap the scratch, and there must be no concurrent writers.
The observed FOO buffer FDE4, length six, avoids that scratch range.
Do not generalize this diagnostic to arbitrary loaded applications.

All **76 v5–v8 tests passed**, including 29 v8 tests. Coverage includes
ordinary, terminal, mixed and absent reads, later descriptors, one-byte
and 256-byte lengths, malformed pointer advancement, image reproduction,
patch guards and exact timing comparisons. Independent release review
approved the controlled FOO trial; its scratch wording correction was
applied without changing the ROM image or checksum.

## Bench sequence

1. Keep the Uno silent during programming, boot and every handheld reset.
   Its last upload and fresh `MODE: LISTEN ONLY` banner verified silence.
   Active replies previously made startup return to diagnostics.
2. Program **ROM00 only** and run the programmer's **VERIFY** operation.
   Report checksum **387331**. Leave the handheld powered off until the
   passive boot capture is prepared. Leave ROM01 unchanged.
3. Boot with the Uno silent. Allow TESTING to finish; the owner observed
   roughly one to two minutes on an earlier coldboot, not a fixed limit.
   Report Main Menu. Preserve alignment and scope connections.
4. With capture armed, run a silent Load/Run → FOO → V24 ADAPTOR →
   LOCAL_LINK control. Record the exact errors or both diagnostic rows.
5. After the Uno is verified silent, reset to Main Menu. Load the archived
   original double-7E response with plus-2/8 data phase:
   `analysis/arduino/releases/stock-v6-framing-matrix/06-prefix7e-open7e/m1000_ir_probe.ino.hex`.
   Verify its configuration, then arm scope and serial capture before
   asking for another Load/Run attempt.
6. Record **both complete R8 rows** and preserve the waveform. Check the
   expected 101 raw cells, accounting for stuffing/destuffing before any
   wire-byte comparison. Restore and verify Uno silence before any reset.

An `8A` result with one-byte advancement exposes the ordinary byte missing
from v7. An `8E` result permits comparison of buffer slot zero with the
terminal byte. Errors 8000 then 8040 without an R8 prefix supply no v8
byte evidence. If the baseline goes quiet again, recover it before drawing
conclusions about phase or inversion.


### 2026-09-24 v8 programmed, boot in progress

Owner reports v8 programmed and programmer VERIFY passed; handheld already
showing TESTING. Fresh Uno serial banner confirms LISTEN ONLY, no transmit.
Passive logger: `analysis/captures/stock-v8-silent-boot-20260924.jsonl`.
Scope armed on D4 yellow falling edge after TESTING was reported; SING,
TER=0, no scope error. Earlier boot events were not captured. Arm state:
`analysis/captures/stock-v8-silent-boot-arm-20260924.json`.
Await Main Menu; no Load/Run requested yet. Receive validation pending.


### 2026-09-24 v8 Main Menu; silent control armed

Owner reports Main Menu after TESTING. Passive Uno log records a yellow
low pulse of 5448 microseconds. Preserved scope POD1, PNG and metadata
under `analysis/captures/stock-v8-silent-boot-20260924` before rearming.
Uno remains LISTEN ONLY; serial logger remains active. Scope now armed
on handheld clock D1 rising, SING / TER=0 / no error, for the silent
Load/Run FOO → V24 ADAPTOR → LOCAL_LINK control. Await exact screen result;
no v8 receive-byte validation yet.


### 2026-09-24 v8 silent control completed

Owner reports 8000 then 8040, matching earlier silent controls. No R8
readout reported; this trial supplies no diagnostic buffer-byte evidence.
Scope capture completed (TER=1, no error) and was preserved under
`analysis/captures/stock-v8-silent-control-20260924` (POD1, PNG, metadata,
analysis). In the captured 80 ms window, handheld D1 has 34 transitions;
Uno D2 and D3 stay low with zero transitions, and yellow D4 stays high.
Serial log remains `stock-v8-silent-boot-20260924.jsonl`, with the verified
LISTEN ONLY banner and received handheld bursts. Uno firmware unchanged
and silent. Request reset to Main Menu before loading original double-7E
plus-2/8 responder; wait for capture-ready before the next Load/Run.


### 2026-09-24 v8 original double-7E trial armed

Owner confirmed Main Menu. Stopped silent logger and used arduino-cli to
upload archived `06-prefix7e-open7e` HEX (SHA-256
`b59bcc70302f6d1160d6275c95a43ee1fd33b5a94a1d007d58a94abf6ad278d7`).
All 10266 flash bytes verified. Fresh serial banner confirms prefix 7E,
opening 7E, phase=2 (+2/8), content_idx=2, no inversion/swap, stuffing=1,
no closing byte, 33000 us delay and every third qualifying burst.
Serial capture: `analysis/captures/stock-v8-double7e-20260924.jsonl`.
Scope armed D2 rising, SING / TER=0 / no error; arm metadata and upload
log use the same stock-v8-double7e prefix. Await both complete R8 rows.
Uno responder is now active: restore verified silence before any reset.


### 2026-09-24 v8 first double-7E result

Owner display:

```text
R8IECA9:8EC00600E4FD
X0EFEE5FDC01A060005
```

CONFIRMED observation: the existing decoder reports LINK_STATUS=8E,
terminal C0, descriptor FE0E length six, buffer FDE4, next-write FDE5,
residual B=5. Under the documented stable-descriptor interpretation,
one terminal INI and zero ordinary INIs occurred in this active descriptor.
Post-return buffer slot zero is C0, matching the terminal capture. Raw
slot one is 1A but lies outside the one-byte advancement: it is invalid,
not a second received byte. The receive return is still EC with carry set;
this is not packet acceptance. The ordinary-byte question remains open.

Saved `analysis/captures/stock-v8-double7e-20260924` POD1, PNG, serial log,
scope metadata and analysis. CONFIRMED raw capture: 101 clock cells;
data sampled 40–80 us after each rise matches the archived original
five lead zeros, two 7E flags and payload 00070002014300000201.
This payload requires no inserted bits under the configured five-ones
stuffing rule; that comparison does not prove ASIC destuffing behavior.
Yellow starts 8262.8 us after first clock and remains low 918.0 us.

V8's terminal-path buffer readback now has one physical consistency check;
ordinary-path readback remains hardware-unvalidated. Next: one unchanged
double-7E repeat to seek the previously observed 8A ordinary path without
changing framing or phase. Do not infer ordinary-byte equality from this
8E result. Restored silent Uno, all 5626 flash bytes verified, fresh
LISTEN ONLY banner saved as `stock-v8-double7e-post-silent-banner-20260924.txt`.
Safe to request handheld reset; no serial logger left running.


### 2026-09-24 v8 unchanged double-7E repeat armed

Owner confirmed Main Menu. Reloaded the identical archived 06-prefix7e-open7e
HEX; arduino-cli verified all 10266 flash bytes. Fresh banner confirms
prefix/opening 7E, phase +2/8, original content, no swap/inversion,
stuffing mode 1, no close, 33 ms delay, every third qualifying burst.
Serial logger running at `analysis/captures/stock-v8-double7e-repeat-20260924.jsonl`.
Scope armed D2 rising: SING, TER=0, no error. Upload log and arm metadata
use `stock-v8-double7e-repeat` prefix. Await complete two-row display.
Responder active; restore verified silence before any handheld reset.


### 2026-09-24 v8 repeat display; invalid waveform capture

Owner repeated the exact display:

```text
R8IECA9:8EC00600E4FD
X0EFEE5FDC01A060005
```

The existing decoder again gives terminal C0, buffer C0/invalid1A,
LINK_STATUS=8E, one-byte advancement and zero ordinary reads under the
stable-descriptor assumption. This is a repeat display observation only.
Scope capture contains 149 D2 rising edges, unstable samples at 40–80 us
and no yellow pulse; it does not match the expected 101-cell reply.
Owner independently identified a likely mistrigger and offered a repeat.
Do not use this capture to claim waveform repeatability or changed wire
behavior. Serial log reports one response and a 920 us yellow low pulse,
but cannot validate the missing physical reply waveform.

All artifacts preserved under `analysis/captures/stock-v8-double7e-repeat-20260924`;
analysis explicitly marks capture_valid=false. Restored silent Uno with
5626 flash bytes verified and fresh LISTEN ONLY banner. Next unchanged
repeat should trigger on yellow D4 falling, retaining 40 ms pretrigger
history to include the expected reply start about 8.3 ms before yellow.
Request Main Menu reset only after verified silence; arm before Load/Run.


### 2026-09-24 v8 yellow-trigger repeat armed

Owner confirmed Main Menu. Identical archived double-7E responder loaded;
arduino-cli verified 10266 flash bytes. Fresh banner confirms original
payload, +2/8 phase, no swap/inversion, 33 ms delay, every third qualifying
burst, prefix/opening 7E, stuffing mode 1 and no closing byte.
Logger: `analysis/captures/stock-v8-double7e-yellow-20260924.jsonl`.
Scope readback confirms DIG4 NEG, 8 ms/div, centered timebase at zero,
SING / TER=0 / no error. This gives 40 ms pretrigger history for the
expected reply preceding the yellow edge. Arm metadata and upload log
use the stock-v8-double7e-yellow prefix. Await both display rows; responder
active, so restore verified Uno silence before requesting another reset.


### 2026-09-24 v8 valid yellow-trigger repeat

Owner again reports:

```text
R8IECA9:8EC00600E4FD
X0EFEE5FDC01A060005
```

CONFIRMED capture observation: 101 D2 rising edges, identical original
raw double-7E sequence at all D3 sampling offsets 40–80 us after each
rise. Yellow starts 8264.0 us after first clock and remains low 918.4 us.
This is a valid repeat of the first v8 waveform (8262.8 us / 918.0 us),
unlike the intervening mistrigger. All artifacts use
`analysis/captures/stock-v8-double7e-yellow-20260924` (serial, POD1, PNG,
metadata and decoded analysis). Configured payload stuffing inserts no
bits in this particular payload; ASIC destuffing behavior remains open.

The existing decoder gives status 8E, one terminal C0 and post-return
buffer C0/invalid1A. One-byte advancement with terminal presence means
zero ordinary reads under the documented descriptor assumptions.
Three v8 displays match, two with validated reply waveforms. The earlier
8A ordinary path has not recurred on v8, so its byte is still unknown.
Do not interpret the unused 1A slot as a received byte or FCS.

Uno restored to silent firmware: all 5626 flash bytes verified, fresh
LISTEN ONLY banner saved under the same yellow-post-silent prefix.
Logger stopped; handheld may remain on the diagnostic display.

Recommended next experiment: a controlled reply-start-delay comparison,
keeping emitted bits and within-cell data/clock phase unchanged, with
33 ms baseline controls and D4-triggered capture. SUSPECTED: relative
arrival/poll timing may affect whether the byte is consumed by ordinary
or terminal INI. Reproducible 8A/8E changes across controlled delays would
support timing sensitivity; repeated 8E would leave the cause unresolved.
This proposal does not identify the controller's internal sampling edge
or explain the earlier hardware quiet state. No new variant is armed.

## Offline review and refined test battery (2026-09-24) {#offline-review}

Hardware testing is parked at the owner's request. Uno remains on the
verified silent image; no logger or armed experiment is running. V8 stays
installed. The following are proposed future tests, not uploaded variants.
This section supersedes the earlier recommendation to prioritize an
unqualified delay sweep.

### What the evidence establishes

CONFIRMED from a fresh Ghidra listing and raw read of ROM00:33CF–341F,
and the caller bytes at ROM00:2FBD–2FCC:

- LINK_STATUS bit 0 has priority: if set, ordinary INI consumes a byte.
- With LINK_STATUS bit 0 clear, LINK_STATUS bit 1 selects terminal handling;
  LINK_STATUS bit 2 permits the final INI; LINK_STATUS bit 3 selects ECh.
- The receive loop does not count software FLAG bytes as an ACK, compare
  received bytes with 7E/81, or compute a software FCS here. The controller
  can still interpret delimiters or validate a frame internally.
- The caller takes the carry-set error path before later header handling.
  The current EC result is therefore not evidence of header acceptance.
- The two-byte subtraction is reached only after the terminal-status
  error check passes. Its presence does not identify a two-byte FCS.

`A9`, `AD` and `29` in the diagnostic prefix are CPU F values. `CA`,
`8E` and `8A` in the status field are LINK_STATUS values. A changed CPU
F value alone is not protocol progress. For CA/8E/8A, LINK_STATUS bit 3
is set in all three; these tested terminal statuses take the same error
branch. CA has LINK_STATUS bit 2 clear; 8E has LINK_STATUS bit 2 set;
8A has LINK_STATUS bit 2 clear. The earlier 8A trial advanced one byte
before terminal handling; v7 did not record that ordinary byte.

CONFIRMED observations from the two valid v8 captures:

| Capture | Clock cells | Yellow onset after first clock | Final clock | Yellow width |
| --- | ---: | ---: | ---: | ---: |
| First double-7E | 101 | 8262.8 us | 12203.2 us | 918.0 us |
| Yellow-trigger repeat | 101 | 8264.0 us | 12202.4 us | 918.4 us |

Both have terminal C0 and post-return buffer C0/invalid1A, one-byte
advancement, and no ordinary read in the active descriptor under the
stable-descriptor interpretation. The intervening 149-edge mistrigger is
excluded. These establish terminal-path readback consistency, not the
meaning of C0 or optical/ASIC byte equivalence.

The firmware returns before emitting yellow. At yellow onset only 68 of
101 clock rising edges have occurred in the valid original-payload trials.
Thus this return cannot be a completed validation of our entire transmitted
ten-byte payload: the final clock is still about 3.94 ms in the future.
An early error, a shorter frame perceived by the ASIC, or an earlier
buffered item remain possible. This does **not** disprove an FCS in the
actual protocol. Altering a future suffix cannot change an earlier decision
if every preceding waveform and initial state is truly identical; merely
editing a build does not itself guarantee that timing equivalence.

### Narrow theories eliminated; broader theories still open

| Theory | Adjudication and next discriminant |
| --- | --- |
| Two flags constitute a software-counted ACK in this receive loop | Ruled out within the examined loop. ASIC delimiter acquisition remains open. |
| Double-7E works solely because eight more clocks were added | The equal-length 00,7E prefix control and 7E,7E result contradict a clock-count-only explanation. Their data patterns differ; delimiter recognition is not proven. |
| C0 is the unchanged raw first payload byte | Contradicted by original first payload byte 00 and mutations. An encoding, different alignment, or unrelated controller datum remains open. |
| C0 is a fixed contiguous raw eight-cell MSB-first window, no inversion | Ruled out across the three original/payload06/payload80 captures under this specific fixed-position model; see exhaustive audit below. |
| C0 is a fixed bit-reversed or inverted raw window | Several candidates survive. Numerical matches do not establish receiver edge, bit order or byte boundaries. |
| ASIC input inversion explains everything | Unproven. The phase experiment lost its restored baseline and cannot establish causality. Changing only a flag to 81 is not equivalent to inverting the complete input stream. |
| C0 is local echo or stale/partial controller data | Unresolved. The unrecorded setup LINK_RXD read and controller buffering prevent exclusion. 03 reversed equals C0, but that is only a numerical match. |
| Terminal C0 equals the missing ordinary byte | Untested on hardware: v8 has not reproduced the 8A ordinary path. |
| A trailing FCS is the only missing ingredient | Unsupported as a diagnosis of the current early rejection. Defer brute force until framing and a usable acceptance/consumption signal exist. |
| The displayed second buffer byte 1A is an FCS | Ruled out as a received second byte in these trials: pointer advancement is only one. |

The constant terminal value does not imply payload independence: the
all-zero-payload experiment timed out, while restoring the original
payload returned the terminal error. That all-zero trial's scope-to-display
association is weaker (two logged transmissions around a reset), so it is
supporting evidence to recheck, not a decisive ASIC model discriminator.
The two isolated payload mutations also changed yellow timing (8262.4 us
original; 8866.4 us for 07→06; 8012.0 us for first 00→80). These are
observed timings, not proof that the changed bit directly caused an error
at a particular ASIC cell.

### Reproducible fixed-window audit

Run `python3 analysis/review_ir_v8_captures.py`. Output:
`analysis/captures/stock-v8-offline-review-20260924.json`.
It reads the saved POD1 samples using each capture's actual preamble,
checks stable D3 values at 40/50/60/70/80 us after D2 rises, and intersects
all possible fixed raw eight-cell C0 windows across the original,
07→06 and first-byte 00→80 waveforms. Candidate windows must finish by
80 us after their final rise, before yellow. This is a permissive cutoff:
the actual port read precedes yellow. It cannot establish precise ASIC
sampling time.

Surviving starts (zero-based emitted cells; five leading zeros, then flags):

| Interpretation of eight raw cells | Surviving starts |
| --- | --- |
| MSB-first, unchanged levels | None |
| LSB-first, unchanged levels | 0, 28 |
| MSB-first, inverted levels | 4, 12 |
| LSB-first, inverted levels | 6 |

Most survivors overlap lead/flag cells. They are mathematical candidates,
not valid decoded payload bytes. Conventional five-ones stuffing inserts
no bits in these three payloads (maximum runs three/two/three). This
removes that particular explanation for the two original failed window
predictions, but does not justify destuffing flag-crossing windows as
payload, nor eliminate an inverted, NRZI, variable-boundary or other
receiver transformation.

### First battery: five runs with two questions

Keep v8, original physical mapping/polarity, +2/8 within-cell phase,
original bit period, two flags, no tail, 33 ms response delay and every
third qualified burst unless a row explicitly changes one item.

| Run | Change from baseline A | Question / prediction |
| --- | --- | --- |
| A1 | None | Recover 8E/C0 with a valid 101-cell capture after the break. |
| B | Payload `00 47 00 02 01 43 00 00 02 01` (07→47 only) | Flip raw cell 30. The remaining payload-region LSB window at 28 predicts C0→C4; surviving lead/flag windows are unchanged. No added stuff bits. |
| A2 | Restore original payload | Confirm B did not leave the hardware in a different state. |
| C | Original payload, requested reply delay 33060 us instead of 33000 us | Probe timing sensitivity without changing bits or within-cell phase. This is +60 us, not an assertion of an exact half measured cell. |
| A3 | Restore 33000 us | Confirm the timing comparison's baseline recovered. |

B interpretations: C4 with matched capture/status supports the specific
LSB-window prediction but does not prove it; C0 with the same terminal
path and valid controls rejects that fixed window. A changed status/read
path is a separate observation; do not force a terminal-byte comparison
when the byte is invalid or now read ordinarily. An ordinary path on v8
finally supplies the missing buffer-byte observation.

C interpretations: a reproducible 8E↔8A change with valid controls supports
arrival-timing sensitivity, not a specific ASIC edge or inversion model.
If C changes the result, add a second C/A pair before a causal claim;
one intermittent 8A result is not sufficient. If C is unchanged, one
tested +60 us offset is insufficient to reject all
timing explanations. Do not expand automatically into a broad sweep.
This is a bounded secondary probe, not a promised way to force 8A.

### Conditional follow-ups; not part of the first five runs

- If the extra-FLAG acquisition question remains useful, compare equal
  length prefixes `00,7E,7E` and `7E,7E,7E` before the original payload,
  with restored controls. Both add eight clocks to the current baseline;
  only their first prefix byte differs. This distinguishes an extra flag
  pattern from extra elapsed clock time, not an ACK's semantic identity.
- Revisit clock/data polarity only with recoverable A/B/A controls.
  Treat data inversion, clock inversion and physical swap as separate
  axes; complement the whole stream when testing input inversion, and
  specify idle levels and stuffing relative to the hypothesized logical
  stream. Historical flag-only 81 tests are not this experiment.
- If the byte remains invariant after targeted mutations and timing
  probes, assess a diagnostic of the **existing** setup read and bounded
  status history. Do not add extra LINK_RXD reads. Any in-loop capture
  changes timing and needs an emulator budget and an uninstrumented
  control. This would be a later ROM design, not justification to burn
  another ROM now.
- Defer FCS search. One-shot v8 cannot test a stream of candidate trailers
  after its first return. A search needs a genuine outcome signal,
  candidate identity/re-arm control, and a framing hypothesis; an 8-bit
  exhaustive failure at one guessed position would not disprove FCS.

### Capture and stopping rules

1. Uno must be verified silent before every handheld reset. Start only
   after Main Menu; verify image and complete banner before arming.
2. Prefer D4 falling trigger, centered 80 ms window. Save both rows,
   raw POD1, actual preamble, PNG, serial log and configuration identity.
3. Validate cell count, bit pattern, stuffing, measured timing and yellow
   association. A serial `reply_sent` line cannot validate the waveform.
4. For delay C, the last handheld clock is roughly 41 ms before yellow
   and may be outside the usual 40 ms pretrigger view. Increase the saved
   window to 100 ms centered (10 ms/div) for **all five runs**, or position
   the trigger to retain at least 50 ms before yellow. Use actual preamble
   resolution; do not infer delay solely from the firmware banner.
5. If D4 never triggers, preserve that fact and the serial log. A later
   D2-triggered retry is a separate trial, not the missing waveform of the
   first attempt. Avoid interpreting 8000/8040 as phase/framing evidence
   without a recovered control.
6. If A1 or a restored A fails, stop the comparison and recover baseline
   with the Uno silent. If a capture mistriggers, exclude it and repeat
   that same candidate. Record reset versus coldboot explicitly.
7. Stop after A3 and adjudicate before adding variants; the only planned
   extension is a C/A confirmation pair if C changed the result. No hardware work
   is required while testing is parked.


Review provenance: an independent same-provider reviewer checked fresh
receive/caller bytes, the captured-waveform audit and the proposed battery.
Cross-provider review was unavailable in the exposed reviewer capabilities;
this is a degraded independent-review fallback, not cross-provider consensus.
The review approved the narrow conclusions and required adaptive C/A
confirmation before a timing-causality claim. No semantic rename, ASIC
identity, register-bit identity or new Ghidra behavior claim was promoted.
