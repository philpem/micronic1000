# Stock-context v7: terminal byte and descriptor diagnostic

Prepared 2026-09-24. **Owner reports v7 programmed, TESTING completed
and Main Menu reached. Single-7E readout reproduced; double-7E captured terminal byte C0h.**
The [v4-v6 handover](stock-context-v4-handover.md) retains the earlier
hardware observations and Uno framing comparisons.

## ROM to program

| Item | Value |
|---|---|
| Image | `analysis/rom_exerciser/releases/stock-context-v7/micron1_stock_context_v7.bin` |
| Size | 32,768 bytes |
| Programmer additive checksum (24-bit) | **386DC5** |
| Additive checksum (16-bit) | `6DC5` |
| SHA-256 | `e229a97bc464a9f332b158b898476f75a5e1b0ca6853079d6c37b8578307c5d2` |
| Manifest | Same path, `.json` extension |
| ROM01 | Leave unchanged |

Program ROM00 and run the programmer's VERIFY operation. Leave the
handheld powered off afterwards and report the checksum. For the initial
installation, the owner completed boot before a fresh recording was
armed; TESTING and Main Menu were observed by the owner, without a new
boot waveform. Programmer VERIFY/checksum has not been explicitly
reported for this installation. No additional reboot was requested;
the first receive trial starts from the confirmed Main Menu.

## What this answers

The double-7E/original-payload stimulus repeatedly returned terminal
`LINK_STATUS=8Eh` with v6's derived `N0001`. Fresh stock bytes and review
show that LINK_STATUS bit 2 forces an optional terminal INI from LINK_RXD,
then LINK_STATUS bit 3 produces error ECh. Matched zero-prefix and
zero-payload controls changed this behavior. The byte's value and actual
descriptor were missing. These observations do not establish a flag-count
ACK or successful packet reception; see the
[code-path review](commstar-evidence.md#observed-receive-paths-and-the-flag-ack-hypothesis-2026-09-24).

V7 captures that byte **from the RAM location already written by INI**.
It does not read LINK_RXD again. It also records the active descriptor
cursor, next write pointer, residual B and count operands. After the stock
receive returns and the yellow pulse finishes, it copies the active
descriptor's four bytes and prints the record. The descriptor contents
are therefore a **post-return memory snapshot**, not a bus trace.

## Readout: photograph both top rows

On EC, v7 writes exactly 40 characters, intended as two 20-column rows:

```text
R7IaaFF:ssvvLLLLPPPP
XDDDDWWWWCCCCTTTTRR 
```

| Field | Meaning |
|---|---|
| `aa`, `FF` | Raw stock return A and CPU F registers |
| `ss` | Terminal LINK_STATUS byte |
| `vv` | Terminal INI byte, **valid only if LINK_STATUS bit 2 is set**; otherwise printed `00` is an invalid placeholder |
| `LLLL` | Active descriptor length |
| `PPPP` | Active descriptor's buffer address |
| `DDDD` | Address of the active four-byte descriptor, not necessarily the chain head |
| `WWWW` | Next write pointer after the terminal read decision |
| `CCCC` | Saved BC count operand from the receive stack |
| `TTTT` | IX: total requested bytes through the active descriptor, modulo 65,536 |
| `RR` | Residual B at the terminal hook; `00` can represent 256 remaining |

**The four-character words are raw little-endian bytes.** For example,
`LLLL=0A00` means length 10; `DDDD=0080` means address 8000h. Do not
mentally reverse fields while reporting them. Send both rows verbatim or
a photo; the decoder labels and converts them:

```sh
analysis/venv/bin/python analysis/rom_exerciser/stock_context_v7.py \
  --decode 'R7IEC2D:8E7E0A000090 X0080019000000A0009'
```

That is a **synthetic emulator example**, not an expected hardware byte.
It means terminal byte 7Eh, descriptor at 8000h, length 10, buffer 9000h,
next write address 9001h. No terminal byte value is predicted for hardware.

For EE, ED or carry-clear success, v7 prints only `R7IaaFF` and stops.
Ignore any stale suffix or second row in that case; there is no displayed
terminal record. An EC result requires both complete rows. The stock LCD
configuration supports 20 characters per row; the owner reported both
rows on the first v7 run. Photograph the display if the layout differs. Reset between trials because this diagnostic is one-shot.

## Physical v7 results (2026-09-24)

CONFIRMED (owner-reported display, decoded by the v7 tooling): both
single-7E trials produced exactly:

```text
R7IEC29:CA000600E4FD
X0EFEE4FD0000060006
```

The terminal LINK_STATUS is CAh; its bit 2 is clear, so the displayed
terminal-byte `00` is invalid. Descriptor FE0Eh contains post-return
length 6 and buffer FDE4h. Next-write pointer FDE4h has not advanced;
saved BC=0000h, IX=0006h and residual B=06h. This is no advancement in
the active descriptor, not proof that the ASIC received no wire data;
the mandatory setup read is outside this count.

The first scope capture was a transient and is invalid as a reply trace.
The repeat serial log records one reply and a 916-us yellow pulse;
its saved scope capture contains 93 clock rising edges, five lead zeros,
MSB-first `7E 00 07 00 02 01 43 00 00 02 01`, 121.6-us median
clock period, and one 918-us yellow low pulse. The repeat capture is valid.
Artifacts use `analysis/captures/stock-v7-01-baseline-repeat-20260924`.

### Double-7E terminal byte

CONFIRMED (owner readout, v7 decoder and independent review):

```text
R7IECA9:8EC00600E4FD
X0EFEE5FD0000060005
```

LINK_STATUS=8Eh has bit 2 set: the terminal INI byte captured from RAM
is **C0h**. The post-return descriptor at FE0Eh remains length 6,
buffer FDE4h; next-write pointer is FDE5h, residual B=5, IX=6 and
saved BC=0. This records one descriptor byte advancement. LINK_STATUS
bit 3 remains set and the return is ECh with carry: frame validity,
byte role, ACK and FCS interpretations remain unproven.

The saved scope matches all 101 cells: five lead zeros, two raw 7Eh
bytes and original payload. Median clock period is 121.6 us; yellow low
begins 8.2624 ms after the first clock rise and lasts 918 us, before
emission finishes. Artifacts:
`analysis/captures/stock-v7-06-double7e-20260924*`.

After saving, the silent Uno image was uploaded and 5,626 flash bytes
verified. Its fresh banner confirms LISTEN ONLY. The double-7E repeat reproduced both rows exactly, including C0h and
one-byte advancement. Its serial log records a reply and 916-us yellow
pulse. The repeat scope capture is invalid: only 30 clock rises at short
spacing, no yellow pulse, consistent with a transient rather than the
101-cell reply. The first double-7E waveform remains valid. Repeat
artifacts use `stock-v7-06-double7e-repeat-20260924*`.

After the repeat, silent firmware was again flash-verified and its
LISTEN ONLY banner checked. Next: reset while silent, then single-7E
control with scope trigger on D4 yellow falling edge (same 80-ms span
and centered trigger) to avoid the D2 transient. No new ROM is needed.

### Final single-7E control and current state

CONFIRMED (owner display and saved GPIO waveform): final single-7E
returned the original two rows, `R7IEC29:CA000600E4FD` /
`X0EFEE4FD0000060006`. Status CAh, invalid terminal byte, no pointer
advancement. The D4 falling trigger captured all 93 intended clock cells
and original payload, with a 918-us yellow low pulse. Artifacts:
`analysis/captures/stock-v7-01-final-20260924*`.

Decode D3 at 60 us after each D2 rising edge. Sampling at 32 us was too
close to one transition and misread one payload bit; offsets 40, 50, 60,
70 and 80 us all reproduce the intended bytes. This is a GPIO decoder
sampling correction, not evidence of the ASIC sampling phase.

The completed comparison is single-7E / double-7E / double-7E /
single-7E: CA/no advancement, 8E/C0/one byte, 8E/C0/one byte,
CA/no advancement. Both double-7E readouts match exactly; only the first
has a valid full reply waveform. All four returns remain ECh errors.
No valid frame, ACK or FCS interpretation has been established.

Uno is now flash-verified silent, with a fresh LISTEN ONLY banner.
Before more framing/trailer trials, examine how the observed C0h could
relate to the emitted bitstream and terminal timing; use a controlled
payload or phase comparison to discriminate candidates. FCS brute force
is premature while the diagnostic returns before emission completes.

### C0 bitstream and stuffing analysis

CONFIRMED (saved POD1 samples, emitter source, reproducible analysis):
`analysis/stock_context_v7_bitstream.py` decodes each of the three valid
v7 captures identically at 40, 50, 60, 70 and 80 us after D2 rising edges.
The double-7E stream is five lead-zero cells, two raw 7Eh flags, then
`00 07 00 02 01 43 00 00 02 01`, MSB first.

The payload's maximum consecutive-one run is three. The configured
insert-zero-after-five-ones rule inserts **zero bits** here; applying
that destuffing rule therefore leaves all 80 payload bits unchanged.
Raw flags are outside the stuffed region and must not be passed through
that payload destuffer. Conversely, a rule expecting one after five
observed zeros fails at the sixth bit of the initial 00h payload byte;
blindly deleting bits under that rule would fabricate a decode. These
facts do not identify the ASIC's polarity or framing convention.

There is no aligned C0h payload byte under either bit order or constant
polarity inversion. Sliding eight-bit matches exist, but also occur in
the baseline that delivered no descriptor byte. Relevant direct-MSB
windows in the double-7E capture are:

| Zero-based emitted cells | Boundary crossed | Final bit sampled at +60 us, relative to first clock |
|---|---|---|
| 18-25 | second 7E / first 00 | 3.1084 ms |
| 35-42 | payload 07 / following 00 | 5.1844 ms |
| 67-74 | payload 43 / following 00 | 9.0892 ms |

Yellow falls at 8.2624 ms, after the terminal read. Thus the complete
67-74 window in this reply arrives too late to supply the captured C0h.
Preexisting controller-buffered data is not excluded by this comparison.
The first two are possible bit-pattern correspondences, not established
ASIC byte boundaries. Inverted/reversed matches exist too; the report
records them without promoting one to the receive convention.

CONFIRMED in the emulator, conditional on the fixture: terminal status
read to yellow falling output is 2,418 T-states; terminal INI to that
output is 2,351 T-states. At the owner-stated 3.6864 MHz, these are
655.924 and 637.750 us. Subtraction places the status read at about
7.6065 ms under the modeled timing. This is not an observed ASIC sample
instant; interrupt/wait-state delays and physical I/O timing are not
measured by that calculation. The emitted-byte buffer may also precede
the Z80 read. The marker is not a bit-sampling strobe.

**Next discriminating test:** keep v7 and the double-7E framing, phase,
length and stuffing mode fixed; change only the second payload byte
07h to 06h (payload-byte bit 0 clear). This changes emitted cell 36 from
1 to 0 and the direct-MSB window 35-42 from C0h to 80h, without adding
any stuff bits. SUSPECTED: C0h corresponds to that shifted window. A
reproducible 80h terminal byte would support the mapping; unchanged C0h
would weaken it, while a changed status alone would remain ambiguous.
Restore the original payload afterwards. No new ROM is needed.
Prepared variant09 in
`analysis/arduino/releases/stock-v7-framing/09-double7e-payload06/`.
Host checks passed (5 targeted tests); only emitted cell36 changes.
Owner confirmed Main Menu while Uno was silent, then authorized test
preparation. Variant09 was flash-verified and tested; results follow.
Restore verified silent firmware before any next handheld reset.

### Payload 07h to 06h result

CONFIRMED (owner display, decoded terminal record):

```text
R7IECAD:8EC00600E4FD
X0EFEE5FD0000060005
```

Terminal byte remains C0h, LINK_STATUS=8Eh, with the same one-byte
advancement, six-byte descriptor and residual B=5. CPU F differs from
the earlier A9h by bit 2 (parity/overflow); the carry-set ECh result
is unchanged.

The scope captured 101 cells; D3 samples at40..80us agree. Relative to
the original double-7E stream, only emitted cell36 changes. Window35..42
is now 80h, but the terminal byte remains C0h. This observation does not
match the specific fixed-window prediction. It does not establish the
flag-boundary candidate, controller-buffer origin or any FCS identity.
The original07h control was subsequently restored, completing this
comparison; see the results below.

Yellow low begins8.8664ms after the first clock rise (original8.2624ms)
and lasts918us. The604us difference is an observed marker-timing change;
no cause or exact ASIC sampling point is assigned from it.
Artifacts: `analysis/captures/stock-v7-09-payload06-20260924*`.
Uno restored to flash-verified silent; fresh LISTEN ONLY banner checked
before requesting the handheld reset for the original payload control.

### Original payload restored after the 06h trial

CONFIRMED (owner rows and valid 101-cell GPIO capture): restoring the
archived06 original payload produced `R7IECA9:8EC00600E4FD` /
`X0EFEE5FD0000060005`. Terminal C0h, status8Eh, one-byte advance.
All original bytes were captured identically at40..80us sampling offsets.
Yellow low began8.2616ms after first clock and lasted918.4us.
Artifacts: `analysis/captures/stock-v7-06-post09-control-20260924*`.

| Payload second byte | Terminal byte | LINK_STATUS | Descriptor advancement | Yellow onset after first clock |
|---|---|---|---|---|
| Original07h | C0h | 8Eh | 1 byte | 8.2624ms |
| Modified06h | C0h | 8Eh | 1 byte | 8.8664ms |
| Restored07h | C0h | 8Eh | 1 byte | 8.2616ms |

The proposed fixed direct-MSB window35..42 mapping did not predict the
observed terminal byte. The marker timing changed with the trial and
returned with the control; this is not a measurement of ASIC sampling
phase or a diagnosis of the error. No alternate window or FCS identity
is promoted. Uno restored to flash-verified silent, LISTEN ONLY banner
checked. This test series is complete; v7 remains installed.

### Prepared first-payload-byte 00h to 80h probe

Variant10 changes only first-payload-byte bit7, retaining second byte07h,
both raw7E flags, timing and stuffing mode. Payload becomes
`80 07 00 02 01 43 00 00 02 01`. Independent review and six targeted
host tests confirm exactly101cells, no inserted stuff bits and only
emitted cell21 changed. The direct-MSB window18..25 becomesD0h;
window35..42 remainsC0h. SUSPECTED: terminal C0h corresponds to the
flag/payload window. ReproducibleD0h with otherwise matching status/count
would support that mapping; unchangedC0h weakens it. Status/count changes
alone remain ambiguous. Verify scope and restore original00h control.
Archive: `analysis/arduino/releases/stock-v7-framing/10-double7e-payload80/`.
Built, reviewed and tested; physical result below. No new ROM required.

### First payload byte 80h result

CONFIRMED (complete owner readout): `R7IECAD:8EC00600E4FD` /
`X0EFEE5FD0000060005`. The initial abbreviated `R7IECAD` report was
clarified with both complete rows; there is no demonstrated display fault.
Terminal C0h, LINK_STATUS=8Eh and one descriptor-byte advancement persist.

The raw capture matches all101 intended cells, stable at40..80us sampling.
Onlycell21 differs from the original; candidate window18..25 isD0h,
while terminal byte remainsC0h. This fails the simple fixed-boundary
C0-to-D0 prediction, without identifying another byte source. Original00h
control was subsequently restored; see below. Yellow onset8.0120ms after first clock, width918us.
Artifacts: `analysis/captures/stock-v7-10-payload80-20260924*`.
Silent firmware flash-verified and LISTEN ONLY banner checked before
requesting the next handheld reset.

### Original00h control after the80h trial

CONFIRMED (owner rows and valid101-cell capture): original payload
restored `R7IECA9:8EC00600E4FD` / `X0EFEE5FD0000060005`.
Terminal C0h, LINK_STATUS=8Eh and one-byte advancement reproduced.
Stable40..80us sampling verifies the entire original stream.
Yellow onset8.2636ms after first clock, low width918us.
Artifacts: `analysis/captures/stock-v7-06-post10-control-20260924*`.

| First payload byte | Terminal byte | LINK_STATUS | Advancement | Yellow onset |
|---|---|---|---|---|
| Original00h (preceding control) | C0h | 8Eh | 1 byte | 8.2616ms |
| Modified80h | C0h | 8Eh | 1 byte | 8.0120ms |
| Restored00h | C0h | 8Eh | 1 byte | 8.2636ms |

The00h/80h/00h comparison is complete. Neither tested fixed direct-MSB
window predicted the returned byte change:07h->06h predicted80h and
00h->80h predictedD0h; both returnedC0h with original controls restored.
These results do not identify another alignment, controller-buffer
source, FCS or status-byte interpretation. C0h's origin remains open.
Uno restored to flash-verified silent with fresh LISTEN ONLY banner.

### Other explanations for invariant C0h (2026-09-24)

The v7 `terminal_byte_valid` field means that the optional terminal INI
occurred and its RAM byte was captured. It does **not** certify a complete
wire byte, an accepted frame or a valid checksum. Fresh stock listing at
ROM00:33CF-33FA confirms that ordinary reads require LINK_STATUS bit0;
the terminal read instead follows LINK_STATUS bit1 and bit2, before
LINK_STATUS bit3 selects ECh. V7 captures RAM immediately after that read.
Both failed fixed-window predictions leave more general alignment and
controller-state explanations open.

| Candidate | Evidence and limitation | Discriminating observation |
|---|---|---|
| SUSPECTED: partial byte or residual shift-register value at an error | All C0h cases are terminal reads on the error path, with no preceding descriptor advancement. This fits a terminal residue but does not identify one. | Hold timing/framing fixed and vary the amount of data clocked before deliberate termination; a repeatable relation between partial length and returned bits would support it. Exact abort/termination semantics remain unknown. |
| SUSPECTED: receiver samples a different clock phase or polarity | Saved D3 samples at every D2 rising edge are zero for original,06h and80h payload trials; later40-80us samples recover intended bits. This only establishes GPIO geometry, not ASIC sampling. | Phase-only comparison with original bytes and pulse width fixed; map status, count, byte and terminal time. Restore current+2/8 control between comparisons. |
| SUSPECTED: retained controller data or local transmit echo | The preceding handheld burst decodes to03h; bit reversal givesC0h. C0h survives both payload edits. This numerical match is not provenance, and the peer still changes terminal behavior. | Capture the value of the existing setup LINK_RXD read and the status trajectory; then test whether returned C0h tracks a deliberately changed local transmit byte. Instrumentation must not add port reads. |
| SUSPECTED: constant error-associated value from the controller | A terminal read can return a value whose error-state meaning differs from ordinary data; status8Eh alone does not identify that meaning. | Obtain ordinary LINK_STATUS-bit0 reads and compare their bytes with the terminal read across distinct error conditions. Do not label C0h as an error code without this evidence. |

A relevant external precedent is the Zilog SCC/ESCC, which transfers
receive-shift-register contents into its receive FIFO at frame termination
and records residue/error information. This only demonstrates that
terminal data need not be ordinary payload; it does not identify the
Micronic ASIC or its register semantics.
[Zilog SCC/ESCC user manual](https://zilog.com/docs/serial/UM0109.pdf).

CONFIRMED (fresh saved-waveform decode): the original preceding handheld
D0 samples at22 D1 rising edges are `0000110000001000001011`. The81h
pattern begins at index5; checked inverted stuffing removal yields
`00000011` (03h). These are the observed handheld-output levels, not the
unknown controller-input interpretation. Reproducible analysis:
`analysis/stock_context_v7_alternatives.py`; JSON under
`analysis/captures/stock-v7-alternatives-analysis-20260924.json`.

Lower-priority explanations: a diagnostic constant/stale print is weakened
by the immediate(HL-1) capture and existing varied-byte emulator tests,
although only a hardware bus trace could fully independently verify the
port value. Full-frame FCS failure remains possible as one controller
error, but the current early terminal read does not establish reception of
the full emitted frame, FCS width or coverage. Blind trailer brute force
therefore still lacks a useful acceptance baseline. NRZI is not established
on the receive path; observed handheld output is pulse coded, so the
historical claim of no NRZI applies to that measured direction only.

The original payload control has already been restored and captured
after both mutations. **Recommended order:** next a bounded phase-only
comparison, using v7 and
original double7E payload; then, if it stays terminal-only, design a ROM
snapshot of the already-existing setup read and receive-status history.
Do not add speculative reads that could clear or advance controller state.
No new hardware trial was performed during this analysis. Uno stayed silent.

### Owner timing expectation and next phase control

Owner expects the return data to be valid before clock rises, as with
transmit. The measured handheld transmit data leads its clock by about
30us; current Uno F7-derived settings instead delay data by about30us
(`STOCK_PHASE_IDX=3`, +2/8cell). The +2/8 setting was held constant for
framing comparisons; it has not established correct ASIC receive timing.
Do not treat obtaining an error-path byte as timing validation.

The next phase comparison should use the measured transmit convention:
`STOCK_PHASE_IDX=1`, -2/8cell, retaining original double7E payload and
all other settings, then restore +2/8 as a control. This is a hypothesis
about suitable receive timing, not proof that RX mirrors TX. Existing
transmit measurements show data falling before clock falls (the data
pulse is shorter than a full setup-plus-clock-high interval), so preserve
the measured pulse width rather than silently imposing a different width.
Prepared variant11 under
`analysis/arduino/releases/stock-v7-framing/11-double7e-phase-minus2/`.
Exact-build host stream gate and existing phase/chronology/stuffing test
passed. Build10388bytes; original101cells and all payload controls off.
MainMenu confirmation is required before active upload; result pending.

### First minus2/8 phase trial

CONFIRMED (owner): decimal errors8000 then8040, no R7 rows reported.
Serial log contains101 handheld bursts and34 `reply_sent=1` events,
all with requested phase-2/8, original payload and33msdelay; no yellow
marker event. Scope queried after run: SING, operation condition8,
TER=0, no error. Yellow-trigger acquisition never completed, so there
is **no valid trial waveform**. No stale waveform was exported as evidence.
This cannot distinguish no receive entry from no diagnostic return, nor
establish the ASIC sampling edge. The original phase must still be restored
as a control after a valid repeat capture.

Next: repeat unchanged variant11 using D2 rising trigger, armed after
upload/reset transients settle. Verify the101-cell stream with data
sampled at clock rise or shortly afterwards (minus2 phase), not at60us
as used for plus2. Then bracket with originalplus2. Uno restored to
flash-verified silent and fresh LISTEN ONLY banner before asking reset.
Artifacts: `analysis/captures/stock-v7-11-phase-minus2-20260924*` and
`stock-v7-11-phase-minus2-outcome-20260924.json`.

### Minus2/8 repeat and owner input-inversion hypothesis

CONFIRMED (owner): minus2 repeat again displayed decimal8000 then8040.
The D2-rising-trigger capture is valid:101 cells, exact original double7E
payload at D2 rising edges. D3 sampled at all101 D2 falling edges is zero.
Serial records34 replies and no yellow event; scope has no yellow pulse.
Artifacts: `analysis/captures/stock-v7-11-phase-minus2-repeat-20260924*`.

Fresh decoding of the previous plus2 control at actual D2 falling edges
recovers its complete original101-cell stream. Thus the phase comparison
is consistent with a receiver using the external falling edge. SUSPECTED
(owner): inversion in the clock receiver makes that a rising edge inside
the ASIC. Direct falling-edge ASIC sampling would produce the same
external observation; the electrical mechanism remains unproven.
The subsequent plus2 restoration failed; see the recovery note below.

SUSPECTED (owner, separate): data receiver also inverts. Complementing
the plus2 falling-edge samples gives flags81h,81h and payload
`FF F8 FF FD FE BC FF FF FD FE`; checked five-zero destuffing is valid
and removes no bits. This is a conditional mathematical transform,
not proof of data-path polarity or the ASIC's expected logical bytes.
Clock inversion does not establish data inversion. Any data-polarity
experiment must account for payload and stuffing as well as the flags;
changing just7E to81 is not equivalent to complementing the data path.
Evidence: `analysis/captures/stock-v7-input-inversion-check-20260924.json`.

Uno restored to flash-verified silent, fresh LISTEN ONLY banner checked.
No new optical connections or hardware identity are inferred.

### Failed plus2 restoration; reboot recovery pending

CONFIRMED (owner): archivedplus2 control now also gives decimal8000 then
8040. The upload was flash-verified; HEX SHA256 remains
`b59bcc70302f6d1160d6275c95a43ee1fd33b5a94a1d007d58a94abf6ad278d7`.
Serial logs47 replies across188 burst records and no yellow event. The
scope remainedSING/TER0, so no yellow-trigger trial waveform exists.
Artifacts: `analysis/captures/stock-v7-06-post11-control-20260924*`.

The phase comparison did not restore its original outcome. Withdraw any
causal inference that minus2 alone explains losing the R7 return, and
any claim that this experiment validates a falling-edge/inverted receiver.
Historical captures retain their measured edge geometry and readouts;
input inversion remains an unproved hypothesis. Hardware/session state
and present emission integrity remain unresolved.

Owner suspects recurrence of an earlier quiet state and requests hardware
reboot. Uno was already reset by silent upload, flashverified and fresh
LISTEN ONLY banner checked. Owner then confirmed Main Menu; repeat
archivedplus2 with D2 clock trigger. Recover the baseline before changing
phase, polarity, payload or ROM. No RAM-clear procedure was requested.

### Post-reboot recovery: ordinary receive byte, terminal8Ah

Owner reports reset restored the diagnostic return:

```text
R7IEC29:8A000600E4FD
X0EFEE5FD0000060005
```

CONFIRMED (decoder): LINK_STATUS=8Ah, terminal-byte-valid false; active
six-byte descriptor atFE0Eh has bufferFDE4h and next-writeFDE5h, IX6,
residualB5 and savedBC0. Status bit2 is clear, so no terminal INI occurs.
The one-byte advancement is therefore an earlier ordinary INI gated by
LINK_STATUS bit0 atROM00:33D4. The displayed00 is an invalid terminal
placeholder, not the value of that ordinary byte. Its value is unknown.
LINK_STATUS bit3 still selects the ECh error return.

Fresh bytes atROM00:33CF-33FB and an emulator fixture with status sequence
01h,8Ah and an arbitrary synthetic byte5Ah reproduce this distinction:
buffer receives5Ah, next-write advances one, terminal display remains00.
This is a software check, not a prediction that hardware received5Ah.

Scope confirms all101 original cells, stable at40..80us after clock rise;
yellow onset8.2480ms after first clock, width918us.
Artifacts: `analysis/captures/stock-v7-06-reboot-control-20260924*`.
Owner's reboot restored a diagnostic return, but not the exact earlier
8Eh/C0h terminal-read result. Thus the phase comparison remains inconclusive.

SUSPECTED: the same controller byte could be consumed on an ordinary poll
in one trial and on terminal handling in another. To test this, a future
diagnostic must preserve ordinary received bytes as well as any terminal
byte; v7 cannot distinguish equal values from different ones in these runs.
Do not infer ordinary byteC0h from the earlier terminalC0h observations.
Uno restored to flash-verified silent and fresh LISTEN ONLY banner checked.

## Test sequence

1. **Silent boot:** after programmer VERIFY, arm the passive Uno recording
   before handheld power-on. Allow the normal TESTING interval and record
   whether Main Menu appears. Keep ROM01, alignment and leads unchanged.
2. **Single-7E reference:** at Main Menu, upload and flash-verify archived
   Uno variant `01-7e-open`; check its fresh banner and arm scope capture.
   Only then run **Load/Run → FOO → V24 ADAPTOR → LOCAL_LINK**. Photograph
   both top rows. The v6 reference was `EC`, status `CA`, derived count 0;
   v7 should first reproduce that status class before interpreting new data.
   With status CAh, `vv=00` is an invalid placeholder, not a received zero.
3. **Double-7E byte capture:** verify the Uno silent, then reset to Main
   Menu. Upload and verify archived
   variant `06-prefix7e-open7e`, start a fresh log, and arm scope. Repeat the
   same Load/Run operation. The v6 reference was `EC`, status `8E`, derived
   count 1. If 8Eh recurs, `vv` is the byte read by the terminal INI. Record
   all fields, not just the byte. CPU F may vary (A9h/ADh were observed).
4. **Reproduce and bracket:** repeat double-7E if needed to establish the
   byte/descriptor result, then restore the single-7E reference. If the
   baseline fails or the new readout is incomplete, preserve the evidence
   and resolve that before further framing/FCS trials. Archived v6 remains
   the rollback comparator; do not interpret a v7-only change as protocol
   acceptance.
5. **Finish:** restore the Uno to verified LISTEN_ONLY, stop the logger and
   restore the scope's saved settings. Variant 08 (double-7E/zero payload)
   is optional only if a remaining payload question justifies another run.

Archived Uno files are under
`analysis/arduino/releases/stock-v6-framing-matrix/`; use those HEX files
rather than rebuilding historical variants from the current sketch:

| Variant | SHA-256 of `m1000_ir_probe.ino.hex` |
|---|---|
| `01-7e-open` | `24213f2ec3417f7d95724ab6a815d505588bc5fadf3dd9e26e19bba7a689c76b` |
| `06-prefix7e-open7e` | `b59bcc70302f6d1160d6275c95a43ee1fd33b5a94a1d007d58a94abf6ad278d7` |
| `08-prefix7e-open7e-zero80` | `cfa06472301ace95d38fbc8ecc1ebf78e7681f915e24c5550057dc780e738540` |

The separate silent image is
`analysis/arduino/releases/stock-silent/m1000_ir_probe.ino.hex`, SHA-256
`2648062784ed40549a52bb409687f6afab954447fb08e5a0eb74ec8d3a681357`.

### Capture preparation

Scope D0/D1 are the handheld data/clock channels; D2 is Uno D5, D3 is Uno
D6, and D4 is yellow/pin 6. Preserve existing ground and optical alignment.
**Before every handheld reset, stop the active Uno responder and verify
the silent image is running.** Only enable a response image after Main
Menu is confirmed. Owner reported a startup crash with the active
responder and had to block IR or move the handheld to reach Main Menu.
The owner clarified that the failure displayed the quoted R diagnostics
and suspected re-entry into Commstar with a Uno response. This mechanism
is SUSPECTED: a reset-to-link control-flow trace would test it. Do not
expose startup to a test response. If the
owner moved or blocked the link, confirm restored alignment before capture.

For each reply, use a centered 8-ms/div capture, DIG2 rising single trigger,
POD1 BYTE RAW export. Stop the old serial logger before uploading; restart
with a fresh banner and reset the Uno retry counter. Let upload/reset
transients settle, then arm the scope after the owner confirms Main Menu.
Verify the scope is actually running and waiting for a trigger before
requesting Load/Run. TER=0 alone is insufficient: it is an event latch,
not an armed-state indication. Check acquisition state and the
front-panel display; preserve any completed acquisition before rearming.
AER? clears its event register, which is summarized in the operation
condition Wait Trig indication: a subsequent cleared indication does not
by itself demonstrate disarming. On 2026-09-24, repeated queries without
AER? returned SING, condition=40, TER=0, and no error, while the screenshot
still showed "Trig'd?". The owner confirmed that the orange Single button
means armed and "Trig'd?" means waiting for a trigger. This resolves the
panel ambiguity; the owner subsequently completed the baseline repeat.

Query actual acquisition rate/points and the SCPI error queue.
**Do not write numeric values to ACQuire:SRATe or ACQuire:POINts**: this
scope rejects those setters with error -128. A previous useful setup read
back 20 MSa/s and 2M points, but transferred POD1 data was 200,000 samples
at 400 ns/sample. Use the transfer preamble to decode time. Save raw data,
PNG, preamble/metadata and the matching serial log before rearming. Scope
transients without a valid emitted sequence must not be treated as a trial.

## Guards and verification

CONFIRMED (builder, stock listing and emulator):

* The builder requires the complete stock-ROM SHA-256 and original patch
  bytes. Changes are confined to the existing call/init sites, terminal
  hook at ROM00:33F8 and the zero cave at ROM00:7E96-7FF9.
* Code ends at ROM00:7FED (exclusive), leaving 13 bytes of the cave unused.
  Stock reset routes, boot witness and pre-existing receive wrapper remain.
* All receive I/O values and cycle timestamps through the terminal sample
  match v6, including any terminal INI. The hook preserves the original
  AF, registers and two-POP continuation on both success/error paths.
* Relative to v6, the hook adds 109 T-states without a terminal INI and
  136 with one, **after** the status sample (about 29.57/36.89 microseconds
  at the owner-supplied 3.6864 MHz clock). Cleanup and marker onset move
  later by that amount; yellow pulse widths remain unchanged. EE/ED paths
  receive no additional hook delay.
* Scratch RAM is C7E0-C7F2, extending v6's upper-TPA snapshot. Use the same
  FOO test state with no loaded application; this is not a general-purpose
  ROM for arbitrary loaded software. Descriptor contents are copied after
  return, and scratch/descriptor overlap is not a supported test setup.
* Forty-seven v5/v6/v7 tests passed, including artifact reproduction, both
  status branches, actual byte values, multi-descriptor chains, the
  256-byte boundary, stale-record suppression and marker timing. The
  independent release review approved the guarded one-shot design.

Build, test and decode with the repository environment:

```sh
analysis/venv/bin/python analysis/rom_exerciser/stock_context_v7.py \
  -o /tmp/micron1_stock_context_v7.bin
analysis/venv/bin/python -m pytest -q \
  analysis/test_stock_context_v7.py \
  analysis/test_stock_context_v6.py analysis/test_stock_context_v5.py
sha256sum /tmp/micron1_stock_context_v7.bin
```
