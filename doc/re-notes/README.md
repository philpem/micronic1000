# Reverse-engineering notes

This section is the **firmware evidence record**. It states what the bytes
do, where, and with what confidence. It grows without limit; the
[reference](../reference/README.md) and [protocol](../protocol/README.md)
contract pages stay small and link here for proof.

## Evidence labels

| Label | Meaning |
|---|---|
| **CONFIRMED** | Directly established by firmware bytes, a trace, or an xref |
| **LIKELY** | Firmware evidence combined with a documented hardware fact |
| **SUSPECTED** | Plausible but unverified; the required confirming observation is stated |
| **OPEN** | Not yet established; a discriminating test is listed |

A repeatable comment in Ghidra carries only **CONFIRMED** facts.

## Pages

* [Method and evidence rules](method.md) — how to read every RE note
* [Listing-repair script](ghidra-repair-script.md) — the consolidated Ghidra
  pass that keeps the database honest, and what auto-analysis gets wrong
* [Commstar evidence and traces](commstar-evidence.md) — full transport, emulator
  peer, and captured requests with ROM addresses and trace bytes
* [Commstar API evidence](commstar-api-evidence.md) — entry-point table, calling
  convention, buffer placement, and transfer contracts with byte-level proof
* [Kernel_TableDispatch tables](inline-dispatch.md) — the inline switch idiom
  and every decoded table
* [OS internals](os-diposb.md) — kernel, BDOS dispatch, and boot chains
* [Forms and UI](forms-ui.md) — form model, templates, and menus
* [CP/M comparison](cp-m-comparison.md) — deviation-by-deviation evidence
* [Interrupts](interrupts.md) — IRQ/NMI and banked-call mechanics
* [Barcode capture](barcode-capture.md) — the `Ext*` edge-capture front
  end, the decode-hook dispatch and delivery path, and the uncapped
  element-count firmware bug.
* [Unbanked RAM map](unbanked-ram-map.md) — what occupies `8000`-`FFFF`,
  what is genuinely safe for host/test scratch, and the traps
* [Memory and I/O evidence](memory-and-io-evidence.md) — byte-level
  derivation for every I/O port, register-indirect access, interrupt
  source trace, latch-bit usage, and the `ram:E5C2` worked example
* [RTC](rtc.md) — HD146818 programming evidence
* [IR wire protocol](ir-wire-protocol.md) — the first scope capture of
  the IR line: bit timing, the bit-stuffed frame layer, where the connect
  dies, and the ordered test plan for an adapter
* [ROM exerciser test plan](exerciser-test-plan.md) — the patched-ROM run
  that reads `HSBUSY` from inside the latch boundary: what it measures, and
  what to do on the happy and sad paths
* [Open questions](open-questions.md) — single address for every `OPEN` item
* [IR feedback automation plan](ir-feedback-test-plan.md) — one reusable ROM,
  connector handshakes and Arduino-controlled receive hypotheses
* [Stock-context v3 round two](stock-context-v3-round2.md) — content
  comparisons, failed interleaved positive control, and hardware audit

Legacy internals paths redirect to these locations. The worklist that
prioritises the open questions lives in the
[research worklist](../research/TASKS.md).
