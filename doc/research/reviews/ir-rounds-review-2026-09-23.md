# IR bench results and next-test review — 2026-09-23

Reviewed branch `ir/stock-context-v3-content` at `4a42dc6`, covering
the wired feedback-v1/v2 experiments, stock-context v3 rounds one and
two, and the prepared receive-dispatch ROM. This is a review of the
evidence and a proposed revision to the plan, not a new hardware run.
No firmware or Arduino configuration was changed during this review.

**Recommendation: retain the stock-context approach, but revise the
diagnostic release and its acceptance checks before another ROM burn.**
Optical arrival is owner-observed at the internal sensor amplifier.
The unresolved problem is how that stimulus reaches controller and
firmware receive processing. Another broad payload sweep has little
discriminating value until a response can be repeated.

## Positive results and their limits

* The black/yellow command and feedback connection made repeated
  standalone tests possible through USB. The v2 records include
  checksums, sequence numbers, mode and sample counts. That is useful
  experimental infrastructure even where the IR result was negative.
  Stock-context v3 uses yellow as a passive event output and leaves
  Arduino D7/black undriven; the earlier feedback `T`/`R` command
  interface is not active in that stock configuration.
* The v1 forced stock-RX experiments returned `EEh`/carry with both
  silent and stimulated conditions. The v1 pending-receive experiments
  did not enter stock RX. V2 H/J/K then sampled controller status in
  several standalone contexts: the documented valid matrices showed
  neither `LINK_STATUS` bit 4 nor bit 0. These negatives characterize
  those contexts and stimuli; they do not eliminate conventions in a
  live stock V24 transaction. V2 IDs 15–32 accidentally ignored the
  requested physical inversions; use the corrected IDs 33–50 for that
  comparison. See the [feedback record](../../re-notes/ir-feedback-protocol.md#first-feedback-v2-bench-result-2026-09-23).
* CONFIRMED by recounting saved serial logs and scope CSV: original F7
  had 100 handheld bursts, 34 Arduino replies and 34 yellow lows.
  Its scope export contains exactly 34 segments with 93 D2 clock
  rises and 34 with yellow low. The roughly 916–924-us pulse matches
  the installed wrapper's carry-set return marker. This is strong
  evidence of stock receive-call activity associated with the reply
  condition. It is not evidence of a successful frame.
* CONFIRMED by recounting: C0b replayed the archived F7 binary with
  34 replies and zero yellow events; C0c had eight events; C0f had
  34 replies and zero events. C0f's scope independently contains
  34 segments with 93 D2 rises and no yellow low. This establishes
  failure to reproduce the control, not elimination of its framing.
* The coldstart record contains a 3,636-us Arduino yellow pulse and
  a matching scope observation. The measurement path worked for that
  event. It does not retrospectively certify every absent pulse.
* The owner probed the handheld sensor-amplifier output and confirmed
  IR arrival, then removed the probe. The owner also explained the
  missing MSO digital highs during the resistor-bypass configuration.
  Treat those as owner-supplied hardware evidence. Further alignment
  sweeps or requests for internal probing are not the next experiment.

Current knowledge is asymmetric: the handheld's transmitted waveform
has strong capture evidence (about 8192 cells/s and separated clock/data
pulses), and the ROM's byte-transport operations are mapped. The return
direction still has no demonstrated complete frame or session. `7Eh`,
the receiving clock/data assignment, phase, stuffing and closure remain
candidate conventions. The two excluded controller bytes in stock RX
do not by themselves identify a CRC or an on-wire trailer.

## Findings requiring changes or narrower claims

### 1. High: forced coldstart is incomplete, with a misleading reset test

CONFIRMED by fresh Ghidra bytes/listing and emulator comparisons:
`ROM00:016C` already branches to `ROM00:01A6` when `BOOTKEYS` bit 0
is clear. The new reset-vector test returns zero for all input ports,
so stock firmware passes that cold-entry test without the patch.
With `BOOTKEYS` bit 0 and bit 1 both set, `ROM00:0172` jumps to
`ROM00:17A5` before reaching the patched gate at `ROM00:01A3`.

Both emulator installations reproduce this table with `ram:F81C=55h`:

| BOOTKEYS input | Stock first reached address | Prepared image first reached address |
|---|---|---|
| `00h` | `ROM00:01A6` | `ROM00:01A6` |
| `01h` | `ROM00:024D` | `ROM00:01A6` |
| `03h` | `ROM00:17A5` | `ROM00:17A5` |

These are bounded control-flow tests, not full boots. There is also
an unchanged system-reset table word `4D 02` at `ROM00:3708`, documented
as the source of BDOS function 00's warm entry. The separate NMI route
and retained RAM image also need consideration. Patching two direct
jumps therefore does not implement the owner's full always-cold request.

Recommendation: explicitly cover reset classification, retained-state
resume and software reset, with tests that distinguish patched behavior
from stock. Preserve the common continuation at `ROM00:024D`: cold
initialization also reaches it, so replacing that entry with an
unconditional cold jump would risk a boot loop. Verify the resulting
full boot reaches the menu, not merely the first cold instruction.
Re-select V24 ADAPTOR after every coldstart.

### 2. High: the newly changed test helper breaks the project environment

CONFIRMED on this checkout:

```sh
analysis/venv/bin/python -m pytest -q \
  analysis/test_stock_context_v3.py analysis/test_stock_instrument.py
```

Result: **29 passed, 2 failed**. The failures are
`test_rx_hook_captures_status_and_byte` and
`test_rx_hook_skips_rxd_without_byte_ready`.
`_run_rx` installs callbacks backed by `mem`, then returns `m.memory`.
In the repository emulator those are different stores. The recent
helper change made the six selected tests pass with the temporary
PyPI `z80` 1.2.0 installation but broke these two project-env tests.
Conversely, that temporary environment fails the stock-v3 stack-write
callback test; it is not a drop-in validation environment.

Recommendation: use the documented `analysis/venv` and repair the
helper consistently with that emulator's memory model. Run both suites
there before claiming the diagnostic release is validated. These are
harness failures; they do not establish faulty generated ROM bytes.

### 3. Medium: the proposed entry hook helps localization, but loses evidence

The prepared `rx` hook snapshots `LINK_STATUS`, conditionally reads one
`LINK_RXD` value, writes `I` plus four hex digits and loops. It stops
before the stock receive arm and before `Link_BlockRx`. Consequently:

* An `I` display proves dispatcher entry, not frame reception or
  acceptance. The first status snapshot can differ from the earlier
  `LINK_STATUS` bit-4 sample used by the IRQ worker.
* `rr=00` is ambiguous between no byte-ready indication and a zero
  data value; inspect `ss`'s `LINK_STATUS` bit 0. The read is before
  the normal arm and cannot be called a decoded payload byte.
* This image has neither the v3 initialization pulse nor its return
  pulse. An absent yellow marker under this image is expected.
* With no `I` display, the run cannot distinguish no dispatcher entry
  from an unexecuted/broken diagnostic display without a separate
  installed-image/display witness.

F7 already supplied evidence of a completed receive call, so this is
a regression-localization test, not a first discovery of that path.
The continued normal error/retry flow also makes a permanently stuck
receive call a lower-priority explanation. The freshly inspected
stock receive loop has explicit polling timeouts, although malformed
descriptors or repeated controller activity prevent claiming a universal
whole-call time bound from that alone.

Recommendation: preserve a recognizable boot witness and, preferably
in one ROM burn, capture dispatcher entry plus raw `Link_BlockRx` A/F,
with an optional stop-at-entry mode. The existing corrected `rxb2`
implementation provides a starting point for the post-call record.
Distinguishing `EEh`, `EDh` and `ECh` is more useful than another
undifferentiated carry-set pulse. Capture bytes/count only when valid;
do not revive the old descriptor-as-payload error. Do not put a slow
LCD print or millisecond entry pulse before the timing-sensitive arm.

### 4. Medium: preserve experiment identity and matched controls

The F7 artifact currently lives in untracked `.cache/ir-arduino/`.
The branch contains the logs but does not carry that exact replay
binary. Archive its HEX and hash, compiler/core versions and build flags
with the experiment before depending on it for another agent's replay.
The recent free-running sensor check used phase -2/8, whereas F7 used
+2/8 and sparse 33-ms replies. Do not combine them as identical stimuli.

The long segmented exports resolve roughly 920-us yellow pulses and
millisecond reply placement. Their 40–50-us export grid does not qualify
edge setup/hold. Use the existing short, higher-rate acquisitions for
edge claims, and acquire short windows on the accessible Arduino signals
only when a changed waveform actually needs qualification.

## Recommended next sequence

1. Repair and verify the coldstart and test-environment issues above;
   settle the diagnostic output before burning another ROM. Record its
   boot identity and expected output so a silent result is interpretable.
2. Use Arduino LISTEN_ONLY at boot and during one explicit V24
   Load/Run attempt. This controls for self-reception and unrelated
   receive dispatch. Record any diagnostic output before proceeding.
3. Replay the archived F7 stimulus with the same boot state and V24
   selection. Arm logging first, then plainly ask the owner to run it.
   Repeat a positive result and interleave a silent attempt. A compact
   diagnostic prefix is enough; do not request the whole LCD contents.
4. If entry occurs, prioritize raw receive return/status over payload
   permutations. If entry stays absent in the active condition, investigate
   controller/IRQ enable and framing recognition in the stock context.
   Absence of entry alone cannot select among those causes.
5. Once there is a repeatable response, compare one convention at a
   time (including both channel assignments where still unresolved),
   with a control before and after. Then move to envelope/header and
   session acceptance. A failed control invalidates the intervening
   negative comparison; it should trigger analysis, not another large
   sweep of payloads.

The detailed run history is in the
[round-one](../../re-notes/stock-context-v3-round1.md) and
[round-two](../../re-notes/stock-context-v3-round2.md) worksheets.
Hardware remains at the handover state: the last verified Uno build is
LISTEN_ONLY; the new receive-dispatch ROM has not been reported installed.
