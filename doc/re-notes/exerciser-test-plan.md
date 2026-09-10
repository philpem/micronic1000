# ROM exerciser — test plan

> **Do not burn or reinstall sum16 `1225`, `2692` or `1E3E`.** The verified `1225`
> run produced a constant buzz and uniformly black LCD. The verified `2692`
> run produced only the expected brief power-up bleep but remained uniformly
> black; its transposed keypad coordinates made YES/NO ineffective. The
> verified `1E3E` run produced both beeps and a uniformly clear LCD, confirming
> that stock `LcdInit` returned. Correction (2026-09-10): contrast polarity
> was not isolated from concurrent startup timing and ordering changes.
> The owner reports that `27E8` displays `CONTRASTC0`, but keys remain
> ineffective. Do not reburn it unchanged; keypad diagnosis precedes IR tests.
> Current replacement: sum16 `2D31`, SHA-256
> `7f2efaa6a4893c889dc6f0059a8411952a2a622419d390c1d892fb2648707bf6`.
> Owner validated `2D4D` heartbeat, idle readings, NO/YES and key release.
> Decreasing the contrast byte darkens the screen; `A4h` is preferred.
> `2D31` changes only the initial contrast to `A4h`; no reburn is needed to
> continue with `2D4D` adjusted manually. The row is `C` followed by hex pairs for contrast,
> decoded key, heartbeat and six masked sense readings (drive masks
> `01h,02h,04h,08h,10h,20h`). NO/YES adjust contrast; ENTER starts the link.
> If keys fail, record the row at rest and with keys held and whether the
> heartbeat advances. Older `CONTRASTC0` instructions below describe `27E8`.

The plan for the next patched-ROM run: what is being measured, what each
outcome means, and what to do next in either direction. The tool itself is
`analysis/rom_exerciser/`; this page is the experiment.

## Why this run exists

Thirteen runs of external stimulus (`conn3`–`conn13`) produced two retry
populations separated by one 64 Hz scheduler period. The raw-capture audit
found that response duration predicts the conn13 split, but preamble and clock
state defeat a universal final-light-off rule. See
[IR wire protocol](ir-wire-protocol.md).

That work is exhausted because the deciding variable is inside the latch
boundary. `LinkBlockTx` arms the handshake at `ROM00:32CC`; the same no-payload
`0EEh` result can follow either the `LINK_STATUS` bit-6-clear wait at
`ROM00:32F3` or a per-byte `LINK_STATUS` bit-7-set wait beginning at
`ROM00:3318`. No optical probe can distinguish those status paths. This run
reads the complete `LINK_STATUS` byte directly.

**Direction matters and is easy to invert.** The firmware waits for
`LINK_STATUS` bit 6 to clear after the arm. Watching an unarmed controller
reading zero would mean nothing, which is why phase 1 replays the arm; whether
the arm itself makes `LINK_STATUS` bit 6 set is one of the measurements.

## What the run measures

| | question | how |
|---|---|---|
| Q1 | Does `LINK_STATUS` bit 6 ever go clear once armed? | phase 1, `LINK_CTRL` = `11`/`13` |
| Q2 | Does anything ever arrive? | phase 2, `LINK_STATUS` bit 0 and `LINK_RXD` |
| Q3 | **Does the controller ever raise its interrupt?** | `IRQN`, `ISTAT` and direct source mask `ISRC`, every record |
| Q4 | Does any `LINK_CTRL` state change any of the above? | phase 3, 128 values per port |
| Q5 | Which physical window is which port? | both ports, alternating every few seconds |
| Q6 | What is the keypad matrix layout? | `KEY` in every record, and on the glass |

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

Q5 is closed for the top state and remains a direct check for the back state.
The real V24 Load/Run route uses `fdd4=43h`: **wire-ID bit 5 is clear**, while
**`LINK_CTRL` bit 1 and port `2Ch` bit 5 are both set**. The owner captured
that route at the top V24 window. The run alternates both states and records
`LINK_CTRL` bit 1, so observing the wire-ID-bit-5-set state—where both output
bits are clear—at the back PLINTH window will confirm the complementary
mapping without relying on elimination.

Phase 3 really does cover 128 effective values per port. Port alternation
would otherwise correlate each port with one parity of the sweep counter and
leave half the states untested. The exerciser rotates the raw counter left,
moving that correlated bit into bit 1, then forces bit 1 to the selected port.
The seven remaining bits therefore enumerate all 128 combinations.

**The instrument is more patient than the firmware.** A frame holds the arm for
well over 0.5 s where `LinkBlockTx` allows 9.92 ms for `LINK_STATUS` bit 6 to
clear. A late clear would explain that specific timeout path; the subsequent
`LINK_STATUS` bit-7 payload gate remains a separate requirement.

## Procedure

0. **Verify the chips.** Read both out, sum the bytes, compare against `ACF8`
   and `2E12`, then `cmp` against `micronic/`. Do this while the case is open;
   it is the check the labels cannot do.
1. **Burn `micron1_exerciser.bin` only if sum16 is `27E8` and SHA-256 is
   `f02073d9743faab7b69c1ff85bdabc018a328000507ecf51574bba95e03814ca`.**
   Label it `27E8`; `ROM01` is untouched. Do not reuse the `1225`, `2692` or
   `1E3E` parts.
2. **Set contrast before configuring the Arduino.** After the brief power-up
   bleep and approximately 0.6 s startup delay, the LCD should show
   `CONTRASTC0`. NO decrements `g_bLcdContrast` and port `46h` by two toward the
   darker `00h` endpoint; YES increments both toward the lighter `FFh`
   endpoint. The hexadecimal value is redrawn after every poll. Press ENTER
   when the text is comfortably readable. The IR code is not touched before
   ENTER.
3. Put the Arduino in `LISTEN_ONLY`, press ENTER, and capture ≥60 s so every
   phase and both ports repeat several times. A complete 128-state sweep per
   port requires a much longer run. A counting hex row means everything
   downstream is working. Use good ambient light: the link run does not depend
   on the still-LIKELY identification of port `2Ch` bit 4 as the backlight.
4. **Watch which window blinks** during each cycle of a few seconds. Note it.
5. **Press N, ENTER or YES** during the capture. Two jobs: `KEY` records the
   index (`6*sense-bit-index + drive-bit-index`), which maps the keypad as a
   free by-product. `IRQN` should
   rise and `ISRC` bit 0 should latch while you do it, because the keypad IRQ
   is armed alongside the link's precisely so the interrupt path can be
   proved live by hand. **If bit 0 never appears even while pressing keys,
   the interrupt setup is broken and an absent link-source bit is not yet a
   result about the link.**
6. **Repeat with stimulus**, replaying the `conn3`–`conn13` modes. The
   exerciser does not care what the Arduino does.
7. **Decode** each capture with `decode_records.py`.

Expect no normal firmware menus: this is a dedicated test and it never powers
down. It first presents the contrast screen; after ENTER, the top LCD row
should count continuously, and N/ENTER/YES are retained as the interrupt
positive-control keys. Power-cycling is the only exit, and after ENTER it
drives the IR LED continuously, so use external power if you can.

## Reading the result

`decode_records.py` reduces each capture to a per-bit verdict per phase per
port. Read them in this order.

### Is the run valid at all?

| LCD | wire | meaning |
|---|---|---|
| hex counting up | streaming | running normally |
| hex frozen | silent | the transmitter stalled; `WD` in the frozen record says how many watchdog trips it took |
| `DEAD` | silent | never got a frame open — `LinkPresent` failed 16 times running |
| `CONTRASTxx` | silent | contrast setup; use NO/YES, then ENTER |
| contrast text frozen but keys inert | silent | keypad scanner or matrix mapping failed; IR has not started |
| contrast text disappears after ENTER | check wire | ENTER was accepted and link startup began |

The `1E3E` run's second beep already proved that stock `LcdInit` returns, so
the new candidate spends that ROM space on an interactive screen instead.

Davison's 1998 monitor uses the same LCD ports and overlapping controller
values, and writes port `46h` before its first HD61830 command. This candidate
copies that ordering, not Davison's full eight-page display-RAM clear: stale
off-screen RAM cannot explain a uniformly driven-black panel. Davison's source
is in `micron.zip` on the
[archived Micronic download page](https://www.geocities.ws/micronic99.geo/download.htm).
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

#### B. `phase 1 · LINK_STATUS bit 6 HSBUSY · changes`

A clear transition occurred while the transmit arm was held. This directly
answers one latch-level question, but does not by itself prove the subsequent
per-byte `LINK_STATUS` bit-7 wait or a complete handshake.

Read `COUNT` for *when* it fell, and compare against the firmware's 9.92 ms
budget — approximately the first record after the arm. Two sub-cases:

* **it falls with the Arduino idle** — clearing `LINK_STATUS` bit 6 does not
  require that stimulus. Reproduce the state with stock ROM and observe
  `LINK_STATUS` bit 7 at the first payload byte.
* **it falls only under stimulus** — the stimulus controls or correlates with
  the bit-6 transition. Bisect it with the Arduino's existing modes while also
  recording `LINK_STATUS` bit 7 and the link interrupt source.

Then put the stock ROM back and reproduce the transition. Only a resulting
payload or successful `C-INIT-COMMS` establishes that the complete transmit
handshake passed. `micronic.peer.CommstarPeer` covers the session layer above
that boundary.

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

Remaining space in the corrected candidate is 11 bytes across all six filler
runs. A steerable follow-up will need to retire fixed phases or other
instrumentation rather than assume the old free-space figures still apply.
