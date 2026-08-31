# Micronic 1000 / PARCON 1000 documentation

This documentation describes the firmware-derived programming and hardware
interfaces of the Micronic 1000 (PARCON 1000). It distinguishes a usable
interface contract from firmware implementation evidence and from open
reverse-engineering questions.

## Start here

* [User guide](manual/user-guide.md) — keyboard, menus, and error screens.
* [Supported application profile](manual/supported-profile.md) — conservative
  boundary for portable COM applications.
* [Programmer's guide](manual/programmer-guide.md) — write CP/M-style
  applications for DIPOS-B.
* [BDOS calls](reference/bdos.md) — standard CALL 0005h services.
* [DIPOS-B extensions](reference/extensions.md) — device, storage, RTC, and timing.
* [Barcode reader](reference/barcode.md) — scanner hook and RDR: byte-stream API.
* [Program file formats](reference/program-formats.md) — COM and DIP grammars.
* [Memory and I/O map](reference/memory-io.md) — banks, RAM, vectors, and ports.
* [Commstar transport](protocol/commstar.md) — controller mechanics and the
  explicit blockers for a physical server implementation.

The Commstar session and file-transfer format is not yet sufficiently decoded
for an interoperable host implementation. In particular, no documented exchange
transfers data from a handheld to a host, and the physical IR wire layer remains
uncaptured. The protocol document distinguishes the emulator-only synthetic
peer from the requirements of a physical server.

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
* [OS internals](re-notes/os-diposb.md)
* [Forms and UI](re-notes/forms-ui.md)
* [CP/M comparison](re-notes/cp-m-comparison.md)
* [Interrupts](re-notes/interrupts.md)
* [RTC](re-notes/rtc.md)
* [Open questions](re-notes/open-questions.md) — single address for every `OPEN`

Legacy paths under `internals/` and `manual/bdos-reference.md` etc. remain
on disk and redirect to the new locations.

## Evidence labels

| Label | Meaning |
|---|---|
| **CONFIRMED** | Directly established by firmware bytes, a trace, or an xref. |
| **LIKELY** | Firmware evidence combined with a documented hardware fact. |
| **SUSPECTED** | Plausible but unverified; the required confirming observation is stated. |

Reference pages use **stability** terms (`Stable` / `Provisional` /
`Not implementable`) and link to the RE notes for evidence.

## Research records

The worklist, coverage tracker, and historical reviews live under
`research/` in the source tree. They preserve the reasoning trail but are
not reader-facing API specifications.

## Building the HTML site

See `BUILD.md` in the source repository. The builder publishes this landing
page plus the `manual/`, `protocol/`, `reference/`, and `re-notes/` trees;
it intentionally excludes the research archive from site navigation.
