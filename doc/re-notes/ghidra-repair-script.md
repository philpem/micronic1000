# Listing-repair script

`analysis/ghidra/AnalyseMicronicRom.java` is the one script that puts the
Ghidra database back into the shape the rest of these notes assume. It takes
no arguments, finds every site it acts on by itself, and is safe to run any
number of times.

Copy it to `~/ghidra_scripts/` and run it against `micron1.bin`. It prints a
per-pass count and ends with a summary.

**Run it after any bulk re-analysis, and any time
`get_function_count` drops unexpectedly.** Ghidra's auto-analysis undoes
several of these repairs on its own schedule; the script is the cheap way to
put them back, and its report tells you what had drifted.

## What it repairs, and why Ghidra gets it wrong

| Pass | Repairs | Why auto-analysis fails |
|---|---|---|
| 0 | The battery-RAM image | The ROM dumps contain no RAM, so nothing in unpaged RAM exists to analyse |
| 1 | The `ram:D837` frame-helper's no-return flag | A wrong flag makes Ghidra delete every C function body |
| 2 | Both banks' boot-load chains | The load script is data that follows no flow edge |
| 3 | `RST 10h` banked-call inline operands | The three operand bytes look like code |
| 4 | `InlineTableDispatch` inline tables | The table follows a `CALL` and the dispatcher tail-jumps |
| 5 | Missing functions at compiler frame prologues | Nothing references a routine that is only reached through the deferred-call queue |
| 6 | The 281-slot runtime stub farm | Every slot is a cold template with no reference to the routine it stands for |

The passes run in that order and **the order is load-bearing**: pass 0 puts the
RAM image in place, and every later pass reads it. Pass 1's byte check looks at
`ram:D837`, which is empty until pass 0 has run.

Pass 4 is `DefineInlineTables.java` folded in with its behaviour preserved;
that script stays in the tree and is still described in
[InlineTableDispatch tables](inline-dispatch.md). Passes 2 and 3 replace the
ad-hoc `AnnotateRst10Calls.java`, with two bugs fixed (below).

## Pass 0 — battery-RAM bootstrap

`micron1.bin` is two 32K ROM banks and nothing else, but almost every routine
worth reading calls into unpaged battery RAM: the frame helper (`D837`), the
switch dispatcher (`E0B2`), the string and arithmetic library (`DB89`, `E04B`,
`DFCC`), the indirect-call thunk (`D828`), the session modules (`D081`,
`D893`, `E104`), the resident kernel (`F180`), and the runtime stub farm
(`ED1C`). On a freshly imported program none of that exists and none of it
disassembles.

This pass reconstructs the observable result of a clean cold boot — it is
`FillBatteryRam.java` folded in. It creates the `battery_ram` block, seeds the
system variables the reset flow writes, replays the ROM→RAM copies, lays down
the stub-farm template, drops analysis artifacts, and disassembles the entry
points.

### Where the copy list comes from

Six of the eleven copies are boot-load chain records, so they are taken from
the same chain walk pass 2 uses — one source of truth, no drift. The other
five are performed by ROM code and appear in no chain, so they stay hardcoded
with the performing routine named against each:

| Copy | Performed by |
|---|---|
| `ROM00:2352` → `ram:FD84` (19) | `ROM00:22E9`/`2306` |
| `ROM00:3257` → `ram:FE93` (16) | `ROM00:3220` |
| `ROM00:3267` → `ram:FE83` (16) | `ROM00:3220` |
| `ROM00:7030` → `ram:D681` (0x212) | `ROM00:3BAA` |
| `ROM00:369D` → `ram:F180` (0x50D) | `InstallKernelToRam`, `ROM00:02FE` |

The script prints both lists and reports any disagreement. **That diff found a
live bug.** `FillBatteryRam.java` hardcoded the `E104` copy as `0130h` bytes;
the chain record at `ROM00:7D7C` says `0129h`. `7C2F + 0129h = 7D58`, exactly
where the chain script starts — the source blob ends where the chain begins.
So `0130h` over-reads seven bytes *of the chain script itself* into `ram:E22D`,
on top of the misc-config block copied there moments earlier. Measured against
the database: at length `0130h` the destination mismatches in 6 bytes; at
`0129h` it matches exactly. The chain is authoritative, so the walk wins and
the disagreement is reported on every run as a standing `DRIFT` line.

### Two guards that were not in the original

**The stub-farm template is not written over a live image.** The fill is
skipped when the region already matches the template, and refused outright if
any slot begins with `D7` — that means real inter-bank thunks are present, so
the database holds a post-boot dump and overwriting it would destroy observed
state.

**`removePhantomFunctions` needed tightening — badly.** The original deleted
every `ram` function at or above `F100`, on the reasoning that they were
invented over unmapped memory. That was true of the database it was written
for. On the current database the resident kernel lives at `F180`, so the
original predicate would delete **61 functions** — `BdosDispatchFn`, every
`Syscall_InvokeService*`, `Kernel_BankedCallEnvelope`, `KernSetBank`,
`BankedCallCommonEntry`, the whole `SessionOpStub_*` farm — 58 of them
hand-named. The predicate now requires **both** that the function still carries
Ghidra's generated `FUN_` name and that its entry is not an instruction. A
hand-named function can never match, and neither can anything pass 5 creates,
because pass 5 only creates where an instruction already exists.

### Seeds

The ten system-variable seeds encode observed cold-boot values that cannot be
derived from the ROM image, so they are kept. On a block this run created they
are all written; on a block that was already there only cells still reading
zero are filled, and a non-zero observed value is reported and left alone.

## Pass 1 — the frame helper does return

**CONFIRMED**, byte-verified at `ram:D836`-`D857`:

```asm
D836  E9              JP   (HL)          ; the trampoline D837 uses
D837  E1              POP  HL            ; the CALL's return address
      C5 44 4D        PUSH BC / LD B,H / LD C,L
      21 00 00 39     LD   HL,0 / ADD HL,SP
      EB 39 F9        EX   DE,HL / ADD HL,SP / LD SP,HL   ; SP += DE
      D5              PUSH DE            ; old SP
      DD E5 FD E5     PUSH IX / PUSH IY
      60 69           LD   H,B / LD L,C
      CD 36 D8        CALL D836          ; = JP (HL): enter the caller's body
D845  FD E1 DD E1 …   POP  IY / POP IX / … unwind, HL back to the caller
```

Two facts follow from those bytes.

* The `DE` loaded immediately before `CALL D837` is the **local frame size**
  added to SP, not a call target. `LD DE,0` means "no locals". This is what
  makes pass 5 possible.
* `CALL D837` **falls through** to the instruction after it — that is exactly
  what `CALL D836` with `HL` holding the popped return address does. The
  helper is not a non-returning function.

The database had `ram:D837` (still named `CoroutineTaskSwitch`) flagged
no-return. With that flag set, Ghidra's non-returning-function repair treats
the body of every compiled routine as dead code. Measured on this program:
a run of the other four passes with the flag still set created 143 functions,
and background auto-analysis then silently deleted **61 existing ones**, 59 of
them hand-named — `Lib_StrCmp`, `Lib_StrCopy`, `RunLoadedProgram`,
`Kernel_RunStagedCall`, the `SessionOpStub_*` farm, and more. It also capped
every prologue function's body at the six bytes of the prologue itself.

Pass 1 clears the flag, after byte-checking that `D837` really holds the
helper, so it is inert on any other program. It runs first because everything
else depends on it.

The identity of `D837` is therefore **not** a coroutine switch, and its plate
now records that. The symbol has deliberately **not** been renamed: that is a
consequential rename needing the owner's call and a full docs pass. See
[Open questions](open-questions.md).

## Pass 2 — boot-load chains

Each bank's `(7FFC)` points at a record script the dispatcher walks at every
cold boot (grammar in [OS internals](os-diposb.md)). The script is data, so
Ghidra decodes ~200 bytes of it as garbage instructions; worse, the `fn=2`
records' target words are the **only** reference to most of the session and
Commstar layer — 134 routines in bank 0, 147 in bank 1.

The pass types each record field as an individual `word` (never an array, so
the existing per-word comments stay visible), adds a reference from each
target word to its routine, disassembles the target when it is undefined, and
creates a function there when there is none.

Two corrections to the old `AnnotateRst10Calls.java`:

* An enqueued word carries no bank of its own — the stub is built with the
  live bank shadow, which is the bank whose chain is running. So a bank-0 word
  resolves in `ROM00` and a bank-1 word in `ROM01`. The old script resolved
  every target in the flat `ram` space, whose block starts at `8000`, leaving
  156 dangling references in the bank-0 chain alone. The pass repoints any it
  finds.
* It writes nothing over an existing comment.

This pass and pass 5 corroborate each other: every bank-0 chain target and
almost every bank-1 target is also a compiler frame prologue, found by an
independent byte signature.

## Pass 3 — banked-call inline operands

`RST 10h` takes `db bank ; dw target` inline. The pass types those three
bytes, points a reference at the callee in that bank's own address space, and
comments the site. A target of `0000` is a stub whose operands are patched at
run time (the deferred-call queue, `ram:D79C`), and gets the comment but no
reference.

Two guards keep it from damaging data:

* it only inspects addresses the listing already decodes as an `RST`
  instruction, never raw `D7` bytes — `D7` is a common high byte in this
  firmware's `D6xx`/`D7xx` jump tables;
* a bank above `0Fh` or a target below `0100h` means the match is table data
  Ghidra mis-decoded, so it is reported and skipped. `ram:D6F7` and `D6F9`
  are exactly this: the high bytes of the words `D713h` and `D727h`.

## Pass 4 — InlineTableDispatch tables

`DefineInlineTables.java` folded in, with its behaviour preserved and a
check-before-write fast path added. The repair is documented in full on its own
page — see [InlineTableDispatch tables](inline-dispatch.md), which covers the
table grammar, the count guard, and the misaligned-handler case at
`ROM01:115F`. Nothing about that pass changes here; it is listed as pass 4 so
the numbering in the script's report matches this page.

## Pass 5 — functions at compiler frame prologues

Every routine the compiler emitted starts `LD DE,nnnn / CALL D837` — 348 sites
across `ROM00`, `ROM01` and the RAM modules. The six-byte signature
`11 lo hi CD 37 D8` pins four fixed bytes, so a chance match in data is about
1 in 2<sup>32</sup> per position: roughly 0.00002 expected false positives
across the whole 96K image.

Ghidra had created no function at 144 of them, including every routine between
`ROM00:4D25` and `5307` — eight consecutive prologues (`4D29`, `4D4F`, `4D75`,
`4E6D`, `4F5A`, `5034`, `50ED`, `5179`, `51EC`, `52A5`) with nothing marking
them. That gap is what produced an earlier documentation error in this
project.

The pass creates a function only where the evidence is already in the
database:

* the listing already decodes the site as `LD DE,imm16` followed by a `CALL`;
  or
* the site is undefined bytes and something independent witnesses it — a
  reference already points at it (in practice, a pass-2 chain record), a human
  has already put a label on it, or the preceding instruction ends exactly one
  byte earlier and cannot fall through, so the previous routine provably ends
  where this one starts.

Anything else is reported, bookmarked under *Micronic frame prologue*, and
left alone. Two sites are permanently deferred: `ROM00:7409` and `ROM00:7472`
are the ROM images of RAM module A (the same code as `ram:D8CE` and
`ram:D937`), so disassembling them in ROM space would resolve every internal
address against the wrong space.

New functions keep Ghidra's default `FUN_*` name — per `AGENTS.md`, an
unanalysed function must stay obviously unanalysed. Where a hand-made label
already existed at the entry, Ghidra adopts it, so `SessionPollIntrq`,
`UiDialogLayout`, `TextOutString` and others became functions under their real
names.

Function bodies come from Ghidra's own flow analysis; the script does not
invent one. It does report any body that swallows the next prologue, which is
the shape of a missed `RET`.

## Pass 6 — the runtime stub farm

281 four-byte slots run from `ram:ED1C` to `F17F`, one per routine that loaded
software or the other bank may call. A `CALL 0EExxh` is how you reach a
firmware routine without knowing which bank it is in.

In the cold image every slot still holds the `KernelInitCopyData` template
`21 01 00 C9` = `LD HL,1 / RET` (verified: all 1124 bytes of `ED1C..F17F`
match the 4-byte pattern at `ram:D6D7`). So each slot returns 1, does nothing,
and — the point for analysis — carries no reference to the routine it stands
for. Every one of those 281 call sites was a dead end the listing could not be
followed across. This pass restores those edges.

### How a slot is built

The fn=2 boot-chain handler at `ram:D727` is the entire mechanism,
byte-verified:

```asm
d72b  EX DE,HL / ADD HL,HL      ; BC = 2N bytes of source words
d72f  LD HL,(d684)              ; the queue cursor
d733  LD A,D7h  / LD (DE),A     ; RST 10h opcode
d737  LD A,(f791) / LD (DE),A   ; the live bank shadow
d73c  LDI / LDI                 ; the 2-byte target
d740  JP PE,d733                ; next slot
d744  LD (d684),HL              ; write the advanced cursor back
```

Slot *i* is therefore `D7 bank lo hi` — an inter-bank thunk in the same four
bytes as the template it replaces — and the bank byte comes from `F791`, the
bank whose chain enqueued it.

**This answers where the installer is: there isn't one.** Searching for a
pointer to the `ROM00:7D88` table finds nothing because the handler reads the
words inline out of the record stream as it walks the chain. `7D88` is simply
where bank 0's fn=2 record keeps them.

### Why the slot numbering is right

The cursor cell `(d684)` reads `ED1C` in the cold image. Bank 0's 134 words
followed by bank 1's 147 come to 281 slots × 4 = 1124 bytes, landing exactly on
`F180` — the resident kernel's base, and exactly the range
`KernelInitCopyData` pre-fills. Three slot-to-target pairs recorded
independently from a live RAM dump all reproduce:

| Slot | Address | Target |
|---|---|---|
| 58 | `ram:EE04` | `ROM00:48BF` |
| 60 | `ram:EE0C` | `ROM00:4AE0` |
| 68 | `ram:EE2C` | `ROM00:4F5A` |

CONFIRMED for bank 0's slots 0..133. Bank 1's slots 134..280 follow from the
same shared cursor and the exact fit; slot 134 resolves to `ROM01:0319`, which
is bank 1's first enqueued word, and slot 280 to `ROM01:65F5`, its last.

The pass adds one `COMPUTED_CALL` reference and one short EOL comment per slot,
and plates the head of the farm once. It creates no labels, and it never
overwrites a comment a human wrote.

### A parsing trap worth knowing about

`ROM00:7D88` is *inside* the bank-0 chain — it is the word array of the fn=2
record whose header sits at `7D84`. The 134 words there also parse as plausible
6-byte records (the first would read `src=3BAA dst=62C7`), so a walker that
steps fixed-size records through them would silently mistake the stub source
table for chain records. The script consumes the fn=2 record by its declared
word count instead, which lands exactly on the `FFFF` terminator at `7E94` —
and the script prints that span (`chain ROM00 7D58..7E94 terminates cleanly`)
on every run precisely so the grammar can be seen to be applied correctly.
The stub source table and the deferred-call enqueue list are the same 134
words; they are not two tables.

## Idempotency

Every pass tests the database before it writes.

* **Passes 0–4 and 6 are exactly idempotent.** A second run reports zero
  changes. Pass 0's copies are skipped when the destination bytes already
  match — which matters for more than speed, because writing would clear the
  code units over the destination and discard the disassembly of a module that
  is already analysed. Its seeds are skipped once at their value, and its
  template fill is skipped once the farm matches.
* **Pass 5 is convergent within a run.** Creating a function makes Ghidra
  disassemble its body, which can expose the next prologue, so the pass
  iterates to a fixed point (two rounds in practice) and is idempotent
  thereafter.

The one line that repeats on every run is pass 0's `DRIFT` report about the
`E104` copy length. That is a standing diagnostic, not an unconverged change:
it is comparing the live chain against the old hardcoded table on purpose, and
it will keep saying so until someone deletes `LEGACY_CHAIN_COPIES`.

Nothing is renamed. A comment is written only where none exists; one that
differs is kept and reported as `KEEP existing …`.

## Measured result

Against the database as of 2026-09-01, starting from 934 functions.

First run — what each pass found wrong:

| Pass | Work done |
|---|---|
| 0 battery RAM | block already present, 11 copies already correct, 1 copy-list disagreement reported |
| 1 frame helper | no-return flag cleared on `ram:D837` |
| 2 boot chains | 14 records walked, 323 words typed, 281 references added, 156 dangling `ram:` references repointed, 19 targets disassembled, 110 functions created |
| 3 banked calls | 1 site repaired, 2 already correct, 5 skipped as mis-decoded table data |
| 4 inline tables | 45 tables already correct (this repair had been applied before) |
| 5 prologues | 348 sites, 33 further functions created on top of pass 2's 110 |
| 6 stub farm | 281 slots, 281 references and 281 comments added |

Second run — every pass reports zero:

```
pass 0  battery RAM  : block already present, 0 vars seeded, 0 copies replayed,
                       11 already correct, 0 phantom functions removed,
                       0 entry points disassembled, stub template unchanged
pass 1  frame helper : no change needed
pass 2  boot chains  : 14 records, 0 words typed, 0 comments added
        targets      : 0 references added, 0 dangling references repointed,
                       0 disassembled, 0 functions created
pass 3  banked calls : 0 repaired, 3 already correct, 4 skipped (data)
pass 4  inline tables: 0 defined, 45 already correct, 0 skipped
pass 5  prologues    : 348 sites, 0 created, 346 present, 2 deferred
pass 6  stub farm    : 281 slots, 0 references added, 0 comments added
```

Final: **1087 functions**, all originals intact, verified by an
address-and-name diff against a pre-run snapshot — zero lost, zero renamed.
346 of the 348 prologue sites now carry a function, against 204 before, and
all 281 stub slots carry a reference to the routine they stand for.

The first-run figures above were measured with pass 1 *absent* — that run is
what exposed the no-return flag, and it is the run that cost 61 functions.
With pass 1 in place the same work completes without any loss, and background
auto-analysis afterwards *adds* functions rather than removing them.

!!! warning "Diff-guard any bulk pass"
    `AGENTS.md` §11 requires a before/after `list_functions_enhanced` diff
    around anything that clears flow. That rule earned its keep here: the
    first run of this work, before pass 1 existed, cost 61 functions, and the
    diff is what made restoring them possible. Snapshot the function list
    before you start.
