# Link-controller exerciser

A patched `ROM00` that turns the handheld into a dedicated test rig for the
link controller. It replaces the cold-boot entry, drives the controller
through the same states the firmware drives it through, and streams what the
controller reports back onto the IR line for as long as it is powered.

`LinkBlockTx` dies at `ROM00:32F3` waiting for `LINK_STATUS` bit 6 (`HSBUSY`)
to go **clear**, and reports `0EEh` — the 238 on the error screen. Thirteen
instrumented runs of external probing established the *rule* (light must still
be present at the 9.92 ms deadline) but never the mechanism, because they were
inferring an internal bit from external timing. This observes it directly.

## First: check the chips are the ones this was built against

Every offset below is an offset into `micronic/micron1.bin`. If the fitted
chip is a different revision, the patch lands in the wrong place.

The chips are labelled `DIP1 ACF8` and `DIP2 2E12`, and those are the low 16
bits of the plain unsigned sum of all 32768 bytes — the number a programmer
prints after a read. Both match the repo images exactly
(`doc/re-notes/method.md`), so the label alone is a sufficient check:

```
python3 -c "import sys;d=open(sys.argv[1],'rb').read();print(f'{sum(d)&0xFFFF:04X} {len(d)}')" FILE
```

| image                   | sum16  |
|-------------------------|--------|
| `micron1.bin` (DIP1)    | `ACF8` |
| `micron2.bin` (DIP2)    | `2E12` |
| `micron1_exerciser.bin` | `F2ED` |

Read the fitted chips out before burning and compare. A sum match plus a
`cmp` against `micronic/` is conclusive; the sum alone is a strong check that
needs no reference to this repo. **Label the burned exerciser `F2ED`** so it
is never confused with a stock `ACF8` part.

## Build

```
analysis/venv/bin/python analysis/rom_exerciser/build.py
```

Writes `micron1_exerciser.bin`. The original is never modified. Three edits,
all guarded — the script refuses rather than clobbering anything if the image
is not the one it was written against:

| Edit | |
|---|---|
| `00A2`-`00FC` | keypad scan and the pin walk, in a 94-byte run of `00` filler (3 left) |
| `724C`-`72FC` | link and LCD helpers, in a 183-byte run (6 left) |
| `7CE0`-`7D00` | LCD init, in a 48-byte run (15 left) |
| `7E96`-`7FE4` | the main body, in a 356-byte run (21 left) |
| `014B` | `JP 7E96`, replacing the cold-boot prologue (checked byte-for-byte first) |

All four filler runs must be empty beforehand. `00A2`-`00FF` sits above every
reset vector (`RST 38h` at `0038`, NMI at `0066`) and below the boot vector at
`0100`. Four byte pairs elsewhere in the image look like control transfers
into it; all four are operand bytes or table entries, checked individually —
and any real one would already be jumping the firmware into 94 bytes of `NOP`. `014B` rather than the reset vector
because `0000` → `0103` → `014B`, and the emulator harness starts directly at
`014B`, so the same patch is exercised on hardware and in the emulator.

The two code regions are a single assembly — `ORG` pads forward and only the
two real regions are copied out of the blob — so they call each other by name
and there is one symbol table.

**629 bytes differ from the original.** One chip: `ROM01` is untouched.

## The LCD, first

It initialises the display and **puts every record on the glass as sixteen hex
digits on the top row**. The headline result is readable with no Arduino, no
scope and no decode at all — you can watch `OR` and `AND` change while you
move the Arduino around.

```
COUNT OR AND RXD SIDE CTRL WD KEY
  00  80  80  00   FF   01  00  FF
```

That display is also the liveness indicator, and a better one than the
side-port beacon it replaces: text on the glass cannot be mistaken for
anything else, and it costs no interpretation.

Nothing in the init is invented. The register values are the ones the firmware
writes at boot, captured from a stock emulator run — it is an **HD61830**,
register-indexed through port `23h` with data on `03h`:

| reg | value | |
|---|---|---|
| R0 | `3C` | mode |
| R1 | `75` | character pitch |
| R2 | `13` | 20 characters per line |
| R3 | `3F` | 64 display lines |
| R4 | `07` | cursor |
| R8 R9 | `00` | display start |
| R11 | `00` | address high — always zero for 160 cells, so `lcd_at` only writes R10 |

Then 160 cells are cleared. Skipping all of this is exactly why a patched boot
comes up dark: nothing has configured the controller, set the drive level, or
cleared the power-on garbage out of its RAM.

**Contrast is port `46h`**, and `CONTRAST` in `exerciser.asm` is the one
number to change if the screen is unreadable. The firmware keeps the level in
`FC05` and pushes it out at `ROM00:1FD4`; the range is `00h`-`FFh` and **lower
is lighter**. Stock firmware boots to `70h` — which the owner reports is almost
black on this unit, and turns down by hand every cold start, since `0257`
overwrites `FC05` on every boot regardless of what was saved. This build ships
`40h`.

Not port `2Bh`: **that is the beeper**, and an earlier version of this file had
it wrong — a contrast value written there would have made the unit sound
continuously. Both identifications are in `doc/reference/memory-map.md` and are
corroborated by MAME's driver (`micronic.cpp`: `2Bh` `beep_w`, `46h`
`lcd_contrast_w`, `2Ch` bit 4 backlight).

**The emulator will not render this.** `boot_hw.py` draws the framebuffer at
`FC06`, which the firmware maintains as a shadow; the exerciser writes the
controller ports directly, which is what actually reaches the glass. Check the
`23h`/`03h` port log instead — the validation section shows what to expect.

## Two modes, chosen at power-up

**Hold any key while powering on** and it runs the pin walk instead of the
link exerciser. Release and power-cycle to go back. That is the whole user
interface, and it needs no knowledge of the keymap — which is the point,
because the keymap is one of the things being reverse-engineered.

### The pin walk

For finding which connector pin carries which port bit. It drives port `2Ch`
with a countable pulse code: **bit 0 pulses once, bit 1 twice, bit 4 five
times, bit 5 six times**, each group separated by a long gap, repeating for
ever. Probe a pin, count the pulses, and you have its bit. No timing
reference, no second scope channel — an LED and an eye would do.

Two of the four groups identify themselves with no probe at all: `2Ch` bit 4
is the **LCD backlight**, so its five-pulse group flashes the screen, and bit 5
is the IR port select. That leaves bits 0 and 1 — the pair the barcode front
end drives — as the real side-connector candidates, with the other two groups
as a free calibration of your counting.

Bits it is not driving leave a silent slot, so the count still equals the bit
number and nothing shifts. `PORTMAP_BITS` in `exerciser.asm` selects the set;
it defaults to `33h` — bits 0, 1, 4 and 5, the ones the firmware itself
drives. `FFh` also walks 2, 3, 6 and 7, which no ROM instruction ever sets:
unknown territory, and the unit powering off mid-walk would be the first
thing you learn about them.

Note bit 5 is the IR port select, so its six-pulse group may not appear on
the side connector at all. That makes it a useful contrast case rather than a
nuisance.

Inputs do not move during the walk — find those with the `KEY` and `SIDE`
fields in the normal mode instead, by shorting each pin in turn and watching
which one changes.

### The keypad, and why it matters more than the side port

`kbd_scan` drives one column at a time through the firmware's own strobe
helper (`ROM00:1A44`: writes port `02h`, settles, reads port `00h` masked to
six rows) and returns `col*6 + row` — the same index `tbl_kbd_map` is built
on. It is reported in every record, so pressing keys and watching `KEY` maps
the keypad empirically.

This supersedes port `2Dh` as the command channel for a steerable follow-up
burn. It needs no wiring, no pinout, and no case modification, and it is
already proven by this run's own capture.

## The four phases

One phase per frame, cycling forever. The phase is the top two bits of the
record counter, so it costs nothing to encode and cannot drift out of step
with the frame boundaries.

| | | `LINK_CTRL` | |
|---|---|---|---|
| 0 | baseline | `03` | the resting value of every status bit — the control the others are read against |
| 1 | TX armed | `13` | `ROM00:32CC`-`32EE` byte for byte, then held for the whole frame |
| 2 | RX armed | `12` | `ROM00:3378`-`33A6` byte for byte, dummy `LINK_RXD` read included |
| 3 | CTRL sweep | varies | one value per frame, advancing each cycle, all 128 with bit 1 held |

**Phase 1 is the experiment.** `HSBUSY` is asserted *by* the arm and the
firmware waits for it to fall — merely watching an idle controller says
nothing, which is why the arm has to be replayed. A frame is ~470 ms where the
firmware allows 9.92 ms, so this is far more patient than the firmware: if the
handshake completes late, that alone explains the failure and points at a
fixable timeout rather than a missing protocol.

Phase 2 asks whether the receive path ever delivers anything. Bit 0, not bit
4, is the bit that says a byte arrived — it gates the `INI` loop at
`ROM00:33CF`.

Phase 3 covers what the firmware never writes. Bits 0, 1, 4 and 5 are the only
ones it ever touches, so bits 2, 3, 6 and 7 are untried. Bit 1 is forced to the
selected port: sweeping it would switch ports underneath the measurement,
which is a confound rather than an experiment.

A `LINK_CTRL` value that stops the controller accepting bytes would stall the
reporting channel, so `waitready` has a watchdog — after ~9 ms with no `TXRDY`
it puts the baseline back and carries on. No phase can wedge the run, and a
counter discontinuity in the capture marks where it happened.

## What comes off the wire

One preamble frame, then record frames, each preceded by a ~4 ms idle gap so
the Arduino's burst delimiter fires:

```
preamble   A5 5A VER ID PSTAT STATUS      once, at power-up
record     COUNT OR AND RXD SIDE CTRL     64 per frame, ~7.3 ms apart
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
| `KEY` | keypad index (`col*6 + row`) of the first key held, or `FFh` |

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

| `bit 6 HSBUSY` | |
|---|---|
| `always 1` | the handshake never completes — exactly the state the firmware dies in, now directly observed |
| `changes` | it completes. If later than 9.92 ms, the firmware's timeout *is* the bug |
| `always 0` | our arm is not what asserts it, and the model needs revisiting |

## Validate before burning

```
MICRONIC_ROM0=$PWD/analysis/rom_exerciser/micron1_exerciser.bin \
  analysis/venv/bin/python analysis/boot_hw.py --no-lcd --max-slices 30000
```

The port log lands in `/tmp/opencode/micronic_boot_io.txt`. The expected
opening matches what `LinkBlockTx` does, access for access:

```
  0  PC=7E9E  2A = 20     the cold boot's own 2Ah setup, reproduced
  1  PC=345F  2A = 20     LinkPortSelect
  2  PC=347D  4A = 02     LINK_CTRL bit 1 set  -- port select, id bit 5 clear
  3  PC=3489  2C = 20     port 2Ch bit 5 set
  4  PC=3491  4F = 1F     LinkProbe WRITES LINK_PROBE
  5  PC=349D  4A = 02     probe: ctrl bit 5 clear
  6  PC=34A7  4A = 03     probe: ctrl bit 0 set
  7  PC=34B1  4A = 02     probe: ctrl bit 0 clear
  8  PC=34B7  2C = 00     probe done, port 2Ch restored
  9  PC=34DC  4A = 02     LinkPresent
 10  PC=34E6  4A = 02
 11           4A = 02     our frame opening: bit 0 low
 12           4A = 03                        bit 0 high
 13           4A = 03                        bit 4 low
 14  PC=34F7  4C = 81     LINK_CMD -- the opening flag
 15+          4D = ..     the preamble, then records
```

`--max-slices 30000` because the beacon burns ~1.9 s of emulated time before
the link is touched at all.

Piping the `4Ch`/`4Dh` writes into the decoder gives the emulator's own
version of the result. Its synthetic controller reports a constant `80h` and
ignores `LINK_CTRL`, so every phase reads the same — only the code path is
validated here, which is the intent. The values are what the hardware run is
for.

## On the hardware

Decode the wire with the Arduino in `LISTEN_ONLY` mode, then drive its
stimulus modes and watch whether anything moves — phase 1 bit 6 above all.

Silence now reads off the screen:

| LCD | wire | meaning |
|---|---|---|
| hex counting up | streaming | healthy |
| hex frozen | silent | the transmitter stalled — `WD` in the frozen record says how many watchdog trips it took |
| `DEAD` | silent | never got a frame open; `LinkPresent` failed 16 times running |
| blank | silent | the patch ran far enough to clear the display, then stopped before the first record |
| garbage or dark | silent | the patch never ran. Not a result — bad burn, bent pin, wrong socket |

`putbyte` blocks, so a stalled transmitter freezes the record loop and the
display with it. A frozen count beside a running one is unmistakable, which is
why the watchdog no longer needs a side-port blink of its own.

45 bytes of filler remain across the four blocks.

## Restoring

Put the original chip back. What it touches in RAM: nine variables and a few
bytes of stack in the upper TPA (`C7E0`-`C800`, which the RAM map documents as
free), and the firmware's own I/O shadows at `F78B`, `F78D`, `F794`, `F796`
and `F799`. Those shadows are volatile working copies that the firmware
re-seeds on its own cold boot, so nothing user-visible survives. No user data
area is written.

The test plan for the run itself is `doc/re-notes/exerciser-test-plan.md`.
