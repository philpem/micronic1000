# IR wire protocol — first hardware capture

Everything below the `4Ah`-`4Fh` latch boundary. Until now this layer was
listed as *Not implementable — requires a hardware capture*
([protocol/commstar.md](../protocol/commstar.md)); this page is that capture
and what it does and does not settle.

Read it alongside [Commstar evidence](commstar-evidence.md), which stays the
record for everything **above** the latches.

## Provenance

| | |
|---|---|
| Instrument | Agilent MSO-X 3054A, s/n MY51260150, fw 02.65 |
| Taken | 2026-09-02 20:08:30, by the owner |
| Files | `m1000_v24_conn2.csv` (50 segments), `m1000_v24_conn1.h5` (segment 1 of the same acquisition, byte-identical) |
| Probes | ch1 = IR **clock**, ch2 = IR **data**, on the V24 ADAPTOR (top) port, handheld → adapter direction |
| Acquisition | segmented, 30769 points × 104.0006 ns = 3.2 ms per segment, armed for 64 segments, **50 fired**, 4.607 s total |
| Stimulus | operator selects V24 ADAPTOR and starts a connection with nothing attached; ends in `*** ERROR *** 8000 Plinth not connected` |

The reverse-engineering that follows was done against the CSV only. The
decoder is `analysis/scope_ir_decode.py`.

## Physical layer — CONFIRMED

| Quantity | True value | Measured |
|---|---|---|
| Bit cell | **122.0703125 µs — 8192 bit/s exactly** | 122.000 µs ± 0.053 (SE, n=50 least-squares fits) |
| Clock | 50% duty, 61.04 µs each way | 65.43 / 56.61 µs at the 50% threshold — see slew, below |
| Data pulse | **5/8 cell = 76.29 µs** | 75.30 µs ± 0.48 (de-biased) |
| Data rise → clock rise | **−1/4 cell = −30.52 µs** | −30.60 µs ± 0.04 (de-biased) |
| Levels | 0 V / 5.5 V | ch1 −0.14/5.41 V, ch2 −0.14/5.57 V |
| Edge speed | — | clock rise 5.2 µs, fall 7.1 µs; data rise 2.5 µs, fall 6.9 µs |

**Sample the data at the clock's rising edge.** Consecutive `1`s are two separate pulses; the line is
pulse-coded, not a held level, so there is no NRZI to undo. The clock is not
free-running — it exists only for the duration of a burst.

### It is a two-phase clock — LIKELY

Comparing like-for-like transitions (rail departures, so a 2.5 µs data rise is
not being measured against a 5.2 µs clock rise), the data edge lands on a
quarter cell before the clock's rising edge to within 80 ns:

```
data rise - clock rise   =  -30.60 us +/- 0.04   =  -0.2507 cell
clock high width         =   62.33 us +/- 0.30   =   0.5106 cell
data pulse width         =   75.30 us +/- 0.48   =   0.6169 cell
```

With a 50% duty clock, **−1/4 cell is exactly the midpoint of the clock's low
phase**. So the data does not change near its sampling edge at all: it changes
half a phase away from it, which is precisely what a two-phase clock buys you.
Setup is 2/8 cell and hold is 3/8 cell around the sampling edge — generous, and
deliberate.

Laying the geometry out in eighths of a cell, with the clock's rising edge as
phase 0:

| Phase | −2 | 0 | +3 | +4 |
|---|---|---|---|---|
| | data rises | **clock rises — sample here** | data falls | clock falls |

Every edge in the protocol sits on a 1/8-cell grid. That implies an internal
phase clock at 8 × 8192 = **65.536 kHz — exactly twice 32.768 kHz**, i.e. both
edges of a watch-crystal clock. Taken with the ÷4 in the next section, the
whole timing structure falls out of one 32.768 kHz source, which is a crystal
the machine demonstrably already has.

The one loose end is the data pulse width: 5/8 cell predicts 76.29 µs against
75.30 ± 0.48 measured, a 2σ shortfall. The falling edge is the slowest in the
system (6.9 µs) and therefore the worst-conditioned de-biasing, so this is
more likely measurement systematics than a real 1 µs discrepancy.

**Credit where due:** the two-phase reading came from the owner reading the
scope directly and saying the data edges looked closer to the middle of the
clock than to a quarter of it. Both descriptions are the same instant — a
quarter cell before the rising edge *is* the middle of the low phase — but the
two-phase framing is the one that explains why.

### The bit rate is exactly 8192, and the CPU clock says so

An earlier revision of this page quoted 8194 bit/s. That was over-precise: a
single per-segment fit is good to a few hundred ppm, and pooling all 50 gives
122.000 ± 0.053 µs, which is **1.3σ from 122.0703125 µs**. The true rate is
8192 bit/s and the measurement never had the resolution to say otherwise.

The owner's correction to the CPU clock is what settles it. **The M1000 runs
at 3.6864 MHz, not the 3.579545 MHz assumed elsewhere in this repository**
(`protocol/commstar.md`, "Timing budget", needs the same correction):

| Source | Divider for 8192 Hz | |
|---|---|---|
| 3.579545 MHz (assumed) | 436.956 | **not an integer** — cannot produce 8192 Hz |
| **3.6864 MHz (owner)** | **450** | exact |
| 32.768 kHz (RTC crystal) | **4** | exact |

So the corrected clock makes 8192 bit/s *reachable*, which the old figure did
not. Among nearby integer dividers of 3.6864 MHz only 450 fits — ÷448 is
+3884 ppm (8.9σ) and ÷452 is −5000 ppm (11.5σ), both excluded.

The `÷4` column is worth noting too: the machine already contains a 32.768 kHz
crystal for its HD146818 RTC, and **122.070 µs is a rate-select line in that
chip's own datasheet** (RS = `0011`, the same divider chain that gives the
1024 Hz periodic interrupt this firmware programs — see [RTC](rtc.md)).
Whether the link controller takes the RTC's square-wave output, has its own
watch crystal, or divides the CPU clock by 450 is **OPEN**; all three land on
the same 122.0703125 µs cell, which is the only thing an adapter needs.

### The slew is the receiver's, not the transmitter's

The capture is taken at the output of the owner's own optical front end: an
**SFH213 photodiode reverse-biased with its cathode to +5 V and a 100k anode
resistor to ground, probed at the anode**. Light raises the anode, so
light = logic 1 and a dark line idles at 0 — which is the polarity this page
assumes throughout, now on a circuit basis rather than an inference.

That circuit, not the M1000, is what shapes the edges:

| | measured | implies |
|---|---|---|
| Clock fall 90–10% | 7.08 µs | τ = 3.22 µs → **C = 32 pF** with 100k |
| Data fall 90–10% | 6.88 µs | τ = 3.13 µs → **C = 31 pF** |
| Clock rise 10–90% | 5.2 µs | photocurrent-driven |
| Data rise 10–90% | 2.5 µs | photocurrent-driven |

The two **falls agree to 3%** because a fall is the node discharging through
100k alone — signal-independent — and 32 pF is what an SFH213 (~11 pF) plus a
10× probe (~15 pF) plus stray gives. The **rises differ by 2×** because a rise
is driven by photocurrent: `V(t) = I·R(1 − e^(−t/τ))` clamps at the rail long
before τ, so the brighter or better-aligned channel arrives faster. Both
observations fall out of the same first-order model, which is decent evidence
the model is right.

Two consequences:

* **An earlier revision of this page inferred that "the M1000's receiver
  cannot be fussy about edge placement, because its own transmitter is not."
  That is withdrawn** — the slew is the measuring receiver's. Nothing here
  bounds the sharpness of the M1000's actual optical output, and a
  microcontroller responder should not claim latitude on this evidence.
* **The de-biasing used above is validated by the model.** Rail departures —
  10% on a rise, 90% on a fall — track the true switching instant to within
  ~0.1τ ≈ 0.3 µs at both ends, which is why the data-to-clock measurement
  lands on a quarter cell to 80 ns.

**Planned front end (owner, 2026-09-03): 47k pull-down plus an NPN buffer.**
Splitting the difference on the resistor while the buffer removes the probe
from the photodiode node:

| R | C | τ | fall 90–10% | as a fraction of a cell |
|---|---|---|---|---|
| 100k | 32 pF (diode + 10× probe) | 3.20 µs | 7.03 µs | 5.8% — what was captured |
| 47k | 32 pF | 1.50 µs | 3.30 µs | 2.7% |
| 47k | 15 pF (buffered, no probe) | 0.71 µs | 1.55 µs | **1.3%** |

Two things to watch, both of which would produce a confusing null rather than
an obvious failure:

* **Polarity.** A common-emitter stage **inverts**. The frame would then decode
  with the flag reading `7Eh` and every data byte complemented, which looks
  exactly like a protocol misunderstanding rather than a wiring choice. If the
  buffer inverts, invert it back in software — or note it, because this page's
  whole polarity argument assumes light = 1 at the measurement point.
* **Base-current loading.** An emitter follower draws `Ie/β` from the node —
  at 1 mA and β = 200 that is 5 µA, which is the same order as the SFH213's
  photocurrent, so the follower can swamp the signal it is meant to buffer. A
  common-emitter stage with a base resistor, or a 74HC14 Schmitt inverter pair
  (near-zero input current, and it squares the edges for free), avoids that.

Halving the load also halves the signal, so the rises — which are
photocurrent-driven and currently clamp early — will slow somewhat even as the
falls improve. The falls are what limit the measurement, so it is still a clear
net win.

### The transmit gate is synchronous; the flag substitution is not

First and last clock pulse of every burst, against the mid-burst population, at
the 50% threshold where overshoot cannot produce false crossings:

| | width | short by >5 µs |
|---|---|---|
| Mid-burst | 61.64 µs | — |
| **First** pulse of a burst | 62.99 µs | **2 of 50** |
| **Last** pulse of a burst | 64.12 µs | **1 of 50** |

If the transmit enable simply gated a free-running phase clock, it would open
and close at a random point in the cell and roughly half of all first and last
pulses would be visibly chopped. They are not: **bursts start and stop on clean
cell boundaries**, so the enable is registered against the phase clock.

That makes the runt at the flush boundary more interesting, not less. It is the
*only* place in a burst where a short clock pulse occurs — a mid-cell event in
a machine that otherwise switches cleanly on cell boundaries, i.e. a data-path
mode change rather than a gate.

## Burst inventory — CONFIRMED

Three distinct cell patterns across 50 triggers, and nothing else on either
line:

| Cells | Count | Pattern (pulse = `1`) |
|---:|---:|---|
| 17 | 16 | `10000001 000001011` |
| 22 | 19 | `00001` `10000001 000001011` |
| 22 | 15 | `00000` `10000001 000001011` |

Every burst ends immediately after its last pulse — the clock stops, it does
not run on through trailing zeros.

### The lead-in is a pipeline flush — LIKELY

An earlier revision of this page called the five-cell lead-in "a preceding
flag, clipped at turn-on", on the grounds that `00001` is bits 3-7 of
`10000001`. **That is wrong**, and the owner's alternative — that the stuffer
has a 4-5 bit output pipeline which is flushed when an unstuffed flag is
written to `LINK_CMD` — fits the measurements better on every count:

| Observation | Flag-fill | Pipeline flush |
|---|---|---|
| Lead-in is 4 cells in 31 bursts, 5 in 3 | must be a fixed 5 | a 4-5 stage pipe, as proposed |
| The pre-flag cell carries a **full-amplitude** 5.6 V data pulse in **22 of 34** bursts and nothing in the other 12 | a flag ends in `1`, so this must always be set — **it is not** | leftover pipe content, so it may vary |
| That cell's clock is a 20-25 µs stub, or missing entirely | unexplained | the flush point, where the framer changes mode |
| That cell's data pulse, when present, is 60-78 µs against a 75-78 µs nominal | unexplained | truncated by the same mode change |
| Lead-in clock edges scatter 6× more than the rest of the burst (sd 2.31 µs vs 0.38 µs, deglitched) | unexplained | the timing chain running but not yet settled |
| Form A has no lead-in at all | the flag fill is sometimes simply absent | the pipe was already empty |

The clock itself does **not** re-phase across the boundary. Fitting one grid to
every deglitched clock edge in each burst puts the step between the lead-in
cells and the flag+data cells at **+0.14 ± 0.20 µs (0.7σ)** — one continuous
clock, jittery at the start and clean after the flag. So the flush is a
data-path event, not a clock restart, which is exactly what "the flag bypasses
the stuffer" predicts.

A detail that fits neatly: the previous transaction's data byte is `03h`, whose
MSB-first bit pattern *ends* `1,1`. A residual `1` left in the pipe from the
last frame is therefore precisely the bit we see in the pre-flag cell. Why it
is absent in the other 12 bursts is **OPEN** — the pipe presumably drains
further under some condition we cannot see from outside.

**None of this matters to an adapter**, which simply hunts for the flag and
ignores whatever precedes it. It matters because it says the controller
contains a pipelined bit-stuffer with a bypass path for flags — one more piece
of evidence that this is a real framer and not a shift register.

**Bursts repeat end-to-end every 93.75 ms**, exactly. Trigger-to-trigger
intervals are 93.08 ms (long→short), 93.75 ms (same→same) and 94.42 ms
(short→long) — the ±0.67 ms is the 5-cell length difference about a constant
gap, so what is periodic is the *retry delay after a transmission ends*, not
the start of transmission.

## Candidate controller architectures — SUSPECTED

Spitballing, but constrained: any proposed structure has to produce all of the
following, and most obvious designs fail at least one.

| | Constraint |
|---|---|
| A1 | Flag `1000_0001` emitted **unstuffed** from a `LINK_CMD` (`4Ch`) write |
| A2 | Data byte emitted **MSB-first, stuffed**, a `1` inserted after five `0`s |
| A3 | 4–5 cells of lead-in *before* the flag, carrying a leftover bit in 22 of 34 bursts and none in the other 12 |
| A4 | The lead-in/flag boundary cell has a runt or missing clock — a mid-cell event |
| A5 | Burst start and end are phase-clean, so the transmit enable is synchronous |
| A6 | One continuous on-grid 8192 Hz clock throughout; no re-phasing (+0.14 ± 0.20 µs) |
| A7 | Edges on a 1/8-cell grid; consecutive `1`s are two distinct pulses, never a held level |
| A8 | The burst ends immediately after the last data bit |

### The stuffing rule: a preset-5 down-counter

The owner's proposal — a counter preset to 5 when a `1` is sent, decremented
when a `0` is sent, inserting a `1` and inhibiting the shift when it reaches
zero — is almost certainly how A2 is done. Three flip-flops, and it reproduces
the observed rule exactly rather than approximately.

What it does *not* do on its own is explain A3. A counter makes its decision in
the same cell as the bit it governs; there is no inherent latency, so no
lead-in falls out of it.

### Where the 4–5 cells come from: two candidates

**(a) The zero-run detector is a delay line.** If "five consecutive zeros" is
detected by passing the data through a **5-bit shift register** and NORing the
taps, then the data is examined *after* five cells of delay, and the output
lags the input by exactly five cells. That is A3's number without adjustment.
Costs five flip-flops and a 5-input NOR — nothing, in a gate array.

**(b) The counter drains after the last bit.** Even with the cheap counter, the
framer may not consider itself finished until the stuff counter has expired.
The clock gate closes when the byte source runs dry (A8), leaving 4–5 cells of
unfinished business latched. Those cells finally clock out when the gate
reopens for the *next* transaction — which is exactly where we see them, and
why the leftover bit is the previous frame's residue.

(b) is the more economical story and it ties A3 to A8 through one mechanism. It
also predicts the residue's value: `03h` MSB-first ends `1,1`, so a leftover
`1` is precisely what should appear — and does, in 22 of 34 bursts. Why the
other 12 drain clean remains **OPEN**.

### How the flag gets in front: probably no flush at all

The natural reading of "flush the flag-fill buffer" is a drain-then-substitute
state machine: on a `4Ch` write, keep clocking the data path until the pipe is
empty, mux in the flag for eight cells, mux back. That works, but it needs a
sequencer and a mux.

**A cheaper structure produces the same wire behaviour with one gate.** Load
`81h` into the *same* shift path as data, and assert a stuff-inhibit line for
those eight bits. Then:

* the flag is unstuffed (A1) because the inhibit is held;
* no explicit flush is needed — the flag simply **queues behind** whatever
  residue is already in the pipe, which is why the lead-in appears *before* the
  flag rather than between the flag and the data (A3);
* the data that follows suffers no extra gap, because by then the pipe is
  moving steadily;
* and the inhibit line is set by a Z80 `OUT` at an arbitrary moment, so unlike
  the carefully registered transmit enable (A5) it can land mid-cell and chop
  the cell in progress — which is A4, the one runt in the whole burst.

That last point is the attractive part: it explains why the burst's *edges* are
clean but its *one internal mode change* is not, using the difference in care
between a synchronised enable and a directly-latched control bit.

### What would discriminate

All of these need code running on the machine — but note the circularity
resolves in the *helpful* direction. Today that means T6, a ROM burn. **Once a
working link exists, arbitrary code can simply be loaded over it**, and every
test below becomes a program to download rather than a chip to swap. So these
are deliberately parked: they are the reward for T5 succeeding, not
prerequisites for it, and the same is true of the `LINK_CMD` sweep in the
`81h`-coincidence section above.

That also inverts the priority of T6. Its value is not that it answers these
questions — T5 succeeding answers them more cheaply — but that it is the
fallback if T5 stalls.

The tests, for when that day comes:

* **Two `4Dh` writes back to back, no flag between.** Structure (a) predicts a
  five-cell gap on the first byte only; (b) predicts none.
* **A `4Ch` write mid-frame.** A drain-then-substitute sequencer delays the
  flag by the pipe depth; the inhibit-line structure emits it immediately after
  the bit in progress.
* **A byte with a long zero run, e.g. `00h` then `FFh`.** The stuffing pattern
  under (a) appears five cells after the byte is written; under (b) it appears
  at once.

### One thing this says about the receiver

Whatever the transmit structure, the M1000's *receive* path presumably mirrors
it, with a de-stuffer of matching latency. An adapter does not need to model
that — it just has to keep the wire timing — but it is a reason not to be
surprised if the handshake response has to arrive later than a naive reading of
`HSBUSY` suggests.

## Frame layer: HDLC with the line sense inverted — LIKELY

Read the burst as a bit-stuffed HDLC-like frame in which a light pulse is a
logical `1`:

* **Idle = 0**, so the LED is dark between bursts. Standard HDLC's all-ones
  idle would hold an IR emitter on for 91 ms in every 94.
* **Flag = `1000_0001` = `81h`**, exactly `~7Eh`. Like `7Eh` it is the unique
  pattern carrying six consecutive identical bits.
* **Stuffing inverted to match**: the framer inserts a `1` after five
  consecutive `0`s.
* **Data is MSB-first.**

Under that reading all three burst forms decode to the same thing:

```
lead-in   flag       data field (raw)   destuffed   byte
-         10000001   000001011          00000011    03h
00001     10000001   000001011          00000011    03h
00000     10000001   000001011          00000011    03h
```

`03h` is the **prelude** — `link id & 1Fh`, written at `ROM00:32B3`, and the
same `03h` that heads every captured session request.

### Why this is more than a fit

Four independent checks, none of which was used to construct the reading:

1. **The stuffed bit is predicted, not fitted.** Run `03h` forwards through
   the framer: MSB-first it is `0,0,0,0,0,0,1,1`; the rule trips on the fifth
   `0` and inserts a `1`, giving `000001011` — nine cells, bit for bit what is
   on the wire. No other byte produces it:

   | byte | on the wire (MSB-first) | | byte | |
   |---|---|---|---|---|
   | `00h` | `000001000` | | `03h` | `000001011` ← **capture** |
   | `01h` | `000001001` | | `07h` | `000001111` |
   | `02h` | `000001010` | | `81h` | `100000101` |

2. **The flag is not stuffed and the data is.** `81h` contains six
   consecutive `0`s. Had the framer stuffed it, the burst would be 18 cells,
   not 17. So the controller applies the stuffing rule to the byte written to
   `LINK_TXD` (`4Dh`) and *not* to the one written to `LINK_CMD` (`4Ch`) —
   which is precisely flag-versus-data handling, and is the strongest single
   piece of evidence that a real framer sits in the ASIC rather than a bare
   shift register.
3. **Six-zero runs occur only inside the flag**, in all three burst forms.
   That invariant is the entire purpose of bit stuffing; a mis-framed reading
   would not respect it.
4. **Bit order is forced.** LSB-first also reproduces the wire, but yields
   `C0h` — and the prelude is `id & 1Fh`, so bits 6 and 7 cannot be set.
   `03h` is the only reading consistent with `ROM00:32B0 AND 1Fh`.

### What it settles

* **The controller forwards the prelude onto the IR line.** This was
  explicitly OPEN at `protocol/commstar.md` ("whether the controller forwards
  the prelude onto the IR line is not determinable from the firmware… a logic
  capture of the line settles it immediately"). It does forward it.
* **The prelude is the HDLC address field.** `FLAG | ADDRESS | …` is the HDLC
  layout, and it explains three firmware oddities at once: why the id is
  masked to five bits, why the prelude is written before the strobe sequence
  rather than with the payload, and why it is excluded from the frame's own
  byte count. It was never a payload byte.
* **The ASIC bit-stuffs.** Any adapter must destuff, and any adapter that
  transmits must stuff. This is not something the firmware could have told us.

### The `81h` coincidence — SUSPECTED, and it matters

`LINK_CMD` (`4Ch`) has **exactly one writer and exactly one value**, and the
flag on the wire is that value. Byte-verified independently for this page: the
only `D3 4C` in either 32K image is at `ROM00:34F5`, `DB 4C` does not occur at
all, and the three `ED 79` (`OUT (C),r`) sites load `C` with `02h`, `02h` and
`46h`, so there is no indirect write either.

```text
34EC  CD F8 34   CALL 34F8h      ; LinkWaitReady - poll TXRDY, DE=02DAh
34EF  C8         RET Z           ; not ready -> caller fails with EBh
34F0  3E 81      LD A,81h
34F2  32 96 F7   LD (F796),A     ; shadow
34F5  D3 4C      OUT (4Ch),A     ; the only write to LINK_CMD in the image
34F7  C9         RET
```

Two readings remain, and the capture cannot separate them:

* **(a) `4Ch` is a "send a flag" strobe** and the ASIC generates the flag
  pattern itself. `81h` is then either the author writing the flag's own value
  as documentation, or coincidence.
* **(b) `4Ch` is an unstuffed byte channel** — write a byte, it goes out raw —
  and the flag is programmable. Check 2 above shows the byte is treated
  differently from a `4Dh` byte either way.

The discriminating test is to write some other value to `4Ch` and scope the
line (see T6). For adapter-building purposes the distinction is moot: the
firmware never varies it, so the opening byte is always `81h`.

## Why the session fails, and where — LIKELY

`Error 8000 / 8001 "Plinth not connected"` is **not** a detection result. It
is printed by `SessionStateBuild` (`ROM00:4351`) via the helper at
`ROM00:4463`, reached from `C-INIT-COMMS`'s result switch (`ROM00:46D6`) on
result 9 or default — i.e. **the peer never answered the link-configure
request**, whatever is physically attached.

Pressing ENTER at that error runs a **second** batch of 50 attempts that ends
`8040 "Line failure"`. That is not a retry of the connect: `8040` is the
default arm of `C-DROP-LINE`'s result switch, so the second batch is the line
teardown failing the same way. See
[session-operation error decades](commstar-evidence.md#session-operation-error-decades).

The wire says exactly where the transaction dies. `LinkBlockTx`
(`ROM00:3277`) gets as far as:

| Step | ROM | On the wire |
|---|---|---|
| `LinkPresent` → `81h` to `LINK_CMD` | `34F5` | flag `10000001` ✓ |
| prelude `id & 1Fh` → `LINK_TXD` | `32B3` | stuffed `000001011` = `03h` ✓ |
| wait `LINK_STATUS` bit 4 (`RXBUSY`) clear, `DE=026Ch` | `32B8` | — |
| strobe `LINK_CTRL` bits 5/4 | `32CC`-`32E6` | — |
| wait `LINK_STATUS` bit 6 (`HSBUSY`) clear, `DE=026Ch` | `32F3` | **nothing further** |
| stream payload bytes | `3315` | never reached |

The clock stops after the address, so no payload byte was ever accepted. The
failure is one of the two handshake waits — most likely `HSBUSY` at `32F3`,
the one that is *supposed* to be cleared by the far end acknowledging.
**Distinguishing bit 4 from bit 6 is OPEN**; both exit paths are silent on the
wire.

Timeout budget, computed from the actual loops **at 3.6864 MHz** (the owner's
figure; `protocol/commstar.md` still says 3.579545 MHz and is wrong by 3%):

| Loop | ROM | Count | Iteration | Deadline |
|---|---|---:|---:|---:|
| `LinkWaitReady` (`TXRDY`) | `34F8` | `02DAh` = 730 | 49 T | **9.70 ms** |
| handshake waits (bits 4, 6) | `32B8`, `32F0` | `026Ch` = 620 | 59 T | **9.92 ms** |
| per payload byte (`TXRDY`) | `3318`/`334E` | `06F9h` = 1785 | 51 T | **24.69 ms** |

An adapter has just under 10 ms to complete the handshake and ~25 ms per byte
thereafter. Generous, but not unbounded — a chatty Arduino sketch with
`Serial.println` in the ISR path will miss them.

### The 50 bursts — LIKELY

The session layer retries a request up to `32h` = **50** times (`ROM00:2F58`
sets `FDD6`, `ROM00:30FC` decrements). The scope was armed for 64 segments and
**exactly 50 fired**, spanning 4.607 s ≈ 50 × 93.75 ms, after which the error
banner appeared. So this capture is almost certainly the *complete* connect
attempt, first request to give-up, and not a window into a longer one.

Confirming test: re-arm for ≥64 segments and check the count is exactly 50
again, and that the 50th burst coincides with the banner.

## There is exactly one path to the wire — CONFIRMED

Byte-verified across both 32K images:

| Latch | Writes in the image | Where |
|---|---|---|
| `LINK_CMD` `4Ch` | **one**, one value (`81h`) | `ROM00:34F5` |
| `LINK_TXD` `4Dh` | **one** `D3 4D`, plus the `OUTI` in the same routine | `ROM00:32B6`, `ROM00:331D` |
| `LINK_PROBE` `4Fh` | one, one value (`1Fh`) | `ROM00:3491` |

No indirect writes: the only three `ED 79` (`OUT (C),r`) sites load `C` with
`02h`, `02h` and `46h`.

So **every outbound byte in the machine goes through `LinkBlockTx`**, and
`LinkBlockTx` cannot emit a payload byte until the `HSBUSY` wait at
`ROM00:32F3` clears. The consequence is worth stating plainly because it
closes off a whole class of ideas:

> No sequence of menu selections, file operations or debug settings can ever
> put more on the wire than a flag and a prelude. The prelude value is the
> only free variable reachable without either solving the handshake or
> changing the ROM.

(The main menu's `4 Diagnostics` → `Set Debug mode` screen, with its `Status`
ON/OFF and `Device` fields, is subject to the same constraint — whatever it
routes, it routes through `LinkBlockTx`.)

## `LinkProbe` does not select a port — CONFIRMED

`LinkProbe` (`ROM00:348A`) writes `1Fh` to `4Fh` and then toggles `LINK_CTRL`
bit 5 and bit 0 through the `ram:F794` shadow. It never calls
`LinkPortSelect`, and it never writes port `2Ch`. Port selection is done only
by `LinkPortSelect` (`ROM00:3454`), and its only caller is `LinkBlockTx`
(`ROM00:327A`):

```text
3454  F5           PUSH AF
3455  3A 8B F7     LD A,(F78B) / AND FDh / LD (F78B),A / OUT (2Ah),A
3460  28 11        JR Z,3473          ; id bit 5 CLEAR -> 3473
3462  3A 94 F7     LD A,(F794) / AND FDh / LD (F794),A / OUT (4Ah),A   ; CTRL bit 1 CLEAR
346C  3A 8D F7     LD A,(F78D) / AND DCh
3471  18 11        JR 3484
3473  3A 94 F7     LD A,(F794) / OR 02h / LD (F794),A / OUT (4Ah),A    ; CTRL bit 1 SET
347D  3A 8D F7     LD A,(F78D) / AND FCh / OR 20h                      ; 2Ch bit 5 SET
3484  32 8D F7     LD (F78D),A / OUT (2Ch),A
3489  C9           RET
```

This confirms the mapping already in
[protocol/commstar.md](../protocol/commstar.md): id bit 5 **clear** →
`LINK_CTRL` bit 1 **set** and `2Ch` bit 5 **set**; id bit 5 **set** → both
clear.

Therefore, during a cold-boot `LinkProbe`, **the port is whatever the latches
were left holding**. At that moment nothing has ever written `2Ch` — the first
write in the machine's life is at `ROM00:3487` — so the port select is in its
power-up state, not a chosen one.

Combined with the table above, the prediction is that **the boot probe emits
nothing at all**: it touches neither `4Ch` nor `4Dh`, so under the framer model
there is no byte for the controller to frame. The owner's null result on the
PLINTH port is consistent with that. Capturing the V24 port during a cold boot
would make it a two-port null and settle it.

**Where in the boot:** the reset vector at `ROM00:0000` is `C3 03 01`
(`JP 0103`), and `0103` is `C3 4B 01` (`JP 014B`). The two probe calls sit at
`ROM00:0202` and `ROM00:0229` — before the warm-boot signature is written
(`ROM00:0232`, `LD A,55h / LD (F81C),A`) and before the self-test banner. Arm
the scope single-shot *before* powering up, not after.

## Owner observations, 2026-09-03

Two results from the hardware, both of which close off planned tests and one
of which is a positive confirmation.

* **PLINTH and V24 ADAPTOR both transmit prelude `03h`.** CONFIRMED (owner).
  This is exactly what the model predicts and is worth stating as support, not
  just as a blocked test: the two ids are `43h` and `63h`, which differ *only*
  in bit 5 — the port select — so `id & 1Fh` is `03h` for both. A reading in
  which the first data byte were anything other than the masked id would have
  no reason to be identical across the two ports.
* **EXT STORAGE ADAPTOR emits no IR at all**; it fails with `Can't open or
  create file` (`ROM01:7CDB`, behind the runtime error-code→string table at
  `ram:D0E0` / `ROM01:7C80`). So the drive path aborts in the file layer
  before any link transaction starts, and it is not a route to a different
  address byte.

* **T3 is done: PLINTH is the back port, V24 ADAPTOR is the top port.**
  CONFIRMED (owner). What this does *not* yet fix is which *link id* drives
  which port — that needs the id to change, i.e. T6.
* **No IR from the PLINTH port during a cold boot.** Consistent with the
  `LinkProbe` analysis above.
* **The receiver is being rebuilt with a 47k pull-down and an NPN buffer**
  (planned 2026-09-03), which should take the fall time from 5.8% of a bit cell
  to between 2.7% and 1.3%. See the front-end section for the polarity and
  base-current cautions.
* **The optical front end used for the capture is an SFH213, reverse-biased,
  cathode to +5 V, 100k anode resistor to ground, probed at the anode.** So
  light = logic 1, and the microsecond edges in the capture are this circuit's,
  not the M1000's.
* **The data edges sit at the middle of the clock's low phase, not a
  quarter-cell offset "lead"** — a two-phase clock. Owner observation from the
  scope, confirmed by measurement; see the physical-layer section.
* **The stuffer has a 4-5 bit output pipeline, flushed by an unstuffed flag
  write to `LINK_CMD`.** Owner hypothesis, and it explains the lead-in cells
  better than the flag-fill reading it replaces.
* **The CPU clock is 3.6864 MHz**, not the 3.579545 MHz assumed elsewhere in
  this repository. CONFIRMED (owner). It changes every ROM timeout by 3% and,
  more usefully, it is the reason 8192 bit/s is exactly reachable — see the
  physical-layer section.
* **The ROMs are socketed but the unit is awkward to open**, so T6 is a
  fallback rather than the first move; the Arduino path (T5) is the primary
  route.

The consequence is that **no user-reachable menu path changes the address
byte**. `FE83`/`FE93` are writable only by BDOS `F8h`/`FAh`/`FBh`, which needs
code, which needs a link. See T6 for the way out of that circle.

## What is still OPEN

| # | Question | Discriminating test |
|---|---|---|
| 1 | Is the framing reading right across more than one byte? | **T6** (256 bytes at once); partially **T1** if the boot probe emits |
| 2 | MSB- or LSB-first, on evidence wider than one byte? | **T1** — `1Fh` differs starkly between the two orders; otherwise **T6** |
| 3 | Is there an FCS, and what polynomial? | **T6**, or **T5** followed by a completed-frame capture |
| 4 | Is there a closing flag, or does the clock simply stop? | **T6** / **T5** |
| 5 | What does the return direction look like? | Not observable without a partner — **T4** characterises the front end instead |
| ~~5a~~ | ~~Which detector is clock and which is data?~~ | **ANSWERED** (conn10): the wiring as built is correct; swapping the emitters kills the reaction |
| 6 | What clears `HSBUSY` / `RXBUSY`? | **T6** — T5 was run to exhaustion (conn3-conn13) and cannot reach it |
| 7 | Does the return clock have to be M1000-locked or may it free-run? | **T5.3** |
| 8 | Is `4Ch` a flag strobe or an unstuffed byte channel? | **T6** |
| 9 | Which *link id* drives which port? (the names are settled: PLINTH = back, V24 = top) | **T6** — the one-byte patch answers it by inspection |
| 10 | Is a light pulse logical 1 or logical 0? | Cosmetic — the two readings are complements; the idle-dark argument picks `1` |

Nothing on this list is reachable from the user interface. That is the single
most important planning fact on this page, and it is why T6 exists.

## Test plan

Revised 2026-09-03 after the owner observations above. No adapter or plinth
exists to monitor, and no code can be run on the machine, so the plan is now:
everything free that the machine already does (T1-T3), then the sweep (T5),
with a patched ROM (T6) as the move that unblocks everything at once.

### T1 — capture the cold-boot probe

**Free, and the only other byte the firmware ever hands the controller.**
`LinkProbe` (`ROM00:348A`) runs twice during cold boot, at `ROM00:0202` and
`ROM00:0229` (byte-verified: `CD 8A 34` at both sites):

```text
348A  3E 7F      LD A,7Fh
348C  E6 1F      AND 1Fh         ; -> 1Fh
348E  32 99 F7   LD (F799),A
3491  D3 4F      OUT (4Fh),A     ; LINK_PROBE = 1Fh
3493  ...        LINK_CTRL bit 5 clear, bit 0 set, bit 0 clear
```

Arm single-shot on the port LEDs and power-cycle. Either outcome is worth
having:

* **Something is emitted** — a second wire sample, from a different latch, of
  a byte (`1Fh`) that is not `03h`. `1Fh` is `0001_1111` MSB-first and
  `1111_1000` LSB-first; neither needs a stuffed bit, both are 8 cells, but
  the patterns are unmistakably different. That settles OPEN 2 on its own.
* **Nothing is emitted** — `4Fh` is a local reset of the controller with no
  wire side, which is what an earlier investigation assumed, and an adapter
  need not answer anything at power-on.

### T2 — flood the detectors, then loop back electrically

A mirror was the original suggestion; the owner's objection is correct and it
is withdrawn. The emitters and detectors share one window, so a mirror couples
the clock emitter into the data detector as readily as into its own, and a
null result would mean nothing. Two better versions:

**T2a — flood (free, now).** Illuminate the detectors with any IR source — a
TV remote will do — while a connect attempt runs, and watch the transmit
burst. Crosstalk is irrelevant to the only question being asked: *does
returned light change the transmit state machine at all?* If the burst length
or the 93.75 ms cadence moves, the receive path gates the transmitter and
`HSBUSY` is reachable from outside. If nothing moves under any illumination,
the controller wants structure, not light.

**T2b — electrical loopback (after T4).** With the front end characterised,
wire the clock emitter's drive into the clock detector's input and the data
emitter's into the data detector's, keeping the two channels separate. That is
a perfect echo adapter with none of the optics problem, and it costs no
protocol design: if the controller accepts its own transmission as a reply,
the handshake clears and the full 12-byte frame appears on the wire — which is
T5's prize without writing any Arduino logic at all. If it does not clear, we
have learned that the controller checks content, and the sweep has a much
narrower target.

T2b is arguably the single best experiment on this page after T6. It is worth
doing before T5 rather than as part of it.

### T3 — which port is which line state — **DONE, partially**

CONFIRMED (owner, 2026-09-03): **PLINTH is the back port, V24 ADAPTOR is the
top port.** That fixes the menu-name ↔ physical-port mapping.

What remains is the *id-bit* half: which of `43h`/`63h` (id bit 5 clear/set,
`LINK_CTRL` bit 1 set/clear) drives which of those two ports. That cannot be
observed while both ids mask to the same prelude, so it moves to T6, where the
one-byte patch answers it by inspection.

### T4 — characterise the receive front end

Before building anything, scope what the photodiode side does: quiescent
level, output swing, and whether it is a clean logic output or a raw analogue
one. Use any IR source — a TV remote will do — to see the response. This
defines the electrical interface the Arduino has to drive and is the one piece
of homework T5 cannot skip.

### T5 — Arduino responder, swept — **completed, and exhausted**

**Done, conn3-conn13. It did not clear the handshake.** See
[adapter experiments](#adapter-experiments-conn3-conn13-confirmed) for what
was learned and what was ruled out. The harness works and the handheld
demonstrably receives us; what no stimulus reaches is `HSBUSY`. Retained below
as built, because the apparatus is reusable and the reasoning behind its
design still holds.

#### As originally planned

`analysis/arduino/m1000_ir_probe/` is the harness. It listens on the
handheld's outbound pair, decodes the frame, answers on the return pair, and
**scores itself**: any burst longer than 30 cells means the `HSBUSY` wait at
`ROM00:32F3` cleared and the handheld went on to stream its 12-byte payload.
No scope is needed in the loop — the scope is for confirming a hit.

The economics are unusually good. The handheld retries 50 times per connect
attempt at 93.75 ms, so **one operator keypress is ~50 free trials**. The
sketch advances one sweep parameter per burst, so the full space —
8 delays × 7 contents × 4 clock modes × 2 polarities = 448 trials — is nine
connect attempts, a few minutes of work.

**Stage 1: listen only.** Build with `LISTEN_ONLY 1` and confirm the monitor
prints 17- and 22-cell bursts at 93.75 ms matching the scope. Debugging a
responder against an unvalidated decoder is two unknowns at once.

**Stage 2: sweep.** Set `LISTEN_ONLY 0`. The parameters:

| Axis | Values | Rationale |
|---|---|---|
| Delay after the last clock edge | 250 µs … 9 ms, 8 points | The `HSBUSY` deadline is 9.92 ms; nothing later can work |
| Content | flag only, flag+`03h` (echo), flag+`7Fh`, flag+`43h`, flag+`63h`, flag fill ×4, bare pulses | `03h` echo is the most plausible; bare pulses test whether the controller wants activity rather than structure |
| Clock mode | clock+data, data only, clock only, free-run | OPEN 7 |
| Polarity | normal, inverted | The two readings of this protocol are complements and the wrong one fails silently |

**The framer is validated against the capture.** Building the `flag+03h` reply
produces `10000001000001011` — bit for bit the handheld's own burst, stuffed
bit included. So a "wrong" result cannot be blamed on the encoder.

**Two engineering notes that matter more than they look.**

* The reply is transmitted *before* anything is printed. One `Serial` line at
  115200 is about 4 ms against a 9.92 ms window; reporting first loses every
  trial.
* Edges are placed by absolute scheduling against `micros()` with direct port
  writes, not chained `delayMicroseconds()`. `digitalWrite()` costs ~4 µs on an
  AVR, against a 31 µs data-lead interval, and the error accumulates across a
  frame. `micros()` has 4 µs granularity, which is ~13% of that lead interval —
  acceptable for a first pass, but if the sweep comes up empty everywhere,
  moving the transmitter to a hardware timer is the first thing to try before
  concluding the content is wrong.

**Wiring.** The handheld's drive lines swing to ~5.5 V — over `VCC+0.5` even on
a 5 V part. Series 10k on each input, or a divider on a 3.3 V board. Keep the
two return channels optically separated with a mask or a short opaque tube per
LED: crosstalk from our clock into the handheld's data detector will look
exactly like a protocol failure.

### T6 — a patched ROM. **Now the primary route**

Every remaining OPEN item is blocked behind "cannot run code, because loading
code needs the link". A patched `ROM00` breaks that circle. This was filed
behind T5 on the grounds that the unit is awkward to open; **T5 has now been
run to exhaustion and did not clear the handshake**, so the balance has
changed. A patched ROM is the only route that gets inside the latch boundary,
and every result from conn3-conn13 says that is where the answer is.

Beyond the one-byte address edit below, the version that matters here is a
routine that drives `4Ah`-`4Fh` in a chosen sequence and **reads `LINK_STATUS`
back to the display or the wire**. That turns bit 6 from an unobservable into
a measurement, and it is the single thing thirteen runs of external probing
could not do. What makes this
much cheaper than it sounds is `ROM00:3220`, called at `ROM00:0205` and
`ROM00:022C` — immediately after each `LinkProbe` — which **restores both
device tables from ROM on every cold boot**:

```text
3220  21 57 32   LD HL,3257h / LD DE,FE93h / LD BC,0010h / LDIR   ; drive table
322B  21 67 32   LD HL,3267h / LD DE,FE83h / LD BC,0010h / LDIR   ; device table
3236  C9         RET
```

Byte-verified defaults, at those exact file offsets in `micron1.bin`:

```
3257  00 7F 73 72 00 00 00 00 00 00 00 00 00 00 00 00   -> FE93 (drives A..P)
3267  80 AB 63 43 80 2B 63 43 80 67 63 43 80 67 63 43   -> FE83 (device slots)
```

So **the address byte on the wire is a one-byte ROM edit** — no Z80 code, no
monitor, no loader. Change the device ids and the prelude changes with them.

**Recommended patch.** Change all four `43h` → `47h` and all four `63h` →
`6Bh` in the `3267` block (offsets `326A/326E/3272/3276` and
`3269/326D/3271/3275`). Bit 5 is untouched in both, so port selection is
unaffected. Then:

| id | prelude | MSB-first field | LSB-first field | burst cells |
|---|---|---|---|---|
| `43h` (now) | `03h` | `000001011` (9) | `110000010` (9) | 17 / 17 |
| `47h` | `07h` | `000001111` (9) | `11100000` (8) | **17 / 16** |
| `6Bh` | `0Bh` | `00001011` (8) | `11010000` (8) | **16 / 16** |

That one edit settles three things at once:

* **OPEN 9** — whichever port's prelude becomes `07h` is the one using id
  `43h`, i.e. id bit 5 clear, i.e. `LINK_CTRL` bit 1 set. The port ↔ id-bit
  mapping closes by inspection.
* **OPEN 2** — `47h` discriminates bit order by *burst length*, countable
  without decoding anything: 17 cells if MSB-first, 16 if LSB-first.
* **The stuffing rule** — `6Bh` needs no stuffed bit where `03h` needs one, so
  its burst must shrink to 16 cells. A framer that did not stuff would not
  change length at all.

**Then the full version.** With a burner in the loop, patch the cold-boot
entry to jump to a wire exerciser: replicate `LinkBlockTx`'s opening sequence
and walk a value through `LINK_TXD`, one transmission per value with a
recognisable gap. One capture then yields the encoding of all 256 byte values,
which closes OPEN 1, and sweeping `OUT (4Ch),n` closes OPEN 8. A multi-byte
frame that is allowed to close answers OPEN 3 and 4.

**Prerequisites and risks.**

* Are the ROMs socketed? `micron1.bin` = `ROM00` (the link code), 32K, dated
  1996-12-24. Only `ROM00` needs touching.
* No ROM checksum appears in the cold-start self-test, which the user guide
  lists as Clock · Powerdown · First Ram Bank · Full Ram · Contig Ram. **Not
  proven** — confirm by inspection before burning, and keep the originals.
* Develop and validate against `analysis/micronic/z80asm.py` and the emulator
  harness `analysis/boot_hw.py` first; a one-byte table edit is verifiable in
  the emulator by reading `FE83` after boot.

### T8 — which way round are the handheld's detectors? — **do this next**

Its two *emitters* identify themselves: one is periodic at 122 µs, the other
sparse. **Nothing identifies its two detectors.** Our emitters may have been
feeding them backwards the whole time, in which case the handheld has been
receiving our data on its clock input and our clock on its data input, and
every negative result so far is void for that reason alone. It is one bit, and
it has never been tested.

The retry cadence gives a way to settle it without the handheld ever answering.
Transmitting stretches the cadence from a flat 93.75 ms to ~109 ms in about
62% of cycles — the handheld demonstrably notices us. Build with
`ORIENTATION_TEST 1`: content, delay and clock mode are held still and only the
orientation alternates, burst by burst. Capture a few hundred cycles and split
the cadence statistics by orientation.

* **One orientation disturbs the cadence more** → that is the one whose clock
  is landing on the clock detector. Fix it and re-sweep.
* **Both disturb it equally** → the disturbance is not clock-driven, which is
  itself informative: it would suggest the controller reacts to light on either
  detector rather than to a decodable bit stream.

Either way it costs one run and removes a variable that currently invalidates
everything else. A phone camera pointed at the port during a burst will also
show which two devices in the window are the emitters — the other two are the
detectors — which at least fixes the geometry even if it does not label them.

### T7 — the plinth, if one can be borrowed

One capture of a successful session supersedes T1-T6 entirely.

## Adapter experiments, conn3-conn13 — CONFIRMED

Eleven instrumented runs against real hardware, roughly 3,500 stimuli, driven
by `analysis/arduino/m1000_ir_probe`. **The handheld has never transmitted
anything but its own burst.** What follows is mostly negative, and the
negatives are the valuable part: they are what stops the next attempt
repeating the same thirteen runs.

Method: the Arduino answers each of the handheld's ~93.75 ms retry bursts with
one stimulus and advances one parameter, so a connect attempt is ~50 trials.
An MSO-X captures four digital channels — the handheld's clock and data, and
ours — and every trace is classified by **decoding what is actually on the
wire**, never by reconstructing a sweep index from the segment number (see
*Method notes* below for why).

### The one rule that explains every result

> Any light on the **data** line that ceases **before ~9.92 ms** after the
> handheld's burst costs it a fixed **+15.6 ms** on its retry cycle. Light
> still present when that deadline passes costs nothing. Nothing else matters.

The cutoff is a step function with nothing in between (conn13, sorting every
stimulus by when our light goes dark):

| our light goes dark | n | reaction |
|---|---:|---:|
| 3-7 ms after the burst | 170 | **100.0%** |
| 10-16 ms | 252 | **3.6%** |

and 9.92 ms is exactly the `HSBUSY` wait at `ROM00:32F3` — `DE=026Ch` = 620
iterations of a 59 T loop on a 3.6864 MHz Z80.

The +15.6 ms is almost certainly the **receive** path being invoked and timing
out: the interrupt poll at `ROM00:31B6` sees inbound activity, dispatches
`LinkBlockRx`, gets no complete block and gives up. It is not a foothold. It
sits on a different status bit from the one that blocks the session, and
conn13 shows it cannot be steered by content, so no amount of further content
work reaches `HSBUSY`.

### What does not matter — all CONFIRMED negatives

| Variable | Range tested | Result |
|---|---|---|
| **Address byte** | `00h`-`3Fh` exhaustively, plus `7Fh`, `FFh` (conn11) | Median reaction **100% across all 66**. No value distinguished except `FFh` (1 of 40 pooled), which is also the only one putting eight consecutive pulses on the data line — protocol or AGC, undetermined |
| **Closing flag** | present/absent at two lengths (conn13) | **No effect.** 17 vs 25 cells both 100%; 81 vs 89 both baseline |
| **Frame completeness** | bare address → legal 7-byte type-2 body → body + FCS slot (conn13) | **No effect** beyond length |
| **Frame length** | 17 to 108 cells (conn13) | Matters only through when the light stops |
| **DC preamble** | 0, 1, 3 ms before the frame (conn9, conn10) | Small consistent gain, 80% → 95%, consistent with lengthening the lit interval |
| **Free-running clock** | Timer2 clocking continuously vs burst (conn12) | **Identical to three significant figures**, 100.0% both. A running clock with no data is exactly the silent baseline, 3.6% vs 3.6% |
| **Start time** | 0.5-12 ms (conn10) | Flat 1-9 ms, dies at 11 ms — i.e. only through the same cutoff |
| **Bit-rate modulation** | 50% duty square wave (conn8) | **Nothing**, 0% — indistinguishable from silence |
| **Emitter orientation** | clock/data swapped (conn10) | Swapping **kills** the reaction: 95% → 0%. The wiring is correct as built |

### What was established positively

* **The emitter assignment is correct.** conn10: every swapped variant
  collapses to baseline while every unswapped one runs 90-95%. The reaction
  follows the signal assignment, not the physical emitter.
* **Light reaches the handheld and it responds.** conn8 onward, against an
  interleaved silent control in the same run: 100% versus 1-4%.
* **The data line does the work.** Steady light on the data emitter alone
  reproduces the whole effect (37-55%); on the clock emitter alone, exactly
  nothing (0.0%).
* **Phase matters where content does not.** Driving clock and data identically
  and in phase produces 0%, while the same light with the protocol's
  quarter-cell data lead produces 74-100% (conn8 vs conn7, timing matched).
  Whatever consumes the data line is sampling it against the clock.

### Method notes — three mistakes worth not repeating

* **Cross-run comparison is worthless here.** Two conclusions were published
  and retracted from it. The handheld's baseline moves between sessions, so
  every comparison must be against a **control interleaved in the same run**,
  a few hundred ms away. conn8 onward all carry a silent control for this
  reason.
* **Do not reconstruct sweep state from the segment index.** It assumes the
  scope caught every burst; conn5 had 13 gaps of >150 ms, which smears every
  per-parameter breakdown toward the mean. Decode the stimulus from the wire —
  it is self-documenting, and `scope_ir_decode.py` does it.
* **Control for duration before reading anything into content.** conn7's
  apparent content effect was entirely a length confound: the long frames
  scored 0% because they ended late, not because of what they carried.

### Where this leaves the problem

Content-side exploration is **exhausted**. The handheld's behaviour has only
ever taken two values — its normal cycle, or that cycle plus 15.6 ms — and
that single bit is fully explained by when our light stops.

`HSBUSY` is a status bit from a controller ASIC, driven by something the
firmware never inspects and the ROM therefore cannot describe. The two routes
that get at it are **T6**, a patched ROM that drives `4Ah`-`4Fh` directly and
reads `LINK_STATUS` back, turning `HSBUSY` from an unobservable into a
measurement; and a **real adapter or plinth**, one capture of which would
settle in seconds what thirteen runs could not infer.

## Building an adapter — what the M1000 must see

Three layers, and only the middle one is unknown.

**Physical.** Drive two emitters (clock, data) at 8192 bit/s, 122.04 µs cell,
data as a ~78 µs RZ pulse straddling the clock's rising edge. Receive the
other two. The M1000's own timing is the reference for what its receiver will
accept, but that its receiver *requires* the same shape is an assumption —
sweep it (T4.3).

**Frame.** Hunt for `10000001`; then destuff — drop the `1` that follows five
consecutive `0`s — and assemble MSB-first bytes. To transmit, stuff and frame
the same way. The first byte after the flag is the address; the M1000 sends
`link id & 1Fh`, and for every id in the device table bits 6-7 are `01`, so
`(prelude & 1Fh) | 40h` reconstructs it — which is exactly what
`micronic.peer` already assumes.

**Session.** Already solved: `micronic.peer.CommstarPeer` parses requests and
produces replies, is transport-independent by design, and drives real firmware
through complete download and upload sessions in the emulator
([commstar-peer.md](../reference/commstar-peer.md)). Two rules bind — objects
of at most 126 data bytes, and `marker` 1 to end a stream. Wire it to the
Arduino's byte stream and the application layer is done.

What is **not** solved, and is the whole of the remaining work: what the far
end must put on the return pair to clear `HSBUSY`, and when. Everything above
runs on top of that one unknown.

## Tooling

`analysis/arduino/m1000_ir_probe/m1000_ir_probe.ino` — the monitor and swept
responder described in T5. Its framer is unit-checked against the capture:
the `flag+03h` reply it builds is byte-identical to the handheld's own burst.

`analysis/scope_ir_decode.py` — clock/data recovery plus the HDLC unframing,
for the segmented CSV or the `.h5`:

```
analysis/venv/bin/python analysis/scope_ir_decode.py m1000_v24_conn2.csv [--raw]
```

It reports the distinct bursts, the flag position, the destuffed bytes and any
leftover bits, and its Schmitt trigger and glitch filter are tuned to this
capture's edge quality. Retune `GLITCH_US` if a future capture is noisier.
