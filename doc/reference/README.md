# API and ABI reference

This section states the **programmer-visible contract** for software that
runs on, or communicates with, a Micronic 1000. It describes what an
application may rely on and how stable each interface is.

## Stability terms

| Stability | Meaning |
|---|---|
| **Stable** | The documented contract is established for the supplied ROMs within its stated preconditions. This does not imply cross-version compatibility or physical-hardware validation. |
| **Provisional** | Partially documented; unspecified behavior must not be treated as a guarantee. Check the linked evidence and limits. |
| **Not implementable** | Blocked by missing hardware, wire, or session evidence. Do not attempt a compatible implementation from this page alone. |

Read these independent qualifications alongside contract maturity:

| Field | Meaning |
|---|---|
| Evidence | `CONFIRMED`, `LIKELY`, or `SUSPECTED`, with a linked derivation |
| Validation | Static bytes, emulator execution, or hardware observation; these are not interchangeable |
| Supported use | Portable subset, advanced resident use, or do not call |
| ROM scope | Supplied images only unless another revision has been verified |

`Advanced, unsafe` is a use restriction, not an evidence level. A known
no-op is implemented with limited utility; `Not implementable` is reserved
for a compatible implementation blocked by missing evidence. RAM addresses
specific to this ROM remain revision-specific even when confirmed.

References lead with callable contracts and link to evidence. Addresses
belong in the contract when needed to use it; derivation and discovery
history belong in the RE notes.

**Three pages are a deliberate exception.** The two Commstar pages
describe an interface nobody has a manual for, so they carry their
addresses, byte quotes and evidence tags inline: an implementer needs to
see what a claim rests on before building hardware against it.
[System memory map](memory-map.md) is an exception for the opposite
reason — its whole subject *is* addresses, and a reader placing resident
code needs to know which of them are structural and which are artefacts
of this ROM build.

## Pages

* [BDOS calls](bdos.md) — standard CP/M-shaped BDOS services
* [DIPOS-B extensions](extensions.md) — device, storage, RTC, and timing extensions
* [Barcode reader](barcode.md) — edge-capture input and decode-hook API
* [Program file formats](program-formats.md) — COM and DIP image grammars
* [Commstar application API](commstar-api.md) — the twenty session entry
  points a loaded COM or DIP can call, their arguments and results
* [Commstar peer library](commstar-peer.md) — `micronic.peer.CommstarPeer`,
  the host half of a session
* [Memory and I/O map](memory-map.md) — the programmer's reference:
  the banked memory model, the `RST 10h` inter-bank call and the
  pointer-mapping requirements, region tables, stacks (and why
  there is no heap), the derived I/O port map, and what it takes to write
  resident code — a barcode decoder module or an OS function patch

## Building a Commstar host

The through-line for that job is: the wire and session contract in
[Protocol: Commstar transport](../protocol/commstar.md), the handheld-side
entry points a program calls in
[Commstar application API](commstar-api.md), a working host implementation in
[Commstar peer library](commstar-peer.md), and the byte-level proof for all
three in [RE notes: Commstar evidence](../re-notes/commstar-evidence.md).

For the reasoning trail, register-level evidence, and open questions behind
each contract, see [Reverse-engineering notes](../re-notes/README.md).
