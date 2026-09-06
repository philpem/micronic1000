# ROM exerciser — test plan

The plan for the first patched-ROM run: what is being measured, what each
outcome means, and what to do next in either direction. The tool itself is
`analysis/rom_exerciser/`; this page is the experiment.

## Why this run exists

Thirteen runs of external stimulus (`conn3`–`conn13`, ~3,500 bursts) produced
exactly one bit of behaviour: the handheld's normal cycle, or that cycle plus
15.6 ms. One rule explains all of them — light must still be present at the
9.92 ms deadline — and no variation of address, framing, completeness, clock
or timing moved it. See [IR wire protocol](ir-wire-protocol.md).

That work is exhausted because the deciding variable is inside the latch
boundary. `LinkBlockTx` arms the handshake at `ROM00:32CC`, then waits at
`ROM00:32F3` for `LINK_STATUS` bit 6 (`HSBUSY`) to go **clear**, and reports
`0EEh` — the 238 on the error screen — when it does not. No external probe can
see that bit. This run reads it directly.

**Direction matters and is easy to invert.** `HSBUSY` is asserted *by* the arm
and the firmware waits for it to fall. Watching an unarmed controller reading
zero would mean nothing at all, which is why phase 1 replays the arm.

## What the run measures

| | question | how |
|---|---|---|
| Q1 | Does `HSBUSY` ever go clear once armed? | phase 1, `LINK_CTRL` = `11`/`13` |
| Q2 | Does anything ever arrive? | phase 2, `LINK_STATUS` bit 0 and `LINK_RXD` |
| Q3 | Does any `LINK_CTRL` state change either answer? | phase 3, 128 values per port |
| Q4 | Which physical window is which port? | both ports, alternating ~1.9 s |
| Q5 | Which connector pin carries which port bit? | the pin walk (hold a key at power-up) |
| Q6 | What is the keypad matrix layout? | `KEY` in every record |

Q4 is already settled from the firmware
([commstar-evidence](commstar-evidence.md#device-table-ports)) — the run
re-measures it because it costs 20 bytes and because getting it wrong silently
invalidates everything else.

**The instrument is more patient than the firmware.** A frame holds the arm for
~470 ms where `LinkBlockTx` allows 9.92 ms. If `HSBUSY` falls late, the
firmware's timeout is the whole failure and the problem is far smaller than it
looks.

## Two modes

**Hold any key while powering on** for the pin walk; otherwise the link run.
That is the entire interface, and it deliberately needs no keymap knowledge,
since the keymap is itself unknown.

## Procedure — A, the pin walk

Do this first: it is quick, it needs no IR alignment, and its result makes
every later side-port observation interpretable.

1. Power on **with any key held**. Port `2Ch` now pulses a countable code:
   bit 0 once, bit 1 twice, bit 4 five times, bit 5 six times, long gap,
   repeat. Bits not being driven leave a silent slot, so the count always
   equals the bit number.
2. Probe each pin of the 5-pin side connector in turn — a scope, a meter on
   a slow range, or an LED and a resistor. Count pulses. Record which pin
   gives which count.
3. Expect one or more pins not to move at all. Those are inputs, ground, or
   power.
4. Bit 5 is the IR port select, so its six-pulse group may not reach the
   connector. Its absence is information, not a fault.
5. For the **inputs**, power-cycle without a key held (mode B) and short each
   remaining pin to ground and to supply in turn, watching the `SIDE` byte in
   the decoded records. `2Dh` bits 0 and 1 are the ones the firmware reads.

If nothing at all pulses on any pin, the outputs do not reach this connector;
set `PORTMAP_BITS` to `FFh` and repeat, accepting that bits 2, 3, 6 and 7 are
undocumented and the unit may do something unexpected.

## Procedure — B, the link run

0. **Verify the chips.** Read both out, sum the bytes, compare against `ACF8`
   and `2E12`, then `cmp` against `micronic/`. Do this while the case is open;
   it is the check the labels cannot do.
1. **Burn `micron1_exerciser.bin`** and label it with the sum `build.py`
   prints. `ROM01` is untouched.
2. **Power up with the Arduino idle**, in `LISTEN_ONLY`. This is the control
   run and everything else is read against it. Capture ≥60 s (≈8 full phase
   cycles, ≈32 sweep values).
3. **Watch which window blinks** during each ~1.9 s half. Note it.
4. **Press a few keys** during the capture — `KEY` records the index
   (`col*6 + row`), which maps the keypad as a free by-product.
5. **Repeat with stimulus**, replaying the `conn3`–`conn13` modes. The
   exerciser does not care what the Arduino does.
6. **Decode** each capture with `decode_records.py`.

Expect a blank screen and a dead keyboard: interrupts are off and it never
powers down. Power-cycling is the only exit, and it drives the IR LED
continuously, so use external power if you can.

## Reading the result

`decode_records.py` reduces each capture to a per-bit verdict per phase per
port. Read them in this order.

### Is the run valid at all?

| side port | wire | meaning |
|---|---|---|
| beacon once, then quiet | streaming | running normally |
| beacon once, then quiet | silent | the stream started, then the transmitter stalled |
| beacon **repeating for ever** | silent | never got a frame open — `LinkPresent` failed 16 times running |
| bit 0 toggling irregularly | silent | the watchdog is tripping: code alive, controller refusing bytes |
| nothing at all | silent | the patch never ran. Not a result |

The side port carries those distinctions because the IR channel cannot report
that the IR channel has stopped. Watch a side-port pin on the scope alongside
the IR line, not instead of it.

In the decode:

| observation | meaning |
|---|---|
| `counter discontinuities` > 0 | records were lost in capture, not by the handheld |
| `watchdog trips` > 0 | some `LINK_CTRL` value stopped the controller accepting bytes; the sweep table names it |

### The happy path

**`phase 1 · bit 6 HSBUSY · changes`.**

The handshake completed. This is the finding the whole project has been
blocked on, and it converts the problem from "unknown protocol" into a search
with a live indicator.

Read `COUNT` for *when* it fell, and compare against the firmware's 9.92 ms
budget — about two records. Two sub-cases:

* **it falls with the Arduino idle** — the controller does not need a peer at
  all, and the failure is in how the firmware drives it. Go straight to
  reproducing the state with a stock ROM.
* **it falls only under stimulus** — the stimulus that did it is the answer.
  Bisect it with the Arduino's existing modes; the exerciser reports each
  attempt in real time, so ~3,500 blind bursts become a few dozen informed
  ones.

Then: put the stock ROM back, reproduce the winning stimulus, and the session
should pass `C-INIT-COMMS`. The remaining error decades (8020s, 8030s, …)
become the build order for the adapter, and
`micronic.peer.CommstarPeer` already covers the session layer above it.

### The sad paths

These are more likely on the evidence, and none is a dead end — **bit 0 is
what splits them**.

| phase 1 bit 6 | phase 2 bit 0 | reading | next |
|---|---|---|---|
| `always 1` | `always 0` | armed, never completes, nothing received | the peer must supply something we have never produced. The sweep table is the next lead; then a real adapter or plinth capture |
| `always 1` | `changes` | **light is getting in** — the receiver works, the handshake criterion is specific | the search space collapses to content and timing, with a live indicator. Best of the sad paths |
| `always 0` | `always 0` | the arm does not assert it — the model is wrong | re-read `ROM00:32CC`; `HSBUSY` may not be controller-generated at all |
| n/a | n/a | wire silent, beacon present | `TXRDY` never asserts even with no firmware competing. Indicts our init sequence, not the link |

A sweep value that changes any bit is a result regardless of the rest — it
would be the first evidence that the controller has a mode the firmware never
uses.

**`LINK_RXD` non-zero anywhere** is the single most valuable observation
available, whatever else happens. It would mean the return path works and
everything since `conn3` has been mis-aimed.

### What would make the run inconclusive

* Optics not aligned — the `conn3`–`conn13` geometry is known good; do not
  change it for this run.
* Capturing less than one full cycle (~1.9 s), so a phase is missing.
* Treating the preamble's `PSTAT` as a controller identity: it is
  `LINK_STATUS` immediately after `LinkProbe`, i.e. the reset state, and is
  useful only as the reference the phase readings are compared against.

## After this run

The follow-up burn should be **steerable** rather than fixed, and the keypad
is the channel — not port `2Dh`. It needs no wiring, no pinout and no case
modification, it is independent of the IR link (the circularity that has
blocked every approach), and this run already proves it works by reporting
`KEY` in every record.

The shape: replace the fixed four-phase cycle with a dispatch on the held key,
so one chip covers the whole experiment space and the operator drives it by
hand while watching the wire. That frees more space than it costs, because the
phase sequencing and the sweep counter both go away.

Remaining space after this build: 2 bytes at `00A2`, 38 at `724C`, 37 at
`7E96` — 77 in all. Enough for a key dispatch, not for a key dispatch plus
everything currently there, which is the right trade once this run has told us
which phases are worth keeping.
