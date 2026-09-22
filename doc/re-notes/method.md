# Method and evidence rules

How this record is written, and what each label means.

## Labels

* **CONFIRMED** — read directly from the bytes, the disassembly, or an xref.
  State where, e.g. “CONFIRMED: writes `0x46` to RTC Reg B at `ROM00:22DF`.”
* **LIKELY** — an era convention, datasheet behaviour, or owner-supplied
  hardware fact *combined with* something observed. State both halves.
* **SUSPECTED** — plausible, unverified. Paired with the specific
  observation that would confirm or refute it.
* **OPEN** — not yet established. The discriminating test is listed in
  [Open questions](open-questions.md) and, for prioritised work, in
  `research/TASKS.md`.

Rules:

* Never promote `SUSPECTED → LIKELY → CONFIRMED` without going back to the
  bytes.
* Never let a `SUSPECTED` claim become a silent premise in another analysis.
* Rejecting one unproven identity does not license asserting another.
  “Unknown, two candidates, here is the test” is preferable to a confident
  wrong answer.
* Byte-verify every table or offset claim with a fresh `read_memory` or
  disassembly before writing it — mind pre/post-increment. The `31F2/31F5`
  off-by-one and the “`FE83` is 4 bytes” error both came from skipping this.
* Repeatable comments carry only **CONFIRMED** facts — they propagate to
  every xref. Hypotheses belong in a plate or a doc, clearly tagged.
* Strings are not proof of behaviour.

## Owner-supplied ground truth

The owner has the hardware and is the arbiter when ROM evidence is silent:

* The `08h/28h` pair **is** the HD146818 RTC; the `4Ah-4Fh` cluster is not.
* There is no serial EEPROM; the serial number is user-entered and lives in
  battery RAM near `FEAB`.
* The right-side scanner port has **eight contacts** (owner correction,
  2026-09-22), with power and ground known and six contacts still unknown.
  The port-`2Dh` edge-timing code is the barcode-reader front end
  (`Barcode_` prefix). The logical scan input is `EXTBUS_EDGE` bit 0;
  its physical contact and the output-contact mappings remain unmeasured.
  The owner proposes manual output-port writes first, then input mapping;
  see the [audit plan](../research/reviews/ir-protocol-audit-2026-09-22.md).
* The two IR ports are **V24 ADAPTOR = top, PLINTH = back**. Firmware
  selects between two line states by wire-id bit 5. A fresh trace of the real
  V24 Load/Run choice uses `fdd4=43h`, the wire-ID-bit-5-clear branch
  (`LINK_CTRL` bit 1 and port `2Ch` bit 5 both set), and the owner observed
  that operation at the top window. **CONFIRMED: wire-ID bit 5 clear is top
  V24; it drives both output bits set.** Wire-ID bit 5 set clears both output
  bits and is **LIKELY** the back PLINTH state by two-port elimination, but
  has not yet been observed at that window. See
  [commstar-evidence](commstar-evidence.md#device-table-ports).
* All drive `C:`+ storage I/O runs over the 4-wire byte transport, so the
  EXT STORAGE ADAPTER must attach via one of the two IR ports; defaults are
  `C:=0x73`, `D:=0x72` (wire-ID bit 5 = 1 in both, hence the likely
  back-port state).
  The earlier claim that BDOS rejects every nonzero drive ID was
  withdrawn after tracing the session helpers. A BDOS `2Eh` path reaches
  the transport; successful peer-dependent file operations still need
  per-operation verification. See
  [storage evidence and remaining questions](open-questions.md#link-identity-and-port-selection).

When ROM evidence and an owner statement seem to conflict, report the
contradiction — do not invent a reconciliation.

## The ROM images are the ones in the machine

The heading records the owner's image provenance. The checksum comparison
below supports that provenance but does not independently prove identity.

**CONFIRMED.**  The two firmware DIPs carry handwritten labels
`DIP1 ACF8` and `DIP2 2E12`.  Both are the low 16 bits of the unsigned sum
of all 32768 bytes of the corresponding image — the checksum every EPROM
programmer of the era prints after a read:

| chip   | image         | sum of bytes | low 16 bits | label  |
|--------|---------------|--------------|-------------|--------|
| DIP1   | `micron1.bin` | `0037ACF8`   | `ACF8`      | `ACF8` |
| DIP2   | `micron2.bin` | `00332E12`   | `2E12`      | `2E12` |

Nothing was fitted to make this work: a plain byte sum was the first
algorithm tried, and it matched both chips.  Twenty-one CRC-16 variants and
a dozen other sum and XOR forms were also computed; none matched either
label. The observed result is that both image byte sums match the
handwritten chip labels. No random-error model was established, so a
one-in-four-billion probability is not justified.

A byte sum detects a single-byte change but is permutation-invariant and
can miss compensating changes. Treat ROM addresses here as addresses in
the supplied dumps. To establish that a chip still matches its dump, read
it back and compare byte for byte; a matching 16-bit sum alone is not
sufficient. The label remains a useful quick read-back check before
programming (see `analysis/rom_exerciser/README.md`).

**LIKELY**, from the labels alone: the parts are field-programmed rather than
masked.  A mask ROM carries a printed vendor part code, not a handwritten
number, and the number written on these is precisely the one a programmer
prints after a read.  The device type is **OPEN** — worth reading off the
package before ordering blanks, since a `27C256` EPROM and a `28C256` EEPROM
are not pin-compatible (`27C256` pin 1 is `VPP` and pin 27 is `A14`; on the
`28C256` those are `A14` and `/WE`).

## Z80 and Ghidra

* The decompiler is a hint, never evidence. Verify against the listing.
* `RST 10h / DB bank / DW target` is the banked-call convention; its
  inline operands are data, not code.
* `JP (HL)` / `JP (IX)` dispatch is everywhere — find the feeding table,
  define it as data, add manual references, and record the index→handler
  map in the dispatcher’s plate.
* The banked window is modelled as overlays `ROM00`, `ROM01`, and `ram`.
  Quote addresses with their space (`ROM01::7A1B`, `ram:fbc2`).
* Alternate-register usage and `EXX` are strong evidence of an interrupt
  or context switch.

## Calling conventions and naming

For every function the plate records **In / Out / Clobbers**, verified at a
call site. A function is not “named” until it carries at least a one-line
plate. Naming uses `Module_Name` PascalCase for new names; existing
concatenated names are grandfathered. Labels for ports use `UPPER_SNAKE`.

## Comment style

* **Plate** — what/why/context, wrapped ~70 cols, with evidence tag.
* **EOL** — one fact, ≤60 chars, only where the opcode alone does not tell
  the story.
* **PRE** — multi-line explanation of an idiom.
* **Repeatable** — one short CONFIRMED sentence; detail goes in a plate at
  the same address.

## What reference pages do

A reference page states a **contract and its stability** (`Stable` /
`Provisional` / `Not implementable`). An RE-notes page states **evidence
and its confidence** (`CONFIRMED`/`SUSPECTED`/`OPEN`). A reference page leads with the contract and links to the relevant
RE-notes anchor. Include addresses needed to call the interface and
explicit limits; keep discovery history and long byte listings in the
evidence layer. See the [reference status terms](../reference/README.md#stability-terms)
for the distinction between evidence, validation, support policy, and ROM scope.

For the navigation split and the rule that makes it hold, see the review
that proposed it (`research/reviews/` archive, Part 3).
