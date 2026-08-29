# Review: from reverse-engineering record to programmer's manual

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
`LinkBlockTx` and `LinkBlockRx` have documented latch ordering, status-bit
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
`manual/bdos-reference.md` and `internals/cp-m-comparison.md` after the
reviewer-approved BDOS pass (no new reverse-engineering; applied existing
findings):

* **fn `1Ah` as stub / "no contracts":** `1Ah` (`BdosSetDmaAddress`,
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
[`internals/rtc.md#bdos-eight-byte-rtc-record`](../internals/rtc.md#bdos-eight-byte-rtc-record):
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

Keep `manual/program-formats.md` as the byte-level specification, then add a
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
