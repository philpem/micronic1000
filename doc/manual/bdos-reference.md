# DIPOS-B BDOS reference

This is the programmer-facing classification of the CALL 0005h surface. It
supplements, rather than replaces, a CP/M 2.2 programming manual. The firmware
is CP/M-shaped, but not stock CP/M. Start with the
[supported application profile](supported-profile.md).

## Status labels

* **CONFIRMED ABI** — registers, flags, effects, and errors are published.
* **CONFIRMED behaviour; ABI incomplete** — implementation is established, but
  a complete caller contract is not yet published.
* **Stub** — callable but no useful CP/M behaviour is supplied.
* **Advanced / unsafe** — system mechanism or a call whose global effects make
  it unsuitable for a general application until its full contract is known.

## Calling convention

Put the function number in C, pass a pointer in DE when the individual
function requires one, and call 0005h. The dispatcher is installed in
battery-backed RAM but the entry gate exists in every mapped bank.

Each function's return register and error convention must be verified from its
implementation before relying on it. The tables below do not invent a uniform
carry/error convention where the firmware does not provide one.

## Standard CP/M-shaped functions

| Function | Service | Status |
|---:|---|---|
| 00h | system reset / warm boot | CONFIRMED behaviour; ABI incomplete |
| 01h, 02h, 06h | console input, output, direct I/O | CONFIRMED behaviour; ABI incomplete; device-routed |
| 03h | reader input | CONFIRMED behaviour; ABI incomplete; barcode-reader stream |
| 04h, 05h | punch and list output | CONFIRMED behaviour; ABI incomplete; device-routed |
| 07h, 08h | get/set IOBYTE | Stub; setting has no routing effect |
| 09h, 0Ah, 0Bh | string output, line input, status | CONFIRMED behaviour; ABI incomplete |
| 0Ch | return version | CONFIRMED: returns 23h; remaining ABI incomplete |
| 0Dh | reset disk system | stub |
| 0Eh, 19h | select/get current drive | CONFIRMED behaviour; ABI incomplete |
| 0Fh-17h | FCB open through rename | CONFIRMED behaviour; ABI incomplete |
| 18h | login vector | stub |
| 1Ah | set DMA address | stub |
| 1Bh, 1Dh, 1Fh | allocation/read-only/DPB vectors | stubs |
| 1Ch, 1Eh | write protect / attributes | stubs |
| 20h-24h | user code and random-file operations | CONFIRMED behaviour; ABI incomplete; see the CP/M comparison |

Functions in the otherwise unallocated range 25h-F2h are unsafe. The
dispatcher can read a handler pointer from unrelated kernel bytes; an
application must not probe this range.

## DIPOS-B extensions

| Function | Service | Status |
|---:|---|---|
| 2Dh | banked-call wrapper | Advanced / unsafe system service |
| 2Eh | directory-search helper | Advanced / unsafe system service |
| 30h | far-call stub | Not an application API |
| 62h | filesystem/directory check | Advanced / unsafe |
| 68h, 69h | no-op stubs | compatibility only |
| F3h | no-op | compatibility only |
| F4h | far-call stub | not an application API |
| F5h | event-wait delay | CONFIRMED behaviour; ABI incomplete |
| F6h/F7h | get/set active device selector | Advanced / unsafe; persistent selector mutation |
| F8h/FAh | read/write 16-byte device-slot table FE83 | Advanced / unsafe; persistent configuration |
| F9h | set device-pair preset | ABI incomplete; runtime consumer not fully decoded |
| FBh | write 16-byte drive configuration table FE93 | Advanced / unsafe; persistent configuration |
| FCh/FDh | set/get RTC | CONFIRMED behaviour; ABI incomplete; see RTC evidence |
| FEh/FFh | set/control RTC alarm | CONFIRMED behaviour; ABI incomplete |

## Related documentation

* [Programmer's guide](programmer-guide.md) — compatibility differences,
  FCB use, device routing, and banked calls.
* [Devices and storage](devices-and-storage.md) — FE83, FE93, and the
  active-device selector.
* [Barcode reader](barcode-reader.md) — the complete fn 03h contract.
* [CP/M comparison](../internals/cp-m-comparison.md) — dispatch-table and
  handler-level evidence.
* [RTC](../internals/rtc.md) — HD146818 programming evidence.
