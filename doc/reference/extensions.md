# DIPOS-B extensions — device, storage, RTC, timing

This page states the **application contract** for DIPOS-B services outside
the standard CP/M-shaped range. Every claim links to the RE notes that
carry the underlying evidence.

## Stability

* **Stable** — documented signature and return; safe to use where noted.
* **Provisional** — exists but has global side effects or incomplete ABI;
  use with caution.
* **Not implementable / Advanced, unsafe** — global-state mutation or
  diagnostic path; an ordinary application must not call it without the
  full contract.

## Overview

| Function | Service | Stability |
|---:|---|---|
| 2Dh | select RST 28 mode | Advanced, unsafe |
| 2Eh | update drive directory metadata | Advanced, unsafe |
| 30h | shared diagnostic dispatch | Advanced, unsafe |
| 62h | filesystem/directory check | Advanced, unsafe |
| 68h, 69h, F3h | no-op stubs | Stable no-op |
| F5h | event-wait delay | Provisional |
| F6h, F7h | get/set active device selector | Provisional (global) |
| F8h, FAh, FBh | read/write device/drive tables | Advanced, unsafe |
| F9h | set device-pair preset | Provisional |
| FCh, FDh | set/get RTC | Stable |
| FEh | internal timed wait | Advanced, unsafe — resident only |
| FFh | program/clear RTC alarm | Stable |

Calling a function in `25h-F2h` that is not listed here is
**Not implementable** — it dispatches through unrelated memory.

For dispatch evidence, see [RE notes: OS internals](../re-notes/os-diposb.md) and
[RE notes: CP/M comparison](../re-notes/cp-m-comparison.md).

## Safe extensions

### F3h — no-op

**Stability:** Stable

No operation; returns immediately.

### F5h — set event-wait delay

**Stability:** Provisional

**In:** `E` is a period byte; values below `04h` become `0Fh`.

**Out:** `A` is the previous period byte.

**Effects:** updates the stored period used by the event-wait loop and
clears its counter.

### F6h / F7h — get/set active device selector

**Stability:** Provisional — global, persistent mutation

* **F6h get:** returns current selector in `A`.
* **F7h set:** stores `E` as the active selector and replicates it into
  banked state; returns `A=00h`. No validation of `E`.

An application that changes the selector should save and restore the prior
value before exit. For the selector windows that choose FE83 entries, see
[Devices and storage](../manual/devices-and-storage.md) and
[Memory and I/O map](memory-map.md).

### F8h / FAh / FBh — table access

**Stability:** Advanced, unsafe — persistent configuration

* **F8h** copies 16 bytes from the FE83 link/device table to `DE`.
* **FAh** copies 16 bytes from `DE` to FE83.
* **FBh** copies 16 bytes from `DE` to FE93.

These are exact 16-byte copies; no per-field validation is performed.
No portable result in `A`.

### F9h — set device-pair preset

**Stability:** Provisional

**In:** `E=00h..04h` selects one of five fixed two-byte presets.

**Out:** on valid input, writes the pair to the active device-pair cells
and returns `A` as the second byte; `E>=05h` writes nothing and returns
`A=E`.

### FCh / FDh — RTC time

**Stability:** Stable

Both use an eight-byte record at `DE`. The canonical layout is:

| Offset | Meaning |
|---:|---|
| +0 | metadata (see notes) |
| +1 | year |
| +2 | month |
| +3 | day-of-month |
| +4 | hour |
| +5 | minute |
| +6 | second |
| +7 | day-of-week |

* **FCh set:** copies `+1..+7` into the RTC clock registers; `+0` is copied
  to scratch state but not written to RTC. Returns `A=00h`. Raw binary,
  24-hour; no range validation.
* **FDh get:** waits for the update-in-progress flag to clear, then fills
  `+1..+7` from the RTC and `+0` from stored metadata. Permanent flag
  blocks return.

For the register mapping and alarm details, see [Memory and I/O map](memory-map.md)
and [RE notes: RTC](../re-notes/rtc.md).

### FFh — RTC alarm control

**Stability:** Stable

* `DE=0000h` clears the alarm interrupt enable.
* Otherwise `DE` points to an eight-byte record; `+4..+6` program the alarm
  hours/minutes/seconds registers and enable the alarm. `+2/+3` are compared
  in software against the current date before the alarm is considered.

Both paths poll the update-in-progress flag before touching control
registers.

### Other extensions

* **2Dh select RST 28 mode** — Advanced, unsafe. Selects the target used by
  the shared `RST 28h` diagnostic path. `E=FFh` no-op, `FEh` default
  diagnostic, `FDh` deferred store, `FCh` fatal. Mutates global state for
  functions `0Dh`, `1Ch`, `1Eh`, `1Fh`, `30h`, `F4h`.
* **2Eh update drive metadata** — Advanced, unsafe. Computes and commits
  directory metadata for the selected drive.
* **30h / F4h shared diagnostic** — Advanced, unsafe. Behaviour depends on
  the current 2Dh mode; with the default target, caller `A` selects a
  diagnostic message.
* **62h integrity check** — Advanced, unsafe. Filesystem check.
* **68h/69h** — Stable no-op stubs.
* **FEh internal timed wait** — Advanced, unsafe, resident-only. Takes
  `E<<4` as interval and blocks on a countdown with `HALT`; requires
  resident context.

## Related

* [BDOS calls](bdos.md) — standard services and calling convention
* [Devices and storage](../manual/devices-and-storage.md)
* [Memory and I/O map](memory-map.md)
* [RE notes: OS internals](../re-notes/os-diposb.md)
