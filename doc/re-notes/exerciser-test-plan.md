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
| Q5 | Which side-port pin carries which bit? | beacon out, `SIDE` in |

Q4 is already settled from the firmware
([commstar-evidence](commstar-evidence.md#device-table-ports)) — the run
re-measures it because it costs 20 bytes and because getting it wrong silently
invalidates everything else.

**The instrument is more patient than the firmware.** A frame holds the arm for
~470 ms where `LinkBlockTx` allows 9.92 ms. If `HSBUSY` falls late, the
firmware's timeout is the whole failure and the problem is far smaller than it
looks.

## Procedure

1. **Verify the chips.** Read both out, sum the bytes, compare against `ACF8`
   and `2E12`, then `cmp` against `micronic/`. Do this while the case is open;
   it is the check the labels cannot do.
2. **Burn `micron1_exerciser.bin`** and label it with the sum `build.py`
   prints. `ROM01` is untouched.
3. **Wire the side port** while the case is open — two in, two out. It is the
   command channel for any follow-up burn.
4. **Power up with the Arduino idle**, in `LISTEN_ONLY`. This is the control
   run and everything else is read against it. Capture ≥60 s (≈8 full phase
   cycles, ≈32 sweep values).
5. **Watch which window blinks** during each ~1.9 s half. Note it.
6. **Repeat with stimulus**, replaying the `conn3`–`conn13` modes. The
   exerciser does not care what the Arduino does.
7. **Decode** each capture with `decode_records.py`.

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

The follow-up burn should be **steerable** rather than fixed. Port `2Dh`
gives two input bits that do not depend on the IR link — the circularity that
has blocked every approach — so the Arduino can select experiments live and
one chip covers the whole space. That is why `SIDE` and the beacon are in this
run: they map the channel in both directions.

Remaining space after this build: 52 bytes at `724C`, 64 at `7E96`. Enough for
a command decoder and one experiment; a steerable version wants the sweep and
phase logic replaced by a dispatch on `2Dh`, which frees more than it costs.
