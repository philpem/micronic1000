# Stock-context v3: first handheld run

Status: **F2S produced receive-return markers; C1 silent control complete**. This is the
worksheet for the first stock-context v3 run; the full electrical setup,
interpretation limits, and later framing matrix remain in
[the harness guide](ir-feedback-protocol.md#current-handoff-stock-context-v3-bench-trial).
Record observations here, then commit the serial logs under `analysis/captures/`.
Scope CSV exports are committed there as lossless `.csv.gz` files; use
`gzip -dc FILE.csv.gz > FILE.csv` to recover an ordinary CSV.

## Fixed hardware and ROM

* ROM00 image: `/home/philpem/Micronic-1000/analysis/rom_exerciser/releases/stock-context-v3/micron1_stock_context_v3_r2.bin`
* Size 32,768 bytes; MD5 `bf518ce09083d420332fd02748f6bbef`;
  unsigned additive byte sums 16-bit `076F`, 24-bit `38076F`.
* ROM01 remains stock. Expected handheld screen after a cold restart is
  the normal Micronic Load/Run UI. A warm restart alone does not establish
  cold RAM initialization.
* Uno D5/D6 drive resistor-limited IR LEDs at the **top V24 window**;
  their receiver-side clock/data assignment is open. Handheld outgoing
  channels remain on Uno D2/D4. Handheld blue/pin 8 is Uno GND;
  yellow/pin 6 is Uno D8 with a 10-kOhm pull-up to Uno 5 V. The owner
  left black/pin 5 connected to Uno D7; D7 remains an undriven input.
  Orange/pin 3 is not connected to Uno 5 V.

## Run order and record

Use the Elegoo Uno R3 build instructions in
`analysis/arduino/m1000_ir_probe/README.md` under “Stock-ROM context capture”.
Every build must include `FEEDBACK_HARNESS=0`; use the README's complete
compile commands, adding the candidate flags shown below. For each upload,
record the exact build flags, Uno startup banner, serial
log filename, handheld screen/operation, scope connections, and result.
Run the passive logger before the handheld operation:

```sh
python3 analysis/stock_context_log.py --log analysis/captures/stock-v3-r1-control.jsonl --duration 120
```

Use a unique filename for each later run; the logger refuses to overwrite.
Reset the Uno after logging begins so its banner is captured. Log any
`# STOCK_YELLOW_DROPS` count. Do not send feedback `T`/`R` commands to the
stock-context sketch.

| Run | Uno build / stimulus | Required observation | Result |
|---|---|---|---|
| C0 | `FEEDBACK_HARNESS=0`, `LISTEN_ONLY=1`, `STOCK_CONTEXT_EVENTS=1`; cold-restart handheld, then choose V24 Load/Run | `STOCK_CONTEXT_V3 width_us=32 drops=16`, normal handheld UI, initialization yellow low near 3.637 ms | PARTIAL: 3,636-us init pulse and V24 attempt captured; Uno startup banner was missed. Repeat a bannered control. |
| F0 | `FEEDBACK_HARNESS=0`, `LISTEN_ONLY=0`, `FREE_TX=1`, `STOCK_FIXED_CANDIDATE=1`, `STOCK_CONTEXT_EVENTS=1`; defaults: D5 clock, D6 data, `7E`, phase -2/8, polarity 0, content 2 | Full `# TX` settings and any yellow RX-width marker; repeat V24 choice across the 250-ms TX cadence | DONE: two user-reported V24 attempts, 250 outgoing burst reports, no yellow RX marker. See log detail below. |
| F1 | F0 plus `STOCK_TX_SWAP=1` | Same observations with LED roles exchanged | DONE: handheld attempt, 111 outgoing burst reports, no yellow RX marker. See log detail below. |
| F2 | F0 plus `STOCK_PHASE_IDX=3` | Test data timing around the second logical clock edge, with F0 LED roles and framing | DONE: 89 outgoing burst reports, no yellow RX marker; scope caught one handheld burst without Uno activity in its 50-ms window. |
| F2S | Repeat F2 with scope segmented memory triggered on handheld clock | Record many handheld bursts and test whether any free-running Uno burst overlaps a receive window | DONE: 100 handheld bursts, four 916–920-us yellow lows, 24 scope windows with Uno output; still `8000` then `8040`, "Line Failure". |
| C1 | Re-upload C0 between any candidate responses | Check whether the same yellow RX marker appears without transmitted light | DONE: 100 handheld bursts; no Uno output, yellow pulse or event drop. Same `8000`/`8040` errors. |
| F3 | F2S plus `STOCK_CLOCK_INVERT=1`; D5/D6 roles and all frame settings unchanged | Test the opposite physical clock edge at the same +2/8-cell data phase | DONE: 100 scope retry segments, 21 with Uno output, no yellow low; owner reported the same two errors. |
| F4 | F2S candidate in `RX_NARROW=1`, fixed reply 4 ms after each handheld burst | Test a repeatable early reply without the free-running timing sweep | DONE: 100 regular 4-ms replies gave no yellow marker; one anomalous 32.58-ms reply was followed by a 916-us carry-set marker. Same `8000`/`8040` errors. |
| F5 | F4 with a fixed 30-ms reply delay and a 100-ms scope window | Test whether a regular late reply causes the marker | DONE: 100 replies achieved 30 ms; no yellow marker or drop; `8000` then `8040`. |
| F6 | F4 with a cyclic 30–36-ms delay in 1-ms steps | Test a narrow late receive window in one handheld run | DONE: all seven delays observed 14–15 times; no yellow marker or drop; `8000` then `8040`. |

**Stop at C0** if its boot banner, expected UI, or initialization marker is
missing: later absent RX markers cannot then distinguish optical failure
from a failed ROM/feedback path. A 0.918-ms low is a stock receive call
returning carry set; a 1.828-ms low is a carry-clear return. Neither proves
frame or Commstar session acceptance. Report the raw yellow lines as well as
the logger's pulse classification.

If F0/F1 produce no reproducible RX marker, use the existing fixed-build
controls to test physical LED levels and the opposite candidate clock edge:
`STOCK_CLOCK_INVERT=1` with `STOCK_PHASE_IDX=3` gives nominal data setup and
hold around the second logical clock edge; `STOCK_PHASE_IDX=1` gives them
around the first. Vary `STOCK_DATA_INVERT` separately. The inverted clock
has extra dark-idle boundary transitions, so a negative result under that
setting is not conclusive. Scope Uno D5, D6, and D8 together for a
representative stimulated run; include D2/D4 if reply timing is in doubt.

Once a matched optical response is repeatable, test flag `7E` versus `81`
with an **explicit, fixed** `STOCK_STUFFING_MODE`, then compare stuffing
modes 0/1/2 using fixed `STOCK_CONTENT_IDX=3` (diagnostic
`00 00 FF FF 96`). Compare `STOCK_CLOSE_FLAG=0/1` separately. Keep
`STOCK_POL_IDX` and both physical LED inversions fixed within each pair.
The diagnostic payload is not asserted to be a valid Commstar message; a
negative result does not identify the rejected field. Interleave a silent
control and retain each build's `wire_flag` and `wire_stuff` report.

## Observation record

* Burn / copy validation: owner reports revision-2 ROM installed; local image
  MD5 and unsigned byte sums match this worksheet. EPROM readback not reported.
* Handheld cold restart and screen: owner saw `TESTING`, then selected
  `FOO` from `V24 ADAPTOR` / `LOCAL_LINK`; connect attempt ended with
  comms error `8000 (238/001)`. Message text was not supplied.
* C0 log: `analysis/captures/stock-v3-r1-control-20260923T1716Z.jsonl`.
  CONFIRMED: raw `# STOCK_YELLOW rise_us=336799412 low_us=3636`;
  51 outgoing burst reports; no other yellow event or drop report.
  The logger classifies this as an initialization-signature candidate, not
  receive evidence. No complete Uno startup banner was captured, so repeat
  C0 with an Uno reset after logging starts before interpreting silence.
* F0 idle log: `analysis/captures/stock-v3-r1-f0-20260923T1719Z.jsonl`.
  Full `STOCK_CONTEXT_V3` and fixed-candidate banners were captured;
  free-running `# TX` reports continued. No handheld outgoing burst or
  yellow event occurred in this window, so it is not an F0 trial.
  F0 remains uploaded for a new timed capture and repeated V24 choice.
* F0 handheld log: `analysis/captures/stock-v3-r1-f0-handheld-20260923.jsonl`.
  The 94.5-s capture has 378 complete fixed-candidate `# TX` lines,
  one truncated line on serial open, and 250 handheld outgoing burst
  reports in three clusters (51, 97, 102). Full TX lines report
  `wire_flag=7E`, `wire_stuff=1`, `swap=0`, no physical inversion,
  content index 2, and maximum software/applied lateness 19/31 us.
  No yellow pulse or event-drop report was recorded. The prior F0 idle
  capture contains the full startup banner; this log opened midstream.
  Owner reported `8040 (238/001)` after the first repeated operation,
  then `8000 (238/001)` followed by `8040 (238/001)` on the next one.
  Exact screen message text and scope traces were not supplied. These
  results do not establish whether the candidate light reached the
  handheld detector or which gate rejected it.
* F1 handheld log: `analysis/captures/stock-v3-r1-f1-handheld-20260923.jsonl`.
  The 57.2-s capture has the full `STOCK_CONTEXT_V3` startup banner,
  223 complete `swap=1` fixed-candidate TX lines and 111 handheld outgoing
  burst reports in two clusters (54, 57). No yellow pulse or event-drop
  report was recorded. Maximum software/applied emission lateness was
  19/29 us. Owner reported the same error sequence:
  `8000 (238/001)` then `8040 (238/001)`; the latter screen displayed
  "Line Failure". No scope trace was supplied.
* F0/F1 comparison: changing only the D5/D6 software LED roles produced
  no stock-RX return marker in either capture. Physical optical delivery
  and controller acceptance remain unobserved. The next controlled
  candidate is `STOCK_PHASE_IDX=3` with `swap=0`, leaving electrical
  levels and all framing settings unchanged. This puts nominal data
  setup/hold around the second logical clock edge rather than the first.
* F2 timing qualification: the owner's scope is reachable at
  `msox3054a`; scope pod D0/D1 are labelled handheld data/clock,
  D2/D3 are labelled Uno D5/D6, and newly connected pod D4 is yellow.
  The first +2/8-cell Uno build had about 400-us steady-state software
  lateness and a 116-us median physical clock interval. Preserve its
  `analysis/captures/stock-v3-phase3-before-fix-{uno.jsonl,keysight.csv.gz}`
  evidence; it was **not** used for a handheld trial. The generic emitter
  queue was too slow for this long positive-phase frame. The repaired
  build schedules each data fall early in the next cell, preserving the
  event order, and was uploaded with verify.
* Final F2 idle proof: `analysis/captures/stock-v3-phase3-ready-uno.jsonl`,
  `analysis/captures/stock-v3-phase3-ready-keysight.csv.gz`, and the matching
  `.png` screen image. CONFIRMED at scope D2/D3 on a 2-us CSV grid
  (acquisition rate was not recorded for this capture): 88/88
  clock pulses, 16/16 data pulses, clock intervals 116–128 us with
  122-us median. All 16 data pulses straddle the second clock edge with
  32–36-us setup and 40–46-us hold. Scope D4 stayed high during this idle
  capture. The Uno reported at most 18-us pre-write and 26-us post-write
  software lateness in 30 complete TX reports. This verifies GPIO-level
  timing, not optical delivery or handheld acceptance.
* F2 handheld log: `analysis/captures/stock-v3-r1-f2-phase3-handheld-20260923.jsonl`.
  The 72.9-s capture contains 292 complete fixed `swap=0`, `phase=+2/8`
  Uno TX reports and 89 handheld outgoing burst reports in two clusters
  (44, 45). There is no yellow pulse or event-drop report; maximum
  pre-write/post-write software lateness is 14/26 us. Owner reported
  `8000 (238/001)` followed by `8040 (238/001)` again.
* F2 single-trigger scope record:
  `analysis/captures/stock-v3-r1-f2-phase3-handheld-keysight.csv.gz`.
  Triggered on handheld clock pod D1, its 50-ms window contains one
  17-pulse handheld clock burst and five handheld data pulses. Scope
  D2/D3 show no Uno output **in that particular window**, and yellow
  D4 stays high. This one window cannot establish whether other Uno
  bursts overlapped other handheld receive intervals.
* Segmented-memory export was tested without handheld input: with a
  three-segment acquisition triggered on Uno D2, HTTP all-segment CSV
  `analysis/captures/stock-v3-segmented-export-check.csv.gz` contains three
  2,000-point segments; SCPI time tags were 0, 250.022 and 500.037 ms.
  F2S then triggered on handheld clock D1 for the live run.
* F2S live run: `analysis/captures/stock-v3-r1-f2s-segmented-handheld-20260923.jsonl`
  and `analysis/captures/stock-v3-r1-f2s-segmented-keysight.csv.gz`.
  CONFIRMED: 100 handheld burst reports and 100 scope segments (2,000
  export rows each, spaced 25 us). A 1.301-s gap separates two sets of 50
  scope segments. Uno D2/D3 activity occurs in 24 windows: 18 complete
  transmissions after the handheld burst and six tails before its next
  burst. Four `# STOCK_YELLOW` low intervals are 916, 916, 920 and
  916 us; each begins about 11.28–11.29 ms after its preceding Uno TX
  start. Scope D4 independently catches one falling edge 44.475 ms after
  segment 11's handheld trigger, about 0.55 ms after the last Uno D3
  transition in that window. The other three yellow lows fell outside
  the captured windows. The marker width matches the instrumented
  `Link_BlockRx` carry-set return path; this establishes a receive call
  return, not frame acceptance. The owner reported `8000 (238/001)` then
  `8040 (238/001)`, "Line Failure". C1 is the required silent control
  before attributing the new markers to Uno light.
* C1 control: LISTEN_ONLY was rebuilt, uploaded with verify, and its first
  logger captured the expected mode and stock-context startup banner.
  Two earlier recording windows did not contain a handheld operation;
  the scope's sporadic triggers in those windows were not a trial.
  In the completed run,
  `analysis/captures/stock-v3-r1-c1-silent-handheld-c-20260923.jsonl`
  records exactly 100 handheld bursts, with a 2.122-s gap between two
  groups of 50; no yellow event or drop was reported. The matching
  `analysis/captures/stock-v3-r1-c1-silent-handheld-c-keysight.csv.gz` has
  100 segments with 21 or 22 handheld clock rises each, zero Uno D2/D3
  rises, and zero D4 yellow low samples. Scope segments have 2,000 CSV
  rows at 25-us spacing, with a 2.120-s gap between groups of 50.
  The owner reported `8000 (238/001)`, "Plinth not connected", then
  `8040 (238/001)`, "Line failure". Thus the short receive-return
  markers seen only in F2S correlate with its emitted candidate, while
  frame acceptance remains unproven.
* F3 idle qualification: built with `STOCK_CLOCK_INVERT=1`,
  `STOCK_PHASE_IDX=3`, `STOCK_TX_SWAP=0`, fixed flag `7E`, content index 2,
  automatic stuffing, no closing flag, and no data inversion. Upload
  verification passed. `analysis/captures/stock-v3-f3-clockinv-idle-uno.jsonl`
  records the full startup banner and complete TX settings; observed
  post-write lateness is at most 22 us. Scope file
  `analysis/captures/stock-v3-f3-clockinv-idle-keysight.csv.gz` contains two
  25,000-row idle segments at 2-us export spacing. Each has 16 D3 data pulses
  that straddle a D2 rising edge with 30–38 us setup and 42–48 us hold;
  there are 89 D2 rising and 89 falling edges, including the inversion
  boundary transitions. D4 yellow remained high. This qualifies the
  GPIO output for the opposite physical clock edge; optical reception
  remained to be measured during a handheld attempt.
* F3 live trial: `analysis/captures/stock-v3-r1-f3-clockinv-handheld-20260923.jsonl`
  contains 1,049 complete fixed TX reports, 101 handheld burst reports
  (one is a two-cell fragment), no yellow event and no drop report.
  Maximum pre-write/post-write lateness is 16/28 us. The matching
  `analysis/captures/stock-v3-r1-f3-clockinv-handheld-keysight.csv.gz`
  has 100 handheld-triggered segments; 95 contain 21 or 22 D1 rises,
  five contain 19 or 20. Uno D2/D3 activity appears in 21 segments,
  including 14 complete transmissions after the handheld burst;
  there is no D4 yellow low sample. The two sets of 50 segments are
  separated by 1.322 s. The owner reported the same errors as C1:
  `8000 (238/001)`, "Plinth not connected", followed by `8040
  (238/001)`, "Line failure". F2S had four carry-set markers with
  18 complete post-burst transmissions, versus none with 14 here;
  this comparison suggests clock polarity matters, but the sparse
  free-running overlaps cannot yet establish a receive convention.
* F4 handheld-paced trial: uploaded a verified `RX_NARROW=1` fixed build
  with F2S settings and `STOCK_REPLY_DELAY_US=4000`. The startup banner
  is in `analysis/captures/stock-v3-f4-paced-idle-uno.jsonl`. The live
  `analysis/captures/stock-v3-r1-f4-paced-handheld-20260923.jsonl`
  has 101 `burst` reports: 100 report the requested/achieved delay
  `4000/4000us`, while one 17-cell report after an eight-cell fragment
  reports `4000/32580us` and 510/522-us emission lateness. Only that
  delayed report is followed by a 916-us yellow low, beginning 11.888 ms
  after its TX start. There is no event-drop report. The owner reported
  `8000` then `8040` again, with no change in outcome.
  The matching `analysis/captures/stock-v3-r1-f4-paced-handheld-keysight.csv.gz`
  contains 100 handheld-triggered segments. In 99 ordinary segments,
  Uno D2's first rise is about 6.6 ms after the handheld trigger,
  about 4 ms after the last D1 rise. Segment 51 contains two Uno
  transmissions; the second starts at D2 about 36.4 ms after the
  trigger. Its expected yellow return lies beyond the scope's 45-ms
  post-trigger window, so the absence of D4 samples in this file does
  not contradict the Uno's pulse report. At this point a late reply
  was a timing hypothesis; F5/F6 below show that delay alone is
  insufficient. A valid frame remains unproven.
* F5 fixed 30-ms trial: a verified otherwise identical `RX_NARROW`
  build is identified by the banner in
  `analysis/captures/stock-v3-f5-paced30ms-idle-uno.jsonl`. The live
  `analysis/captures/stock-v3-r1-f5-paced30ms-handheld-20260923.jsonl`
  records 100 handheld bursts and 100 replies at exactly
  `30000/30000us`, with no yellow event or drop and at most 11/22-us
  pre/post-write lateness. The owner reported `8000` then `8040`.
  The scope's 100-ms window captured 51 segments (one per roughly two
  handheld retries), all with Uno D2 output beginning about 32.6 ms
  after the handheld trigger and ending about 43.8 ms afterward.
  D4 has no yellow low sample. Raw scope CSV:
  `analysis/captures/stock-v3-r1-f5-paced30ms-handheld-keysight.csv.gz`.
* F6 delay sweep: added a guarded fixed-candidate `RX_NARROW` option
  that cycles the requested reply delay. The verified build's banner
  in `analysis/captures/stock-v3-f6-delay-sweep-idle-uno.jsonl` gives
  30 ms start, 1 ms step and seven values. The live
  `analysis/captures/stock-v3-r1-f6-delay-sweep-handheld-20260923.jsonl`
  has 100 bursts; requested and achieved delays match exactly for all
  seven values, each appearing 14 or 15 times. No yellow event or drop
  was recorded; maximum pre/post-write lateness is 14/22 us. The owner
  again reported `8000` then `8040`. The matching
  `analysis/captures/stock-v3-r1-f6-delay-sweep-handheld-keysight.csv.gz`
  contains 52 segments, all with Uno output. D2 starts about 32.6–38.6 ms
  after the handheld trigger across the delay sweep, and D4 has no
  low sample. These regular late replies reject delay alone as the
  explanation for the F2S/F4 markers. The effects of free-running
  emission and the abnormal F4 transition remain separate candidates.

## Scope sampling audit

The owner observed **78.1 kSa/s** during the long segmented run. SCPI
`:ACQ:SRAT?` confirmed 78,100 samples/s for the F6 setup (128
segments, 10 ms/div). This is one acquisition sample per 12.8 us.
Its 2,000-row CSV export spans 100 ms, so exported rows are 50 us
apart. Individual 122-us bit cells have only about 9.5 acquired
samples and about 2.4 CSV rows; do **not** use these long-window CSVs
for bit decoding or microsecond setup/hold measurements. A 916-us
yellow low is long enough to span about 18 exported rows, and the
30–36-ms delay sweep is resolved at this setting. The F5/F6 inference
uses only millisecond timing and the presence or absence of yellow.

The same setup with 128 segments at 5 ms/div was re-acquired at
156 kSa/s, with 25-us CSV row spacing. That rate was **not logged
during** F2S/C1/F3/F4, so their historical CSV rows are not evidence
of a faster acquisition. Their pulse/burst counts and millisecond
comparisons stand; fine edge decoding remains out of scope.

For the actual edge setup/hold check, new acquisitions used fewer
segments. The repeated F2 waveform at 5 ms/div in real-time mode
reported 20 MSa/s; its 25,000-row CSV has 2-us spacing and again
shows 88 D2 clock pulses, 16 D3 data pulses, 32–36-us data setup and
42–46-us hold around D2's falling edge. The repeated F3 waveform at
5 ms/div with two segments reported 10 MSa/s; each 25,000-row CSV
segment has 2-us spacing and 16 data pulses straddling a D2 rising
edge with 30–38-us setup and 40–48-us hold. The 2-us export grid
limits the quoted edge times even though the underlying acquisition
rate is higher. Raw captures:
`analysis/captures/stock-v3-phase3-rate-qualified-keysight.csv.gz` and
`analysis/captures/stock-v3-f3-clockinv-rate-qualified-keysight.csv.gz`.
SCPI settings and sample-rate readings are preserved in
`analysis/captures/stock-v3-scope-rate-audit-20260923.json`.
* Next discriminating trial and reason: PENDING
