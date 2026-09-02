# Programmer manual

The programmer manual is the task-oriented reference for software that runs
on, or communicates with, a Micronic 1000.

- [User guide](user-guide.md) — operator reference: keyboard, special
  keys, menu map, and error-screen format.
- [Supported application profile](supported-profile.md) — conservative,
  evidence-backed boundary for portable COM applications.
- [Programmer guide](programmer-guide.md) — DIPOS-B and CP/M-compatible entry
  points.
- [Devices and storage](devices-and-storage.md) — device routing, RAM disks,
  and external storage boundaries.

Start with the supported application profile, then use the programmer guide.
For callable contracts see [API and ABI reference](../reference/README.md);
for evidence see [Reverse-engineering notes](../re-notes/README.md).

Contract pages live under `reference/` and `protocol/`:

- [BDOS calls](../reference/bdos.md) and [DIPOS-B extensions](../reference/extensions.md)
  (stable contracts; the old `bdos-reference.md` path redirects)
- [Barcode reader](../reference/barcode.md)
- [Program file formats](../reference/program-formats.md)
- [Memory and I/O map](../reference/memory-map.md)
- [Commstar transport](../protocol/commstar.md)
