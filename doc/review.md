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

## Findings

### P0 -- the BDOS reference is not yet an implementable API reference

`manual/bdos-reference.md` lists services and broad status, but omits the
per-call ABI required to use them: input registers, output registers and
flags, buffer structures and lengths, blocking behaviour, state changes,
and exact error results. Its calling-convention section also says that each
function's return and error convention must be verified before use. A
programmer therefore has to repeat reverse-engineering work before safely
calling a service described as supported.

This applies especially to extensions F5--FF. F5 explicitly lacks its
parameter contract; F9 is only partly decoded; F6/F7/F8/FA/FB give no
register or buffer contract. F8/FA/FB change global configuration, so a
safe save--modify--restore pattern is needed before they can be recommended
to applications.

### P0 -- the RTC ABI is incomplete and internally unclear

The programmer guide says FC uses an eight-byte time block but does not
define the byte offsets, encodings, valid ranges, or return condition. The
RTC reference documents seven calendar-register writes and a sixteen-byte
register-file read, but does not reconcile those facts into the FC/FD caller
buffers. It is consequently impossible to implement clock support solely
from the manual.

### P0 -- the barcode hook recipe is unsafe as published

The example contains pseudo-assembly (`CALL 5, C=03h`) rather than
assemblable Z80 source. More importantly, it does not define a complete
hook ABI: bank-byte setup, preserved/clobbered registers, interrupt and
reentrancy rules, hook/result lifetime, error behaviour, and restoration of
the previous hook. A reader could install a handler that works by accident
or destabilises the resident system.

### P1 -- storage guidance is contradictory

The programmer guide correctly says that drive mapping is
configuration-dependent, but later says only A/B are file storage and tells
programs never to use C:+. `manual/devices-and-storage.md` instead says that
the user-visible device names are not a universal drive-to-hardware mapping.
The manual must distinguish the confirmed default mapping from configurable
mapping and give a supported rule for detecting or preserving the current
configuration.

### P1 -- CP/M compatibility is overstated

The guide concludes that a CP/M program using FCB and console calls will run
"essentially unchanged", while Set DMA (1Ah) and several normal CP/M disk
services are stubs. That statement needs a narrow, testable compatibility
profile: supported functions, default-DMA assumptions, FCB constraints,
console/device assumptions, program exit/reset behaviour, and explicitly
unsupported CP/M patterns.

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
