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
| Q3 | **Does the controller ever raise its interrupt?** | `IRQN`, `ISTAT` and direct source mask `ISRC`, every record |
| Q4 | Does any `LINK_CTRL` state change any of the above? | phase 3, 128 values per port |
| Q5 | Which physical window is which port? | both ports, alternating every few seconds |
| Q6 | Which connector pin carries which port bit? | the pin walk (hold a key at power-up) |
| Q7 | What is the keypad matrix layout? | `KEY` in every record, and on the glass |

**Q3 is the one no external experiment could have asked.** The firmware's
receive path is interrupt-driven — IRQ source 2 is the link controller, and
its handler at `ROM00:31B6` tests `LINK_STATUS` bit 4 and enters
`LinkBlockRx` ([interrupt map](../reference/memory-map.md#link-interrupt)).
A controller that signals without holding a bit long enough for a poll to
catch would be invisible to every previous run and to the polled fields here.

The keypad interrupt (source 0) is armed alongside it. That is not a
measurement — it is the control. Without it a flat `IRQN` could not be told
apart from a broken interrupt setup, and the whole answer to Q3 would be
worthless. `ISRC` separates them directly: the ISR reads active-low port
`05h`, complements it, and accumulates its source bits. Bit 0 is keypad and
bit 2 is link. The separately polled `KEY` field is not used for attribution;
a key can be pressed or released between that sample and an interrupt.

The keypad is a real interrupt source, which is why this works: it is what
wakes the machine from sleep, and all three of the firmware's sleep masks
enable it ([sleep and wake](../reference/memory-map.md#sleep-wake)). `KEY`
itself is polled rather than interrupt-driven, so it reports presses whether
or not interrupts function — which is the whole reason it cannot serve as the
control on its own.

The exerciser reproduces the matching sleep latch too: after every matrix
scan it writes `48h` to `F782` and port `02h`, exactly as
`ROM00:1766`-`176B` does for the `FAh` mask. That selects column 3; N, ENTER
and YES are known keys in that column and are the positive-control keys.

Q5 remains OPEN. The firmware proves menu choice → wire ID → latch state, and
the owner identifies the physical windows, but the emulator cannot prove
which latch state reaches which window. The run alternates both states and
records `LINK_CTRL` bit 1, providing the required hardware observation.

Phase 3 really does cover 128 effective values per port. Port alternation
would otherwise correlate each port with one parity of the sweep counter and
leave half the states untested. The exerciser rotates the raw counter left,
moving that correlated bit into bit 1, then forces bit 1 to the selected port.
The seven remaining bits therefore enumerate all 128 combinations.

**The instrument is more patient than the firmware.** A frame holds the arm for
well over 0.5 s where `LinkBlockTx` allows 9.92 ms. If `HSBUSY` falls late, the
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
2. **Power up with the Arduino idle**, in `LISTEN_ONLY`. Check the screen
   first: a counting hex row means everything downstream is working, and if
   the contrast is wrong for your unit, change `CONTRAST` in `exerciser.asm`
   — port `46h`, `00h`-`FFh`, lower is lighter, stock firmware boots to `70h`
   — before going further. This is the control run and everything else is read
   against it. Capture ≥60 s so every phase and both ports repeat several
   times. A complete 128-state sweep per port requires a much longer run.
3. **Watch which window blinks** during each cycle of a few seconds. Note it.
4. **Press N, ENTER or YES** during the capture. Two jobs: `KEY` records the
   index (`col*6 + row`), which maps the keypad as a free by-product. `IRQN` should
   rise and `ISRC` bit 0 should latch while you do it, because the keypad IRQ
   is armed alongside the link's precisely so the interrupt path can be
   proved live by hand. **If bit 0 never appears even while pressing keys,
   the interrupt setup is broken and an absent link-source bit is not yet a
   result about the link.**
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

| LCD | wire | meaning |
|---|---|---|
| hex counting up | streaming | running normally |
| hex frozen | silent | the transmitter stalled; `WD` in the frozen record says how many watchdog trips it took |
| `DEAD` | silent | never got a frame open — `LinkPresent` failed 16 times running |
| blank | silent | ran far enough to clear the display, then stopped before the first record |
| garbage or dark | silent | the patch never ran. Not a result |

The screen carries those distinctions, which is the point of initialising it:
every failure mode now names itself without a scope, an Arduino or a decode.
The top row is the current record — `COUNT OR AND RXD SIDE CTRL WD KEY IRQN
ISTAT` as twenty hex digits — so **`OR` and `AND` can be read live while you
move the Arduino around**, and the IR capture becomes the recording rather
than the only instrument. `ISRC` is the eleventh, wire-only byte.

In the decode:

| observation | meaning |
|---|---|
| `counter discontinuities` > 0 | records were lost in capture, not by the handheld |
| `watchdog trips` > 0 | some `LINK_CTRL` value stopped the controller accepting bytes; the sweep table names it |
| `ISRC` bit 0 remains clear while keys are pressed | the interrupt setup is broken. Not a result — fix before concluding anything about Q3 |
| `ISRC` bit 0 sets and bit 2 remains clear | a real negative: the path works and the controller never raised an IRQ |
| `ISRC` bit 2 sets | **the link raised an IRQ.** Go to happy path A before reading anything else |

### The happy paths

There are two now, and they are independent — either alone is a result.

#### A. `ISRC` bit 2 sets

**The controller signalled.** Read this first, because it needs no phase and
no stimulus to be meaningful, and because `IRQN` climbing while every polled
bit stays flat is the single most informative thing this burn can produce: it
would mean the controller has been signalling all along, on a channel nothing
before this could observe.

No timing inference from `KEY` is needed: `ISRC` is captured from the pending
register in the ISR itself. If bits 0 and 2 arrive together, both remain set.

`ISTAT` then says what `LINK_STATUS` held at interrupt time. Compare it with
the polled `OR` for the same phase — **if they differ, the polls have been
missing state**, and every negative from `conn3` onward is re-opened.

Three reading caveats. `IRQN` counts *records in which at least one interrupt
fired*, not interrupts: the handler masks on entry and the record loop re-arms
once per record, which is what stops a continuously asserting source
livelocking the run. `ISTAT` is sticky for the whole run, so it answers
"ever", not "when" — use `IRQN`'s first increment for timing. `ISRC` is also
sticky. And `ISTAT` is sampled on *every* interrupt including the keypad's,
so it is `LINK_STATUS` at interrupt time, not at *link*-interrupt time.

#### B. `phase 1 · bit 6 HSBUSY · changes`

The handshake completed. This is the finding the whole project has been
blocked on, and it converts the problem from "unknown protocol" into a search
with a live indicator.

Read `COUNT` for *when* it fell, and compare against the firmware's 9.92 ms
budget — approximately the first record after the arm. Two sub-cases:

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

More likely on the evidence, and none is a dead end. Three observables split
them: `HSBUSY` under arm, the receive bits, and `IRQN`.

| bit 6, phase 1 | phase 2 bit 0 / `RXD` | `ISRC` bit 2 | reading | next |
|---|---|---|---|---|
| `always 1` | flat | 0 | armed, never completes, nothing received, nothing signalled | the peer must supply something we have never produced. The sweep table is the next lead, then a real adapter or plinth capture |
| `always 1` | flat | **sets** | the controller is signalling but no polled bit moves | read `ISTAT`. The interrupt is reaching us and the state it carries is not in any poll — a new channel, and the most promising of the sad paths |
| `always 1` | **moves** | either | **light is getting in** — the receiver works, the handshake criterion is specific | the search space collapses to content and timing, with a live indicator |
| `always 0` | flat | 0 | the arm does not assert it — the model is wrong | re-read `ROM00:32CC`; `HSBUSY` may not be controller-generated at all |

A sweep value that changes any of the three is a result regardless of the
rest — it would be the first evidence that the controller has a mode the
firmware never uses. Watch `ISRC` bit 2 across the sweep especially: `LINK_CTRL`
bits 6 and 7 are what `ROM00:34BD`/`34D2` raise and lower around receiving,
and they look like an interrupt enable pair, so a sweep value that starts the
interrupts is a plausible outcome.

Silence is not in this table because it is not a phase reading — the screen
signatures above cover it.

**`LINK_RXD` non-zero anywhere** is the single most valuable observation
available, whatever else happens. It would mean the return path works and
everything since `conn3` has been mis-aimed.

### What would make the run inconclusive

* Optics not aligned — the `conn3`–`conn13` geometry is known good; do not
  change it for this run.
* Capturing less than one full cycle (a few seconds), so a phase is missing.
* Treating the preamble's `PSTAT` as a controller identity: it is
  `LINK_STATUS` immediately after `LinkProbe`, i.e. the reset state, and is
  useful only as the reference the phase readings are compared against.
* Reading `IRQN` as an interrupt count. It is a count of *records in which an
  interrupt fired*, capped at one per record by design, and it counts keypad
  interrupts too. Read `ISRC` for direct source attribution.
* Expecting `ISTAT` to localise anything. It is sticky for the whole run.
* Forgetting that taking interrupts costs coverage: the handler runs inside
  the sampling loop, so a record whose interrupt fired has one ~30 µs hole in
  its `OR`/`AND` window. Against a 122 µs wire cell, and at most once per
  record, that cannot hide an event — but it is why `ISTAT` is sampled in the
  handler rather than inferred from the polled accumulators.

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

Remaining space after this build is 22 bytes across three filler runs. A
steerable follow-up will need to retire fixed phases or other instrumentation
rather than assume the old free-space figures still apply.
