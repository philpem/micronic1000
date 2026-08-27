# OS and hardware internals

These pages describe the implementation details needed to write a driver,
extend DIPOS-B, or interpret a ROM/RAM disassembly.

- [Memory map](memory-map.md) — banks, RAM, vectors, and system variables.
- [I/O map](io-map.md) — peripheral ports and evidence status.
- [Interrupts](interrupts.md) — restart, IRQ, and NMI entry points.
- [DIPOS-B OS](os-diposb.md) — kernel structure and resident services.
- [CP/M comparison](cp-m-comparison.md) — deliberate deviations from CP/M 2.2.
- [RTC](rtc.md) — HD146818 register access and clock support.

For unresolved findings and historical review notes, see the source-tree
`research/` archive.
