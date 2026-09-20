# Review: from reverse-engineering record to programmer's manual

## Implementation status — 2026-09-20

The accuracy and editorial findings below have been addressed: monitor and
restart corrections, COM explanation, malformed tables, stale status and
index descriptions, duplicated format specification, status vocabulary,
pointer scope, scratch ownership, and checksum-provenance wording.

The storage follow-up **overturned the evidence page's local-only claim**:
fresh tracing shows BDOS `2Eh` reaches session transport. The initial
review deliberately flagged the contradiction rather than adopting either
side. Current docs now distinguish default IDs, firmware routing, and
unverified successful peer operations. The old 32/224 KiB A:/B: capacity
split and the speculative loaded-software reconciliation are withdrawn.

Provisional API cards explicitly identify unspecified contracts instead of
inventing clobbers, error sets, or blocking bounds. Physical interoperability
and the unresolved routed-storage contracts remain research questions, not
documentation claims. Rendered-output/PR checks and a first-program example
are the next implementation batch. The dated findings below are the
review-time record, not an additional current worklist.

## Documentation review — 2026-09-20

### Scope and assessment

This pass reviewed accuracy, consistency, information architecture, reader
tasks, terminology, rendering, links, and publication checks. It inspected
the manual/reference pages, their supporting evidence and research records,
the MkDocs configuration, generated HTML, and the reported live memory-map
page. It is not a byte-level re-audit of every firmware claim or a complete
browser/accessibility test. New byte checks were concentrated on the COM
ceiling, monitor entry/callers, and restart-vector contradictions.

The principal problem is **corrections not reaching every summary**. The
manual/reference/evidence/archive split is useful, but the same facts are
still copied into several pages and then revised independently. A reader
can follow a valid link and reach a contradictory answer. Existing
annotation coverage measures names and plates, not this consistency.

Firmware corrections below received an independent same-provider review;
the cross-provider reviewer was unavailable in this tool set. Reads used
Ghidra's `micron1.bin` explicitly. No emulator workload was run in this pass.

### P1 — accuracy findings

1. **Built-in monitor claim is false for the documented entry — corrected.**
   [OS internals](re-notes/os-diposb.md#debug-facilities) inferred a monitor
   from a prompt and a function name. **CONFIRMED:** `ROM00:3513` is
   `AF C9`, or `XOR A; RET`. The M/Z error path calls it and returns;
   the conditional cold-boot call continues at `ROM00:0299`. The saved
   word at `ram:FEF8` is stacked AF, not DE:BC. Removed the built-in
   monitor, service-key menu bypass, and incorrect saved-context claims
   from the current docs and Ghidra comments. An external monitor/ICE
   purpose remains **SUSPECTED**, requiring alternate-ROM or debugger
   evidence; there is no demonstrated handoff protocol to describe.

2. **COM limit is correct, but its mapping was unexplained — corrected.**
   **CONFIRMED:** startup sets the exclusive ceiling to `D081h`, the
   start of resident Workstation module B. The COM loader subtracts
   `0100h` plus the initial chunk from that ceiling. Its total capacity
   is `CF81h` = 53,121 bytes: 32,512 in the selected lower bank and
   20,609 in shared upper RAM. No individual RAM page is larger than
   32 KiB. Added the explanation below the error table in
   [Program formats](reference/program-formats.md#why-the-ceiling-is-d081h)
   and linked the byte-level derivation. Distinguish image capacity from
   free workspace; an image can consume the suggested resident-hook area.

3. **Restart-vector prose contradicts the bytes — corrected.**
   [Interrupts](re-notes/interrupts.md#maskable-irq-fully-decoded) and
   [OS internals](re-notes/os-diposb.md#3-rst-trampolines) shifted BDOS
   to `0008` and described `0010` as a jump to `F5E1`. **CONFIRMED:**
   both ROMs have `0005 -> F180`, `0008 -> F5E1`, and inline code at
   `0010`. The initial kernel image sends `RST 28h` to `F57E` and
   `RST 30h` to the returning stub, so the assertion that all four
   `RST 20h/28h/30h/38h` entries are IRQ-style event polling is also
   withdrawn. Initial vector contents and runtime patches must remain
   distinct in any further analysis.

4. **The supported profile is stale — outstanding.**
   [Supported profile](manual/supported-profile.md#excluded-from-the-portable-profile)
   says the barcode hook contract is incomplete and RECORD/BLOCK grammar
   remains open; [Barcode reference](reference/barcode.md#stability)
   calls the hook contract measured and stable, while
   [Commstar](protocol/commstar.md#scope-and-implementation-status)
   documents recovered formats and bidirectional emulator transfers.
   The profile can deliberately exclude advanced APIs, but should say
   that is a support policy rather than missing evidence. Replace its
   obsolete transfer/provider explanation with the current physical-link
   blockers. Likewise, the home page still says wire modulation, framing
   and timing are uncaptured, while Commstar reports an outbound capture.
   These are confirmed textual contradictions; this review does not
   independently revalidate the underlying experiments.

5. **Storage guidance conflicts with the current investigation — outstanding.**
   The programmer guide presents A:/B: as two usable local stores and
   C:+ as configurable link devices. [Open questions](re-notes/open-questions.md#link-identity-and-port-selection)
   reports that all fourteen drive-ID consumers reject nonzero IDs,
   including the default B: ID `7Fh`. Treat that as a conflict requiring
   adjudication, not permission to invent how a RAMDISK or external drive
   works. Publish one table distinguishing selectable letter, configured
   ID, demonstrated file operations, and unresolved behavior. Propagate
   the outcome to the guide, devices page, method page, and worklist.

6. **Resident-memory advice contains superseded reasoning — outstanding.**
   [Memory map](reference/memory-map.md#32-fixed-ram-8000-ffff) calls
   `F68D-F77F` the remainder of a round `600h` kernel arena; the
   [unbanked-RAM evidence](re-notes/unbanked-ram-map.md) explicitly rejects
   that explanation. Its scratch guidance is also more qualified than
   the reference's recommendation of `C000-D080`: this span may be part
   of the loaded application image. Carry the ownership/image-size
   condition directly into every recommendation, and link to the current
   tests instead of repeating an old causal explanation.

7. **Universal pointer rule overstates the actual limitation — outstanding.**
   [Memory map §2.5](reference/memory-map.md#25-the-rule-and-two-independent-corroborations)
   says every argument, buffer, or callback across a bank boundary must
   be at least `8000h`, but immediately describes the bank-aware BDOS DMA
   bounce path. The barcode socket also explicitly carries a bank plus
   target. Scope the rule to a plain pointer dereferenced under a
   different mapping without bank-aware handling. List each API's
   actual pointer contract rather than imposing a universal prohibition.

### P2 — rendering and publication findings

**Six malformed table blocks were confirmed in generated HTML and fixed:**

| Page | Table | Defect |
|---|---|---|
| Memory map | Banked memory model | Three headers, four separator cells |
| Memory map | Patching dispatch tables | Four headers, five separator cells |
| OS internals | Patching dispatch tables | Four headers, five separator cells |
| Programmer guide | DIP header | No header/separator row |
| Commstar | Response-object shapes | Six headers, five separator cells |
| RTC evidence | Register A rates | Missing separator row |

The initial `mkdocs build --strict` succeeded with these defects. Python
Markdown emitted paragraphs of pipes rather than tables. Therefore a strict
build alone is not a rendering check. The build also reported an
unrecognized `reviews/` directory link at INFO level; the rendered archive
link had no target. Replaced it with links to the actual review pages.

Recommended checks: retain the strict build, check rendered article links
and fragments, detect table-like paragraphs left unrendered, and verify
important table headings/cell counts. Add a browser smoke test for diagrams
and narrow layouts. The existing deployment workflow runs only on pushes
to master or manual dispatch; add a pull-request validation job without
deployment permissions. Do not mistake the existing push build for a
pre-merge review gate.

Diagram scripts depend on jsDelivr and only run when their globals exist.
Provide a visible load/error state and usable text or static fallbacks.
Test an offline page, keyboard navigation, narrow tables, and dark mode.
These are recommended checks, not claims of observed accessibility failures.

### P2 — structure and maintainability

* **Choose a canonical owner for each fact.** Keep COM/DIP grammar in
  Program formats, API contracts in the references, and verification in
  evidence pages. The guide should teach use and link to those contracts;
  its duplicate DIP grammar and loader-address catalogue invite drift.
* **Give readers three routes:** using the handheld, writing a program,
  and investigating firmware. Keep the current sections but add short
  task paths. A first-program walkthrough should name its tested
  assembler, commands, image, emulator run, expected output, and real
  hardware limitations. Existing fragments assume substantial CP/M
  knowledge and are not a reproducible getting-started workflow.
* **Reconcile status vocabulary.** `Stable`, `Provisional`, `Not
  implementable`, `Advanced, unsafe`, and `This ROM image only` mix
  confidence, policy, implementation state, and compatibility scope.
  Use separate fields for evidence, validation environment, supported
  use, and ROM scope. A known no-op is implemented; an unknown physical
  handshake is a different category. Avoid blanket “safe to build on”
  language for addresses specific to one dump.
* **Complete API cards consistently.** Use input/output registers,
  clobbers, buffer layout and bank constraints, blocking, errors, side
  effects, and a precise evidence link. The BDOS page's compact groups
  omit details that its card format appears to promise. Separate a
  conservative unspecified-register contract from a claim that each
  register is actually clobbered.
* **Separate current conclusions from history.** The barcode page leads
  with naming policy and superseded identity arguments. Move those to
  the evidence/archive and lead with reading a scan. Mark reviews with
  dates and fixed/outstanding status. The old review below is historical,
  not another current status dashboard. TASKS still contains obsolete
  coverage and completed-item summaries; link to the canonical coverage
  tracker rather than duplicating its numbers.
* **Repair index and build descriptions.** Reference README lists Memory
  and I/O map and System memory map as two pages, but both target the same
  file. BUILD says research is excluded from navigation; mkdocs.yml
  explicitly includes it. Home says legacy source files remain on disk;
  redirects are generated and those source paths have moved. The archive
  description was corrected in this pass; reconcile the other descriptions.
* **Keep section structure predictable.** Memory map duplicates the
  theme's table of contents and mixes numbered and unnumbered headings;
  the programmer guide uses §7b, and OS internals has an empty legacy
  code-loading heading. Prefer descriptive headings with stable explicit
  anchors where needed. Split long evidence pages by topic only when
  it improves lookup; preserve incoming fragment links during any split.

### P3 — style and evidence precision

Use `DIPOS-B` consistently; use `RST 10h` for the instruction and explain
“restart vector 2” once. `RST 2h` in the comparison table is misleading
assembly notation. Use KiB for binary sizes and choose one address notation
per audience; always include the address space in firmware evidence.
Preserve exact quoted error messages with hexadecimal and decimal IDs.
Replace generic “see notes” links with the relevant evidence anchor.

Reduce emphatic claims such as “complete picture”, “fully decoded”, “every”,
“nothing”, and “single most important” unless the bounded evidence supports
them. State observed workloads and coverage instead. In particular,
[Method](re-notes/method.md#the-rom-images-are-the-ones-in-the-machine)
treats two matching 16-bit byte sums as roughly one-in-four-billion proof of
image identity. That probability needs an independent uniform-error model;
a matching sum alone does not establish byte-for-byte identity. Report the
matches and their limitations directly, and reserve identity verification
for a read-back comparison or stronger provenance.

### Suggested order of work

1. Reconcile storage support, resident-memory ownership, pointer contracts,
   and the supported-profile/home-page status against their evidence.
2. Remove duplicated specifications and standardize API/status cards.
3. Add rendered-output and pull-request checks, then a reproducible
   first-program walkthrough and browser/accessibility checks.

The targeted fixes in this pass cover the six tables, broken archive link,
COM explanation, monitor correction, and restart-vector contradiction.
The broader recommendations above remain review findings for a subsequent
documentation pass.

**Validation:** `mkdocs build --strict` and `git diff --check` pass.
A rendered-HTML scan of 52 pages finds zero table-like paragraphs left
unrendered and zero broken relative article links/fragments. Ghidra's
before/after function-list snapshots are identical (914 internal entries;
the MCP count including the external entry remains 915); comments and the
unresolved-monitor bookmark were saved. Browser diagram execution and
hardware behavior were not tested in this review.

---

## Earlier review — historical assessment

The sections below preserve the earlier review and its incremental updates.
Their status statements are historical; use the dated review above for the
current assessment.

## Scope and verdict

This review considers the published `doc/` tree as a manual for someone
writing, packaging, loading, and debugging software for the Micronic 1000.
It does not question the value of the reverse-engineering record: the
evidence discipline, byte-level detail, and explicit open questions are
strong. The problem is the boundary between that record and the promised
programming interface.

The site builds successfully with `mkdocs build --strict`. Navigation and
Markdown links therefore work in the current build. The principal gaps are
API completeness, safe examples, end-to-end workflow, and clear separation
of a stable application contract from implementation evidence.

## Update: newly completed evidence work

The review remains substantially unchanged after the latest reverse-engineering
pass, but two improvements should be reflected in its scope.

`analysis/boot_hw.py` now drives the RTC from measured Z80 execution progress,
rather than charging a fixed execution slice, and reliably paces injected
keyboard events through the firmware's event ring. It has been verified through
the banner serial-entry path to the Main Menu. This improves the internal
emulator as an evidence and regression tool; it does not yet provide the
end-to-end developer deployment or live-link workflow identified below.

The 4Ah-4Fh Commstar controller path is now byte-verified in both directions.
`Link_BlockTx` and `Link_BlockRx` have documented latch ordering, status-bit
branches, delays, and timeout bounds; the corresponding Ghidra plates and
comments were updated. Earlier electrical labels such as `TX-ready`, `ACK`,
and `clock` were deliberately withdrawn: they remain **SUSPECTED** pending a
hardware trace. This strengthens the evidence boundary but does not resolve
the missing live RECORD/BLOCK payload capture or session grammar.

### Implementation status

The manual now includes a conservative [supported application
profile](manual/supported-profile.md), and the BDOS index uses explicit
ABI/evidence classifications rather than presenting behaviour-only findings as
stable contracts. Navigation exposes that profile before the broader guide.
All dispatched functions are now classified and described; several routed or
device-dependent paths deliberately retain limited contracts. A first-program
tutorial still requires executable examples and a deployment route, and
configuration wrappers must await safe F6h-FBh application contracts. The
no-hardware priority order is maintained in `TASKS.md`.

### Superseded historical claims (BDOS review 2026-08-28 — see `manual/bdos-reference.md`)

The following review observations are **superseded** by the current
`reference/bdos.md` (canonical; `manual/bdos-reference.md` redirects) and
`re-notes/cp-m-comparison.md` (`internals/cp-m-comparison.md` redirects)
after the reviewer-approved BDOS pass (no new reverse-engineering; applied
existing findings):

* **fn `1Ah` as stub / "no contracts":** `1Ah` (`Bdos_SetDmaAddress`,
  `ROM00:0CEC`) is an **implemented set-DMA** (stores `DE`), not a stub; its
  downstream record-I/O ABI remains incomplete. Earlier prose that grouped
  `1Ah` with inert stubs is superseded.
* **fn `0Dh`/`1Ch`/`1Eh`/`1Fh`/`30h`/`F4h` as inert stubs:** these are **unsafe
  mutable `RST 28h` paths** via `Bdos_SharedErrorStub` (`ROM00:1893`)
  conditional on `Bdos_SelectRst28Mode` (`ram:F55A`), not stubs. The
  diagnostic behaviour only applies when the default target `F57E` is
  installed (`E=FEh`); `FFh`/`FDh`/`FCh` select no-op/deferred/fatal modes.
* **fn `19h` in `HL`:** `19h` returns the current drive in `A` (not `HL`).
* **fn `02h`/`04h`/`0Ah`/`21h`/`22h` detail:** `02h` has four path-dependent
  `A` results (`00h` no destination, `08h` mode, routed `00h`/`FFh`);
  `04h` (`ROM00:10D2`) uses `Device_LookupConfigEntry` (`ROM00:31FF`) and
  `FBC5` high nibble to select an `FE83` descriptor (`80h` local else
  routed), is **CONFIRMED and returning**, not a non-returning `RST 38h`
  case; `0Ah` includes the `1Bh` counted literal block; `21h`/`22h`
  address only via `+21h`/`+22h` (`+23h` not read; 31-byte copy stops
  before it). The table `CONFIRMED behaviour; ABI incomplete` markings
  now match the cards.
* **fn `2Dh`/`2Eh`:** `2Dh` is `Bdos_SelectRst28Mode` (`ram:F55A`) and `2Eh`
  is `Bdos_UpdateDriveDirectoryMetadata` (`ROM00:0D79`), not a generic
  banked-call wrapper / filename search helper.
* **fn `FEh`/`FFh`:** `FEh` is `Bdos_InternalTimedWait` (`ROM00:1122`,
  `E<<4`, `IY+23h`/`word[FEFA]`, `FD4D` `HALT` wait, `A=00h`), not a general
  RTC alarm setter; `FFh` polls `UIP` before both clear and program paths
  (permanent `UIP` blocks both).

Where this review and the current BDOS reference disagree, the **BDOS
reference is authoritative**.

## Findings

### P0 -- BDOS reference completeness (partially resolved)

The current reference now publishes the uniform CALL-5 envelope and verified
contracts for the supported calls, and classifies every dispatched function.
It intentionally does not turn every mechanically understood service into a
supported API: routed/device-dependent errors and configuration-mutating
F6h-FBh calls still require caution. Safe save-modify-restore wrappers for
F8h/FAh/FBh remain an open documentation task.

### P0 -- the RTC ABI is incomplete and internally unclear

The programmer guide says FC uses an eight-byte time block but does not
define the byte offsets, encodings, valid ranges, or return condition. The
RTC reference documents seven calendar-register writes and a sixteen-byte
register-file read, but does not reconcile those facts into the FC/FD caller
buffers. It is consequently impossible to implement clock support solely
from the manual.

**Update 2026-08-29 — resolved for byte layout, OPEN items preserved:**
The canonical 8-byte layout is now published in
[`re-notes/rtc.md#bdos-eight-byte-rtc-record`](../re-notes/rtc.md#bdos-eight-byte-rtc-record)
(`internals/rtc.md` redirects):
`+1..+7` → regs `09/08/07/04/02/00/06` (year/month/day-of-month/hour/
minute/second/day-of-week), `+0` metadata handling per service, raw
binary 24-hour (Reg B `46h`), no firmware validation/conversion, service
identities `FCh=1150`/`FDh=113E`/`FEh=1122`/`FFh=112D`, `FFh` `DE=0` vs
program both `UIP`-polled, and alarm preamble `RegA|80h` (likely
ineffective) then `2Ah`. Remaining **OPEN**: `+0` exact meaning (LIKELY
century `19`, from `g_bRtcRecordMetadata` init `13h`), day-of-week
numbering (`0=Sunday` LIKELY from `1984-01-01` default), and whether
out-of-range values are validated (firmware performs none).

### P0 -- the barcode hook recipe is unsafe as published

The example contains pseudo-assembly (`CALL 5, C=03h`) rather than
assemblable Z80 source. More importantly, it does not define a complete
hook ABI: bank-byte setup, preserved/clobbered registers, interrupt and
reentrancy rules, hook/result lifetime, error behaviour, and restoration of
the previous hook. A reader could install a handler that works by accident
or destabilises the resident system.

### P1 -- storage guidance contradiction (resolved)

The programmer guide now distinguishes the confirmed default FE93 mapping
(internal A/B, external C/D entries) from the configurable runtime table and
no longer presents C:+ as a universal fixed mapping. A supported preservation
workflow for configuration changes remains open.

### P1 -- CP/M compatibility overstatement (resolved)

The guide now describes a CP/M-shaped entry convention rather than blanket
compatibility, and points first to the narrow supported profile. It also
correctly records 1Ah as implemented while excluding the unsafe standard-
numbered diagnostic paths and undefined extension range.

### P1 -- no end-to-end developer workflow exists

There is no first-program path that starts with a source file and ends with
an executing image. The material lacks a supported assembler/toolchain
assumption, COM origin/startup convention, minimal console and file examples,
termination behaviour, artifact-transfer/load instructions, debugging
workflow, and a troubleshooting table. The DIP format is precise as a
reverse-engineering specification but lacks a producer recipe, complete
example image, packer/validator, and known-good deployment route. The
physical loader provider is explicitly still open, which should be surfaced
as a clear deployment limitation rather than left for readers to infer.

### P2 -- terminology and evidence boundaries need tightening

The banked-call mechanism is called `RST 2`, `RST2`, and `RST 10h`. Since the
published byte is D7h and conventional Z80 source normally spells this
`RST 10h`, standardise on that spelling and introduce "RST vector 2" only as
an explanatory alias. Likewise, "no bootstrap loader" is ambiguous beside
the documented ROM boot-load chain; it should say "no CP/M disk bootstrap"
if that is the intended claim.

Evidence labels are explained on the landing page but are uneven in the
programmer-facing pages. An API table needs a status per entry such as
**CONFIRMED ABI**, **CONFIRMED behaviour; ABI incomplete**, **EXPERIMENTAL**,
or **UNSAFE**. Internal addresses and discovery history are valuable, but
should be secondary to the contract a programmer can rely on.

### P2 -- delivery and usability weaknesses

The manual navigation mixes task-oriented pages with dense internals. The
landing page distinguishes them, but a reader needs an obvious API/manual
track and a separate evidence/internals track. Diagrams also depend on
CDN-hosted Mermaid and WaveDrom scripts with no local fallback; the strict
build verifies static generation, not offline or archival readability.

## Recommendations

### 1. Establish a supported-programming profile

Publish one short, versioned page headed "Supported application profile".
It should state exactly what can be relied upon today:

* target CPU, memory model, program origin, stack ownership, interrupt mode,
  bank assumptions, and warm-boot/exit behaviour;
* the supported CP/M subset and every material deviation;
* which entry points are stable, experimental, or forbidden;
* the default device/storage configuration, what is configurable, and what
  an application must restore; and
* the current deployment limits, including the unresolved physical loader
  provider.

This page should be normative. Link each assertion to an evidence page
rather than putting implementation addresses in the normative prose.

### 2. Replace the BDOS index with contract cards

Give every callable function a compact contract card:

```text
Function: 02h -- Console output
Status: CONFIRMED ABI
In:     E = byte
Out:    <exact returned registers and flags>
Blocks: <yes/no and condition>
Effects: routes through active console device
Errors: <exact result or "none observed">
Example: <assembling Z80 snippet>
Evidence: <link to internals/disassembly rationale>
```

Use the same format for F5--FF, RTC, configuration, and barcode services.
Do not label an operation "supported" until its minimum safe ABI is known;
instead classify it as behaviour-confirmed but ABI-incomplete.

### 3. Add a verified first-program tutorial and reference examples

Provide small, tested source files with expected output or observable
results:

1. a minimal COM program at 0100h that writes to the console and exits;
2. keyboard/poll input using function 06h;
3. an FCB read/write example that states the DMA limitation plainly;
4. an RTC get/set example once its buffer ABI is confirmed; and
5. a barcode hook example only after the complete hook contract is verified.

For every snippet, show an actual assembler invocation, output filename and
size check, load/run steps, and a failure diagnosis. Mark untested snippets
as illustrative rather than executable.

### 4. Make program packaging reproducible

Keep `reference/program-formats.md` (`manual/program-formats.md` redirects) as the byte-level specification, then add a
producer-facing companion:

* annotated hexadecimal examples of one valid COM and one valid DIP;
* a precise field-by-field writer algorithm, including type-1 block sizing
  and all known rejection conditions;
* a host-side packer/validator in `analysis/`, with golden inputs and tests;
* a statement of what the loader verifies versus what a build tool must
  verify; and
* an explicit, current deployment matrix (known route / inferred route /
  unavailable pending hardware capture).

### 5. Make global mutations safe by design

Provide library-quality wrappers or documented macros for active-device,
FE83, FE93, and hook operations. They should read and preserve the old state,
validate input, restore state on all exits, and state persistence across warm
boot/power loss. Until then, move these calls out of the guide's "Things to
use" list into an advanced/experimental section.

### 6. Separate reader layers in the information architecture

Organise the published navigation as:

```text
Start here
  Supported application profile
  First COM program
  Build, transfer, load, and debug
Application reference
  BDOS contracts
  Files and devices
  Program formats
  RTC
  Barcode (advanced)
Compatibility and limitations
Evidence and internals
  Existing reverse-engineering pages
Research archive
```

Keep raw addresses, Ghidra names, boot-chain analysis, and open hypotheses in
the evidence layer. Cross-link them from contracts, but do not require an
application author to interpret them.

### 7. Improve publication resilience

Vendor or provide static fallbacks for Mermaid/WaveDrom diagrams, keep text
equivalents for every diagram, and add CI checks for strict MkDocs builds,
internal links, fenced-code syntax, and example assembly/validation tests.

## Suggested acceptance criteria

The documentation can reasonably call itself a programmer's manual when a
new reader can, without Ghidra or a separate CP/M manual:

1. build and run a documented COM example;
2. use each advertised stable BDOS call from its published ABI card;
3. understand which functions may block or mutate persistent global state;
4. create and validate a documented DIP image, or clearly see why deployment
   is not yet supported; and
5. distinguish confirmed contracts from hypotheses and implementation notes.

Until then, the current site is an unusually valuable reverse-engineering
record and partial reference, but not yet a self-sufficient programmer's
manual.
