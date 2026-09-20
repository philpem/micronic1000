# Micronic 1000 / PARCON 1000 documentation

This documentation describes the firmware-derived programming and hardware
interfaces of the Micronic 1000 (PARCON 1000). It distinguishes a usable
interface contract from firmware implementation evidence and from open
reverse-engineering questions.

## Start here

Choose a path for your task:

* **Use the handheld:** user guide → menus and error recovery.
* **Write an application:** supported profile → programmer guide → API cards
  and program formats.
* **Investigate firmware:** method and evidence rules → subsystem evidence →
  current worklist. Historical session entries describe what was believed
  at the time; consult the current evidence before relying on them.

* [User guide](manual/user-guide.md) — keyboard, menus, and error screens.
* [Supported application profile](manual/supported-profile.md) — conservative
  boundary for portable COM applications.
* [Programmer's guide](manual/programmer-guide.md) — write CP/M-style
  applications for DIPOS-B.
* [BDOS calls](reference/bdos.md) — standard CALL 0005h services.
* [DIPOS-B extensions](reference/extensions.md) — device, storage, RTC, and timing.
* [Barcode reader](reference/barcode.md) — scanner hook and RDR: byte-stream API.
* [Program file formats](reference/program-formats.md) — COM and DIP grammars.
* [Memory and I/O map](reference/memory-map.md) — banks, RAM, vectors, and ports.
* [Commstar transport](protocol/commstar.md) — controller mechanics, the
  session state machine, and the explicit blockers for a physical server.
* [Commstar application API](reference/commstar-api.md) — the session entry
  points a loaded COM or DIP program calls.
* [Commstar peer library](reference/commstar-peer.md) — the host half of a
  session, transport independent.

**Where Commstar stands.** Both directions now run end to end against real
firmware in the emulator: a program download to the handheld, and a record
upload from it. Outbound IR framing and timing have been captured. A
physical host is still blocked on the return-side handshake and validation
of the timed receive-arm policy. See the
[current protocol status](protocol/commstar.md#scope-and-implementation-status)
for the distinction between captured wire behavior and emulator results.

## Reference

* [API and ABI reference](reference/README.md) — contracts with stability
  terms (`Stable` / `Provisional` / `Not implementable`)
* [Protocol reference](protocol/README.md) — Commstar transport
* [Programmer manual](manual/README.md) — task-oriented guides

## Reverse-engineering notes

Implementation evidence lives in `re-notes/` — the full RE record with ROM
addresses, trace bytes, and confidence tags:

* [Method and evidence rules](re-notes/method.md)
* [Commstar evidence and traces](re-notes/commstar-evidence.md)
* [Commstar API evidence](re-notes/commstar-api-evidence.md)
* [Kernel_TableDispatch tables](re-notes/inline-dispatch.md)
* [Listing-repair script](re-notes/ghidra-repair-script.md)
* [OS internals](re-notes/os-diposb.md)
* [Forms and UI](re-notes/forms-ui.md)
* [CP/M comparison](re-notes/cp-m-comparison.md)
* [Interrupts](re-notes/interrupts.md)
* [Unbanked RAM map](re-notes/unbanked-ram-map.md)
* [Memory and I/O evidence](re-notes/memory-and-io-evidence.md) — byte-level
  derivation for ports, interrupt trace, latch bits, worked example
* [Barcode capture](re-notes/barcode-capture.md)
* [RTC](re-notes/rtc.md)
* [IR wire protocol](re-notes/ir-wire-protocol.md)
* [ROM exerciser test plan](re-notes/exerciser-test-plan.md)
* [Open questions](re-notes/open-questions.md) — single address for every `OPEN`

MkDocs generates redirects for legacy URLs under `internals/` and for
moved manual pages such as `manual/bdos-reference.md`; the old Markdown
source files have moved.

## Evidence labels

| Label | Meaning |
|---|---|
| **CONFIRMED** | Directly established by firmware bytes, a trace, or an xref. |
| **LIKELY** | Firmware evidence combined with a documented hardware fact. |
| **SUSPECTED** | Plausible but unverified; the required confirming observation is stated. |

Reference pages use **stability** terms (`Stable` / `Provisional` /
`Not implementable`) and link to the RE notes for evidence.

## Research records

The worklist, coverage tracker, session log, and historical reviews live
under `research/`. They preserve the reasoning trail; they are not API
specifications, but they are published alongside the reverse-engineering
notes.

## Building the HTML site

See `BUILD.md` in the source repository. The builder publishes this landing
page plus the `manual/`, `protocol/`, `reference/`, `re-notes/`, and
`research/` trees.
