# InlineTableDispatch: inline switch tables

`InlineTableDispatch` (`ram:E0B2`) is a switch helper whose jump table is
stored **inline, immediately after the CALL** rather than in a separate data
block. Every call site therefore carries its own table, and Ghidra renders
those bytes as stray data unless they are decoded deliberately. This page
records the format and every decoded table.

## Table format

**CONFIRMED** — byte-verified from `ram:E0B2-E0D8`.

```text
CALL E0B2
    u16  count
    { u16 case_value, u16 handler } * count
    u16  default_handler
```

## Calling convention

**CONFIRMED** from the disassembly:

* **In:** `HL` = the value being switched on.
  `E0B2` does `EX DE,HL` then `POP HL`, so the return address becomes the
  table pointer and the switch value is moved to `DE`, then copied to `BC`.
* **Out:** control never returns to the call site. `E0D8` is `JP (HL)` onto
  the selected handler, so **the handler returns to the caller's caller**.
  Treat the bytes after the table as unreachable from this call.
* **Clobbers:** `AF`, `DE`, `HL`. `BC` is preserved (`PUSH BC` at `E0B4`,
  `POP BC` at `E0D7`).

## Matching

The comparison is two-stage: `E0C1-E0C3` compares the low byte, and only on a
match does `E0CD-E0CF` compare the high byte. A high-byte mismatch rejoins the
skip path at `E0C7`, so a full 16-bit compare is performed.

The counter is pre-decremented (`DEC DE` at `E0BA`, sign-tested at `E0BD`), so
a `count` of 0 falls straight through to the default. On exhaustion `HL` is
left pointing at the last entry's handler high byte, and the default is read
from the two bytes immediately following — which is why the default sits after
the entries with no terminator.

## Decoding the tables

`analysis/decode_inline_tables.py` finds every `CD B2 E0` in the supplied
images and decodes the table that follows. Regenerate the listing below with:

```sh
analysis/venv/bin/python3 analysis/decode_inline_tables.py \
  --quiet --markdown doc/re-notes/inline-dispatch-tables.md
```

The battery-RAM image it reads (`analysis/battery_ram.bin`) is gitignored
like the other RAM dumps; dump `ram:8000` for `0x8000` bytes from the Ghidra
database to recreate it. **There are no call sites in RAM** — all 45 are in
ROM, so the ROM images alone are sufficient.

The decoder is validated against the five tables that were already documented
by hand (`4E4E`, `528E`, `53C4`, `540D`, `5A66`); all five match exactly.

## Defining the tables in Ghidra

Ghidra disassembles these tables as code by default, because the bytes follow
a `CALL` and nothing tells it the flow does not continue there. That produced
**279 bogus instructions** across the 45 sites and derailed the surrounding
listing.

`analysis/ghidra/DefineInlineTables.java` fixes this. Copy it to
`~/ghidra_scripts/` and run it against `micron1.bin`; it takes no arguments
and needs nothing from the Python decoder.

It scans every initialised memory block for `CALL E0B2`, decodes the table
that follows, clears the range, types it as `word[2*count+2]`, and attaches a
plate listing the decoded cases. A table whose count exceeds 64, or which
would run past the end of its block, is skipped and reported rather than
defined — that guard is what keeps a chance byte sequence from being typed as
a table.

It then adds a reference from every entry to its handler and disassembles any
handler left as raw bytes. That pass matters because the dispatcher reaches
handlers through `JP (HL)`: Ghidra has no flow to them, so without it the
tables carry no xrefs and a handler that was only reachable via the bogus
fall-through reverts to undefined bytes. 233 references; 4 handlers needed
recovering.

The script is idempotent: a second run reports 0 instructions cleared, so it
is safe to re-run after any reanalysis that re-disassembles the tables.

The Python decoder and the Ghidra script find the sites independently and
agree on all 45, which is a useful cross-check on both.

## Every call site

45 sites, 188 cases: 25 in ROM00, 20 in ROM01, none in RAM. Case values are
**not** a single namespace — each table's values mean whatever its caller
switches on. Do not read them as wire commands.

| Call | Table | Cases | Case values | Default |
|---|---|---:|---|---|
| `ROM00:3FEC` | `3FEF-4002` | 4 | `0x0`, `0x4`, `0x8`, `0x9` | `3FE2` |
| `ROM00:46D6` | `46D9-46E4` | 2 | `0x0`, `0x9` | `46BD` |
| `ROM00:47E3` | `47E6-47F1` | 2 | `0x0`, `0x9` | `47CA` |
| `ROM00:4890` | `4893-48BA` | 9 | `0x0`, `0x1`, `0x4`, `0x9`, `0xb`, `0xc`, `0xf`, `0x12`, `0x13` | `487F` |
| `ROM00:494D` | `4950-496F` | 7 | `0x0`, `0x1`, `0x4`, `0x9`, `0xf`, `0x12`, `0x13` | `493C` |
| `ROM00:49FA` | `49FD-4A20` | 8 | `0x0`, `0x1`, `0x4`, `0x9`, `0xd`, `0xf`, `0x12`, `0x13` | `49E9` |
| `ROM00:4AB1` | `4AB4-4AC7` | 4 | `0x0`, `0x1`, `0x9`, `0xf` | `4A98` |
| `ROM00:4CC5` | `4CC8-4CE3` | 6 | `0x0`, `0x1`, `0x2`, `0x3`, `0x4`, `0x5` | `4CB4` |
| `ROM00:4D0E` | `4D11-4D24` | 4 | `0x0`, `0x4`, `0x8`, `0x9` | `4CFD` |
| `ROM00:4E4E` | `4E51-4E68` | 5 | `0x0`, `0x4`, `0x6`, `0x8`, `0x9` | `4E3D` |
| `ROM00:4F37` | `4F3A-4F55` | 6 | `0x0`, `0x4`, `0x7`, `0x8`, `0x9`, `0xa` | `4F26` |
| `ROM00:5019` | `501C-502F` | 4 | `0x0`, `0x4`, `0x8`, `0x9` | `5008` |
| `ROM00:50D6` | `50D9-50E8` | 3 | `0x0`, `0x4`, `0x9` | `50C5` |
| `ROM00:5162` | `5165-5174` | 3 | `0x0`, `0x4`, `0x9` | `5151` |
| `ROM00:51D5` | `51D8-51E7` | 3 | `0x0`, `0x4`, `0x9` | `51C4` |
| `ROM00:528E` | `5291-52A0` | 3 | `0x0`, `0x4`, `0x9` | `527D` |
| `ROM00:53C4` | `53C7-53E2` | 6 | `0x0`, `0x1`, `0x2`, `0x3`, `0x4`, `0x5` | `53B3` |
| `ROM00:540D` | `5410-5423` | 4 | `0x0`, `0x4`, `0x8`, `0x9` | `53FC` |
| `ROM00:54C6` | `54C9-54E0` | 5 | `0x0`, `0x1`, `0x4`, `0x9`, `0xf` | `54B5` |
| `ROM00:5643` | `5646-5661` | 6 | `0x0`, `0x1`, `0x2`, `0x3`, `0x4`, `0x5` | `5640` |
| `ROM00:572E` | `5731-5738` | 1 | `0x6` | `5725` |
| `ROM00:5780` | `5783-578A` | 1 | `0x6` | `5777` |
| `ROM00:581B` | `581E-5825` | 1 | `0x6` | `5812` |
| `ROM00:5A66` | `5A69-5A80` | 5 | `0x44`, `0x45`, `0x60`, `0x61`, `0x64` | `5A63` |
| `ROM00:604E` | `6051-6064` | 4 | `0x0`, `0x4`, `0x9`, `0xc` | `6045` |
| `ROM01:0FCA` | `0FCD-0FD8` | 2 | `0x0`, `0x1` | `0FD9` |
| `ROM01:104B` | `104E-105D` | 3 | `0x1`, `0x2`, `0x4` | `105E` |
| `ROM01:1163` | `1166-1175` | 3 | `0xd`, `0x14`, `0xdb` | `115F` |
| `ROM01:1214` | `1217-1222` | 2 | `0x0`, `0x1` | `1202` |
| `ROM01:1503` | `1506-1515` | 3 | `0x0`, `0x1`, `0x2` | `1516` |
| `ROM01:1F96` | `1F99-1FB4` | 6 | `0x1`, `0x6`, `0xb`, `0xc`, `0x11`, `0x12` | `1F23` |
| `ROM01:257C` | `257F-2592` | 4 | `0x1`, `0x6`, `0xb`, `0xc` | `257B` |
| `ROM01:28EA` | `28ED-28FC` | 3 | `0x1`, `0x6`, `0x13` | `28E6` |
| `ROM01:2C24` | `2C27-2C4A` | 8 | `0x1`, `0x6`, `0xb`, `0xc`, `0xd`, `0x11`, `0x12`, `0x14` | `2C16` |
| `ROM01:2CAC` | `2CAF-2CCE` | 7 | `0x1`, `0x6`, `0xb`, `0xc`, `0x11`, `0x12`, `0x13` | `2CCF` |
| `ROM01:3B53` | `3B56-3B79` | 8 | `0x1`, `0x2`, `0x4`, `0x8`, `0x10`, `0x20`, `0x40`, `0x80` | `3B7A` |
| `ROM01:45D1` | `45D4-45EB` | 5 | `0x2`, `0x4`, `0x8`, `0x20`, `0x40` | `45C2` |
| `ROM01:4A2D` | `4A30-4A3F` | 3 | `0x39`, `0x41`, `0x58` | `4A15` |
| `ROM01:581F` | `5822-5835` | 4 | `0x0`, `0x1`, `0x2`, `0x3` | `5836` |
| `ROM01:5991` | `5994-59A7` | 4 | `0x0`, `0x1`, `0x2`, `0x3` | `59A8` |
| `ROM01:5E2E` | `5E31-5E40` | 3 | `0x0`, `0x1`, `0x2` | `5E41` |
| `ROM01:62D1` | `62D4-62E3` | 3 | `0x1`, `0x2`, `0x4` | `62E4` |
| `ROM01:66EC` | `66EF-6706` | 5 | `0x0`, `0x1`, `0x2`, `0x3`, `0x4` | `6707` |
| `ROM01:6B40` | `6B43-6B52` | 3 | `0x0`, `0x1`, `0x4` | `6B2B` |
| `ROM01:6E64` | `6E67-6E76` | 3 | `0x0`, `0x1`, `0x2` | `6E56` |

## Notable tables

* `ROM00:5A66` — cases `0x44`, `0x45`, `0x60`, `0x61`, `0x64`. These are the
  numeric values that also appear in the link-frame request payload, not the
  0..13 `g_bSessionState` values. `0x60` appears here but has never been seen
  on the wire.
* `ROM00:4E4E` — cases `0`, `4`, `6`, `8`, `9`; the session result-word
  dispatcher whose default arm stores result 6 and raises
  `0x1F9A "Line failure"`.
* `ROM00:53C4` — cases `0`..`5`, the only fully dense case set.
