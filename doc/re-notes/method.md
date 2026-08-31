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
* The 5-pin side port was used with a barcode pen; the port-`2Dh`
  edge-timing code is the barcode-reader front end (`Barcode_` prefix).
* The two IR ports are **V24 ADAPTOR = top, PLINTH = back**. Firmware
  selects between two line states by wire-id bit 5; which bit value maps to
  which port is **OPEN**.
* All drive `C:`+ storage I/O runs over the 4-wire byte transport, so the
  EXT STORAGE ADAPTER must attach via one of the two IR ports; defaults are
  `C:=0x73`, `D:=0x72` (both bit 5 = 1).

When ROM evidence and an owner statement seem to conflict, report the
contradiction — do not invent a reconciliation.

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
and its confidence** (`CONFIRMED`/`SUSPECTED`/`OPEN`). A reference page
carries no ROM address, no evidence tag, and no trace bytes — it links to
the RE-notes anchor that does.

For the navigation split and the rule that makes it hold, see the review
that proposed it (`research/reviews/` archive, Part 3).
