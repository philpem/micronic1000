# Stock-context v4: receive result and handover

**Next image: [v7 terminal-byte/descriptor diagnostic](stock-context-v7-handover.md),
ROM00 checksum 386DC5.** The Uno-only series below is complete; v7 is
built and emulator-tested, with physical validation pending.

Prepared 2026-09-24 on `ir/stock-context-v3-content`, PR #26.
**Historical preparation record. V4 was installed and did not reach the
expected prompt in the first physical trial; see the update below.**
This replaces the proposed `stock-rx-entry` burn. Keep old releases as
historical evidence, not as the next image to install.

## 2026-09-24 physical trial and stock-reset comparison

### Review: recommended next tests

This review supersedes the immediate receive-entry ROM proposal below.
Keep the installed v6 ROM00 (`385DEB`) for the next series. CONFIRMED:
the unswapped F7 stimulus repeatedly produces `EC29`, terminal
`LINK_STATUS=CAh`, derived `N0000`, and a return marker, including
after the swapped comparison. The owner has confirmed optical delivery.
Neither internal ASIC input identity nor a schematic is needed to
compare candidate input frames against this repeatable response.

The swapped run completed the normal UI error sequence. A permanently
stalled receive call is therefore a weaker working hypothesis than
the prior plan implied; no-entry versus no-return remains unmeasured.
Do not spend the next ROM burn solely on that distinction. A marker
before receive would add I/O and delay before receive arm and require
a new baseline. The v6 hook deliberately samples after the stock
terminal read, preserving the earlier receive sequence.

Recommended Uno-only matrix, holding original `swap=0`, drive levels,
phase, five lead cells, 33-ms delay and ten-byte F7 payload fixed:

| Order | Opening byte | Closing byte | Purpose |
|---|---|---|---|
| A | `7Eh` | none | Reproduce the v6 F7 reference |
| B | `7Eh` | `7Eh` | Add closure only |
| C | `81h` | `7Eh` | Owner's mixed-marker hypothesis; change opening from B |
| D | `81h` | none | Separate opening choice from closure |
| A again | `7Eh` | none | Verify reference recovery |

Explicitly use stuffing mode 1 throughout this matrix. CONFIRMED
(archived Uno source `1f0bff5`): automatic stuffing switches from
inserting zero after five ones to inserting one after five zeros when
the selected opening flag changes from `7Eh` to `81h`. Also,
`putClosingFlag()` calls `putFlag()`, so the existing close option
cannot express independent `81h` opening and `7Eh` closing. Prepare
and verify that small Uno extension before hardware testing. Check
the generated bits and scope capture; this matrix has 93 cells for
the open variants and 101 for the closed variants with this payload.
It tests this fixed stuffing convention, not every possible protocol.

Reset the handheld to Main Menu before each attempt; verify the Uno
banner and reset its reply counter before the V24 operation. Record
the exact LCD text, return marker, actual transmitted bits and launch
delay from handheld clocks. If a candidate changes the outcome,
bracket its repeat with working A controls. If A fails, stop causal
comparisons and restore the reference. Prior F8-F11b negatives do not
settle this matrix because the later exact F7 reference failed too.

If closure changes the result, compare it with eight additional
clock-only cells under the same opening byte. This controls added
duration/clocks; a delimiter interpretation still needs evidence.
Inspect the first emitted reply separately: archived F7 counts short
burst fragments for sparse pacing, whereas later code filters them.
Do not silently change this counter while changing framing, or infer
equivalent exposure from aggregate reply counts.
Use the current counter (ignore bursts shorter than nine cells) in
every matrix variant, but first require its A baseline to reproduce
the archived F7 readout on v6. If that baseline fails, restore the
archived F7 HEX and resolve the discrepancy before running candidates.
Keep all candidate builds on the same source and counter behavior.

A changed A/F or terminal status is a discriminating response. A
changed `N` is a derived measurement to qualify, not proof of accepted
bytes. A carry-clear return is a stronger transport milestone; v6
stops before subsequent frame validation, so it cannot prove a working
session. No `R6I` is also an observation, not a successful frame.

If this small controlled matrix leaves every returning candidate at
`EC29/CA/N0000`, prepare a richer ROM diagnostic: raw descriptor/count
operands, selected receive-buffer contents after return, and only
then a carefully assessed entry/status-history witness if needed.
Avoid a pulse or LCD output before receive without quantifying the
timing change and reproducing F7 under the new instrumentation.
Keep boot/standby issue #27 separate from the now-repeatable v6 V24
test. This review did not upload firmware or operate the hardware.

Owner follow-up: a trailer FCS remains SUSPECTED and may use the
stuffed data path before a raw closing marker. The stock reader's
terminal-status check is compatible with ASIC-managed validation,
but does not identify an FCS or prove every optical byte reaches RAM.
Do not run a rotating 256-byte search against one-shot v6: its first
receive return stops execution. See the
[FCS evidence and search constraints](commstar-evidence.md#fcs-hypothesis-and-test-limits-2026-09-24).
The delimiter matrix is delegated to a cheaper worker. Prepared HEXes
and per-variant manifests are in
`analysis/arduino/releases/stock-v6-framing-matrix/`: `01-7e-open`,
`02-7e-close-7e`, `03-81-close-7e`, `04-81-open`, and `05-81-tail00`.
The new
`STOCK_CLOSE_BYTE` option appends one raw byte outside the stuffed
payload; row E uses `00` only to emit eight data-low cells, not as a
protocol closing flag or FCS. Host tests compile the actual framer and
check all five complete bit strings plus terminal stuffing.
The new baseline must reproduce the archived F7 readout on v6 before
the other variants are interpreted.

### Framing matrix physical results so far

CONFIRMED (owner display and captured Uno GPIO): row A (`7E` open) and
row B (`7E` opening, raw `7E` closing marker) both returned
`R6IEC29SCAN0000`. The row A scope capture contains 93 D2 clock cells;
row B contains 101. In both, D3 sampled 40 us after each D2 rise matches
the five lead zeros, opening `7E`, fixed ten-byte payload and, for row B,
the raw closing `7E`. The launch began 33.048 ms (A) and 33.046 ms (B)
after the last D1 rising edge. Captures and byte-for-byte decode summaries
are in `analysis/captures/stock-v6-framing-baseline-20260924*` and
`analysis/captures/stock-v6-framing-02-7e-close7e-20260924*`.

The D4 yellow low pulse was about 918 us in both captures. In row B it
began at 11.867 ms, while the closing marker was still being clocked:
the close marker started at 11.344 ms and the final D2 clock rose at
12.200 ms. CONFIRMED: adding the closing marker did not change the
owner-reported diagnostic or the captured yellow-pulse duration. Because
the marker begins before the closing byte finishes, the unchanged pulse
does not show that the ASIC processed the entire closing marker. It also
does not identify a trailer FCS or exclude one.

Row C (`81` opening, raw `7E` closing) displayed
`R6IECA9SCAN0000`. Its capture contains 101 D2 rising clock cells and
matches the five lead zeros, opening `81`, fixed payload and raw closing
`7E`. Yellow D4 was low for 918 us, beginning at 12.3548 ms, 153.2 us
after the final D2 rising edge. The changed displayed `F` byte is not
evidence of progress: the captured `LINK_STATUS=CAh` follows the same
bit-3 error branch as row A, and `N0000` is unchanged. See
`analysis/captures/stock-v6-framing-03-81-close7e-20260924*`.

A same-length repeat of row C again emitted 101 cells (`81` + payload +
raw `7E`) and displayed `R6IECADSCAN0000`. The serial suffix differed
from the first row-C display, but `LINK_STATUS=CAh` still followed the
same bit-3 error branch; `N0000` remained unchanged. Yellow D4 was low
for 918 us. See
`analysis/captures/stock-v6-framing-03-81-close7e-repeat-20260924*`.

After row C, the baseline image was reinstalled and verified. The owner
again reported `R6IEC29SCAN0000`; the recovery capture reproduced 93
D2 rising clock cells and the exact five lead zeros, opening `7E`, and
fixed payload. Yellow D4 was low for 918.4 us. See
`analysis/captures/stock-v6-framing-01-recovery2-20260924*`.

Row D (`81` opening, no explicit closing marker) displayed
`R6IEE6D` on two runs. The valid repeat capture has 93 D2 rising clock
cells and matches the five lead zeros, opening `81`, and fixed payload.
Yellow D4 was low for 918 us, beginning 37.6624 ms after the D2 trigger.
The first D2 rising edge followed the final D1 rising edge by 33.0492 ms.
The Uno log reports an 8-cell burst ignored, then its 17-cell reply,
followed by `NO DATA-LINE ACTIVITY OBSERVED`. This is the probe's
software observation; it does not establish whether or how the ASIC
received bytes. The first row-D scope save was a reset transient and is
retained as invalid; use the `...04-81-open-repeat...` raw capture,
PNG and metadata for the valid emitted-frame record.

Row E (`81` + payload + raw `00`, eight data-low cells) also displayed
`R6IEE6D`, with 101 D2 rising cells and a 918-us yellow pulse. The
capture confirms five lead zeros, `81`, the unchanged payload and eight
trailing zero cells. Its text matches row D's 93-cell open frame, while
the 101-cell `81` + payload + raw `7E` row-C repeat displayed
`R6IECADSCAN0000`. The two tail patterns therefore produced different
reported terminal outcomes at the same total clock count; this alone
does not establish which bytes the ASIC received. See
`analysis/captures/stock-v6-framing-05-81-tail00-20260924*`.

Rows F and G tested a raw prefix before the same opening `7E`, payload,
and no closing marker. Row F used prefix `7E`; on both A and final A
repeat the owner saw `R6IECA9S8EN0001`. Each capture has 101 D2 rising
cells, and the repeated run's D3 samples match the first F capture at all
101 cell positions. Yellow D4 was low for 918.0 us on the first run and
918.4 us on repeat, beginning at 8.2272 ms and 8.2236 ms respectively.
That pulse begins before the 101-cell emission finishes, so it does not
show that the ASIC processed the full emitted sequence.

CONFIRMED from the v6 status branch: F's `LINK_STATUS=8Eh` has bit 2 set,
which takes the optional terminal `INI` read from `LINK_RXD`; the status
is preserved across the surrounding push/pop, and bit 3 remains set to
select the existing error path. The displayed `N0001` is consistent with
one read for this ordinary small descriptor. This does not identify the
received byte or show that the frame was accepted.

Row G used raw prefix `00`; the owner saw `R6IEC29SCAN0000`, matching the
01 opening-only reference. Its 101-cell capture contains five lead lows,
raw `00`, opening `7E`, and the unchanged payload. The scope capture and
analysis files are `analysis/captures/stock-v6-framing-06-prefix7e-repeat-20260924*`
and `analysis/captures/stock-v6-framing-07-prefix00-open7e-refresh-20260924*`.

Row H used that double-`7E` prefix with an 80-cell zero payload. The
owner displayed `R6IEE6D`. The valid single-trigger capture contains 101
D2 rising cells and the expected five lead lows, two `7E` bytes, and 80
zero payload cells. D4 was low for 918 us starting 32.9096 ms from the
scope trigger. The Uno log contains two transmitted replies separated by
a reset, but the scope record contains only one complete emitted frame;
the saved single-trigger capture maps to the first reply. This is
emitted-wire evidence, not evidence that the ASIC accepted the frame.
See `analysis/captures/stock-v6-framing-08-prefix7e-open7e-zero80-20260924*`.

Row I restored the original ten-byte payload with the same two `7E`
bytes and 101-cell timing. The owner displayed `R6IECADS8EN0001`; the
captured D3 samples match row F's original-payload double-flag waveform.
D4 was low for 918 us at 8.212 ms. The readout gives CPU A=`ECh`, F=`ADh`,
terminal `LINK_STATUS=8Eh`, and `N0001`. `LINK_STATUS` bit 2 is set, so
the stock path performs the optional terminal `INI` read;
`LINK_STATUS` bit 3 remains set and selects the existing error path. The
reported one-read count is consistent with an ordinary small descriptor.
The result does not identify the received byte or establish frame
acceptance. See
`analysis/captures/stock-v6-framing-06-prefix7e-open7e-control-20260924*`.

The next step is offline: inspect the actual terminal-byte value and
descriptor guard that limits receive reads. Do not interpret the current
yellow pulse or `N0001` as proof of valid frame reception. After testing,
the Uno was restored to the flash-verified LISTEN_ONLY image. The scope
was returned to its saved acquisition mode, timebase, trigger and waveform
settings; sample rate and point count were queried, not written, because
the scope rejects numeric writes to those acquisition fields.

The final row-A reference again displayed `R6IEC29SCAN0000`. Its capture
contains 93 D2 rising cells matching five lead zeros, opening `7E` and
the fixed payload; yellow D4 was low 918.4 us. The final capture is in
`analysis/captures/stock-v6-framing-01-final-20260924*`. The Uno has
since been restored to the flash-verified LISTEN_ONLY image and its fresh
banner confirms that it is not transmitting. The scope was restored to
its saved settings. Alignment, optical levels and controller state
remain unmeasured.

The boot/standby control-flow question is tracked in
[issue #27](https://github.com/philpem/micronic1000/issues/27).

### V6 terminal-status diagnostic ready for hardware

CONFIRMED (owner, 2026-09-24): ROM00 v6 passed programmer VERIFY with
sum24 `385DEB`. A true coldstart displayed TESTING, then `Backup
battery low`, workstation serial-number entry and Main Menu. The
LISTEN_ONLY Uno recorded a 5,452-us yellow initialization pulse. The
silent V24 FOO control produced the owner's `8000 error`, then
`8040 error`, with no `R6I...` prefix; its capture has 100 handheld
bursts, zero Uno replies and no receive marker.

The matched F7 run (reset-button return to Main Menu, then explicit V24
selection) produced the owner's exact display
`R6IEC29SCAN0000ess`. CONFIRMED by v6 hook bytes, stock `ROM00:33F7-
33FA`, emulator tests and independent readout review: the diagnostic
field is `R6I EC 29 S CA N 0000`. The trailing `ess` is stale screen
text after the one-shot stop. Raw A=`ECh`, F=`29h`; the sampled terminal
`LINK_STATUS=CAh` has `LINK_STATUS` bits 0 and 2 clear and bits 1, 3,
6 and 7 set. F sign is clear, selecting the `ROM00:33FA` status-bit-3
branch rather than the short-count branch. `N0000` is the diagnostic's
reported **derived** count of receive-loop `INI` data reads. For an
ordinary small descriptor it means no `INI` occurred before the
terminal sample. This count excludes the mandatory setup read of
`LINK_RXD` at `ROM00:338C`; it is not a physical byte-arrival counter.
The v6 count expression also has a 256-byte descriptor boundary
ambiguity because B=`00h` represents 256 remaining before the first
`INI`. Preserve `N0000` as a reported measurement until the active
descriptor length is observed directly.

CONFIRMED (Uno capture): one 17-cell handheld burst had
`reply_sent=1`, followed by a 920-us yellow return marker starting
11,912 us after the Uno's reported F7 TX start. A 5,452-us
initialization marker preceded that run. No logger drops were reported.
The Uno was restored to the archived LISTEN_ONLY HEX, flash-verified,
and a fresh banner confirmed silent mode. OPEN: why the controller
reported `LINK_STATUS` bit 3 and whether the F7 optical waveform met
the receive controller's framing/timing requirements. The matched
silent/F7 difference supports a stimulus relationship but does not
prove a decoded reply frame. The GPIO scope comparison below verifies
the actual Uno output at high resolution. It does not establish the
optical signal by itself or what the handheld controller decoded;
the owner separately confirmed signal at the optical receivers. Keep
the F7 payload fixed while exposing active descriptor length and
`LINK_STATUS` progression in a narrowly scoped diagnostic.

#### Same-image F7 scope repeat

CONFIRMED (owner): with v6 still installed, the repeated V24 operation
again displayed `R6IEC29SCAN0000`. The Uno was flashed with the exact
archived F7 HEX using the local Arduino CLI and its flash verified.
The passive logger ran before the scoped attempt and contains several
earlier reset-button/F7 returns; only the final, owner-reported attempt
was captured by the single-shot scope. Do not attach the scope record
to every earlier serial event. The scoped attempt's Uno log reports
one `reply_sent=1` burst followed by a 920-us yellow low, 11,912 us
after its reported TX start. The Uno was restored to flash-verified
LISTEN_ONLY afterward; a fresh banner confirmed no transmission.

CONFIRMED (50-MSa/s Keysight POD1 record, owner-confirmed mapping,
independent decode): scope D2 on Uno D5 has exactly 93 clock pulses;
scope D3 on Uno D6 has 16 data-high pulses. Sampling D3 40 us after
each D2 clock rise produces **93/93 matching cells** against the F7
source: five clock-only lead cells, `7Eh` flag, then all 80 MSB-first
payload bits `00 07 00 02 01 43 00 00 02 01`. No cell was missing.
The D2 rise intervals have median 121.44 us and range 114.88-127.94
us; D3 rising edges occur 23.92-30.94 us after their D2 clock rise.
Scope D4 on yellow fell 11,868.28 us after the trigger and stayed low
918.42 us; its fall was 541.98 us after the last D3 falling edge.
The F7 payload has no run of five one bits, so this capture cannot
exercise or validate the configured bit-stuffing rule. D2/D3 measure
Uno GPIO voltage, not emitted IR intensity or optical polarity at the
handheld detector. D4 witnesses the ROM's carry-set return, not frame
acceptance. `LINK_STATUS=CAh` remains unexplained.

Evidence: `analysis/captures/stock-v6-f7-scope-repeat-20260924.pod1.bin.gz`
and adjacent preamble JSON, analysis JSON, PNG, and Uno JSONL. The raw
POD1 record has 1,000,000 bytes at 20 ns/sample over 20 ms. The scope
settings were restored to their prior 8-ms/div, DIG1-trigger, AUTO
running state after download. The
[Keysight 3000 X-Series Programmer's Guide](https://www.keysight.com/us/en/assets/9018-06894/programming-guides/9018-06894.pdf)
describes the POD1 waveform transfer and preamble format used here.

#### F7 LED-role swap, same v6 ROM

CONFIRMED (owner, 2026-09-24): after a reset-button return to Main
Menu, with alignment and scope leads unchanged, the swap-only F7
trial showed `8000 error` then `8040 error`, with no `R6I...` prefix.
This is the same reported screen sequence as the silent control. The
control rebuild from source commit `1f0bff5` was byte-identical to the
archived F7 HEX; the test image changed only `STOCK_TX_SWAP=0` to `1`.
The upload passed Arduino CLI flash VERIFY and its banner confirmed
`swap=1`, fixed `7Eh` flag, phase 2, content index 2 and 33-ms delay.

CONFIRMED (Uno serial capture): the V24 operation produced 148 logged
handheld bursts and 50 `reply_sent=1` events from 02:43:35 to
02:43:46 UTC. No yellow return marker was logged during that interval.
The sole 5,448-us yellow pulse in this capture preceded the attempt
at 02:42:58 UTC and is consistent with the reset-button path; it
must not be counted as a reply marker.

CONFIRMED (Keysight POD1 capture): with scope D3 on Uno D6 and D2 on
Uno D5, D3 carried 93 clock pulses and D2 carried 16 data-high pulses.
Sampling D2 40 us after each D3 rise gave **93/93 cells** matching
the five lead clocks, `7Eh` flag and unchanged 80 payload bits
`00 07 00 02 01 43 00 00 02 01`. D3 period median was 120.92 us
(range 113.52–133.68 us); D2 rises followed D3 rises by
17.2–30.8 us. D4 had no yellow edge in this 20-ms frame window.
The serial log covers the whole attempt, while the scope establishes
the electrical waveform for one frame. Neither measures emitted light
or the handheld's optical receive pins. Separately, the owner has
checked that signals reach the handheld's optical receivers; that
check did not identify which receiver carries clock or data.

The matched change in owner display and return-marker behavior is
consistent with sensitivity to the LED-role assignment. It does not
identify which LED serves which optical channel or prove that the
unswapped frame was decoded correctly: alignment, optical levels and
controller state remain unmeasured. The A/B/A control below tests
whether the contrast persists. The absence of `R6I...` alone does not distinguish no
`Link_BlockRx` entry from a call that did not return.

Evidence: `analysis/arduino/releases/f7-sparse33-swap1/manifest.json`;
`analysis/captures/stock-v6-f7-swap1-20260924.jsonl` and the adjacent
`stock-v6-f7-swap1-scope-20260924` raw POD1, preamble JSON,
analysis JSON and PNG. The Uno is restored to flash-verified
LISTEN_ONLY with a fresh silent banner; the scope is restored to its
prior 8-ms/div, DIG1, AUTO running state.

#### A/B/A unswapped replay

CONFIRMED (owner): keeping the same optical alignment and scope leads,
the handheld returned to Main Menu by reset button. Reinstalling the
exact archived unswapped F7 HEX passed flash VERIFY; its banner showed
`swap=0` with the same flag, phase, payload and reply delay. The next
V24 operation displayed `R6IEC29SCAN0000`, reproducing the earlier
unswapped v6 result after the intervening swapped failure.

CONFIRMED (Uno/scope): the serial log shows one replied 22-cell burst
and a 916-us yellow return marker; a separate 5,452-us marker preceded
the run after reset. The 20-ms POD1 record has D2/Uno D5 clock 93
times and D3/Uno D6 data 16 times. All 93 sampled cells match the
unchanged F7 bits. D4 yellow fell 11,884.56 us after the scope trigger
and stayed low 918.4 us, starting 553.84 us after the last D3 fall.
Thus the observed `R6I`/return-marker difference survived an
unswapped → swapped → unswapped sequence with the same v6 ROM and
reported alignment. This is a repeatable assignment-dependent outcome
under the present setup, not a physical mapping of the IR emitters or
proof of decoded frame data. CONFIRMED (owner hardware check): IR
signals reach the handheld's optical receivers. Which receiver carries
clock versus data remains unknown: the receive logic is inside an ASIC
and the owner has no schematic or accessible signal identity. Mapping
those internal channels is not a prerequisite for a black-box protocol
test. The next discriminant is a narrow ROM witness that separates
receive-call entry, wait and terminal return, and reports the active
descriptor length to qualify `N0000`.

Evidence: `analysis/captures/stock-v6-f7-unswap-a2-20260924.jsonl`
and the adjacent `stock-v6-f7-unswap-a2-scope-20260924` raw POD1,
preamble JSON, analysis JSON and PNG. The Uno was again restored to
flash-verified LISTEN_ONLY with a fresh silent banner, and the scope
was restored to its prior 8-ms/div, DIG1, AUTO running state.

The tested ROM00 image is
`analysis/rom_exerciser/releases/stock-context-v6/micron1_stock_context_v6.bin`.
Leave ROM01 stock. The v6 release is 32,768 bytes, MD5
`0291174d024df3e039083e6a267e710d`, additive sum16 `5DEB`,
programmer sum24 **`385DEB`**, SHA-256
`fb9171ee01b89e4cadda605674372ea0b1aabcf2fcd2ee559b0ecc6dee472066`.
The adjacent JSON records all guarded patch sites. Physical results are
recorded above.

CONFIRMED (builder bytes and emulator): v6 retains v5's stock reset
routes, initialization marker and receive wrapper. The sole new stock
instruction patch is `ROM00:33F8`, after the fourth `RRCA` has sampled
the terminal `LINK_STATUS` byte. The hook snapshots rotated status,
remaining B, the saved descriptor count and IX, then performs the
original pops and carry branch. There is no added I/O or delay before
the terminal status sample. Modeled v5 and v6 I/O and registers match
through that sample, and raw AF matches on return for the EC29 case.
The snapshot uses RAM:C7E4-C7E9 in addition to v5's C7E0-C7E3.
Those cells are diagnostic scratch for this one-shot FOO trial, not a
general claim that loaded software leaves them free.

On an `ECh` return, the exact v6 diagnostic prefix is
`R6IaaFFSssNnnnn`: `aa` is raw return A, `FF` raw return F,
`ss` the reconstructed terminal `LINK_STATUS` byte, and `nnnn` the
derived receive-loop data-read count, in hexadecimal. For ED/EE it
prints only `R6IaaFF`; no terminal sample is attributed to those paths.
The diagnostic then stops intentionally; any adjacent `in progress`
text may be left over from the application screen. For the observed
v5 `EC29`, `ss` must have `LINK_STATUS` bit 0 clear and bits 1 and 3
set. `N0000` is qualified by the descriptor-length caveat above;
neither count outcome by itself identifies why `LINK_STATUS` bit 3
was set or proves a valid frame.

Bench sequence: verify the v6 programmer checksum, coldstart with the
Uno on flash-verified LISTEN_ONLY and passive capture running, wait
through TESTING, PARCON and standby/wake to Main Menu, then record the
silent V24 FOO control. After reset-button return to Main Menu, run the
archived F7 build under a separate capture with the same explicit V24
selection. Record the exact `R6I...` prefix and yellow pulse. Restore
LISTEN_ONLY after the trial. Do not use a short TESTING timeout: the
owner measured roughly one to two minutes for v5 and reports that
normal runs can take several minutes.

### V5 comparison on hardware

CONFIRMED (owner, 2026-09-24): v5 ROM00 was installed and programmer
checksum `3834FC` matched the release. On a true cold start, `TESTING...`
ran for approximately one to two minutes, followed by a beep, a
double-beep and the `PARCON 1000` information screen. Main Menu arrival
was subsequently confirmed: the screen went blank in standby, then a
second double-beep and `Backup battery low` warning preceded Main Menu.
The owner explicitly identifies that transition as a return from
standby, not a warmboot. The silent Uno recorded one
`# STOCK_YELLOW` event at 2026-09-24 00:07:51.851828 UTC, low for
5,448 us; the logger classifies it as the v4/v5 initialization-signature
candidate. This demonstrates arrival at the late boot marker and is not
evidence of an RX frame. The serial capture was still running under its
earlier v4-era filename when v5 was installed; the event is after the
owner's v5 coldstart report. The mechanism behind v4's different
physical behavior is still open in issue #27.

The first v5 silent V24 control used Load/Run, FOO, V24 ADAPTOR and
LOCAL_LINK. CONFIRMED (Uno capture): 100 handheld bursts were recorded,
with zero Uno transmissions and no yellow event. CONFIRMED (owner):
the display showed `8000 error`, then `8040 error`; no `R4I...` prefix
was reported. These are the owner's displayed strings, not an inferred
error-code mapping. The archived F7 HEX was then uploaded and flash-
verified with `avrdude`; its startup banner confirmed fixed `7E`,
positive 2/8-cell phase, 33-ms delay and one reply per three
qualifying bursts, beginning with the first.
The first matched F7 attempt has now returned: CONFIRMED (Uno capture)
one reported full 22-cell burst with `reply_sent=1`, followed by one
916-us yellow low. The logger associates the marker with the F7 TX
start by 11,888 us. CONFIRMED (owner display): `R4IEC29in progress`.
The diagnostic writes only the seven-character `R4IEC29` prefix and
intentionally loops; `in progress` is leftover screen text. Raw A=`ECh`,
raw F=`29h`, so F bit 0 (carry) is set. The stock receive call returned
with an error. The byte/flag trace below identifies the terminal
status-bit exit for this exact F value. The Uno was restored to the
flash-verified LISTEN_ONLY HEX. The owner pressed the handheld reset
button and reached Main Menu; that is a reset-button observation, not
evidence of a destructive cold start.
The first reset-button silent V24 repeat again logged 100 handheld
bursts, zero Uno transmissions and no yellow event. CONFIRMED (owner):
`Error 8000` then `Error 8040`. This supports the silent baseline on
the reset-button path but does not substitute for a fresh-coldstart
matched pair.
The subsequent reset-button return to Main Menu emitted another
5,448-us yellow initialization marker; the marker alone cannot classify
that route as cold or warm. The second F7 attempt reproduced the same
display `R4IEC29in progress`, paired with a 920-us yellow low beginning
11,888 us after the Uno's reported F7 TX start. The Uno reported one
`reply_sent=1` burst but labelled its sampled handheld data line
`NO DATA-LINE ACTIVITY OBSERVED`; the stimulus relationship remains
bounded by that observation. After this one-shot stop, the archived
LISTEN_ONLY HEX was restored, flash-verified and banner-verified.

### EC29 branch trace and next discriminating test

CONFIRMED (fresh ROM00 bytes, Ghidra listing, caller and independent
flag review): the shared `ECh` return at `ROM00:341C` has two incoming
branches. The terminal-status branch at `ROM00:33FA` uses the fourth
`RRCA` of one `LINK_STATUS` sample to test `LINK_STATUS` bit 3. Reaching
it also requires `LINK_STATUS` bit 0 clear and bit 1 set; bit 2 is
undetermined. The short-count branch at `ROM00:340D` follows a
carry-cleared `SBC HL,0002h`. Its carry branch requires HL=0 or 1,
giving `FFFEh` or `FFFFh` and leaving F sign set. `LD A,ECh` and `SCF`
preserve that sign flag. **The observed F=`29h` has sign clear, so both
v5 F7 trials took the terminal `LINK_STATUS` bit-3 branch.** A=`ECh`
alone could not establish this. A bounded emulator check gave F=`A9h`
for short count and F=`2Dh` for a sample bit-3 status case; the exact
non-sign bits can vary and are not the basis of the branch decision.
The v5 wrapper preserves the stock AF return before printing it.

OPEN: why the controller set `LINK_STATUS` bit 3. This result does not
establish a decoded return frame or session acceptance. V6 implemented
the proposed terminal `LINK_STATUS`/derived-count snapshot after the
status sample, without adding I/O or delay to the receive loop before
that sample. The selected hook point is
after the fourth `RRCA` at `ROM00:33F7`: the register A then contains
the sampled status rotated right by four, and B plus the saved
descriptor count and IX can account for bytes consumed. A guarded
trampoline must preserve AF, BC, DE, HL, IX, SP and both original exits;
the builder and emulator compare stock and patched I/O through
the terminal sample and raw AF on return. The readout displays the
reconstructed status and count alongside raw A/F; the matched
silent/F7 V24 pair is recorded above. The Uno's
`NO DATA-LINE ACTIVITY OBSERVED` report on the second F7 trial means
zero observed data-line rises during its clock-cell burst; the sketch
can still transmit on that first qualifying burst. Preserve that
uncertainty when attributing the controller error. Use the scope on
accessible optical/Uno signals only if the new status/count result
leaves a waveform question; another internal amplifier probe or broad
alignment sweep is not requested.

CONFIRMED (owner observation): the programmer's VERIFY operation passed
with additive checksum `38358B`, matching the v4 release. On the handheld,
`TESTING...` appeared with a flashing cursor, but the owner did not see
`To Continue Press>>` or Main Menu. Pressing Enter cleared and redrew
`TESTING...`; the owner could not distinguish a reset from a redraw by a
power LED. The silent Uno was reset over USB and its LISTEN_ONLY banner
was recorded. No yellow boot pulse was captured in the passive log. This
does not establish whether the CPU reached the pulse site or whether the
yellow measurement path remained intact. No V24 or F7 trial followed.
The log also has zero-cell Uno `burst 1` reports roughly 202 seconds
apart; they are not evidence of a handheld restart or IR exchange.
The owner reports that after a period of inactivity the handheld turns
off the LCD and backlight and waits in a low-power standby state for a
key. SUSPECTED (owner hypothesis): standby/wake may be exercised during
`TESTING...`; a redraw on Enter could therefore be a wake rather than a
warm restart. A CPU/control-flow trace through the display-off and key
wake paths would discriminate these explanations.

The owner's historical baseline is that physical `TESTING...` normally
takes several minutes. A modified emulator run with its two RAM-test
shortcuts disabled reached the v4 pulse call at 141,238,856 T-states and
the first prompt at 142,140,846 T-states. **Do not use the corresponding
38-second figures as physical boot deadlines:** the emulator still skips
other hardware behavior, and the owner reports a longer normal run.

CONFIRMED (stock ROM bytes and Ghidra comments): `ROM00:01A3` chooses the
warm continuation when the RAM signature is `55h`; `ROM00:0172` chooses
an alternate boot path from `STATUS_SENSE` bit 1. The warm continuation at
`ROM00:024D` is also the fall-through destination of cold initialization.
V4 changes both decisions and three other reset sites to force cold entry.
The physical trial does not identify which, if any, caused the observed
redraw. The ROM's RAM-test bodies are unmodified.

Prepared comparison image:
`analysis/rom_exerciser/releases/stock-context-v5/micron1_stock_context_v5.bin`.
It keeps v4's receive wrapper, `R4IaaFF` readout and yellow markers
byte-for-byte, and restores all five v4 reset-route edits to stock.
This is a single-variable test of the forced-cold change, not a proven
repair. Size 32,768 bytes; MD5 `4383c0246149d5c4a1613266c5f94151`;
sum16 `34FC`; sum24 `3834FC`; SHA-256
`99e5fdb28066b62ef43b25353c8f65aed1d5368438f6a831a81712b4e7e61da8`.
Its adjacent JSON records the patch sites. V5 physical validation is
recorded above.
The v5 builder reproduced the release byte-for-byte; 73 targeted tests
pass in `analysis/venv`, and the canonical accelerated boot reached Main
Menu with all three expected inputs. Those checks do not simulate the
physical reset/power circuit.
Historical v5 installation instruction: use this image on ROM00 only
and leave ROM01 stock.
Because v5 restores stock warmstart selection, start with a true physical
coldstart after the ROM swap so the RAM kernel is refreshed. The owner
already used battery removal and discharge of the retention capacitor
for this in the v4 trial. With the Uno silent, allow the physical cold test its normal several
minutes and record the first screen after `TESTING...`, plus any yellow
boot pulse. If the prompt/menu returns, repeat a fresh silent V24 trial
before considering F7. If it repeats the v4 behavior, keep the reset
cause open and compare against the previously booting v3 image.

## What is known

See the [review](../research/reviews/ir-rounds-review-2026-09-23.md) and
[round-two record](stock-context-v3-round2.md). F7 originally produced 34
carry-set return markers; exact replay later failed to reproduce them.
No successful return frame or session is established. `7E` is still a
return-direction candidate. Optical arrival at the handheld's amplifier
is owner-confirmed; the internal probe is removed. Do not request another
probe or alignment sweep. Earlier unverified PLINTH/V24 selections prevent
using all negative trials to eliminate conventions.

## Release and implementation

Install **only ROM00** from
`analysis/rom_exerciser/releases/stock-context-v4/micron1_stock_context_v4.bin`.
ROM01 is unchanged. Its adjacent JSON contains every patch and checksum.

| Check | Value |
|---|---|
| Size | 32768 bytes |
| MD5 | `40750ca8c387483001a0348d4cd3ae36` |
| sum16 | `358B` |
| SHA-256 | `2d78a065c49f9a113b45caa074d8d1f12e9b5b1dfce30698974579ec7b375174` |

CONFIRMED by builder bytes and emulator tests: the ROM uses the guarded
zero cave at ROM00:7E96–7FF9 and the existing stock dispatcher call at
ROM00:2FC1. It records the incoming descriptor pointer in scratch RAM,
calls stock `Link_BlockRx` once, emits the previous carry-class yellow
pulse **after return**, then displays **`R4IaaFF`** and stops. `aa` is the
raw hexadecimal A register; `FF` is the raw hexadecimal F register.
The `I` is literal and denotes this dispatch/receive-result diagnostic.
For example, `R4IEExx` has A=`EE`; the final two digits must still be
recorded. F bit 0 is carry. The seven-character prefix is sufficient;
there is no need to transcribe the rest of the screen.

* `EE` with carry set: stock receive timeout.
* `ED` with carry set: descriptor exhaustion.
* `EC` with carry set: terminal `LINK_STATUS` bit 3 or short count.
  A alone cannot distinguish them. F sign clear excludes short count;
  F sign set does not by itself exclude the status-bit path.
* Carry clear: stock byte reader returned without its error indication.
  This one-shot diagnostic stops before session/header validation.

The descriptor snapshot at RAM:C7E0–C7E1 and raw F/A at C7E2–C7E3 are
implementation scratch, not an extra owner readout. No LCD or yellow
write precedes the stock receive call. The added wrapper CALL and RAM
snapshot add 33 T-states (about 9 us) before stock receive entry versus
the original direct CALL. A missing display cannot distinguish no
entry from a stuck receive call; if that ambiguity becomes material,
use a separately witnessed entry-only diagnostic rather than treating
absence as protocol rejection. The bounded modeled receive paths all
return in tests, but hardware status behavior is not fully modeled.

The boot/logger witness is now **about 5.451 ms low on yellow**
(20,095 T-states at 3.6864 MHz), distinct from v3's 3.636 ms.
It occurs at common initialization, before menu startup; it is the
installed-image identity witness, not proof of receiving IR. The logger
recognizes this as `v4_boot_signature_candidate` and never associates it
with a preceding transmission. RX pulses retain the earlier approximately
0.9/1.8-ms carry-set/clear widths.

## Coldstart changes and limits

CONFIRMED by guarded bytes and differential execution: ROM00:0172,
01A3, 3812 and retained-state entry 17A5 redirect to cold body 01A6.
The BDOS function-00 table word at ROM00:3708 now points to 01A6;
the copied table at RAM:F1EB and real copied BDOS dispatch are tested.
The common continuation at ROM00:024D is left intact, avoiding a cold
boot loop. Cold boot refreshes the RAM kernel from this new image.

The NMI handler is left intact: modeled states 0 and 2 reach the stock
power-down path; state 1 returns without restarting. The power-down loop
waits for hardware reset; that reset's retained-state branch now enters
cold initialization. No test claims to simulate the analog power/reset
circuit. Confirm the first physical boot shows TESTING and reaches the
menu. Do not interpret an ignored NMI as a warmstart or promise recovery
from arbitrary corrupted retained RAM. **Coldstart resets source selection:
explicitly choose V24 ADAPTOR on every run.**

## Arduino artifacts and last known state

Last verified live state: silent LISTEN_ONLY on `/dev/ttyACM0`.
This preparation pass did not open USB, reset the Uno, upload or transmit.
Yellow is on Uno D8 and scope D4; black remains on undriven D7.
D5/D6 drive the existing IR circuit. The electrical setup is settled.

Archived without recompilation:

* `analysis/arduino/releases/f7-sparse33/m1000_ir_probe.ino.hex`
  SHA-256 `c25dda43b1d3cf3a78bf0d1dc2e2b43dbdda34138aa996a22d7f8fda67210d8f`.
* `analysis/arduino/releases/stock-silent/m1000_ir_probe.ino.hex`
  is the cached LISTEN_ONLY control; verify its banner before use.

Each directory contains a manifest, original build options and compiler
commands. Original absolute paths are provenance, not a portable build
recipe. Both use Uno / AVR core 1.8.8 / avr-gcc 7.3.0-atmel3.6.1-arduino7.
Use the HEX without bootloader with the Arduino CLI uploader at
`.cache/ir-arduino/m1000-arduino-cli/arduino-cli` in this checkout.
F7 is opening `7E`, stuffing 1, phase +2/8 cell, type-2 payload
`00 07 00 02 01 43 00 00 02 01`, delayed 33 ms on qualifying bursts
1, 4, 7, ... (one in every three), with short fragments ignored.
The amplifier-check free-running build was a different
phase and repetition mode; it is not the F7 control.

## Next agent: test sequence

**Stop and ask the owner plainly before any handheld action.** Start and
verify capture first, then send a standalone request and wait. Do not bury
requests in JSON or let a timed capture expire before the owner starts.

1. Verify release checksums and arrange the new ROM installation. With
   the silent Uno and USB logging already active, ask for a coldstart.
   Record Uno startup banner, a roughly 5.45-ms yellow boot witness,
   TESTING, and arrival at the menu. If the witness is absent, resolve
   image/logger identity before interpreting absent RX events.
2. Still silent, ask for **Load/Run, FOO, V24 ADAPTOR, LOCAL_LINK**.
   Record any `R4I...` prefix or the normal error sequence. A diagnostic
   in this control indicates receive activity without an Arduino reply;
   record it before considering stimulus attribution.
3. Upload the archived F7 HEX and verify its banner. Start a new named
   capture, then ask for the same explicitly selected V24 operation.
   Record the prefix, pulses, full handheld bursts and emitted replies.
   This ROM stops on the first receive return, so 100/34 burst/reply
   totals are no longer an expected completion condition.
4. Repeat the matched silent/F7 pair on fresh coldstarts, confirming V24
   each time. Keep the Uno silent during each boot; enable F7 only for
   the intended stimulated attempt. Stop on inconsistent boot identity,
   event drops, or a result in the silent control that changes attribution.
   Each diagnostic stop needs a fresh coldstart.
5. Preserve each result and exact build identity before selecting a new
   single-variable comparison. No broad payload sweep until repeatable
   controller/stock RX evidence has been obtained. Restore LISTEN_ONLY
   and verify its banner at handover.

Start the existing passive logger with a unique output path, for example:

```sh
python3 analysis/stock_context_log.py --log analysis/captures/stock-v4-silent-boot-01.jsonl --duration 300
```

Capture the banner by resetting the Uno after logging begins. If using
scope CSV, record acquisition sample rate and exported time spacing.
The earlier 40-us export interval can resolve the millisecond markers,
but cannot settle clock/data setup at roughly 122-us cells. Use a separate
short-window, higher-rate acquisition for any edge-timing inference.
Segmented memory remains useful for multiple exchanges; it does not by
itself guarantee an adequate sample rate. The scope is `msox3054a:5025`.

## Reproduction and validation

```sh
analysis/venv/bin/python analysis/rom_exerciser/stock_context_v4.py \
  -o /tmp/micron1_stock_context_v4.bin
analysis/venv/bin/python -m pytest -q analysis/test_stock_context_v3.py \
  analysis/test_stock_instrument.py analysis/test_stock_context_v4.py \
  analysis/test_stock_context_log.py
MICRONIC_ROM0=/tmp/micron1_stock_context_v4.bin timeout 300 \
  analysis/venv/bin/python analysis/boot_hw.py --lcd --max-slices 100000 \
  --expect 'To Continue Press>>:\r' --expect 'serial number:12345678\r' \
  --expect 'Main Menu:'
```

Use **analysis/venv**, whose emulator executes callback-backed memory.
The earlier helper regression has been corrected; PyPI z80 is not an
equivalent substitute. Acceptance: 69 tests pass, release bytes reproduce,
raw A/F match unpatched stock for modeled EE/EC/ED and carry-clear cases,
receive port I/O is identical until return, boot pulse preserves registers,
and stock/patched reset inputs 00/01/03 discriminate correctly.

The canonical harness reached Main Menu with all three expect steps
completed. Its normal RAM-test shortcuts remain enabled: this validates
startup integration through the menu, not a physical destructive RAM test
or a full electrical power-cycle model. The log is archived beside the
ROM as `boot-menu.log.gz`. Physical boot and IR acceptance remain pending.
