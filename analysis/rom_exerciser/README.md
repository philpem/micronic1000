# Link-controller exerciser

A patched `ROM00` that turns the handheld into a dedicated test rig for the
link controller. It replaces the cold-boot entry, opens a frame the way
`LinkBlockTx` does, and then **streams `LINK_STATUS` onto the IR line**, one
byte per sample, for as long as it is powered.

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
| `micron1_exerciser.bin` | `DB30` |

Read the fitted chips out before burning and compare. A sum match plus a
`cmp` against `micronic/` is conclusive; the sum alone is a strong check that
needs no reference to this repo. **Label the burned exerciser `DB30`** so it
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
| `7E96`-`7EED` | the exerciser, in a 356-byte run of `00` filler that must be empty beforehand |
| `014B` | `JP 7E96`, replacing the cold-boot prologue (checked byte-for-byte first) |

`014B` rather than the reset vector because `0000` → `0103` → `014B`, and the
emulator harness starts directly at `014B`, so the same patch is exercised on
hardware and in the emulator.

**90 bytes differ from the original.** One chip: `ROM01` is untouched.

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
 14  PC=34F7  4C = 81     LINK_CMD -- the flag goes on the wire
 15+ PC=7EDA  4D = ..     LINK_STATUS, streaming (11476 writes in 400 slices)
```

The emulator's synthetic controller always reports `80h` (TXRDY set, nothing
else), so the *values* mean nothing here — only the path does. The values are
what the hardware run is for.

## On the hardware

Decode the wire with the Arduino in `LISTEN_ONLY` mode. The stream is
`flag` then status bytes back to back, so the existing decoder finds the flag,
destuffs, and yields one `LINK_STATUS` sample per byte. Watch bit 6 (`HSBUSY`)
and bit 4 (`RXBUSY`), and drive the Arduino's stimulus modes to see what, if
anything, moves them.

Silence on the wire is itself a result: it would mean `TXRDY` never asserts,
i.e. the controller never reports ready even with no firmware competing for it.

`LINK_ID` in `exerciser.asm` selects the port (`43h` = id bit 5 clear, `63h`
for the other); 268 bytes of the filler block remain for further experiments —
sweeping `LINK_CMD` values, driving `LINK_CTRL` in orders the firmware never
uses, or writing `4Dh` back to back to discriminate the stuffer architectures.

## Restoring

Put the original chip back. Nothing else is required: no battery-RAM state is
changed beyond a few bytes of stack in the upper TPA (`C800` down), which the
RAM map documents as free.
