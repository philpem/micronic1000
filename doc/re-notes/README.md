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
* [Commstar evidence and traces](commstar-evidence.md) — full transport, emulator
  peer, and captured requests with ROM addresses and trace bytes
* [OS internals](os-diposb.md) — kernel, BDOS dispatch, and boot chains
* [Forms and UI](forms-ui.md) — form model, templates, and menus
* [CP/M comparison](cp-m-comparison.md) — deviation-by-deviation evidence
* [Interrupts](interrupts.md) — IRQ/NMI and banked-call mechanics
* [RTC](rtc.md) — HD146818 programming evidence
* [Open questions](open-questions.md) — single address for every `OPEN` item

Legacy internals paths redirect to these locations. The worklist that
prioritises the open questions lives in `research/TASKS.md` in the source
tree and is not published here.
