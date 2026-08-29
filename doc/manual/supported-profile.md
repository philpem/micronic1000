# Supported application profile

This page states the portion of DIPOS-B that an application can use from the
current evidence. It is deliberately narrower than the firmware's full
surface. Every claim is either **CONFIRMED** or explicitly limited below.

## Target environment

* **CONFIRMED:** CPU code is Z80 code. A program enters through the CP/M-style
  `CALL 0005h` gate with its function number in `C`.
* **CONFIRMED:** a raw COM image loads at `0100h` and may occupy through
  `D080h`, a maximum of `0xCF81` bytes (53,121 bytes). See
  [Program formats](program-formats.md).
* **CONFIRMED:** the `0000h-7FFFh` window is banked; `8000h-FFFFh` is fixed
  battery-backed RAM. Do not assume a bank selection survives a call unless
  its routine-level contract says so.
* **CONFIRMED:** `RST 10h` (restart vector 2) is DIPOS-B's banked-call
  dispatcher. It is an advanced system mechanism, not part of the portable
  COM application profile.

## Safe starting subset

The following operations are appropriate starting points for a conventional
CP/M-style application, subject to the ABI qualification in the
[BDOS reference](bdos-reference.md): console input/output, strings and line
input (functions 01h, 02h, 06h, 09h, 0Ah and 0Bh), standard FCB file
operations (0Fh-17h and 21h-24h), and drive selection (0Eh and 19h).

**CONFIRMED behaviour; ABI incomplete:** these services are implemented, but
the current manual does not yet publish a complete per-function register,
flag, blocking, and error contract. Treat returned registers other than a
documented value as volatile, and do not turn this list into an ABI guarantee.

## Excluded from the portable profile

* Do not call the dispatcher range `25h-F2h`: it can derive a target from
  unrelated kernel bytes.
* Do not rely on CP/M disk-management calls `0Dh`, `1Ch`, `1Eh`, `1Fh`,
  `30h`, `F4h`; they are **unsafe mutable `RST 28h` diagnostic paths**
  conditional on the global `Bdos_SelectRst28Mode` (`ram:F55A`), not inert
  stubs. `1Bh`/`1Dh` get allocation/read-only vector are `HL=0000h` stubs;
  `1Ah` set-DMA is implemented (stores `DE`) but downstream ABI remains
  incomplete; `FEh` is an internal timed wait (`Bdos_InternalTimedWait`)
  requiring resident context.
* Do not modify the active-device selector or `FE83`/`FE93` configuration tables
  until the complete `F6h-FBh` contracts and restoration rules are published.
* Do not install a barcode decode hook from a general application. Its complete
  bank, register-preservation, lifetime, and reentrancy contract is still
  incomplete.
* Do not claim Commstar file-transfer compatibility: the controller-facing
  byte transaction is documented, but live RECORD/BLOCK payloads and session
  grammar remain open.

## Packaging and deployment

COM and DIP grammars are byte-verified in
[Program formats](program-formats.md). The runtime loader's physical input
provider has not been identified, so this repository cannot yet give a
hardware-independent transfer recipe. A generated image can be checked against
the documented grammar and size limits, but loading it onto a real device still
requires an owner-provided route or a future capture-backed workflow.

## Reading the references

Use the [BDOS reference](bdos-reference.md) for service classification, then
the [programmer's guide](programmer-guide.md) for CP/M deviations and FCB
context. Evidence pages explain why a claim is believed; they are not a
substitute for a published callable ABI.
