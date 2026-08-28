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

Put the function number in **C**, pass a pointer argument in **DE** when the
individual function requires one, and `CALL 0005h`. The dispatcher is installed
in battery-backed RAM, but the entry gate exists in every mapped bank.

The complete call envelope is byte-verified (`Kernel_BankedCallEnvelope`
`ram:F376-F3C3` plus its return continuation `ram:F3C4-F407`, and
`KernRestoreBankNotify` `ram:F54E`, which preserves AF):

- **Into the handler** the dispatcher passes `A` = the caller's original `A`,
  `HL` = `ram:FEFA`, `DE` = the caller's `DE`, `B` = 0, and `C` = function
  number. Handlers normally read only `E`/`DE` (or nothing).
- **Out of the call**, `A` and `HL` are the handler's own `A`/`HL` results;
  `BC`, `DE`, `IX`, and `IY` pass through exactly as the handler left them.
- **Flags are not handler-derived.** The return continuation executes
  `AND 0x07` on `ram:FDBD` at `ram:F3CA`, and that result is the flag state
  the caller sees. With no hook armed (`FDBD & 7 == 0`, the default) the caller
  sees `Z=1, C=0, S=0, P/V=1`. A handler's own carry/zero exits are therefore
  **not observable** through `CALL 0005h`.

Consequently only the `A` (and, where documented, `HL`) value is a portable
return. The cards below state those results and never promise `carry`/`zero`
semantics; where an earlier card mentioned flags, that has been superseded by
this uniform rule.

## Standard CP/M-shaped functions

| Function | Service | Status |
|---:|---|---|
| 00h | system reset / warm boot | CONFIRMED behaviour; ABI incomplete |
| 01h, 02h, 06h | console input, output, direct I/O | fn 06 poll ABI confirmed; output ABI incomplete; device-routed |
| 03h | reader input | CONFIRMED behaviour; ABI incomplete; barcode-reader stream |
| 04h, 05h | punch and list output | CONFIRMED behaviour; ABI incomplete; device-routed |
| 07h, 08h | get/set IOBYTE | Stub; setting has no routing effect |
| 09h, 0Ah | string output, line input | CONFIRMED behaviour; ABI incomplete |
| 0Bh | console status | CONFIRMED ABI |
| 0Ch | return version | CONFIRMED ABI: HL=0023h |
| 0Dh | reset disk system | Advanced / unsafe shared diagnostic path |
| 0Eh | select disk | CONFIRMED ABI |
| 19h | get current drive | CONFIRMED behaviour; ABI incomplete |
| 0Fh-17h | FCB open through rename | CONFIRMED behaviour; ABI incomplete |
| 18h | login vector | stub |
| 1Ah | set DMA address | CONFIRMED behaviour; ABI incomplete |
| 1Bh, 1Dh | allocation/read-only vectors | stubs (HL=0000h) |
| 1Ch, 1Eh, 1Fh | write protect / attributes / DPB | unsafe RST-28 path; do not call |
| 20h | get/set user code | stub (A=00h) |
| 21h, 22h, 24h | random read/write/set record | CONFIRMED behaviour; ABI incomplete |
| 23h | compute file size | CONFIRMED behaviour; ABI incomplete |

Functions in the otherwise unallocated range 25h-F2h are unsafe. The
dispatcher can read a handler pointer from unrelated kernel bytes; an
application must not probe this range.

## Verified contract cards

### 06h -- direct console I/O

**Status:** CONFIRMED behaviour; output ABI incomplete.

**In:** `E=FFh` selects the nonblocking input/status poll. Any other value
is passed as the output byte to the fn 02h console-output path.

**Out, poll:** the result is path-dependent. If the pending-event bit is
set, the call clears it and returns `A=1Eh`. Otherwise it checks the selected
device's keyboard input and then the console ring. A ring byte is returned
and consumed when present. An empty ring atomically reads and clears a
separate pending byte, so `A` is the only reliable result. Flags are never
meaningful through `CALL 0005h` (see Calling convention).

**Blocks:** the `E=FFh` path is nonblocking: it contains no wait loop or
`HALT`. The output path can retry its transport call, so it is not guaranteed
nonblocking.

**Effects:** poll can clear the pending-event bit, advance/reset the console
ring pointers, or clear the pending byte. Output is routed through the active
console-device selection.

**Errors:** the output path explicitly returns `A=FFh` when its device-send
helper fails. The byte-level cause remains open. (Flags are not observable
through `CALL 0005h`.)

**Limit:** the meanings of the pending-event bit, `1Eh`, and the empty-ring
pending byte are not yet established. `E=FEh` and `E=FDh` are ordinary output
bytes here, not additional CP/M-style input modes.

**Evidence:** dispatch word at `ROM00:3714`; handler
`BdosDirectConsoleIo`, `ROM00:0FD6-1014`; output router
`DeviceConsoleOut2`, `ROM00:0F37-0FA3`.

### 0Bh -- console status

**Status:** CONFIRMED ABI.

**In:** no register input is read.

**Out:** `A=FFh` when either the pending-event bit is set or the current
keyboard-ring byte is nonzero; otherwise `A=00h`. Flags are not meaningful
through `CALL 0005h`.

**Blocks:** no; the handler has no calls, loop, or `HALT`.

**Effects:** enables interrupts with `EI`; it otherwise does not modify RAM.

**Errors:** none encoded.

**Limit:** this status test does not inspect the console ring used by fn 06h,
and it does not identify the event bit's source.

**Evidence:** dispatch word at `ROM00:371E`; handler entry
`BdosGetConsoleStatus`, `ROM00:0FC5-0FD5`.

### 0Ch -- return version

**Status:** CONFIRMED ABI.

**In:** no register input is read.

**Out:** `HL=0023h` (CP/M 2.3-style version value). Flags are not meaningful
through `CALL 0005h`.

**Blocks:** no.

**Effects and errors:** none.

**Evidence:** dispatch word at `ROM00:3720`; `BdosReturnVersion`,
`ROM00:15C7-15CA`.

### 0Eh -- select disk

**Status:** CONFIRMED ABI.

**In:** `E` is the drive number, `00h` through `0Fh` (A: through P:).

**Out:** `A=00h` after a valid selection; `A=FFh` when `E>=10h`. Test `A`;
flags are not meaningful through `CALL 0005h`.

**Blocks:** no. A valid selection performs a bounded 64-bank replication
sweep, with no wait loop or `HALT`.

**Effects:** stores the selected value as the current drive and copies it to
page-zero cell 4 in every bank. The BDOS dispatcher restores the caller's
bank before return.

**Errors:** `A=FFh` for drive numbers outside `00h..0Fh`.

**Evidence:** dispatch word at `ROM00:3724`; `BdosSelectDisk`,
`ROM00:15B3-15C6`; `Mem_BankSweepPutByte`, `ram:F46D-F47C`.

### 23h -- compute file size

**Status:** CONFIRMED behaviour; ABI incomplete.

**In:** `DE` points to an FCB on a RAM drive.

**Out:** on success, `A=00h` and the three-byte little-endian random-record
field at FCB offsets `+33..+35` receives the size in 128-byte records. A
missing matching directory entry returns `A=FFh`. A non-RAM drive follows the
`A=2Bh` error path.

**Effects:** temporarily wildcards the FCB extent, searches matching directory
entries, then restores the original extent. It computes the final record count
from the highest matching extent and that extent's record count.

**Limit:** remaining register/flag preservation and the exact `2Bh` user error
mapping are not yet a public contract.

**Evidence:** dispatch word at `ROM00:374E`; `BdosComputeFileSize`,
`ROM00:0CF1-0D6A`.

### Console and line input/output

**00h -- warm restart:** transfers into the restart sequence; it is not a
normal returning subroutine and no preserved-register contract is published.

**01h -- console input:** enters the device-routed console-input path and
returns the input byte in `A`. It returns `A=1Eh` when a pending input event
was consumed instead of a character; no-input and transport-error paths enter
device helper code whose blocking meaning is device-dependent.

**02h -- console output:** `E` is sent through the active console route. On the
verified local paths it returns `A=00h` after a successful device send and
`A=FFh` after a device-send failure; the no-destination path returns the device
descriptor byte in `A`. Flags are not meaningful.

**03h -- reader input:** enters the staged reader stream. The documented scan
stream begins with `1Bh`, then a count byte and that many data bytes; wait and
error behavior remain device-dependent (see [barcode-reader](barcode-reader.md)).

**04h -- punch output:** stores `E` in the output byte, derives a device index
from the active selector (`fbc5 >> 4 & 1Fh`), then falls off the handler
suffix. There is no normal return; treat this call as unresolved.

**05h -- list output:** `E` is the output byte. On the routed path it builds a
request in shared work storage and waits until a completion cell is nonzero;
the local path calls the device output helper. Its return `A` is
path-dependent.

**09h -- print string:** `DE` points to bytes terminated by `$` (`24h`). The
routine emits each preceding byte through the output helper and restores `DE`
before return; output failure behavior is incomplete.

**0Ah -- buffered console input:** `DE[0]` supplies the maximum count;
`DE[1]` receives the accepted count and accepted bytes are written from
`DE[2]` upward. `0Dh` terminates, `7Fh` backspaces, and `1Bh`/`FFh` abort. The
handler returns `A = accepted count`, matching `DE[1]`.

### FCB directory calls (ABI-incomplete)

These calls take `DE` as a mutable FCB-like buffer. They normalize bytes
`DE+1..+11`; invalid-drive paths enter a shared error helper whose final
return value is not established (flags are never meaningful, see Calling
convention).

**0Fh/10h -- open/close:** local success returns `A=00h`; local failure
returns `A=FFh`. Open copies directory bytes `+1..+31` to the caller buffer;
close copies those caller bytes back and writes the entry.

**11h/12h -- search first/next:** local success returns a four-slot directory
result index in `A`; failure returns `A=FFh`. Both temporarily write `3Fh` at
caller offset `+12`, restore it, and copy a 128-byte result to the DMA buffer.
Search-next uses global continuation state.

**13h -- delete:** local success returns `A=00h`; no-match returns `A=FFh`.
It permanently writes `3Fh` at `+12`, marks matched entries
`E5h`, and processes eight words at offsets `+16..+31`; their meaning is OPEN.

**16h -- make:** local success returns `A=00h`; existing/local-failure paths
return `A=FFh`. It clears caller `+12`, creates a zeroed 32-byte entry, and
copies resulting directory bytes back to the caller buffer.

**17h -- rename:** expects two adjacent FCB-like records, the second at
`DE+10h`. It updates the selected entry's eleven name bytes from the second
record; its completed-path `A` is not a portable success indicator.

### FCB record calls (ABI-incomplete)

**14h/15h -- sequential read/write:** normal paths transfer one 128-byte
record through the configured DMA buffer and return `A=00h`. Both advance
caller `+20`; rollover increments `+12` and clears `+20`. Nonzero results are
path-dependent.

**21h/22h -- random read/write:** use caller `+21..+23` to select state,
transfer one 128-byte record on a normal path, and return `A=00h`. Selection
mutates caller `+20`; observed nonzero results are not public error names.

**24h -- set random record:** derives and writes a three-byte little-endian
value at caller `+21..+23` from `+12` and `+20`; its high byte is zero. It
does not transfer data and has no established result ABI.

## DIPOS-B extensions

| Function | Service | Status |
|---:|---|---|
| 2Dh | banked-call wrapper | Advanced / unsafe system service |
| 2Eh | directory-search helper | Advanced / unsafe system service |
| 30h | shared diagnostic dispatch | Advanced / unsafe; caller A selects diagnostic behavior |
| 62h | filesystem/directory check | Advanced / unsafe |
| 68h, 69h | no-op stubs | compatibility only |
| F3h | no-op | compatibility only |
| F4h | shared diagnostic path | Advanced / unsafe; caller A selects diagnostic behavior |
| F5h | event-wait delay | CONFIRMED behaviour; A = previous period byte |
| F6h/F7h | get/set active device selector | Advanced / unsafe; persistent selector mutation |
| F8h/FAh | read/write 16-byte device-slot table FE83 | Advanced / unsafe; persistent configuration |
| F9h | set device-pair preset | CONFIRMED behaviour; result values documented |
| FBh | write 16-byte drive configuration table FE93 | Advanced / unsafe; persistent configuration |
| FCh/FDh | set/get RTC | CONFIRMED behaviour; FC returns A=00h |
| FEh/FFh | set/control RTC alarm | CONFIRMED behaviour; result ABI limited |

### F4h -- shared diagnostic dispatch

**Status:** Advanced / unsafe. Do not use as a far-call service.

**In:** the normal BDOS path restores the caller's `A` before entering the
handler. The handler's `C=FEh` assignment is overwritten before comparison.

**Out:** values in the fatal diagnostic table do not return. Other values
return, but the caller-visible result is not meaningful: `A` echoes the
caller's own value and flags are envelope-derived (see Calling convention).
There is no application-stable result.

**Effects:** may display a diagnostic or wait for input.

**Evidence:** wrapped dispatch word at `ROM00:36F0`; shared handler
`Bdos_SharedErrorStub`, `ROM00:1893-1896`; dispatcher and diagnostic paths
`ram:F382-F407` and `ROM00:2B55-2BCC`.

### Special-dispatch extensions

**2Dh -- banked-call wrapper:** switches to bank 0, invokes the fixed
bank-0 vector, restores the previous bank, and applies the kernel IRQ policy.
Its argument and return ABI are not application-safe; use it only as an
internal system mechanism.

**2Eh -- directory helper:** runs the FCB/directory search helper. Its mutable
FCB state and result conventions are internal filesystem mechanics, not a
portable application API.

**30h -- shared diagnostic dispatch:** reaches the same unsafe
`Bdos_SharedErrorStub` as F4h; caller `A` selects diagnostic behavior.

**62h -- integrity check:** invokes the filesystem integrity-check shim.
Input, result, and repair semantics remain ABI-incomplete.

**68h/69h:** both reach the same one-instruction `RET` compatibility stub.

### Direct compatibility stubs

**07h/08h -- IOBYTE:** both reach one `RET` instruction. Neither reads nor
writes an IOBYTE; do not use them for device routing.

**18h -- login vector:** returns `HL=FFFFh`. No login-vector computation is
performed.

**19h -- current drive:** returns the active-drive byte in `A`.

**1Ah -- DMA address:** stores `DE` as the DMA pointer. This is a real state
mutation, not a no-op; its downstream record-I/O ABI remains incomplete.

**20h -- user code:** returns `A=00h`; no user-code state is read or written.

### Safe extension mechanics

**F3h:** one-instruction `RET` compatibility no-op.

**F5h:** takes `E` as an event-wait period byte; values below `04h` become
`0Fh`, writes the result to the period cell, and clears its counter. Returns
`A = previous period byte`. The stored period is `FBD6:FBD7` (the result in
the high byte); its units remain OPEN.

**F6h/F7h:** get/set the active-device byte. F6h returns `A=(fbc5)`. F7h
stores `E` to `fbc5` and replicates it into banked page-zero state (returns
`A=00h` from the bank sweep); it performs no value validation.

**F8h:** copies exactly 16 bytes from the FE83 configuration table to the
writable buffer at `DE`. **FAh** copies exactly 16 bytes from `DE` to FE83;
**FBh** does the same to FE93. These leave `A` as the caller bank byte (no
portable result). Table-field meanings and persistence remain OPEN.

**F9h:** indexes one of five fixed two-byte presets with `E=00h..04h`, writing
the selected pair to the active device-pair cells (`fbc8`,`fbc7`). Valid input
returns `A = the pair's second byte`; `E>=05h` writes nothing and returns
`A=E`. Preset field meanings remain OPEN.

### RTC and alarm extensions

**FCh -- set RTC time:** `DE` points to an eight-byte source buffer. The
service copies it to RTC scratch state, writes the RTC time registers under
the SET/divider-stop sequence, and returns `A=00h`. The source byte at `+0`
is copied but its meaning is OPEN; fields `+1..+7` map to the RTC time file.

**FDh -- get RTC time:** `DE` points to an eight-byte writable destination.
The service waits for RTC Reg-A UIP to clear, reads the time file, and writes
the result to that buffer. A permanently asserted UIP bit prevents return.
Byte `+0` remains OPEN.

**FEh -- alarm work-item wait:** this is not a general alarm-time setter.
Its low `E` byte is shifted by four, registers a work item, and blocks in a
`HALT` loop until the work-item word clears. The full-slot condition is not
caller-observable through the envelope, and no portable result is defined.

**FFh -- program or clear RTC alarm:** `DE=0000h` clears RTC Reg-B AIE.
Otherwise, `DE` points to eight source bytes; the service waits for UIP clear,
programs alarm registers, and enables AIE. Only the bytes consumed for those
alarm registers are established; field names and lifecycle semantics remain
OPEN.

## Related documentation

* [Programmer's guide](programmer-guide.md) — compatibility differences,
  FCB use, device routing, and banked calls.
* [Devices and storage](devices-and-storage.md) — FE83, FE93, and the
  active-device selector.
* [Barcode reader](barcode-reader.md) — the complete fn 03h contract.
* [CP/M comparison](../internals/cp-m-comparison.md) — dispatch-table and
  handler-level evidence.
* [RTC](../internals/rtc.md) — HD146818 programming evidence.
