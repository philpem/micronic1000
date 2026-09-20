# Supported application profile

This page states the portion of DIPOS-B that an application can use from the
current evidence. It is deliberately narrower than the firmware's full
surface. Scope: the supplied DIPOS-B ROM images and the documented emulator
tests; this is not a compatibility promise for other firmware revisions.
The [reference status terms](../reference/README.md#stability-terms) separate
contract maturity from support policy and validation environment.

## Target environment

* **Stable:** CPU code is Z80 code. A program enters through the CP/M-style
  `CALL 0005h` gate with its function number in `C`.
* **Stable:** a raw COM image loads at `0100h` and may occupy through
  `D080h`, a maximum of `0xCF81` bytes (53,121 bytes). See
  [Program formats](../reference/program-formats.md).
* **Stable:** the `0000h-7FFFh` window is banked; `8000h-FFFFh` is fixed
  battery-backed RAM. Do not assume a bank selection survives a call unless
  its routine-level contract says so.
* **Stable:** `RST 10h` (restart vector 2) is DIPOS-B's banked-call
  dispatcher. It is an advanced system mechanism, not part of the portable
  COM application profile.

## Safe starting subset

The following operations are appropriate starting points for a conventional
CP/M-style application, subject to the ABI qualification in the
[BDOS reference](../reference/bdos.md): console input/output, strings and line
input (functions 01h, 02h, 06h, 09h, 0Ah and 0Bh), standard FCB file
operations (0Fh-17h and 21h-24h), and drive selection (0Eh and 19h).

**Provisional — implemented, ABI incomplete:** these services work, but
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
* Barcode hook installation is an advanced resident-code operation, excluded
  by this profile's support policy. Its measured entry/return contract,
  bank handling, lifetime and buffer limits are published in the
  [barcode reference](../reference/barcode.md#the-decode-hook). Reading scans
  via BDOS `03h` does not require installing a hook.
* Do not claim physical Commstar interoperability from emulator success.
  RECORD/BLOCK formats and bidirectional transfers are documented; the
  remaining return-wire handshake and validation limits are listed in
  [Commstar status](../protocol/commstar.md#scope-and-implementation-status).

## Packaging and deployment

Start with [Build and run a first COM program](first-program.md) for a
reproducible emulator workflow and explicit physical-deployment limits.

COM and DIP grammars are byte-verified in
[Program formats](../reference/program-formats.md). The synthetic peer can
download programs through the firmware's Load/Run path in the emulator.
Outbound IR has been captured; physical deployment remains blocked on the
return-side handshake and validation against a historical adapter. See
[Commstar server readiness](../protocol/commstar.md#historical-server-readiness).
Image validation checks packaging, not hardware transfer compatibility.

## Reading the references

Use the [BDOS reference](../reference/bdos.md) for service classification, then
the [programmer's guide](programmer-guide.md) for CP/M deviations and FCB
context. Evidence pages explain why a claim is believed; they are not a
substitute for a published callable ABI.
