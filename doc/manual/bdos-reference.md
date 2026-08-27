# DIPOS-B BDOS reference

This is the programmer-facing reference for the stable CALL 0005h surface.
It supplements, rather than replaces, a CP/M 2.2 programming manual. The
firmware is CP/M-shaped, but not stock CP/M.

## Calling convention

Put the function number in C, pass a pointer in DE when the individual
function requires one, and call 0005h. The dispatcher is installed in
battery-backed RAM but the entry gate exists in every mapped bank.

Each function's return register and error convention must be verified from
its implementation before relying on it. The tables below classify whether a
function is usable, stubbed, or unsafe; they do not invent a uniform
carry/error convention where the firmware does not provide one.

## Standard CP/M-shaped functions

| Function | Service | Status |
|---:|---|---|
| 00h | system reset / warm boot | supported |
| 01h, 02h, 06h | console input, output, direct I/O | supported; device-routed |
| 03h | reader input | supported; barcode-reader stream |
| 04h, 05h | punch and list output | device-routed |
| 07h, 08h | get/set IOBYTE | compatibility stub; setting has no routing effect |
| 09h, 0Ah, 0Bh | string output, line input, status | supported |
| 0Ch | return version | returns 23h |
| 0Dh | reset disk system | stub |
| 0Eh, 19h | select/get current drive | supported |
| 0Fh-17h | FCB open through rename | supported |
| 18h | login vector | stub |
| 1Ah | set DMA address | stub |
| 1Bh, 1Dh, 1Fh | allocation/read-only/DPB vectors | stubs |
| 1Ch, 1Eh | write protect / attributes | stubs |
| 20h-24h | user code and random-file operations | implemented table entries; see the CP/M comparison for routine-level detail |

Functions in the otherwise unallocated range 25h-F2h are unsafe. The
dispatcher can read a handler pointer from unrelated kernel bytes; an
application must not probe this range.

## DIPOS-B extensions

| Function | Service | Status |
|---:|---|---|
| 2Dh | banked-call wrapper | advanced system service |
| 2Eh | directory-search helper | advanced system service |
| 30h | far-call stub | not an application API |
| 62h | filesystem/directory check | advanced |
| 68h, 69h | no-op stubs | compatibility only |
| F3h | no-op | compatibility only |
| F4h | far-call stub | not an application API |
| F5h | event-wait delay | supported, exact parameter contract needs a routine-level reference |
| F6h/F7h | get/set active device selector | supported |
| F8h/FAh | read/write 16-byte device-slot table FE83 | supported, powerful and persistent |
| F9h | set device-pair preset | partial; runtime consumer is not fully decoded |
| FBh | write 16-byte drive configuration table FE93 | supported, powerful and persistent |
| FCh/FDh | set/get RTC | supported; use the RTC reference for buffer format evidence |
| FEh/FFh | set/control RTC alarm | supported |

## Related documentation

* [Programmer's guide](programmer-guide.md) — compatibility differences,
  FCB use, device routing, and banked calls.
* [Devices and storage](devices-and-storage.md) — FE83, FE93, and the
  active-device selector.
* [Barcode reader](barcode-reader.md) — the complete fn 03h contract.
* [CP/M comparison](../internals/cp-m-comparison.md) — dispatch-table and
  handler-level evidence.
* [RTC](../internals/rtc.md) — HD146818 programming evidence.
