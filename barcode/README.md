# Barcode decoder for the Micronic 1000

A resident barcode decoder for the DIPOS-B decode hook, in Z80 assembly.
It replaces the ROM's default hook — which discards every scan — and
decodes **Code 39**, **UPC-A**, **EAN-13**, **UPC-E** and
**Interleaved 2 of 5**, **Codabar** and **Code 128**, in either scan
direction.

Build it as a `.DIP` for the loader to place, or as a `.COM` that copies
itself up and installs. Either way the decoder ends up in fixed RAM,
where it survives program exit, warm boot and power cycling.

## Building

```sh
make                    # decoder.bin, decoder.dip, decoder.com in build/
make test               # unit suite, ~3s -- enough for most changes
make test-firmware      # the whole path through the emulator, ~5 min
make clean
```

The default assembler is **z88dk's `z80asm`, run from its Docker image**,
so nothing needs installing locally:

```sh
make                        # uses `sudo docker run z88dk/z88dk`
make DOCKER=docker          # if your user is in the docker group
make ASM=pasmo              # or build with pasmo instead
```

`ORIGIN` sets the link address (default `0xC000`). It is a build
dependency, so changing it rebuilds — the address is baked into the binary
and a stale one fails in confusing ways.

The two assemblers produce binaries of the same size that behave
identically but are **not byte-identical**: z88dk links three object files
with each table inline, while the pasmo path concatenates into one
translation unit, so the data lands at different addresses. Both pass the
same test suite.

## Installing on the handheld

Both packages install the hook themselves. The difference is only *when*
the decoder reaches its final address:

| | `.DIP` | `.COM` |
|---|---|---|
| Placement | the loader does it, before entry | a copy loop at run time |
| Image size | payload once | payload carried in the image too |
| Build | needs the header and block table | a flat binary |

Neither can write the hook socket from a block: `FBC0h` is above the
loader's `D081h` ceiling, so running code has to do it. That is what the
small installer stub in each package is for.

### Where it lives

`C000h`–`D080h` is the recommended range. It is unbanked, so the hook is
reachable whatever bank is paged in, and nothing in the firmware uses it.
A hook in a banked page *is* called correctly — the socket is a banked-call
thunk — but nothing marks that bank in use and the next program load reuses
it, so the decoder would vanish.

### Lifetime

The hook survives program exit, warm boot and power cycling. Only a cold
start reinstalls the ROM default — and a cold start also pattern-tests all
of `8000h`–`FFFFh`, so it would have erased the decoder anyway. There is no
separate terminate-and-stay-resident call; installing the hook *is* the
residency mechanism.

## What it decodes

**Code 39** — variable length, full ASCII subset not implemented (the 43
standard characters plus `*` as the delimiter). Self-checking: an element
pattern with no table entry simply fails, so a misread rejects rather than
producing wrong data.

One sharp edge worth knowing: **every Code 39 pattern is another valid
pattern read backwards** — `0` reverses to `F`, `A` to `1`. So a reversed
scan decoded in place would give a plausible, entirely wrong string. What
prevents that is the delimiter: `*` reverses to `P`, so the start-character
check refuses a mirrored read, and the reversed pass restores the element
order before decoding. Do not remove the `*` checks.

**EAN-13 and UPC-A** — one decoder, because UPC-A *is* EAN-13 with a
leading zero and the two check-digit rules agree under that reading. A
UPC-A is reported as twelve digits (the implied zero is not printed), an
EAN-13 as thirteen, which is what a scanner would give you.

These are *delta* symbologies: element widths only mean something relative
to the module width, which is taken from the left guard. They are not
self-checking, so the check digit is the only thing between a misread and
a plausible wrong number — which is why it is verified before anything is
published.

Code 39 is tried first, precisely because it *is* self-checking: EAN/UPC
only sees scans Code 39 has already declined.

#### Three codes, one table

Right-hand digits use the R code, the bitwise complement of the left-hand
L code. Complementing swaps bars for spaces but leaves the run lengths
alone, so L and R share a table. The G code, used by some left-hand digits
in EAN-13, is R reversed — so its run lengths are L's *backwards*. That is
how a digit's parity is recovered: look the quad up as it stands for L,
and reversed for G.

#### The thirteenth digit

It is drawn nowhere in the symbol. It exists only in *which* of the six
left-hand digits use G rather than L, which `ean_parity.inc` translates. A
parity pattern that is not in that table is not an EAN-13.

#### Either direction

**Every symbology here reads in either direction.** A wand can be drawn
right-to-left; reversing the captured elements restores the original
order, so each decoder tries forward and, on failure, reverses into a
shared scratch buffer and decodes that as an ordinary forward symbol. The cost is one extra pass on symbols that fail forward — every
genuinely reversed scan, and every piece of noise.

This works even for UPC-E, whose guards are different sizes at each end
(three elements and six). It is tempting to think an asymmetric symbol
needs its own mirrored layout; it does not, because the elements are being
put back in their original order rather than read in place.

**UPC-E** — the zero-suppressed form: six digits in 51 modules, which the
capture sees as 33 elements. There are no R codes; every digit is L or G,
and **neither the number system nor the check digit is drawn** — both live
in the parity pattern. Number system 1 uses the same ten patterns
complemented, so a failed lookup is simply retried against `XOR 3Fh`.

The result is reported as the eight digits printed on the label: number
system, six data digits, check digit. That also lets a host tell the
symbologies apart by length alone — 8, 12 and 13.

Internally the decoder expands to the twelve-digit UPC-A anyway, because
that is what the check digit is computed over. The last data digit decides
where the suppressed zeros go, which is the whole of the format:

| last digit | expands to |
|---|---|
| 0, 1, 2 | `N X1 X2 X6 0 0 0 0 X3 X4 X5 C` |
| 3 | `N X1 X2 X3 0 0 0 0 0 X4 X5 C` |
| 4 | `N X1 X2 X3 X4 0 0 0 0 0 X5 C` |
| 5–9 | `N X1 X2 X3 X4 X5 0 0 0 0 X6 C` |

**Interleaved 2 of 5** — digits in pairs, five bars carrying one and five
spaces the other, woven together. A wide/narrow code like Code 39, so no
absolute calibration is needed; the threshold is taken per digit pair,
which always contains four wide and six narrow.

ITF's hazard is not misreading a digit — an invalid five-bit group has no
table entry — but that **a clipped scan can decode as a shorter valid
symbol**, since any whole number of pairs is legal. Both the start (four
narrow) and stop (wide, narrow, narrow) are therefore verified. The
optional mod-10 check digit is *not* verified: it is not part of the
symbology, and a host that wants it can check the digits returned.

**Codabar** — seven elements per character, four bars and three spaces,
with a narrow gap between. Unlike Code 39 the number of wide elements per
character is *not* fixed, so there is no "exactly three wide" invariant to
lean on; the dedicated `A`–`D` delimiters are the only structural check,
and a symbol must open and close with one.

The delimiters are **returned with the data**, because which pair was used
carries meaning — blood banking and libraries both use the choice of A/B/C/D
to distinguish label types. Stripping them would discard that.

**Code 128** — six elements per character, always eleven modules, plus a
seven-element stop. Because *every* character is eleven modules, each one
carries its own calibration: this is the most robust symbology here against
a scan that changes speed part-way.

It is also the only one besides Code 39 that is genuinely self-checking,
and it checks harder: a checksum modulo 103 over the start value plus each
data value times its position. A corrupted character fails the sum rather
than decoding to something plausible.

Code sets A, B and C are supported, with the start character choosing one,
values 99/100/101 switching, and 98 shifting a single character between A
and B. **FNC1–4 are skipped rather than surfaced** — they carry no data,
but a host wanting GS1 application identifiers would need FNC1 visible,
which would mean an out-of-band way to report it.

### Not handled

* **GS1 / FNC1 semantics**, per above.
* **Code 39 full ASCII**, the two-character escapes that extend the 43
  characters to 128.

## Layout

```
src/dipos.inc          the hook contract: addresses, limits, hazards
src/hook.asm           entry, count clamping, symbology dispatch, result
src/code39.asm         Code 39
src/upc.asm            EAN-13, UPC-A and UPC-E, either direction
src/itf.asm            Interleaved 2 of 5
src/codabar.asm        Codabar
src/code128.asm        Code 128, sets A/B/C
src/code39_table.inc   generated by tools/gen_tables.py
src/upc_table.inc      generated by tools/gen_tables.py
src/ean_parity.inc     generated by tools/gen_tables.py
src/upce_parity.inc    generated by tools/gen_tables.py
src/itf_table.inc      generated by tools/gen_tables.py
src/codabar_table.inc  generated by tools/gen_tables.py
src/code128_table.inc  generated by tools/gen_tables.py
tools/gen_tables.py    emits the pattern tables, with self-checks
tools/mkdip.py         wrap the binary as a .DIP
tools/mkcom.py         wrap the binary as a .COM
tools/upc.py           EAN-13 / UPC-A / UPC-E encoder, for test scans
tools/run_tests.py     the end-to-end firmware runner
tests/                 the unit suite (pytest)
```

## Two firmware quirks the decoder works around

**The element count can exceed the buffer.** `ROM00:1409` stores the
uncapped count and `ROM00:1446` hands it to the hook, while the 128-element
cap at `ROM00:140F` applies only to the reverse-copy loop. Feed 140
elements and the hook is told 140 while only 128 exist. `hook.asm` clamps
before anything else looks at it.

**Output is limited to 26 bytes.** The delivery copy at `ROM00:148B` is an
unbounded `LDIR` into a buffer with 26 bytes of room, so an over-long
result would corrupt the device table rather than being truncated.
`hook.asm` refuses instead.

Both are documented in [the barcode reference](../doc/reference/barcode.md),
with the evidence in [the RE notes](../doc/re-notes/barcode-capture.md).
