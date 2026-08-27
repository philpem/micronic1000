# Review 2: cross-subsystem quality, comments, and AGENTS.md

*Second-opinion review agent, 2026-08-24. Read-only — no changes made
to the Ghidra DB or existing docs. Everything cited was re-checked
against the binary this session. Companion to
review-barcode-os-integration.md.*

Scope: (1) adjudicate the ExtBus*/"EXT STORAGE" re-identification made
in response to my first review; (2) technical spot-checks across the
other subsystems/docs; (3) a comment-quality review of the Ghidra
annotations; (4) review of AGENTS.md.

---

## 1. The re-identification: right instinct, wrong replacement

The retraction of the over-confident "barcode/light-pen" *labels* was a
defensible epistemic move. But the rewrite replaced one unproven
identity with another — **"wire 0x2B = EXT STORAGE ADAPTER" is asserted
in TASKS.md, barcode-reader.md, protocol-comms.md and (worst) in the
io:002d repeatable comment, and it is not just unproven, it is
contradicted by the firmware**:

1. **Storage traffic cannot flow through the 2D front end**, and the
   agent's own docs say so ("EXT STORAGE data transfers do NOT use this
   2D front-end"). A device whose *only* handler is an edge-width
   timer with no TX path cannot be a storage adapter.
2. **The storage devices live in the other table.** The external
   storage path (Disk* → 0A6D → `LinkTransportOpen` 2EAB) opens its
   wire from the **FE93** letter-indexed table (`DeviceTableIndex`
   31FF: index ≥ 'A' → FE93). FE93's non-RAM defaults are **0x73/0x72
   — bit6 set, real 4x transport devices**. The ROM01 menu complex
   agrees: the 5-entry pointer list at 757F (WORKSTATION MEMORY,
   WORKSTATION RAMDISK, PLINTH, V24 ADAPTOR, **EXT STORAGE ADAPTOR**)
   is the *storage-target* menu — EXT STORAGE ADAPTOR belongs with the
   letter/FE93/4x side, not with wire 0x2B. I found **no binding
   anywhere** from the string "EXT STORAGE ADAPTOR" to the byte 0x2B;
   if the agent has one, it should be cited at byte level.
3. **The console default refutes it.** FE83 entry 2 (console selector
   value 1) is **0xAB = bit7 (keyboard) + 0x2B**. "Keyboard mixed with
   ext-storage-adapter" as a *console input device* is absurd;
   "keyboard mixed with a scan wand" is exactly how a data-capture
   terminal works.
4. **The functional signature**: reject <9 elements, ~8-loop noise
   filter on the first element, bar/space width table, success beep,
   silent-retry on reject, and a pluggable hook whose contract is
   "turn a width table into a byte string" — that is a barcode reader
   front end. No storage protocol looks like this.
5. **External ground truth**: the owner states the machine's accessory
   set includes a barcode pen/wand and a wand-emulating CCD scanner
   gun on the side port, and Micronic's own patent (US 4,423,319)
   covers the optical-pen interface. Owner-supplied hardware facts are
   admissible evidence (AGENTS.md already honours "owner corrections"
   for the RTC and serial-EEPROM questions) — the ROM-strings-only
   standard applied here is stricter than the project applies anywhere
   else. Note the absence of "barcode" strings is expected under the
   project's own model: the ROM ships **no decoder** (the default
   fbc2 hook discards captures), so there is no UI for a feature that
   only exists once a customer DIP installs it.

**Recommendation:** keep neutral *mechanics* names if preferred
(`ExtBus*` is livable, though `EdgeCapture*` would say more), but
(a) delete every "= EXT STORAGE ADAPTER" claim (TASKS.md item,
barcode-reader.md header, protocol-comms.md §"corrected model", and
the io:002d repeatable comment — repeatable comments propagate to
every xref, so this error currently decorates 8 call sites);
(b) present "optical wand / barcode front end" as the **LIKELY**
interpretation (owner hardware + patent + functional signature),
not merely "a hypothesis"; (c) ask the owner to adjudicate whether
the `Reader*` names should return. This is the owner's machine; a
one-line answer settles it.

### Errors introduced by the rewrite itself

* protocol-comms.md / TASKS.md now say "Default FE83 =
  `{0xAB, 0x2B, 0x67, 0x67}`". Wrong: FE83 is **16 bytes**
  (`80 AB 63 43 | 80 2B 63 43 | 80 67 63 43 | 80 67 63 43`, source
  ROM00:3267), read through four selector windows of `fbc5`
  (console = entries 1-4, reader-channel = 5-8, punch = direct 1-16,
  list per BdosListOutChar). The quoted 4 bytes are just entries
  2/6/10/14. My first review printed the full table; the rewrite
  dropped it.
* barcode-reader.md §capture step 1 says the caller buffer pointer is
  **`fbc7`** — it is **`fbb7`** (fbc7 is the unrelated BDOS-F9 preset
  byte). One-character typo that sends a reader to the wrong variable.
* The completion-event follow-up (`LinkResetSession` 30BD does
  `fbc9 |= 1` and clears fdca) — **verified correct**, good close-out.

---

## 2. Technical spot-checks in other areas

### 2.1 BDOS dispatcher: the 25h-F2h/F3h description is inverted (real bug)

os-diposb.md ("25h-F2h: extended/wrapped table; ≥F3h rejected") and the
36A0 plate say the same. The code (36AE-36E7) does the opposite, and
something worse:

```
CP 0x25 / JR C,36e2    ; fn < 25h  -> valid F1EB table
CP 0xF3 / JR NC,36e1   ; fn >= F3h -> DEC B (B=FF) -> wrapped index
...specials 2D/2E/30/62/68/69...
(fall through)  36e1   ; fn 25h-F2h unmatched -> ALSO DEC B path!
36e2: HL = F1EB + 2*BC ; B=FF wraps: C=F3..FF lands on F1D1 (the
                       ; 13-entry extension table) — correct by design
```

So: **F3h-FFh are the valid wrapped extension table** (as the
programmer's guide correctly says), and **an unmatched fn in
25h-F2h is dispatched through a wild pointer** (e.g. fn 40h reads its
handler word from ~F06B — arbitrary kernel bytes). Nothing is
"rejected". Fix both texts, and document the hazard in the
programmer's guide: *calling an undefined BDOS function in 25h-F2h
jumps through garbage — do not probe for extensions by calling them.*

### 2.2 memory-map.md: FE83/FE93 rows are wrong

* "FE83 … 4×4B records `(0x80|flag, link-id, 'c','C')`, indexed by
  console-device slot ('a'-'p')" — FE83 is **16 independent one-byte
  wire ids indexed numerically 1-16** (31FF low branch); the
  'c'/'C' reading is 0x63/0x43 wire ids ASCII-fied, and the letter
  indexing actually belongs to **FE93** (`SUB 0x41` branch). The two
  rows have their indexing swapped and the "record" structure is an
  artifact of reading columns as fields.
* Same ASCII-fication in the FE93 row ("`{0,0x7F,'s','r'}`" — those
  are wire ids 0x73/0x72).

### 2.3 Small accuracy nits

* Both RST-dispatcher listings (memory-map.md §RST2,
  interrupts.md §banked-call) omit the `LD E,(HL)` at 0011 that loads
  the requested bank — as printed, E is never loaded and the listing
  doesn't work. (interrupts.md also has a stray 5-digit address,
  "0186C".)
* The pre-rewrite barcode-reader.md claimed the arm window uses
  `D=0xF8`; the byte is **0x18** (13DF). Moot after the rewrite, but
  symptomatic: several errors in this project (this one, the
  31F2/31F5 off-by-one, FE83-as-4-bytes) came from describing bytes
  from memory instead of re-reading them.
* gap-analysis.md (88/480 named, 18%) and TASKS.md ("593/593, 100%
  named") flatly contradict each other, and both are stale: the
  program now has **667 functions, 58 still `FUN_*`** (mostly
  ROM01 promoted gaps and RAM session modules — including
  `FUN_ram_f46d`, called by `SetActiveConsoleDevice`, and
  `FUN_ROM00_35c9`, the quiet-bus helper in the capture path).
  `FUN_ram_8c0c`, recorded in TASKS as "false positive — deleted",
  exists again (auto-analysis re-created it). Pick ONE coverage
  tracker, refresh it after every function-creation pass, and record
  the 8c0c situation so it stops resurrecting.

### 2.4 What is *good* (and should be the template)

* **rtc-investigation.md** is the best doc in the repo: byte-level
  claims, a live-capture trace cross-checking the static reading, a
  falsifiable rate calculation, and explicit open items.
* **protocol-comms.md**'s transport/frame sections and
  **os-diposb.md**'s ABI/loader sections are strong.
* Plates on `RtcWriteTime` (22AB), `TemplateBuilder` (ROM01:0271) and
  `KernelImage_BdosMain` (36A0, modulo §2.1) are exactly what a plate
  should be: purpose, mechanism, cross-references, why.

---

## 3. Comment quality in the Ghidra DB

### 3.1 Coverage is bimodal

Where the agent worked deliberately (RTC, link transport, BDOS
dispatch, boot), plates are good and EOL comments exist at the right
places (e.g. `31CA: HL = id table base (2B,2A,23,03,FF); IX =
handler-ptr table` — genuinely useful). Elsewhere, core functions have
**nothing**:

* `KeyboardReadChar` (18C0): no plate, no comments — yet it contains
  three things a reader cannot get from the mnemonics:
  `AND 0xFB` / `OR 0x04` on `fbc9` (clear/set the **keyboard event
  bit 2** of the event-pending byte), the key ring pointer `fbf0`,
  and `CP 0xCD / JP Z,3513` — **scancode 0xCD is a hotkey into
  MonitorEnter**. That last one is a discovery-grade fact sitting
  uncommented.
* `ExtBusAcquireEdge` (13B8): the most intricate routine in the
  subsystem — **zero inline comments**. It needs perhaps six:
  - `13BB LD (fbbd),SP / LD SP,fbb5` — *SP is repurposed as the
    width-table write pointer; widths are PUSHed downward from FBB3;
    real SP parked in FBBD* (classic Z80 trick, invisible otherwise —
    it is also *why* the table needs reversing later);
  - `13C9 LD C,4` — arm-window retries; `13D9` timeout → SCF = "no
    signal";
  - `13EA CP D` — width overflow at H=0x18 ends the capture;
  - `13FA SUB 8 / JR C,13bf` — first element <8 loops = noise,
    restart;
  - `140C CP 9 / RET C` — reject captures with <9 elements;
  - `1458-1467` — the hook dispatch: *BIT 7,H = resident? ;
    CP 0xD7 = target already a RST10 banked stub? else run the
    synthesized stub at fbc0*.
* `ExtBusComplete` (14A3) and `ExtDecodeHookDiscard` (1567) have **no
  plates**. For 1567 the missing one-liner is the single most
  important fact in the subsystem: *"default hook: zeroes the element
  count → every capture is discarded until software installs a real
  decoder at fbc2."*
* `RtcRegWrite` (22DB): the `OUT (0x28),A` EOL is good, but the
  indirect `OUT (C),B` with C=8 has no comment — precisely the
  indirected-port case AGENTS.md itself flags.

### 3.2 Stale plates after the mass rename (systemic)

The `Reader*` → `ExtBus*` rename did not touch the plates:
`ExtBusAcquireEdge`'s plate still opens **"ReaderEdgeDecode:
barcode/light-pen edge-timing decoder"**, and `ExtBusArm`'s still
opens **"ReaderArmRoute: arm the barcode/light-pen route"** — each
function now contradicts itself between name and header. Whatever the
naming outcome of §1, name/plate/docs must move together. (Also fix
the `LinkBlockTx` plate's confused tail: "See HD146818-style
register/bit naming … datasheet = Micronic 4x link transceiver" —
there is no such datasheet and the RTC reference is a copy-paste
artifact.)

### 3.3 What a good comment adds here (concrete house examples)

The test: *does the comment tell the reader something the opcode
doesn't?* Restating the operation fails ("put 14 into A"); decoding
flags, bits, magic numbers, idioms, and intent passes. Examples drawn
from this codebase, usable directly in AGENTS.md:

```
; -- branch/flag semantics: say what the branch MEANS --
CP   0x25
JR   C, use_table      ; fn < 25h: CP/M range -> F1EB dispatch table
SBC  HL,DE
JP   Z, arm_scan       ; ring empty (head==tail) -> arm a new capture
CP   B
JR   NZ, next_id       ; not this wire-id, try next table entry

; -- bit masks: name the bit, not the arithmetic --
AND  0xFB              ; clear kbd-event flag (fbc9 bit2)
OR   0x40              ; LINK_CTRL bit6: link online
AND  0x7F              ; strip kbd flag (bit7); low 7 bits = wire-id

; -- magic numbers: say where the number comes from --
CP   0x09
RET  C                 ; <9 elements: too short for a symbol, reject
CP   0xD7              ; D7 = RST 10h opcode: is target a banked stub?
LD   D, 0x18           ; width timeout: capture ends when H hits 18h

; -- idioms: one PRE comment saves an afternoon --
; SP is repurposed as the width-table pointer: each element width is
; PUSHed (grows down from FBB3); real SP saved at FBBD. This is why
; the table is stored reversed and un-reversed at 1415.
LD   (0xFBBD), SP
LD   SP, 0xFBB5

; -- computed control flow: name the destination --
PUSH HL                ; HL=1468: hook returns into the envelope-copy
JP   (HL)              ; tail-call the fbc2 decode hook
```

Anti-patterns to ban explicitly: `LD A,0x14 ; put 14h in A`;
`INC HL ; next byte`; comments that repeat the label
(`CALL LinkBlockTx ; call LinkBlockTx`); and *asserting identity in a
repeatable comment* (a repeatable propagates to every xref — it
carries the project's highest burden of proof, see io:002d).

### 3.4 Priorities

1. Fix the io:002d repeatable and the two stale ExtBus plates (§1,
   §3.2) — these actively mislead today.
2. Plates for `ExtDecodeHookDiscard`, `ExtBusComplete`,
   `KeyboardReadChar`, `BdosPunchOutChar`, and the fbc0/fbc1/fbc2
   cells (labels exist; the cells still have no comments — get_comment
   returns empty on all three).
3. Inline-comment pass over 13B8/12EC/1317/1443-14A2 per §3.1.
4. Then the 58 remaining `FUN_*` (start with `FUN_ram_f46d`,
   `FUN_ROM00_35c9`, and the ROM01 promoted gaps that block xref
   tracing).

---

## 4. AGENTS.md review

Strong foundation: the annotation philosophy ("ground claims; neutral
when unsure; a wrong name is a regression"), the port-label table, the
plate/EOL/PRE/repeatable breakdown, and the update-docs/save-program
discipline are all right. Recommended changes:

1. **Encode process, not conclusions.** The file currently hard-codes
   contested findings as standing rules ("Port 2Dh … NOT `Reader*`
   (unproven)"; "the 120F-14EE handlers stay `ExtBus*`"). If the owner
   confirms the barcode reading (§1), the rules file itself is wrong
   and must be edited — which is how the last whiplash happened.
   Keep in AGENTS.md only the durable rule ("identity claims carry a
   confidence tag; renames follow evidence via TASKS.md"), and point
   at TASKS.md for the current-identity list. AGENTS.md should almost
   never change; TASKS.md changes every session.
2. **Add an "external ground truth" section**: owner-supplied hardware
   facts (no serial EEPROM; 4x ≠ RTC; barcode wand/CCD-gun accessories
   exist on the side port; US 4,423,319) are evidence agents may cite,
   with the owner as the arbiter when ROM-internal evidence is silent.
   Without this, agents oscillate between over- and under-claiming.
3. **Rename hygiene rule** (missing, and §3.2 shows why): *a rename is
   name + plate first line + doc mentions + TASKS entry, in one pass;
   grep the docs for the old name before finishing.*
4. **Plate-required rule**: a function is not "named" until it has at
   least a one-line plate. (Prevents the ExtBusComplete/1567 gaps and
   makes the coverage tracker honest.)
5. **Comment examples**: replace the single LinkBlockTx example with a
   good/bad table like §3.3 — branch-meaning, bit-naming,
   magic-number, idiom, computed-flow examples, plus the explicit
   anti-patterns. This is the highest-leverage edit for the stated
   goal (human-readable disassembly).
6. **Repeatable-comment bar**: state that repeatables propagate to
   every xref and therefore carry only CONFIRMED facts; hypotheses go
   in the doc, not the repeatable.
7. **Byte-verification rule**: any table/offset claim in a comment or
   doc must come from a fresh `read_memory`/disassembly, not recall —
   and mind pre/post-increment when deriving table bases (the
   31F2/31F5 off-by-one and the FE83 "4 bytes" both came from this).
8. **Resolve the data-naming contradiction**: AGENTS.md prescribes
   Hungarian `g_bXxx`, but most existing labels are snake_case
   (`p2a_shadow`, `ext_decode_hook_ptr`, `comm_work_table`). Either
   convention works; the file should match the DB's reality (or
   declare the migration) so agents stop producing a mix.
9. **One coverage tracker**: name gap-analysis.md as canonical, delete
   the competing "100 %" claim style from TASKS, require a refresh
   after any pass that creates functions (§2.3).
10. Nits: the tool prefix is `mcp__ghidra__*`, not `ghidra-mcp_*`;
    "save periodically" could name an interval or "after every batch";
    and the AGENTS.md "errored column 0xFF03" example should say what
    the actual error class was (table-base off-by-one) so the lesson
    generalises.

---

## 5. Summary for the main agent

* Undo the "EXT STORAGE ADAPTER = 0x2B" assertions everywhere; ask
  the owner to adjudicate the barcode naming; meanwhile "optical
  wand front end, LIKELY" is the honest tag. Fix the FE83 4-byte
  regression and the fbb7/fbc7 typo.
* Fix the inverted 25h-F2h/F3h dispatcher description (os-diposb.md +
  36A0 plate) and document the wild-dispatch hazard.
* Fix memory-map.md's FE83/FE93 rows and the RST2 listings.
* Run the plate/inline-comment pass of §3.4; adopt the §3.3 example
  table; reconcile the coverage trackers.
* Apply the ten AGENTS.md edits — especially #1 (process over
  conclusions), #2 (external ground truth), #3 (rename hygiene) and
  #5 (comment examples).
