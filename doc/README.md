# Micronic 1000 / PARCON 1000 — Technical Findings

Reverse-engineering notes for the Micronic 1000 handheld (Z80, 3.58 MHz,
2 × 27C256 EPROMs, 256K static RAM). Analysis targets: `micron1.bin`
(bank 0 ROM) and `micron2.bin` (bank 1 ROM), loaded in Ghidra as the
`ROM00` and `ROM01` overlay address spaces over the shared `ram` space.

**Status legend used throughout:**

| Tag | Meaning |
|-----|---------|
| CONFIRMED | Directly proven from code/bytes |
| LIKELY | Strong circumstantial evidence |
| SUSPECTED | Plausible but unproven |

## Documents

* [Memory map](memory-map.md) — ROM/RAM organisation, banked window,
  battery-backed RAM layout, system variables
* [I/O map](io-map.md) — port assignments and bit-level functions
* [Interrupts](interrupts.md) — interrupt handling and vector usage
* [Operating system: DIPOSB](os-diposb.md) — kernel structure, ABI,
  comparison against standard CP/M (with references)
* [Commstar transfer protocol](protocol-comms.md) — hardware transport,
  frame grammar, session/state names, role model (host or unit) and
  sequence/state diagrams
* [RTC (HD146818) path](rtc-investigation.md) — the 08h/28h indexed
  interface, register map, periodic-interrupt rate
* [Build the HTML site](BUILD.md) — how to render these Markdown
  documents (with Mermaid diagrams) into HTML

## Summary of headline findings

1. The OS identifies itself as **DIPOSB** (`DIPOSB Ver 228` string @
   ROM00:041E). It is **not** CP/M, but exposes a **CP/M-style CALL-5
   program interface** (os-diposb.md).
2. `0000-7FFF` is a 32K bank-switched window (two ROM images as banks
   0/1, further banks = 32K RAM pages), selected by **port 47h**
   (CONFIRMED).
3. `8000-FFFF` is fixed battery-backed RAM holding the resident DIPOSB
   kernel, copied from ROM at cold boot (CONFIRMED: `InstallKernelToRam`
   → F180, 50Dh bytes).
4. Kernel code is invoked via RST trampolines, per-bank jump tables,
   and the page-zero CALL-5 gate.
5. Keyboard matrix fully decoded (`drive 02h` = column bit, `sense 00h`
   = row bit; `index = row*6+col`); the power-on service combos is
   **H+L+P**; boot-key bits on port 49h (CONFIRMED).
6. **Real-time clock = HD146818 on ports 08/28** (register select on
   08h, data on 28h); periodic interrupt at 1024 Hz drives the scheduler
   tick (CONFIRMED, see rtc-investigation.md). The 4x latch cluster is
   **not** the RTC.
7. **External data link = 4x parallel transport**: TX data 4Dh, RX data
   4Eh, status 4Bh, control 4Ah — used for PLINTH/V24 IR, side/external
   port (CONFIRMED; see protocol-comms.md).
8. **Session roles are reversible**: the M1000 can be the host (initiator)
   **or** the unit/responder; per-link slots keep it consistent. See
   protocol-comms.md (role section + diagrams).