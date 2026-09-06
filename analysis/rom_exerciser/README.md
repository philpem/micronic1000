# Link-controller exerciser

A patched `ROM00` that turns the handheld into a dedicated test rig for the
link controller. It replaces the cold-boot entry, opens a frame the way
`LinkBlockTx` does, and then **streams the controller's own registers onto the
IR line** for as long as it is powered.

That stream is the point. `LINK_STATUS` bit 6 (`HSBUSY`) is what stops every
session — the firmware gives up waiting for it at `ROM00:32F3` and reports
`0EEh`, the 238 on the error screen — and it cannot be observed from outside
the case. Thirteen instrumented runs of external probing
(`doc/re-notes/ir-wire-protocol.md`) could not reach it. This makes it a time
series that the existing Arduino receiver decodes with no changes.

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
| `micron1_exerciser.bin` | `1382` |

Read the fitted chips out before burning and compare. A sum match plus a
`cmp` against `micronic/` is conclusive; the sum alone is a strong check that
needs no reference to this repo. **Label the burned exerciser `1382`** so it
is never confused with a stock `ACF8` part.

## Build

```
analysis/venv/bin/python analysis/rom_exerciser/build.py
```

Writes `micron1_exerciser.bin`. The original `micronic/micron1.bin` is never
modified. Two edits, both guarded — the script refuses rather than clobbering
anything if the image is not the one it was written against:

| Edit | |
|---|---|
| `7E96`-`7F64` | the exerciser, in a 356-byte run of `00` filler that must be empty beforehand |
| `014B` | `JP 7E96`, replacing the cold-boot prologue (checked byte-for-byte first) |

`014B` rather than the reset vector because `0000` → `0103` → `014B`, and the
emulator harness starts directly at `014B`, so the same patch is exercised on
hardware and in the emulator.

**206 bytes differ from the original.** One chip: `ROM01` is untouched.

## Validate before burning

```
MICRONIC_ROM0=$PWD/analysis/rom_exerciser/micron1_exerciser.bin \
  analysis/venv/bin/python analysis/boot_hw.py --no-lcd --max-slices 400
```

The port log lands in `/tmp/opencode/micronic_boot_io.txt`. The expected
opening, byte for byte, all of it matching what `LinkBlockTx` does:

```
  0  PC=7E9E  2A = 20     the cold boot's own 2Ah setup, reproduced
  1  PC=345F  2A = 20     LinkPortSelect
  2  PC=347D  4A = 02     LINK_CTRL bit 1 set  -- port select, id bit 5 clear
  3  PC=3489  2C = 20     port 2Ch bit 5 set
  4  PC=3493  4F = 1F     LinkProbe reads LINK_PROBE
  5  PC=349D  4A = 02     probe: ctrl bit 5 clear
  6  PC=34A7  4A = 03     probe: ctrl bit 0 set
  7  PC=34B1  4A = 02     probe: ctrl bit 0 clear
  8  PC=34B7  2C = 00     probe done, port 2Ch restored
  9  PC=34DC  4A = 02     LinkPresent
 10  PC=34E6  4A = 02
 11  PC=7EE5  4A = 02     our frame opening: bit 0 low
 12  PC=7EED  4A = 03                        bit 0 high
 13  PC=7EE5  4A = 03                        bit 4 low
 14  PC=34F7  4C = 81     LINK_CMD -- the opening flag
 15+          4D = ..     the preamble, then records
```

Piping the `4Ch`/`4Dh` writes into the decoder gives the emulator's own
version of the hardware result — the negative one, since its synthetic
controller reports a constant `80h`:

```
preamble  version 3  LINK_ID 43  LINK_PROBE FF  LINK_STATUS 80
counter discontinuities: 0
  bit 7 TXRDY   always 1
  bit 6 HSBUSY  always 0
```

The emulator's synthetic controller always reports `80h` (TXRDY set, nothing
else), so the *values* mean nothing here — only the path does. The values are
what the hardware run is for.

## What comes off the wire

One preamble frame, then record frames forever, each preceded by a ~4 ms idle
gap so the Arduino's burst delimiter fires:

```
preamble   A5 5A VER ID PROBE STATUS      once, at power-up
record     COUNT OR AND RXD               64 per frame, ~4.9 ms apart
```

| field | |
|---|---|
| `COUNT` | rolling record number, +1 each record — a lost record is visible, and it is the time base |
| `OR` | every `LINK_STATUS` sample taken during this record's window, OR'd together |
| `AND` | the same samples, AND'd together |
| `RXD` | `LINK_RXD`, read once per record, after the status samples |

`OR` and `AND` are what make the modest record rate sufficient. The wait for
`TXRDY` between bytes is a tight polling loop — one `LINK_STATUS` sample every
~21 µs — and every sample folds into both accumulators. A bit that pulses high
for a single 122 µs wire cell still shows up in `OR`; one that drops for a
single cell still shows in `AND`; a genuinely constant bit reads the same in
both. **No event on the wire's own timescale can be aliased away.** Only the
ordering of events inside one record is lost.

`LINK_PROBE` is read once, into the preamble, never in the loop: its read side
effects are unknown and the point of this burn is to measure `HSBUSY` without
confounds. Same reasoning bounds `LINK_RXD` to one read per record.

Every frame begins on a record boundary whose `COUNT` is a multiple of 64, so
byte alignment is structural, not guessed.

## Decoding

```
analysis/venv/bin/python analysis/rom_exerciser/decode_records.py capture.csv
analysis/venv/bin/python analysis/rom_exerciser/decode_records.py --hex log.txt
```

CSV is the MSO's four-channel format, the same one `scope_ir_decode.py` reads;
`--hex` takes one frame of whitespace-separated hex per line, for an Arduino
serial log. The headline is the per-bit verdict:

```
LINK_STATUS, over every sample in every record:
  bit 7 TXRDY   always 1
  bit 6 HSBUSY  always 0
  ...
```

`HSBUSY  always 0` is the negative result, and a strong one — the bit the
firmware waits on at `ROM00:32F3` never asserts under any stimulus. Anything
else is the positive result, and `COUNT` says when.

## On the hardware

Decode the wire with the Arduino in `LISTEN_ONLY` mode, then drive its stimulus
modes and watch whether anything moves.

Silence is itself a result: it would mean `TXRDY` never asserts, i.e. the
controller never reports ready even with no firmware competing for it.

## Restoring

Put the original chip back. Nothing else is required: no battery-RAM state is
changed beyond a few bytes of stack in the upper TPA (`C800` down), which the
RAM map documents as free.
