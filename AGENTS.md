# AGENTS.md — Micronic 1000 reverse-engineering

Instructions for AI agents working on this repository. The goal is to
**reverse-engineer the Micronic 1000 (PARCON 1000) handheld's DIPOS-B
operating system from firmware ROM dumps** so that a human can read the
disassembly and understand what each piece does, *why*, and in what
context.

Your job is **annotation, not reconstruction**. The deliverable is a
Ghidra database in which every function, label, data structure, I/O
access and comment reflects what the bytes actually do, plus the
write-ups in `doc/`. There is no C source to produce and no
recompilation step. Do not write reconstructed C unless explicitly
asked.

This file records **durable process rules**. Current findings, open
questions, and the identity of contested subsystems live in
`doc/research/TASKS.md` and the `doc/` write-ups — those change every session;
this file should almost never change. When a finding is revised, edit
TASKS.md and the docs, not this file.

---

## 0. Opencode platform usage

### Subagents

When using reverse-engineering subagents:

- Use `investigate` for ordinary binary analysis.
- `investigate` intentionally has no configured model: it inherits the primary
  session model selected with `/model` or the model-selection key binding.
- Use `investigate_deep` only for difficult, ambiguous, cross-cutting, or
  unresolved questions.
- Treat subagent conclusions as proposals until their supporting evidence has
  been considered.
- Before annotating a consequential new or revised finding, invoke a reviewer
  from a different model family: `review_openai` for Anthropic work, and
  `review_anthropic` for OpenAI/DeepSeek work. Consequential findings include
  semantic renames, hardware identities, calling conventions, computed-table
  mappings, overturned findings, and promotion to CONFIRMED.
- If a subscription-backed deep investigator or reviewer fails because of
  authentication, quota/rate limiting, timeout, provider outage, model
  unavailability, or a 5xx response, retry the unchanged task with
  `investigate_deep_openrouter_fallback` or `review_openrouter_fallback`.
  Do not use availability fallback for weak analysis, refusals, context-length
  errors, malformed requests, or tool/schema errors.
- If review returns REVISE, REJECT, or UNDERDETERMINED, send the disputed
  claims and review evidence to `investigate_deep`. Resolve disagreements by
  returning to the bytes, never by model majority vote.
- Do not ask `annotate` to commit speculative findings.
- Only send the parent-adjudicated, reviewer-approved safe scope to `annotate`.
- Preserve uncertainty in annotations where the evidence remains tentative.
- Use `general` for routine delegated work, not substantive binary analysis.

---

## 1. Repository layout

- `micronic/micron1.bin`, `micron2.bin` — the two ROM dumps. Loaded in
  Ghidra as one program (`micron1.bin`, project `micronic1000`) with
  three address spaces used throughout: `ROM00`, `ROM01` (overlays of
  the banked window), and `ram` (battery-backed RAM incl. the resident
  kernel). All work happens in that program. Pass the `program` arg
  (`micron1.bin`) explicitly on MCP calls that take it.
- `micronic_notes.md` — the owner's hardware spec notes (Z80 @
  3.579545 MHz, 256K SRAM, 2×27C256, HD61830 LCD, HD146818 RTC, port
  positions, power). Owner-supplied facts; cite as such.
- `doc/` — the write-ups (see `doc/README.md` for the index). **Update
  these in the same pass as any Ghidra change they describe.**
  `doc/build.py` renders `site-html/` (`cd doc && python3 build.py`,
  see `doc/BUILD.md`; Mermaid blocks render JS-side).
- `analysis/` — Python/Java tooling (protocol scripts, boot-chain
  decoder, emulator harness); has its own README.md.
- Ghidra is reached through MCP tools (`ghidra-mcp_*` in this
  environment: `decompile_function`, `disassemble_function`,
  `read_memory`, `get_xrefs_to`, `rename_function_by_address`,
  `set_plate_comment`, `set_comment`, `create_label`, `save_program`,
  …). The `annotate` subagent (see opencode.json) applies
  already-decided findings to the DB — it must not do new inference.

---

## 2. Ghidra is the memory, not the conversation

Every fact you establish must be written into the Ghidra database **in
the same turn you establish it**: a rename, a plate comment, a
pre/EOL comment, a data type, a label, or a bookmark for anything
unresolved. If the session is compacted or restarted, the Ghidra
database plus `doc/` are the *entire* state; anything held only in
conversation is lost.

Before you write "as established earlier", check that it is actually in
the database or a doc. If it isn't, put it there. Save the program
after every batch of changes, and always at the end of a session.

The MCP disassembly listing does not always render equates/labels
inline; the Ghidra GUI does. Set them anyway — the database is
authoritative, not the tool output.

---

## 3. Evidence discipline

This project labels every claim with one of the established tags —
in docs, in plate comments, and in replies:

- **CONFIRMED** — read directly from the bytes, the disassembly, or an
  xref. State where: "CONFIRMED: writes 0x46 to RTC Reg B at
  ROM00:22DF."
- **LIKELY** — an era convention, datasheet behaviour, or owner-supplied
  hardware fact *combined with* something observed. State both halves.
- **SUSPECTED** — plausible, unverified. Must be paired with the
  specific observation that would confirm or refute it.

Rules:

- Never promote SUSPECTED → LIKELY → CONFIRMED without going back to
  the bytes.
- Never let a SUSPECTED claim in one function become a silent premise
  in the analysis of another. If you catch yourself relying on an
  unlabelled assumption, stop and label it.
- **Rejecting one unproven identity does not license asserting a
  different unproven identity.** "Unknown, two candidates, here is the
  discriminating test" is a better deliverable than a confident wrong
  answer — and this project has been burned in both directions
  (over-claiming "barcode" labels, then over-correcting to an equally
  unproven "ext storage" identity).
- **Byte-verify every table/offset claim** with a fresh `read_memory`
  or disassembly before writing it into a comment or doc — never from
  recall. Mind pre/post-increment when deriving table bases: the
  31F2/31F5 handler-table off-by-one and the "FE83 is 4 bytes" error
  both came from skipping this.
- **Repeatable comments carry only CONFIRMED facts.** A repeatable on a
  port or data cell propagates to every xref, so it carries the
  project's highest burden of proof. Hypotheses go in the doc or a
  plate, clearly tagged.
- Strings are not proof of behaviour: a string near a routine is not
  evidence of what the routine does — and the *absence* of a string is
  not evidence a feature doesn't exist (features whose support arrives
  in loaded software leave no ROM strings).

### External ground truth (owner-supplied hardware facts)

The owner has the hardware. Facts they supply are admissible evidence
(cite them as such) and they are the arbiter when ROM-internal evidence
is silent. Currently on record:

- The 08h/28h indexed pair **is** the HD146818 RTC; the 4Ah-4Fh cluster
  is **not** the RTC (confirmed twice).
- There is **no serial EEPROM**; the serial number is user-entered
  after battery removal and lives in battery RAM (FEAB area).
- **The 5-pin side port was used with a barcode pen** (documentary
  evidence, owner-confirmed 2026-08-24), and the edge-timing capture
  code is consistent with nothing else on the hardware. The port-2D
  subsystem is therefore adjudicated the **barcode reader front end**;
  use the `Barcode_` module prefix for new names there. Micronic's US
  patent 4,423,319 covers the optical-pen interface; a wand-emulating
  CCD scanner gun also exists.
- The two IR ports are physically: **V24 ADAPTOR = top port, PLINTH
  = back port** (owner-stated 2026-08-24; this supersedes the earlier
  "bottom/front" wording in `micronic_notes.md` and internals/os-diposb.md,
  both corrected on that date). Firmware selects between the two 4x
  port configurations by wire-id bit5 (LinkBlockTx `AND 0x20` →
  LinkPortSelect, byte-verified); which bit5 value is which physical
  port is still OPEN — needs a hardware test.
- The **EXT STORAGE ADAPTER's attachment point is not yet adjudicated**
  — do not bind it to a wire-id or port until the owner confirms.
  What is CONFIRMED: all drive-C:+ storage I/O runs over the 4x byte
  transport (never the 2D edge input), so it must connect via one of
  the two IR ports; default FE93 storage wires are C:=0x73, D:=0x72
  (both bit5=1, same port, adjacent unit addresses).
- The main power source is 4×AA with a lithium coin cell for RAM
  retention.

When ROM evidence and an owner statement seem to conflict, report the
contradiction — do not invent a mechanism to reconcile them, and do not
silently drop either side.

---

## 4. When the owner tells you you're wrong

Assume the error is upstream of where they pointed. In order:

1. Identify the rejected claim and find where it entered the analysis.
2. List every conclusion that depended on it — including anything
   already written into Ghidra or the docs.
3. Discard those conclusions rather than patching them. Revert or amend
   the Ghidra names/comments and doc text that carried them.
4. Re-derive from the bytes, not from your previous reasoning.
5. Say explicitly what you discarded.

Do not defend the original claim or restate it in different words. If
you think the owner is mistaken, say so once, with byte-level evidence,
then follow their direction. And do not over-correct: replacing the
rejected claim with a new unproven one is the same failure with a
different name (see §3).

---

## 5. Z80-specific analysis rules

Ghidra's Z80 support is serviceable for disassembly and poor for
decompilation. **The decompiler is a hint, never evidence.** Do not
quote decompiler output as a finding — verify against the listing
(several past errors here came from trusting decompiled parameter
flow). Places auto-analysis gets this firmware wrong; check each by
hand:

- **Inline data after RST/CALL.** The banked-call restart takes inline
  operands: `RST 10h / DB bank / DW target` (dispatcher at 0010 does
  `POP HL / LD E,(HL)…`). The deferred-call queue is built of the same
  4-byte `{D7,bank,addr}` stubs, and the decode-hook dispatcher
  recognises them by `CP 0xD7`. Ghidra will disassemble inline
  operands as instructions and invent bogus functions: clear and
  re-type them at every call site, and record the convention in the
  callee's plate.
- **Restart vectors.** All are kernel entries here (see
  doc/internals/memory-map.md §page zero): 0008 → JP F180 (BDOS dispatch),
  0010 → JP F5E1 (banked-call dispatcher), 0020 → JP F5EA,
  0028 → JP F5ED, 0030 → JP F5F0, 0038 → JP F5F3 (doubles as the
  IM 1 IRQ entry), NMI at 0066 → JP F5F6. Keep them labelled in
  *both* ROM banks (and in ram: BankedRst*Stub labels, byte-verified
  2026-08-25).
- **Computed jumps.** `JP (HL)` / `JP (IX)` dispatch is everywhere
  (BDOS tables F1EB/F1D1, LinkCommandLookup, the fbc2 hook, UI
  vtables). Find the feeding table, define it as data, add manual
  references from the jump to each target, and record the
  index → handler mapping in the dispatcher's plate.
- **Self-modifying / RAM-resident code.** The kernel and session
  modules are copied to battery RAM and some trampolines self-patch
  (ram:D79C area). Comment both the writer and the modified
  instruction, and cross-reference them.
- **Banking.** Already modelled: `ROM00`/`ROM01` overlays over the
  banked window, selected by port 47h (shadow F791). Never analyse
  banked addresses in a flat space; when quoting an address, include
  the space (`ROM01::7A1B`, `ram:fbc2`).
- **Alternate register set / EXX** in a routine is strong evidence of
  an interrupt handler or context switch (the coroutine machinery at
  ram:D837 uses SP/IX/IY switches) — note it in the plate.
- **Stack tricks.** This firmware repurposes SP as a data pointer
  (e.g. the edge-capture width table: `LD (fbbd),SP / LD SP,fbb5` then
  PUSH per element) and makes calls by pushing a return address before
  `JP (HL)`. These are exactly the idioms a PRE comment exists for.
- **Undocumented opcodes** (`SLL`, IXH/IXL/IYH/IYL): verify Ghidra
  decoded a DD/FD prefix rather than silently misdisassembling.

---

## 6. Calling conventions

Z80 code of this vintage has no single convention. For every function
you annotate, record in the plate comment:

- **In:** registers carrying arguments and their meaning
- **Out:** return registers; what carry/zero mean on exit
  (carry-set-on-error is common here but verify per function)
- **Clobbers / Preserves:** when it matters to callers

Set the Ghidra signature to match where the storage model allows, but
the plate is authoritative. Verify the convention at **at least one
call site**, not just inside the callee.

---

## 7. Naming conventions

### Functions

- **PascalCase, prefixed with the module/area and an underscore** for
  all *new* names (owner's preference): `BDOS_ReaderInChar`,
  `Barcode_AcquireEdge`, `Link_BlockTx`, `RTC_RegWrite`,
  `Session_RxWaitFrame`, `UI_FieldListRender`. Pick the module prefix
  from the established subsystem set (BDOS, Link, Session, RTC, Clock,
  LCD, Kbd, Disk/Fs, Device, UI/Field, Diag, Syscall, and `Barcode`
  for the port-2D capture front end — adjudicated barcode reader, §3;
  existing `ExtBus*` names are grandfathered); check
  `search_functions` before inventing a new one.
- Existing concatenated names (`LinkBlockTx`, `BdosReaderInChar`, …)
  are **grandfathered — do not churn them**. The owner may do a
  repo-wide rename pass to the `Module_Name` style at the end; until
  then both styles coexist and a rename is only justified when the
  *meaning* changes.
- Leave `FUN_*` on anything you have not actually analysed — it must
  stay obvious what is untouched. Explicit stubs get explicit names
  (`SessionOpStub_<addr>`).
- **Do not mass-rename on pattern matching alone**, and do not encode
  an unproven identity in a name: prefer a mechanics name
  (`ExtBusAcquireEdge`, `EdgeCapture*`) plus a tagged comment over a
  speculative identity name. The current identity of contested
  subsystems is recorded in `doc/research/TASKS.md`, not here.

### Rename hygiene (a rename is not just a rename)

A rename is: the symbol + the plate's first line + every doc mention +
the TASKS.md entry, **in one pass**. Grep `doc/` for the old name
before you finish. (The `Reader*`→`ExtBus*` rename left plates that
still contradicted their own function names — do not repeat that.)

### Plate-required rule

A function is not "named" until it carries at least a one-line plate.
Naming without a plate is half-done work and makes the coverage
tracker lie.

### Data / RAM cells / constants

- **UPPER_SNAKE is reserved for I/O ports and constant values**
  (port labels like `LINK_CTRL`, equates/enum members for register
  bits and magic constants). Do not use it for functions or RAM
  variables.
- Shared-state RAM cells get lowercase labels. Established practice is
  mixed (`g_bBankShadowP47`, `p2a_shadow`, `ext_decode_hook_ptr`);
  existing names are grandfathered. For **new** labels use: `g_`
  prefix for RAM globals (optionally with the `b/w/ab/p/s` type
  letter), `tbl_` for ROM tables, `str_` for strings, and only name
  what the code provably is.

### I/O ports

Each physical port is labelled at its `io:NN` address with an
UPPER_SNAKE peripheral-based name (never address-based), carrying a
**repeatable comment** describing the signal (CONFIRMED facts only —
§3). Canonical table:

| Port | Label | Device / function |
|------|-------|-------------------|
| 00h | `KBD_SENSE` | keyboard matrix sense (read) |
| 02h | `KBD_DRIVE` | keyboard matrix drive/column (write) |
| 03h | `LCD_DATA` | LCD data byte |
| 04h | `OUT_LATCH` | output/power latch (shadow F784) |
| 05h | `STATUS_IN` | status/boot-key byte |
| 07h | `CTRL_07` | control latch |
| 08h | `RTC_ADDR` | RTC address latch (HD146818) |
| 23h | `LCD_REG` | LCD register/command select |
| 28h | `RTC_DATA` | RTC data (HD146818) |
| 2Ah | `CTL_LATCH_2A` | peripheral control latch |
| 2Bh | `SOUND` | beeper/sounder |
| 2Ch | `CTL_LATCH_2C` | control latch |
| 2Dh | `EXTBUS_EDGE` | edge/level input for the 2A/2B-wire capture front end (barcode reader, §3) |
| 46h | `LCD_CONTRAST` | LCD contrast DAC |
| 47h | `BANK_SEL` | 32K bank select (shadow F791) |
| 48h | `LCD_STROBE` | drive/sense strobe (with 49h) |
| 49h | `BOOTKEYS` | boot-key/probe sense (with 48h) |
| 4Ah | `LINK_CTRL` | 4x external-link control latch (shadow F794) |
| 4Bh | `LINK_STATUS` | link status (ready/ACK/RX phase) |
| 4Ch | `LINK_CMD` | link command/ACK (0x81) |
| 4Dh | `LINK_TXD` | link TX data byte |
| 4Eh | `LINK_RXD` | link RX data byte |
| 4Fh | `LINK_PROBE` | device probe/reset (0x1F) |

Use **datasheet names** for chip registers/bits where a datasheet
exists (HD146818 Reg A `DV`/`RS`, Reg B `PIE`/`SET`/`24h`; HD61830).
Once a port's bits are identified, define an enum/equate set and apply
it at every access site so the meaning survives without re-derivation.
For indirected access (`OUT (C),r`), comment the instruction that loads
the port number into C.

---

## 8. Comment style

Ghidra comment kinds, used deliberately:

- **Plate** (function header): what/why/context. One-line purpose
  first, then In/Out/Clobbers (§6), side effects, notable callers,
  cross-refs, evidence tag. Ignore the `set_plate_comment` tool's
  warnings about Algorithm/Parameters sections.
- **EOL**: short, one fact, ≤ ~60 chars, only where the instruction
  alone doesn't tell the story.
- **PRE**: any explanation longer than one line — bit lists, state
  notes, idioms, why. Wrap ~70 cols, one fact per line.
- **Repeatable** (data/ports): ONE short sentence, ≤ ~60 chars —
  the description that should appear at every xref. CONFIRMED facts
  only; any detail beyond one sentence goes in a PLATE comment at the
  same address, not in the repeatable. (Owner correction 2026-08-25:
  long repeatables/EOLs on the stub farms violated this — fix pattern:
  short repeatable + long plate at the same address.)

**The test for every comment: does it say something the opcode
doesn't?** Restating the operation fails. Decoding flags, bits, magic
numbers, idioms, and intent passes.

```asm
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
RET  C                 ; <9 elements: too short, reject capture
CP   0xD7              ; D7 = RST 10h opcode: target already a banked stub?
LD   D, 0x18           ; width timeout: capture ends when H hits 18h

; -- idioms: one PRE comment saves an afternoon --
; SP repurposed as the width-table pointer: each element width is
; PUSHed (table grows down from FBB3); real SP parked at FBBD.
; This is why the table is stored reversed and un-reversed at 1415.
LD   (0xFBBD), SP
LD   SP, 0xFBB5

; -- computed control flow: name the destination --
PUSH HL                ; HL=1468: hook returns into the envelope-copy
JP   (HL)              ; tail-call the fbc2 decode hook
```

Anti-patterns (never write these):

```asm
LD   A, 0x14           ; put 14h in A            <- restates the opcode
INC  HL                ; next byte               <- says nothing
CALL LinkBlockTx       ; call LinkBlockTx        <- repeats the label
```

…and never assert an unproven identity in a repeatable comment (§3).

### Plate template (copy the skeleton)

```
<One-line purpose — imperative or declarative.>
<2–4 lines of mechanics: cells/ports read+written, the key algorithm
  step. Wrapped ~70 cols. No pseudo-asm, no caller list.>
In:   <registers / stack args and their meaning>
Out:  <return + flag contract, e.g. "HL=1 if HL<=DE" / "carry set on err">
<Clobbers: … — only when a caller cares>
CONFIRMED: <entry>-<end>.   (or LIKELY / SUSPECTED + one-phrase why)
```

Re-flow prose to ~70 cols, one fact per line, never hand-wrap mid-token.
Plates MUST be multi-line ASCII with real newlines — never one squashed
line. Structure: **brief** one-line purpose, **longer** description
(mechanics/why), then **Input / Output / Clobbers**, each on its own line,
then the evidence tag.

SHORT form — for trivial functions whose whole contract fits one sentence,
a single descriptive line is allowed instead of the full In/Out/Clobbers
block. Example: `Lib_SignedLe16` = "Signed 16-bit less-or-equal (EX DE,HL
into SignedGe16)" + repeatable "HL=1 if HL<=DE (signed) else 0".

LABELS, not addresses: do not cite a RAM cell or I/O port by its numeric
address in a comment. Give it a descriptive label and mention the label —
e.g. "clear g_bLinkActive" not "clear fbc9 bit0"; "read g_sessionResultW"
not "read e681". If the cell has no label yet, create one before
reference.

### Reusable "comment this code" prompt

Paste this block into any agent doing a commenting pass, after the list
of target functions. It encodes the rules above so you don't restate them.

---
Annotate Z80 disassembly in this project's Ghidra program. For each target
function write ONLY comments that add meaning:

1. PLATE (function header), multi-line ASCII with real newlines, wrapped
   ~70 cols (NEVER one squashed line). Structure: brief one-line purpose,
   then a longer mechanics/why description, then In:/Out:/Clobbers:, then
   the evidence tag line (CONFIRMED <entry>-<end> byte-verified, or
   LIKELY/SUSPECTED with a reason). NO pseudo-asm restatement, NO caller
   list. SHORT form (a single descriptive line, no In/Out/Clobbers) is
   allowed only for trivial functions whose contract fits a sentence.
2. EOL: at most ONE line (<=60 chars), only where the instruction alone
   doesn't convey the MEANING — name the bit, the magic number's source,
   or the branch's significance. Never restate the opcode.
3. PRE: an explanation spanning several instructions (idiom, stack/pointer
   trick, multi-register dance) — multi-line, wrapped, says WHY.
4. Magic numbers and bit masks MUST be decoded in place ("0x25 = error
   code, short buffer"; "bit5 = port select"), never left as bare hex.
5. LABELS, not addresses: never cite a RAM cell or I/O port by its raw
   numeric address in a comment. Use (or propose) a descriptive label and
   mention the label — e.g. "clear g_bLinkActive" not "clear fbc9 bit0".
6. If a cell/register meaning is only guessed, tag it LIKELY/SUSPECTED;
   never claim CONFIRMED for an unverified identity.

Avoid (all restate the opcode or say nothing):
  LD A,0x14  ; put 14h in A
  INC HL     ; next byte
  CALL x     ; maybe does a thing
---

## 9. The DIPOS-B / CP/M layer

DIPOS-B exposes a CP/M-2.2-style interface but is **not** stock CP/M —
standard CP/M structure is a *starting hypothesis* to verify, never a
fact to assume. The established picture is in `doc/internals/os-diposb.md`,
`doc/internals/cp-m-comparison.md` and `doc/manual/programmer-guide.md`; read
them before touching BDOS code. Deviations from stock CP/M (RAM
"disks", device-routed console, the F3-FF extension table, the banked
RST 10h call, the unchecked 25h-F2h dispatch) are among the most
interesting findings — call them out explicitly rather than smoothing
them into the standard name.

---

## 10. Unknown hardware — structured elimination, not a favourite guess

When you hit an I/O port or RAM region with unknown function:

1. Record every access: address, direction, value/mask, surrounding
   control flow (→ `doc/internals/io-map.md` / `doc/internals/memory-map.md`).
2. Characterise the access **pattern** before naming anything:
   init-time single write, polled spin loop, bit-test status, byte
   stream, handshake pair, edge timing.
3. Enumerate candidate peripherals plausible for a Z80 handheld of this
   era and score each against the pattern.
4. State the **discriminating observation** for the top two candidates.
5. If the ROM alone cannot discriminate: write both candidates into the
   doc as SUSPECTED, bookmark it in Ghidra, add it to the open items in
   `doc/research/TASKS.md`, and move on. **The owner can test on hardware. Do
   not pick one to keep the narrative moving.**

This procedure is how the RTC was correctly separated from the 4x link
cluster; skipping it is how the port-2D front end got two wrong
identities in a row.

---

## 11. Working loop and efficiency

Work one function or one hardware question at a time:

1. State the target and what you expect to learn.
2. Gather: disassembly, xrefs in/out, strings/tables it touches.
3. Form hypotheses and tag them (§3).
4. Verify against bytes — including at least one call site.
5. Write everything into Ghidra and the affected docs, same turn.
6. Report what's done and what's open.

Efficiency:

- Don't re-read a function you've annotated — read your own plate.
- Batch related MCP queries instead of round-tripping one xref at a
  time.
- Prefer following a concrete call chain over breadth-first sweeps.
- If you've made ten tool calls on one function without a taggable
  conclusion, stop and report where you're stuck.
- Check `doc/research/TASKS.md` and `doc/research/gap-analysis.md` for what's next
  before starting ad-hoc exploration.
- **Clear-flow repairs must be diff-guarded.** `clear_flow_and_repair`
  follows flow beyond the seed and silently deletes real functions
  (it cost 14 functions, incl. 4 named, on 2026-08-25; recovered with
  a before/after `list_functions_enhanced` diff). Procedure: dump the
  function list before and after, diff by space/address/name, restore
  every loss with `create_function` + the surviving symbol, and save
  promptly — deferred auto-analysis will otherwise re-pollute the
  range on its own schedule.
- **Serialize Ghidra-write agents; save between them.** Parallel agent
  rounds with MCP bursts cost ~124 in-memory functions on 2026-08-26
  (client-side timeouts executing server-side + AAM churn). Run ONE
  Ghidra-writing agent at a time, `save_program` after each, and if
  `get_function_count` drops unexpectedly mid-session STOP: do not
  save, exit without saving, and reopen the last disk state (the
  conversation log holds enough to re-apply anything decided later).

---

## 12. Docs, coverage, and session log

The `doc/` files are the notes system — do not create parallel files:

- `doc/internals/io-map.md` — port table with evidence labels (the IO_PORTS log)
- `doc/internals/memory-map.md` — ROM/RAM/banking + system variables
- `doc/research/TASKS.md` — worklist, open questions (each with the observation
  that would resolve it), session log, "do not regress" list, and the
  **current-identity list for contested subsystems**
- `doc/research/gap-analysis.md` — the **single canonical coverage tracker**.
  Refresh it after any pass that creates or renames functions; do not
  keep competing "%-named" claims in other files.

At the end of every session: update the docs touched, append a short
session entry to TASKS.md (what was analysed, concluded, overturned),
rebuild the site with `mkdocs build` (or `cd doc && make build`), and
save the Ghidra program.

---

## 13. Things not to do

- Do not trust strings, labels, or apparent structure as proof of
  behaviour — in either direction (§3).
- Do not reconcile contradictory evidence by inventing a mechanism;
  report the contradiction.
- Do not produce reconstructed C.
- Do not mass-rename on pattern matching alone; do not rename without
  updating plates and docs in the same pass (§7).
- Do not describe what a routine "probably" does without a SUSPECTED
  tag.
- Do not summarise the overall architecture beyond what CONFIRMED
  findings support — premature architecture narratives are the main
  way wrong assumptions get entrenched.
- **Emulator runs are a memory hazard on this 2 GB box** (OOM-killed
  the opencode process tree 2026-08-24): keep the boot-harness I/O log
  bounded (done), run only one emulator process at a time, always
  under `timeout`, and never start a long run while Ghidra + opencode
  are already resident. The harness's `gc.disable()` is load-bearing —
  collect manually in the slice loop, not by re-enabling gc.

### Do not regress (owner-confirmed, durable)

- 08/28 device **is** the HD146818 RTC: keep `Rtc*` names. The 4x
  cluster (4A-4F) is the external data link: keep `Link*` names.
  Neither is "comms"/modem-indexed-register hardware.
- No serial EEPROM; serial number is user-entered, stored near FEAB.
- RST vector roles (0010 banked dispatch, 0038 IRQ, 0066 NMI) as
  documented in internals/memory-map.md.
- Port-2D capture subsystem identity is **CLOSED**: it is the barcode
  reader front end (owner-adjudicated 2026-08-24, §3); new names there
  take the `Barcode_` prefix. Existing `ExtBus*` names in the DB are
  grandfathered — do not flip them to `Reader*` or to the disproven
  "EXT STORAGE ADAPTER" identity; check TASKS.md's do-not-regress
  list and §3 before any rename pass in this area.
