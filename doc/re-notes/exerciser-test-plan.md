# ROM exerciser — test plan

> **Scope: hardware test plan (patched-ROM run).**
> This page documents the patched-ROM exerciser that reads `LINK_STATUS`
> directly — what it measures, how to burn and run it, how to decode
> the results, and the happy/sad paths. The physical/wire layer is in
> [IR wire protocol](ir-wire-protocol.md). The firmware evidence for
> the link controller transactions is in
> [Commstar evidence](commstar-evidence.md). Together these three cover
> every layer from the analog IR waveform through the latch boundary
> to the session protocol.

**On this page:** The complete plan for the patched-ROM hardware run:
the `2609` burn, what each phase measures (Q1–Q6), the step-by-step
procedure, how to read the error row and the per-record fields
(COUNT, OR, AND, IRQN, ISRC…), the happy and sad paths, and the
follow-up steerable burn design. Intended for the owner running
the experiment; read together with the companion pages above.

* [Current burn](#current-burn-startup-diagnostic-2609) — build identity
  and LCD row format
* [Why this run exists](#why-this-run-exists)
* [What the run measures](#what-the-run-measures) — Q1–Q6
* [Procedure](#procedure) — burn, contrast, Arduino setup, capture
* [Reading the result](#reading-the-result) — error rows, happy paths,
  sad paths, inconclusive signs
* [IR handshake investigation plan](#ir-handshake-investigation-plan-phases-03)
  — Phases 0–3
* [After this run](#after-this-run) — the steerable follow-up

## Current burn: startup diagnostic `2609`

SHA-256: `ec7d06b03167531c3099ce3afc925c013b6abee0cc6b62096c123c203f7b7b72`
(32768 bytes, 716 changed bytes vs stock).
The validated setup and `A4h` contrast are retained. After ENTER, stages
`01` (probe), `02` (top-V24 select/baseline), `03` (frame open), `04`
(preamble), `05` (baseline records) appear at the upper left.

A ready timeout displays `EESSRRCCNN`: stage `SS`, fresh error-entry
`LINK_STATUS` byte `RR`, `LINK_CTRL` shadow `CC`, completed data-write count
`NN` modulo 256. The full first row is overwritten; NO/YES remain available.
Report the complete error row, or the stage number if frozen without `EE`,
plus Arduino output. Reset is required to restart the experiment.

This diagnostic uses wire version `0Eh`, fixed top V24 and no control sweeps.
Each reporting wait is bounded to 255 samples; initial frame opening uses
16 stock bounded waits. Scope and detailed build instructions are in
`analysis/rom_exerciser/README.md`. The remainder below describes historical
version-`0Dh` experiments, not the current sweep coverage.

> **Do not burn or reinstall sum16 `1225`, `2692` or `1E3E`.** The verified `1225`
> run produced a constant buzz and uniformly black LCD. The verified `2692`
> run produced only the expected brief power-up bleep but remained uniformly
> black; its transposed keypad coordinates made YES/NO ineffective. The
> verified `1E3E` run produced both beeps and a uniformly clear LCD, confirming
> that stock `Lcd_Init` returned. Correction (2026-09-10): contrast polarity
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
boundary. `Link_BlockTx` arms the handshake at `ROM00:32CC`; the same no-payload
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
`Link_BlockRx` ([interrupt map](../re-notes/interrupts.md#link-interrupt)).
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
enable it ([sleep and wake](../re-notes/interrupts.md#sleep-wake)). `KEY`
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
well over 0.5 s where `Link_BlockTx` allows 9.92 ms for `LINK_STATUS` bit 6 to
clear. A late clear would explain that specific timeout path; the subsequent
`LINK_STATUS` bit-7 payload gate remains a separate requirement.

## Procedure

0. **Verify the chips.** Read both out, sum the bytes, compare against `ACF8`
   and `2E12`, then `cmp` against `micronic/`. Do this while the case is open;
   it is the check the labels cannot do.
1. **Burn `micron1_exerciser.bin` only if sum16 is `2609` and SHA-256 is
   `ec7d06b03167531c3099ce3afc925c013b6abee0cc6b62096c123c203f7b7b72`.**
   Label it `2609`; `ROM01` is untouched. Do not reuse the `1225`, `2692`,
   `1E3E`, or `2726` parts.
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
   Build the sketch with `RECORD_READOUT 1` (as well as `LISTEN_ONLY 1`) to
   read the de-stuffed records straight over serial with no scope; every
   non-hex log line is ignored by `decode_records.py --hex`. See
   `analysis/rom_exerciser/README.md`.
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
| `DEAD` (not a screen string in this build) | silent | frame never opened; the real screen is the `EE03RR0300` row below |
| `CONTRASTxx` | silent | contrast setup; use NO/YES, then ENTER |
| contrast text frozen but keys inert | silent | keypad scanner or matrix mapping failed; IR has not started |
| contrast text disappears after ENTER | check wire | ENTER was accepted and link startup began |

### Precomputed error rows (`2609`)

A terminal timeout homes the cursor and overwrites the whole first row with ten
hex digits and ten blanks:

```text
EE SS RR CC NN
```

`EE` is the error marker; `SS` the startup stage; `RR` a **fresh** port-`4Bh`
(`LINK_STATUS`) sample taken on entry (`exerciser.asm:802`), not the last
polling sample; `CC` the port-`4Ah` (`LINK_CTRL`) shadow (`03h` before the
transmit arm, `13h` after — see below); and `NN` the count of completed
port-`4Dh` (`LINK_TXD`) data writes, modulo 256. Read `SS` first, then `RR`:
that is the measurement.

Only stages `03`-`05` can produce a row. Every timeout is a bounded bit-7
(`TXRDY`) wait that expired (`waitready`, `exerciser.asm:445-453`), and the only
sites that jump to the error screen are that wait and the 16-attempt frame-open
loop (`open_try`, `exerciser.asm:693-697`). Stages `01`/`02` have no bounded
wait, so a **frozen `01`/`02` with no `EE` is a hang**, not a timeout; report
the number as-is. CONFIRMED: `failure` unconditionally writes `0xEE` first
(`exerciser.asm:806`), and `dead: jp failure` (`:331`) is the only route in.

`CC` is `03h` before the arm and `13h` after (CONFIRMED). The arm `arm_tx` at
`0x0250` (replicating stock `ROM00:32CC-32EE`: raise `LINK_CTRL` bit 5, then
bit 4, settle 32 iterations, drop bit 5 leaving bit 4 SET) runs once the first
preamble byte `A5` has been written, so: stage `03` rows and stage `04` rows
with `NN=00` show `CC=03h`; stage `04` rows with `NN>=01` and all stage `05`
rows show `CC=13h` (CTRL_SHADOW `13h` vs `03h` baseline).

| Failure | `SS` | `CC` | `NN` | Row shape | `RR` reading and diagnosis | Next action |
|---|---|---|---|---|---|---|
| `Link_Present` failed all 16 stock attempts; frame never opened | `03` | `03` | `00` | `EE03RR0300` | bit 7 clear: TXRDY never asserted through ~16x9.7 ms. bit 7 set: it appeared just after the bound | No command and no data byte reached the wire (`Link_Present` writes `81h` only on success). Check controller presence/power; compare with the stock ROM |
| First preamble byte cannot be sent | `04` | `03` | `00` | `EE04RR0300` | bit 7 clear: TXRDY still not asserted. bit 7 set: late ready | Probe/select/open passed but the first data write cannot complete (arm has not yet run) |
| Preamble stalls mid-stream | `04` | `13` | `01`-`04` | `EE04RR13NN` | bit 7 clear: stalled at this byte. bit 4/0 set: inbound activity while transmitting | TX worked for `NN` bytes then stopped: intermittent ready, or a peer reply |
| Record frame cannot start | `05` | `13` | `05` | `EE05RR1305` | bit 7 clear: the frame flag or the first record field timed out | Preamble complete. `putflag` is uncounted (`exerciser.asm:467-471`), so `NN=05` does not distinguish a missing frame flag from a missing `COUNT` field |
| Inside a record | `05` | `13` | `06`-`15` | `EE05RR13NN` | bit 7 clear: stalled at this field | Failing field is `(NN-5) mod 11`, 0-based: 0 `COUNT`, 1 `OR`, 2 `AND`, 3 `RXD`, 4 `SIDE`, 5 `CTRL`, 6 `WD`, 7 `KEY`, 8 `IRQN`, 9 `ISTAT`, 10 `ISRC` |
| After one or more complete records | `05` | `13` | `5+11R` | `EE05RR1310` at `R=1` | bit 7 clear: the next record's first field, or a frame flag, timed out | Completed records `R = ((NN-5) x 163) mod 256`, since `163 = 11^-1 mod 256` |

The regression test asserts these shapes with a simulated controller, e.g.
`EE03400300` (never ready), `EE04010302` (mid-preamble), `EE05000310` (first
record done). On hardware `RR` is whatever port `4Bh` reads — extract the
decisive bits by hand:

| `RR` bit | Name | Firmware meaning |
|---|---|---|
| 7 | TXRDY | the exerciser's own wait condition; set means ready arrived just after the bound |
| 6 | HSBUSY | the firmware waits for this to **clear** at `ROM00:32F3`; set means still busy |
| 4 | RX pending | inbound frame waiting (`ROM00:34E7`); set means the peer may be answering |
| 0 | RX byte | a received byte is ready (`ROM00:33CF`); set means the return path is alive |

`RR` is one instant; the record `OR`/`AND` accumulators from the Arduino or
scope capture are the authority on whether a bit was stuck or merely late. One
row cannot establish a stuck bit on its own.

The `1E3E` run's second beep already proved that stock `Lcd_Init` returns, so
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
  `LINK_STATUS` immediately after `Link_Probe`, i.e. the reset state, and is
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

## IR handshake investigation plan (Phases 0–3)

This plan records the **already-established** receive-path findings and the
next hardware/software steps without new inference. It is the reference for the
open questions described in
[IR wire protocol — The receive path and the awaited status bit](ir-wire-protocol.md#the-receive-path-and-the-awaited-status-bit).

### Phase 0 — hardware gate (already prepared)

* **Burn build `2609`**, Arduino `LISTEN_ONLY` + `RECORD_READOUT`, press ENTER,
  decode with `decode_records.py`.
* Holds the `ROM00:32CC`-`ROM00:32EE` arm (raise `LINK_CTRL` bit 5, then bit 4,
  32-iteration settle ~0.11 ms, drop bit 5 leaving bit 4 SET) and samples
  `LINK_STATUS` (`4Bh`) as per-record `OR`/`AND` plus `ISRC` bit 2.
* **Witness variant as independent Phase-0 read (CONFIRMED):** `micron1_witness.bin` (`2E3E`, built with `build.py --witness`, 824 changed bytes, SHA-256 `aa843c38dcb8131612d3d235871397bf6e6ace73d00aeeb50c79d4a7a6f124a0`) does the same stock opening (Link_Probe, top-V24 port select, control setup), writes the flag via Link_Present, writes ONE first data byte (`A5`), performs the `arm_tx` handshake, then **raises LINK_CTRL 6/7** (the stock 34BD/2FAE action; whether 6/7 gates the receive path, only its interrupt, or another function is Provisional) (`LINK_CTRL` bits 6/7 via `ctrl_or 40h` then `ctrl_or 80h`, doing what `ROM00:34BD`/`ROM00:2FAE` does — CONFIRMED fix; every earlier exerciser build left them clear so the link RX interrupt was never enabled by the exerciser (consequence Provisional)) and watches the receive path. It then never writes `LINK_CMD`/`LINK_TXD`/`LINK_CTRL` again, so nothing it sends can disturb the receive path (CONFIRMED by emulator: exactly one `0x81` to `LINK_CMD`, one `0xA5` to `LINK_TXD`, arm values `23h`/`33h`/`13h`, enables `53h`/`0D3h`, then silence). Its LCD row is `W` `OR AND ISRC IRQN ARMD HB` — `OR`/`AND` are `LINK_STATUS` over the current window (~0.1 s, reset after each LCD update) so a stimulus is visible live; `ISRC`/`IRQN` sticky for the run; `ARMD` is `LINK_STATUS` sampled immediately after the arm; `HB` heartbeat; reset only by power-cycling. The default `2609` record-stream build stays byte-identical when the witness code is stripped; both live in the same reclaimed `scr` region at `0250-02FD` (CONFIRMED). The witness also serves as an independent Phase-0 read for `LINK_STATUS` bit 6 with no peer.
* **Discriminator:**
  * If `LINK_STATUS` bit 6 sets then **clears with no peer**, it is a
    **transmit-complete** condition — go to Phase 3.
  * If it **stays set with no peer**, the **peer-handshake** reading survives —
    go to Phase 2.

### Phase 1 — offline, partly done

Finish mapping the receive chain (`ROM00:2FBD`, `LinkRxDispatcher` at
`ROM00:3010`/`3028`/`3056`, `ROM00:30DC` `Link_ValidateFrameHeader`) and where
`LINK_CTRL` bits 6/7 are raised/lowered relative to the transmit handshake
(`ROM00:34BD` / `ROM00:34D2` pair; `Link_BlockTx` clears at `ROM00:327D`; IRQ
poll re-arms at `ROM00:31C2`). Records the window ordering from static code.

### Phase 2 — hardware: receive-convention sweep

Hold the arm, then **stop transmitting** and sample `LINK_STATUS` (`OR`/`AND`)
and the link IRQ source while the Arduino sends return-path stimuli sweeping:

* **(a) flag sense:** `1000_0001` vs `0111_1110`;
* **(b) data polarity** (inverted vs non-inverted);
* **(c) data/clock phase** sign and magnitude (`+/-1/4` and `+/-1/8` cell);
* **(d) delivery:** continuous idling flags vs a burst timed after the
  handheld's burst;
* **(e) content:** bare flag → flag+address → flag+prelude `03h`.

**Witness + Arduino `RX_SWEEP` pairing (CONFIRMED code, syntax-checked with host stub, no AVR toolchain in CI):** the witness ROM (`2E3E`, `build.py --witness`, 824 changed bytes, SHA-256 `aa843c38dcb8131612d3d235871397bf6e6ace73d00aeeb50c79d4a7a6f124a0`, enables `LINK_CTRL` 6/7 before listening) is the Phase-0/Phase-2 instrument that removes the record-stream build's TX confound — it stops transmitting after the arm, raises LINK_CTRL 6/7 (Provisional RX-enable), and reports `LINK_STATUS` `OR`/`AND` (current ~0.1 s window, live) and sticky `ISRC` on the LCD (`W` `OR AND ISRC IRQN ARMD HB`). The Arduino sketch `analysis/arduino/m1000_ir_probe/m1000_ir_probe.ino` gains `RX_SWEEP` (set `RX_SWEEP 1`, all other mode flags `0`). It answers each handheld burst with one combination of: flag sense `{0x81, 0x7E}`; data polarity `{normal, complemented}`; data-to-clock phase `{-4,-2,0,+2,+4}` eighths of a cell (transmit convention is a −2/8-cell data lead); content `{flag only, flag+03h, flag+03h+legal body+flag}`. Reply ~3 ms after the handheld burst; one combination advances per burst and the parameters are printed. It does NOT score itself: the controller's reaction is read from the witness ROM (`LINK_STATUS` `OR`/`AND`, `ISRC`).

**Timing guidance — CONFIRMED (emulator):** the gating is temporal. The
firmware holds LINK_CTRL 6/7 clear for the ~10–12 ms `Link_BlockTx` transaction (620 × 59 T
~ 9.92 ms at 3.6864 MHz, `ROM00:32F0`, within the ~93.75 ms retry interval)
and raises them by `ROM00:34BD` at `ROM00:2FAE` after it. A return-path
stimulus timed after that ~10 ms TX window is the safe choice under either reading of 6/7; timing a reply to the handheld's burst alone (∼1–9 ms) lands
inside the window in which the firmware holds LINK_CTRL 6/7 clear; whether that prevents reception depends on the Provisional 6/7 reading. 65 exerciser tests pass.

**Discriminator:** any of `LINK_STATUS` bit 6 **clear**, `LINK_STATUS` bit 4
**set**, or **IRQ source 2** asserting identifies the receive convention.
This answers open questions **C** and **D** and, if bit 6 clears, **A/B**.

### Phase 3 — redo the `conn`-style reply with a completed handshake

With a completed transmit handshake (Phase 0 outcome) and — if Phase 2 finds one
— the correct return convention, redo the `conn`-style reply and hunt for the
post-handshake payload. `micronic.peer.CommstarPeer` already covers the session
layer above that boundary. This answers **B**.

### Offline work available (no hardware)

1. **Static receive-chain map (Phase 1)** — partly done above; finish the
   `2FBD`/`LinkRxDispatcher`/`30DC` walk and the `LINK_CTRL` 6/7 raise/clear
   ordering relative to the transmit handshake.
2. **Emulator traces of the firmware's TX/RX enable ordering** (`analysis/boot_hw.py`)
   to confirm the window ordering; note the controller model is synthetic, so
   this validates **control flow only**, not electrical timing.
3. **"RX witness" exerciser variant (CONFIRMED, done)** — `micron1_witness.bin` (`2E3E`, `build.py --witness`, 824 changed bytes, SHA-256 `aa843c38dcb8131612d3d235871397bf6e6ace73d00aeeb50c79d4a7a6f124a0`) performs the transmit opening+arm once, **enables `LINK_CTRL` 6/7** (`ctrl_or 40h`/`80h` — what `34BD`/`2FAE` does; earlier builds left them clear so RX IRQ could never fire), then stops transmitting and samples `LINK_STATUS` (`OR`/`AND`) and the link IRQ source over a long window, reporting on the **LCD** (`W` `OR AND ISRC IRQN ARMD HB`, `OR`/`AND` per-window live, `ISRC`/`IRQN` sticky, `ARMD` post-arm sample) — the IR channel cannot be used while listening. Emulator-validatable; no IR emission during the listen window except the enables (CONFIRMED: one `0x81`/`0xA5` + arm `23h`/`33h`/`13h` + `53h`/`0D3h`, then silence). Default `2609` stays byte-identical.
4. **Arduino Phase-2 receive-convention sweep modes (CONFIRMED, done)** — `analysis/arduino/m1000_ir_probe/m1000_ir_probe.ino` now has `RX_SWEEP` (flag sense `{0x81,0x7E}`, data polarity `{normal, complemented}`, phase `{-4,-2,0,+2,+4}` eighths, content `{flag only, flag+03h, flag+03h+legal body+flag}`, ~3 ms reply, one combination per burst, parameters printed; syntax-checked with host stub, no AVR toolchain in CI).
5. **Write the Phase-2 bench procedure** (wiring, sweep order, capture length,
   decode steps, and the per-record `OR`/`AND`/`ISRC` decision table).

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
