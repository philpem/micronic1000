# Stock-context v3: first handheld run

Status: **awaiting handheld ROM burn and bench observations**. This is the
worksheet for the first stock-context v3 run; the full electrical setup,
interpretation limits, and later framing matrix remain in
[the harness guide](ir-feedback-protocol.md#current-handoff-stock-context-v3-bench-trial).
Record observations here, then commit the serial logs under `analysis/captures/`.

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
  yellow/pin 6 is Uno D8 with a 10-kOhm pull-up to Uno 5 V. Black/pin 5
  is disconnected from D7; orange/pin 3 is not connected to Uno 5 V.

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
| C0 | `FEEDBACK_HARNESS=0`, `LISTEN_ONLY=1`, `STOCK_CONTEXT_EVENTS=1`; cold-restart handheld, then choose V24 Load/Run | `STOCK_CONTEXT_V3 width_us=32 drops=16`, normal handheld UI, initialization yellow low near 3.637 ms | PENDING |
| F0 | `FEEDBACK_HARNESS=0`, `LISTEN_ONLY=0`, `FREE_TX=1`, `STOCK_FIXED_CANDIDATE=1`, `STOCK_CONTEXT_EVENTS=1`; defaults: D5 clock, D6 data, `7E`, phase -2/8, polarity 0, content 2 | Full `# TX` settings and any yellow RX-width marker; repeat V24 choice across the 250-ms TX cadence | PENDING |
| F1 | F0 plus `STOCK_TX_SWAP=1` | Same observations with LED roles exchanged | PENDING |
| C1 | Re-upload C0 between any candidate responses | Check whether the same yellow RX marker appears without transmitted light | PENDING |

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

* Burn / copy validation: PENDING
* Handheld cold restart and screen: PENDING
* C0 log / yellow initialization marker / event drops: PENDING
* F0 log / screen / RX marker / scope file: PENDING
* F1 log / screen / RX marker / scope file: PENDING
* C1 log / RX marker: PENDING
* Next discriminating trial and reason: PENDING
