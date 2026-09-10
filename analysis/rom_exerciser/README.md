# Link-controller exerciser

> **DO NOT REBURN `1225`, `2692` OR `1E3E`.** The verified `1225` image produced a
> constant buzz and uniformly black LCD. The verified `2692` image reduced
> that to the expected brief power-up bleep, but its display remained black;
> its transposed keypad coordinates also made YES/NO ineffective. The verified
> `1E3E` image produced both diagnostic beeps and a uniformly clear LCD, proving
> that stock `LcdInit` returned. Contrast polarity was not isolated from the
> concurrent delay and ordering changes. The owner reports that sum16 `27E8`
> displays readable `CONTRASTC0`, but keys still have no observable effect.
> Do not reburn unchanged `27E8` to investigate the keypad.

## Current diagnostic build: `2D31` (2026-09-10)

**Hardware validation:** the owner tested `2D4D`: heartbeat advances; idle
key is `FFh` with all sense readings zero; NO gives key `11h`, last sense
byte `04h` and decreasing contrast; YES gives key `17h`, last sense byte
`08h` and increasing contrast. Both return to idle on release. Decreasing
the contrast byte darkens the screen in the tested range; `A4h` is the
owner's preferred default. The earlier `27E8` failure's cause is not explained.

`2D31` changes only the initial contrast byte from `C0h` to `A4h`; working
LCD startup, diagnostics and key handling are unchanged. **No reburn is needed
to continue testing `2D4D`: adjust it to `A4h` with NO.** No Arduino is needed for setup.
The first row now contains 19 characters, grouped here only for explanation:

```text
C A4 FF 01 00 00 00 00 00 00
  CC KK HH S1 S2 S4 S8 SA SB
```

| Field | Meaning |
|---|---|
| `CC` | Contrast shadow; starts at `A4h` |
| `KK` | Decoded matrix index: NO=`11h`, YES=`17h`, ENTER=`16h`, none=`FFh` |
| `HH` | Counter increments each screen; initial battery-RAM value is arbitrary |
| Six `S` bytes | Port `00h` sense values masked with `3Fh`, for port `02h` drive masks `01h,02h,04h,08h,10h,20h` respectively |

The six sense bytes are a separate, complete scan immediately after decoding;
a key transition can therefore make the two scans disagree for one screen.
Held NO should show `04` in the last sense byte; held YES should show `08`
there. NO decreases the contrast byte, YES increases it, and ENTER starts IR.
Both contrast operations still use the stock shadow-preserving adjusters.
If keys remain ineffective, record the row at rest and while holding each key,
and whether `HH` keeps changing. Do not interpret a static counter as a
key-mapping fault. Multiple simultaneous keys are not validated by this scanner.

The scanner's drive index is now calculated as `6-B`, avoiding a redundant
bit-index call. All 36 single-key coordinates are CPU-tested. Small equivalent
code compactions fit the diagnostics without adding patch regions: constant
wire-ID masking and a shared TX/RX final control-mask write (RX gains a JR).
The established LCD initialization bytes and its settling delays are preserved.

A patched `ROM00` that turns the handheld into a dedicated test rig for the
link controller. It replaces the cold-boot entry, drives the controller
through the same states the firmware drives it through, and streams what the
controller reports back onto the IR line for as long as it is powered.

`LinkBlockTx` can report `0EEh` — the 238 on the error screen — either after
its `LINK_STATUS` bit-6-clear wait at `ROM00:32F3` or after a per-byte
`LINK_STATUS` bit-7-set wait beginning at `ROM00:3318`. Thirteen instrumented
runs of external probing found repeatable timing reactions but could not
identify the internal path, because they inferred latch state from optical
timing. This ROM observes the complete `LINK_STATUS` byte directly.

## First: check the chips are the ones this was built against

Every offset below is an offset into `micronic/micron1.bin`. If the fitted
chip is a different revision, the patch lands in the wrong place.

The chips are labelled `DIP1 ACF8` and `DIP2 2E12`, and those are the low 16
bits of the plain unsigned sum of all 32768 bytes — the number a programmer
prints after a read. Both match the repo images exactly
(`doc/re-notes/method.md`), but the label is only an identifier: read-back
plus `cmp` is the required check before reuse.

```
python3 -c "import sys;d=open(sys.argv[1],'rb').read();print(f'{sum(d)&0xFFFF:04X} {len(d)}')" FILE
```

| image                   | sum16  |
|-------------------------|--------|
| `micron1.bin` (DIP1)    | `ACF8` |
| `micron2.bin` (DIP2)    | `2E12` |
| `micron1_exerciser.bin` | `2D31` |

The replacement exerciser SHA-256 is
`7f2efaa6a4893c889dc6f0059a8411952a2a622419d390c1d892fb2648707bf6`.
The retired `1E3E` image SHA-256 was
`5b6ce0b67ebfadad3e5d746dbd1dd4370cd337e99c0d77724e213d941160386b`.
The retired `2692` image SHA-256 was
`cf2474dbd4be30a04998382f8e9946522cb2f87f91a7b516f40ff3119ae04c65`.
The retired `1225` image SHA-256 was
`9162097f6ca6bf56674d6cdcd2d3bcb25050902efc813d4eba3dcee3b019ffeb`.
The dedicated regression test reconstructs the image and locks its
fingerprint and 717-byte diff count.

Read the fitted chips out before burning and compare. A sum match plus a
`cmp` against `micronic/` is conclusive; the sum alone is a strong check that
needs no reference to this repo. The `1225`, `2692` and `1E3E` parts should be
retained only for read-back diagnosis and must not be installed again. Label
the replacement `2D31` and verify its full SHA-256 before installation.

## Build

```
analysis/venv/bin/python analysis/rom_exerciser/build.py
```

Writes `micron1_exerciser.bin`. The original is never modified. Six filler
regions and the boot entry are guarded — the script refuses rather than
clobbering anything if the image is not the one it was written against:

| Edit | |
|---|---|
| `0047`-`0061` | the interrupt handler, in a 31-byte run of `00` filler (4 left) |
| `0069`-`007E` | `DEAD` display and the NMI guard, in a 23-byte run (1 left) |
| `00A2`-`00FF` | keypad scan, pre-init delay and diagnostic screen, in a 94-byte run (0 left) |
| `724C`-`7302` | link, LCD and keypad-arm helpers, in a 183-byte run (0 left) |
| `7CE0`-`7D0F` | stock-reset/LCD and contrast helpers, in a 48-byte run (0 left) |
| `7E96`-`7FF7` | the main body and raw sense display, in a 356-byte run (2 left) |
| `014B` | `JP 7E96`, replacing the cold-boot prologue (checked byte-for-byte first) |

All six filler runs must be empty beforehand. Two other runs of zeros are
deliberately **not** used, because they are data rather than filler:
`325B`-`3266` is the drive table's own `E:`-`P:` entries, and `7D1E`-`7D2F`
is the zero tail of the table at `7D10`, with another table starting at
`7D30`. `00A2`-`00FF` sits above every
reset vector (`RST 38h` at `0038`, NMI at `0066`) and below the boot vector at
`0100`. Four byte pairs elsewhere in the image look like control transfers
into it; all four are operand bytes or table entries, checked individually —
and any real one would already be jumping the firmware into 94 bytes of `NOP`. `014B` rather than the reset vector
because `0000` → `0103` → `014B`, and the emulator harness starts directly at
`014B`, so the same patch is exercised on hardware and in the emulator.

The six code regions are a single assembly — `ORG` pads forward and only the
six real regions are copied out of the blob — so they call each other by name
and there is one symbol table.

**717 bytes differ from the original.** One chip: `ROM01` is untouched.

## The LCD, first

It initialises the display and **puts the first ten fields of every record on
the glass as twenty hex digits on the top row**. The headline result is
readable with no Arduino, no scope and no decode at all — you can watch `OR`
and `AND` change while you move the Arduino around. The final `ISRC` field is
wire-only because eleven bytes would wrap the display.

```
COUNT OR AND RXD SIDE CTRL WD KEY IRQN ISTAT
  00  80  80  00   FF   01  00  FF   00    00
```

That display is also the liveness indicator, and a better one than the
side-port beacon it replaces: text on the glass cannot be mistaken for
anything else, and it costs no interpretation.

The exerciser sets the chosen contrast in `g_bLcdContrast` (`ram:FC05`) and
writes it directly to port `46h` before any LCD command. It then waits about
462 ms at the owner-stated 3.6864 MHz and calls stock `LcdInit` at `ROM00:1EEC`.
**CONFIRMED:** that routine supplies a further approximately 109 ms delay,
initializes the LCD state and framebuffer, calls the stock HD61830 register
sequence at `ROM00:1F33`, clears all 160 VRAM cells through the normal output
path, writes `g_bLcdContrast` to port `46h` again, and disables the cursor.
The register sequence is:

| reg | value | |
|---|---|---|
| R0 | `3C` | mode |
| R1 | `75` | character pitch |
| R2 | `13` | 20 characters per line |
| R3 | `3F` | 64 display lines |
| R4 | `07` | cursor |
| R8 R9 | `00` | display start |
| R10 R11 | `00` | cursor address, low byte followed by high byte |

The normal cold-start prerequisites are preserved too. Before the contrast
write, the helper writes `CTL_LATCH_2A=20h`, executes the exact stock
`ROM00:0156`-`015D` delay loop (about 33.5 ms), reads `IRQ_STATUS`, writes
`IRQ_MASK=FFh`, and writes `SOUND=00h`. Those last three I/O operations exactly
match `ROM00:01B1`-`01B9`; omitting them is the confirmed difference that the
failed `1225` hardware run exposed. Stock cold boot also performs a full RAM
test before `LcdInit`; that test makes no I/O writes but contributes substantial
elapsed startup time. The added 462 ms delay conservatively restores settling
time without modifying RAM.

There was one **SHOWSTOPPER** in the previous v13 image: its per-record home
helper wrote HD61830 cursor-address low register R10 without rewriting
cursor-address high register R11. The [Hitachi datasheet](https://www.displayfuture.com/Display/datasheet/controller/hd61830b.pdf)
requires R11 to be set again after R10 because an R10 bit-7 transition from
set to clear can carry into R11. After clearing 160 cells, that could redirect
the live record writes to page 1 and leave the visible screen blank. The new
`lcd_home` emits `R10=00h` followed by `R11=00h`, exactly matching
`ROM00:1F91`-`1F9E`. A regression test locks both the stock initializer call
and this low-then-high sequence.

Lee Davison's 1998 Micronic monitor source is an independent board-level
cross-check. It uses the same LCD ports and overlapping controller values, and
most importantly writes port `46h` before issuing any HD61830 command. The
candidate now follows that ordering. Davison's full eight-page display-RAM
clear is deliberately not copied: stale off-screen RAM cannot explain a
uniformly driven-black panel. The historical source is available from the
[archived Micronic download page](https://www.geocities.ws/micronic99.geo/download.htm).

**Correction: the hardware runs did not isolate contrast polarity.** The
`1E3E` run reached its post-`LcdInit` beep and left the LCD uniformly clear,
but contrast value, write ordering and settling delay changed together.
The earlier black screen does not establish that its final contrast write
was reached. The later controlled `2D4D` test now establishes that decreasing
values darken the screen in the tested range; endpoint behaviour is not
established. The replacement starts at `A4h` and remains in the diagnostic
keypad loop before touching the IR link.
Physical **NO** is intended to decrement `g_bLcdContrast` by two toward `00h`;
physical **YES** is intended to increment it by two toward `FFh`.
The stock adjusters update both the shadow and port `46h`, and the
displayed hexadecimal value is redrawn after every poll. Press **ENTER** when
the text is comfortably readable; only then does the IR test begin.

**Historical `27E8` owner result, 2026-09-10:** `CONTRASTC0` is visible, but keys have no
observable effect. This proves initial text output, not repeated loop
execution or working hardware scanning. Synthetic keypad tests establish
software behaviour for supplied sense bytes, not actual sense bytes on the
unit. Next diagnostic: an independent visible heartbeat, six raw port-`00h`
sense readings labelled by port-`02h` drive mask, and the decoded key index,
before any IR access. Preserve the now-working LCD startup sequence.

Not port `2Bh`: **that is the beeper**, and an earlier version of this file had
it wrong — a contrast value written there would have made the unit sound
continuously. Both identifications are in `doc/reference/memory-map.md`, from
the ROM. MAME's driver agrees, but it is another reverse-engineering effort
working from the same bytes, so treat it as corroboration rather than
measurement: the on-unit YES/NO sweep is what will actually confirm `46h`.

**The emulator will not render this.** `boot_hw.py` draws the framebuffer at
`FC06`, which the firmware maintains as a shadow; the exerciser writes the
controller ports directly, which is what actually reaches the glass. Check the
`23h`/`03h` port log instead — the validation section shows what to expect.

## Port alternation

The earlier optional port-`2Ch` pin-walk mode is not in this candidate. Its
vetted filler space now holds the corrected keypad scanner and contrast setup
screen; preserving the link measurement and making the display usable take
priority over mapping the unrelated side connector.

In link mode the first cycle uses `43h`, whose **wire-ID bit 5 is clear**. It
drives **`LINK_CTRL` bit 1 set** and **port `2Ch` bit 5 set**, and was observed
on the top V24 ADAPTOR window. The run then alternates with `63h`, whose
wire-ID bit 5 is set and which clears both output bits. `LINK_CTRL` bit 1 in
each record identifies the state: set is `43h`, clear is `63h`. The
alternation remains useful because the complementary state has not yet been
observed directly at the back PLINTH window.

### The keypad, and why it matters more than the side port

`kbd_scan` drives one column at a time through the firmware's own strobe
helper (`ROM00:1A44`: writes port `02h`, settles, reads port `00h` masked to
six sense lines). Stock `ROM00:1921`-`1933` and Davison's independent
`KEY_scan` both compute `6*sense-bit-index + drive-bit-index`. The retired
`2692` image transposed those terms, which maps physical NO from 17 to 32 and
YES from 23 to 33. The current scanner uses the stock bit-index helper and a
CPU-level test drives the real NO/YES matrix coordinates through it.

This supersedes port `2Dh` as the command channel for a steerable follow-up
burn. It needs no wiring, no pinout, and no case modification, and it is
covered by CPU-level tests using the physical NO, YES and ENTER coordinates.

## The link interrupt

The firmware's receive path is **interrupt-driven**, not polled: IRQ source 2
is the link controller, and its handler at `ROM00:31B6` tests `LINK_STATUS`
bit 4 and enters `LinkBlockRx` if set
(`doc/reference/memory-map.md#link-interrupt`). An exerciser that only polled
would miss a controller that signals but never holds a bit long enough for a
poll to catch.

So this one takes the interrupt too. `RST 38h` at `ROM00:0038` jumps through
`F5F3`, which is where the firmware installs its own handler at `ROM00:2893`;
we install ours the same way, set `IM 1`, and unmask bits 2 and 0 (`04h` =
`FAh`, active low). The handler counts, ORs `LINK_STATUS` at interrupt time
into its own accumulator, and acknowledges by reading `05h`.

**The keypad (source 0) is armed on purpose, and it is the control rather than
a measurement.** With the link alone, a flat `IRQN` could not be told apart
from a broken interrupt setup — and the answer to the question this whole
addition exists to ask would be worthless. The keypad is a genuine interrupt
source, so pressing keys proves the path end to end. `ISRC` separates them
directly from the active-low source bits read from port `05h`: bit 0 is the
keypad and bit 2 is the link. `KEY` cannot safely attribute an interrupt,
because it is sampled only once near the start of each record.

The keypad control also mirrors the firmware's sleep configuration after
every scan: `F782` and port `02h` receive `48h`, paired with the same `FAh`
IRQ mask at `ROM00:1766`-`177F`. This arms column 3; N, ENTER and YES are
known keys in that column, so use one of those to prove source 0.

`FAh` is not a guess. The firmware writes exactly that to `04h` when it sleeps
(`ROM00:1779`), and all three of its sleep masks enable bit 0, because the
keypad is what wakes the machine — see
[sleep and wake](../../doc/reference/memory-map.md#sleep-wake).

Worth keeping straight: `KEY` does **not** come from the interrupt.
`kbd_scan` polls the matrix directly through `ROM00:1A44`, which is exactly
why `KEY` alone could never have proved the interrupt path live, and why the
keypad had to be armed as a source rather than merely observed as a field.

It masks everything on the way in and the record loop re-arms once per record,
so a source that asserts continuously costs one interrupt per record rather
than livelocking the machine. `IRQN` counts those entries, `ISRC` identifies
their sources, and `ISTAT` is the link status the controller held at interrupt
time, which is not the same as any status a poll happens to catch.

NMI at `ROM00:0066` jumps through `F5F6`, equally uninitialised here, so a
`RETN` is planted there before LCD initialisation. A stray NMI returns safely
and restores the prior interrupt-enable state.

The cost is jitter: the ISR runs inside the sampling loop, so a record whose
interrupt fired has one ~30 µs gap in its coverage. Bounded to one per record,
against a 122 µs wire cell.

## The four phases

One phase per frame, cycling forever. The phase is the top two bits of the
record counter, so it costs nothing to encode and cannot drift out of step
with the frame boundaries.

| Phase | State | `LINK_CTRL`, `63h`: wire-ID b5=1, output b1=0 | `LINK_CTRL`, `43h`: wire-ID b5=0, output b1=1 | Purpose |
|---|---|---|---|---|
| 0 | baseline | `01` | `03` | resting control value |
| 1 | TX armed | `11` | `13` | `ROM00:32CC`-`32EE` byte for byte, then held for the whole frame |
| 2 | RX armed | `10` | `12` | `ROM00:3378`-`33A6` byte for byte, dummy `LINK_RXD` read included |
| 3 | CTRL sweep | varies, bit 1 forced clear | varies, bit 1 forced set | one value per frame, advancing each cycle, all 128 per wire-ID state |

**Phase 1 is the experiment.** The firmware waits for `LINK_STATUS` bit 6 to
clear after the arm, so merely watching an idle controller says nothing; the
arm has to be replayed. A frame is well over 0.5 s where the firmware allows
9.92 ms. The record therefore shows whether `LINK_STATUS` bit 6 is ever set in
this state and, if it is, whether it later clears. It does not assume which
optical event controls that status bit.

Phase 2 asks whether the receive path ever delivers anything. Bit 0, not bit
4, is the bit that says a byte arrived — it gates the `INI` loop at
`ROM00:33CF`.

Phase 3 covers every combination, including the two bits the firmware never
writes: bits 2 and 3. Bit 1 is forced to the selected port because sweeping it
would switch ports underneath the measurement. The raw sweep counter is
rotated left first: port alternation fixes its original bit 0, and the rotate
moves that correlated bit into the forced-away bit 1. Thus each port really
does receive all 128 effective states.

A `LINK_CTRL` value that stops the controller accepting bytes would stall the
reporting channel, so `waitready` has a watchdog — after ~9 ms with no `TXRDY`
it puts the baseline back and carries on. No phase can wedge the run, and a
counter discontinuity in the capture marks where it happened.

## What comes off the wire

One preamble frame, then record frames, each preceded by a ~4 ms idle gap so
the Arduino's burst delimiter fires:

```
preamble   A5 5A VER PSTAT STATUS         once, at power-up
record     COUNT OR AND RXD SIDE CTRL WD KEY IRQN ISTAT ISRC
                                             64 per frame
```

| field | |
|---|---|
| `COUNT` | rolling record number, +1 each record — a lost record is visible, and it is the time base. Top two bits are the phase |
| `OR` | every `LINK_STATUS` sample taken during this record's window, OR'd together |
| `AND` | the same samples, AND'd together |
| `RXD` | `LINK_RXD`, read once per record, after the status samples |
| `SIDE` | port `2Dh`, the 5-pin side port, read once per record |
| `CTRL` | the `LINK_CTRL` value this phase asked for, so a capture is self-describing and the sweep needs no schedule shared with the decoder |
| `WD` | rolling count of `waitready` watchdog trips — it rises only when a `LINK_CTRL` value stopped the controller accepting bytes |
| `KEY` | keypad index (`6*sense-bit-index + drive-bit-index`) of the first key held, or `FFh` |
| `IRQN` | rolling count of interrupts taken — link **and keypad**, see below |
| `ISTAT` | `LINK_STATUS` OR'd across every interrupt, sticky for the run |
| `ISRC` | active-high port-`05h` source bits OR'd across every interrupt; bit 0 is keypad and bit 2 is link. Wire-only; the first ten fields fill the LCD row |

`OR` and `AND` are what make the modest record rate sufficient. Waiting for
`TXRDY` is a tight polling loop — one `LINK_STATUS` sample every ~35 µs — and
every sample folds into both accumulators. A bit that pulses high for a single
122 µs wire cell still shows up in `OR`; one that drops for a single cell still
shows in `AND`; a genuinely constant bit reads the same in both. **No event on
the wire's own timescale can be aliased away.** Only the ordering of events
inside one record is lost.

**Every port is touched in the direction the firmware touches it, and only
that direction.** `4Ah`, `4Ch`, `4Dh`, `2Ah` and `2Ch` are write-only across
both ROMs; `4Bh`, `4Eh` and `2Dh` are read-only. `4Fh` is write-only, so it is
never read here — an earlier version sampled it into the preamble, which was a
read of a port nothing in the firmware reads, on an ASIC whose read strobes are
not characterised. `PSTAT` carries `LinkProbe`'s returned `LINK_STATUS`
instead (`ROM00:34BA`), which is a real measurement: the controller straight
out of reset, and the reference every later sample is read against.

Every frame begins on a record boundary whose `COUNT` is a multiple of 64, so
byte alignment is structural, not guessed.

## Decoding

```
analysis/venv/bin/python analysis/rom_exerciser/decode_records.py capture.csv
analysis/venv/bin/python analysis/rom_exerciser/decode_records.py --hex log.txt
```

CSV is the MSO's four-channel format, the same one `scope_ir_decode.py` reads;
`--hex` takes one frame of whitespace-separated hex per line, for an Arduino
serial log. Output is a per-bit verdict per phase. What to read, in phase 1:

| `LINK_STATUS` bit 6 (`HSBUSY`) | |
|---|---|
| `always 1` | this arm cannot pass the firmware's `LINK_STATUS` bit-6-clear wait |
| `changes` | a clear transition occurs; compare its time with the 9.92 ms firmware allowance |
| `always 0` | the arm does not make `LINK_STATUS` bit 6 set |

## Validate before burning

```
timeout 60 analysis/venv/bin/python -m pytest -q analysis/test_rom_exerciser.py
```

The CPU tests execute the assembled image with synthetic port responses.
The opening is:

```
  0  PC=7CE7  2A = 20     stock CTL_LATCH_2A setup, before the LCD
  1  PC=7CF6  04 = FF     stock cold-start IRQ_MASK: all sources masked
  2  PC=7CFA  2B = 00     stock cold-start SOUND: beeper silent
  3  preinit  46 = A4     contrast before any HD61830 command
4-21 PC=1Fxx  23/03       exact stock HD61830 register sequence
 ... PC=1Fxx  23/03       stock 160-cell clear and cursor setup
990  PC=1FDB  46 = A4     stock LcdInit repeats the contrast write
 ... setup   23/03       home; contrast, key, heartbeat and six sense bytes
 ... PC=1A49 02 = ..     keypad decode scan plus complete diagnostic scan
```

Tests cover every single-key matrix coordinate, NO/YES adjustment and no-key
operation followed by ENTER. They check the complete diagnostic text, stack
balance and absence of IR output before setup returns. These are software
tests, not evidence that the physical sense inputs match the supplied model.
The link wire format remains version `0Dh`; constant port masking and the
shared RX tail mean the body is no longer byte-identical to `1E3E`.

## On the hardware

Decode the wire with the Arduino in `LISTEN_ONLY` mode, then drive its
stimulus modes and watch whether anything moves — phase 1 `LINK_STATUS` bit 6
above all.

First set the display: wait for the diagnostic row described above, use NO
to decrease or YES to increase the contrast byte, then press ENTER. No IR setup or transmission occurs until
ENTER is detected.

Silence now reads off the screen:

| LCD | wire | meaning |
|---|---|---|
| hex counting up | streaming | healthy |
| hex frozen | silent | the transmitter stalled — `WD` in the frozen record says how many watchdog trips it took |
| `DEAD` | silent | never got a frame open; `LinkPresent` failed 16 times running |
| `CONTRASTxx` | silent | contrast setup; use NO/YES, then ENTER |
| contrast text frozen but keys inert | silent | keypad scanner or matrix mapping failed; IR has not started |
| contrast text disappears after ENTER | check wire | ENTER was accepted and link startup began |

`putbyte` blocks, so a stalled transmitter freezes the record loop and the
display with it. A frozen count beside a running one is unmistakable, which is
why the watchdog no longer needs a side-port blink of its own.

7 bytes of filler remain across the six blocks.

## Restoring

Put the original chip back. What it touches in RAM: fourteen variables and a few
bytes of stack in the upper TPA (`C7E0`-`C900`, which the RAM map documents as
free), and the firmware's own I/O shadows at `F78B`, `F78D`, `F794`, `F796`
and `F799`. Those shadows are volatile working copies that the firmware
re-seeds on its own cold boot, so nothing user-visible survives. No user data
area is written.

The test plan for the run itself is `doc/re-notes/exerciser-test-plan.md`.
