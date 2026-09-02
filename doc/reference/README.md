# API and ABI reference

This section states the **programmer-visible contract** for software that
runs on, or communicates with, a Micronic 1000. It describes what an
application may rely on and how stable each interface is.

## Stability terms

| Stability | Meaning |
|---|---|
| **Stable** | Intended application contract. Behaviour is exercised in the published reference and will not be reclassified without a firmware-based justification. Safe to build on. |
| **Provisional** | Partially documented or subject to future refinement. Usable with caution; check the linked RE note for limits. |
| **Not implementable** | Blocked by missing hardware, wire, or session evidence. Do not attempt a compatible implementation from this page alone. |

Reference pages carry no ROM addresses, no `CONFIRMED`/`SUSPECTED`/`OPEN`
evidence tags, and no trace bytes. Every claim links to the RE-notes anchor
that carries the underlying evidence.

**The two Commstar pages are a deliberate exception.** They describe an
interface nobody has a manual for, so they carry their addresses, byte
quotes and evidence tags inline: an implementer needs to see what a claim
rests on before building hardware against it.

## Pages

* [BDOS calls](bdos.md) — standard CP/M-shaped BDOS services
* [DIPOS-B extensions](extensions.md) — device, storage, RTC, and timing extensions
* [Barcode reader](barcode.md) — edge-capture input and decode-hook API
* [Program file formats](program-formats.md) — COM and DIP image grammars
* [Commstar application API](commstar-api.md) — the twenty session entry
  points a loaded COM or DIP can call, their arguments and results
* [Commstar peer library](commstar-peer.md) — `micronic.peer.CommstarPeer`,
  the host half of a session
* [Memory and I/O map](memory-io.md) — bank window, fixed RAM, and port assignments

## Building a Commstar host

The through-line for that job is: the wire and session contract in
[Protocol: Commstar transport](../protocol/commstar.md), the handheld-side
entry points a program calls in
[Commstar application API](commstar-api.md), a working host implementation in
[Commstar peer library](commstar-peer.md), and the byte-level proof for all
three in [RE notes: Commstar evidence](../re-notes/commstar-evidence.md).

For the reasoning trail, register-level evidence, and open questions behind
each contract, see [Reverse-engineering notes](../re-notes/README.md).
