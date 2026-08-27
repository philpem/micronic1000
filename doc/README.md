# Micronic 1000 / PARCON 1000 documentation

This documentation describes the firmware-derived programming and hardware
interfaces of the Micronic 1000 (PARCON 1000). It distinguishes a usable
interface contract from firmware implementation evidence and from open
reverse-engineering questions.

## Start here

* [User guide](manual/user-guide.md) — keyboard, menus, and error screens.
* [Programmer's guide](manual/programmer-guide.md) — write CP/M-style
  applications for DIPOS-B.
* [BDOS reference](manual/bdos-reference.md) — supported CALL 0005h
  functions and DIPOS-B extensions.
* [Barcode reader](manual/barcode-reader.md) — scanner hook and RDR:
  byte-stream API.
* [Commstar protocol](protocol/commstar.md) — verified transport contract,
  implementation readiness, and the remaining session-layer gaps.

The Commstar session and file-transfer format is not yet sufficiently
decoded for an interoperable host implementation. The protocol document
states exactly which layers are safe to implement and which require a trace
or hardware capture.

## Reference and internals

* [System architecture](internals/os-diposb.md)
* [CP/M compatibility comparison](internals/cp-m-comparison.md)
* [Memory map and RAM extension points](internals/memory-map.md)
* [I/O map](internals/io-map.md)
* [Interrupts and banked calls](internals/interrupts.md)
* [RTC interface](internals/rtc.md)

## Evidence labels

| Label | Meaning |
|---|---|
| **CONFIRMED** | Directly established by firmware bytes, a trace, or an xref. |
| **LIKELY** | Firmware evidence combined with a documented hardware fact. |
| **SUSPECTED** | Plausible but unverified; the required confirming observation is stated. |

## Research records

The worklist, coverage tracker, and historical reviews live under
`research/` in the source tree. They preserve the reasoning trail but are
not reader-facing API specifications.

## Building the HTML site

See `BUILD.md` in the source repository. The builder publishes this landing
page plus the `manual/`, `protocol/`, and `internals/` trees; it intentionally
excludes the research archive from site navigation.
