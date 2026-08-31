# BDOS calls — standard CP/M-shaped services

This page states the **application contract** for the standard BDOS services
reachable via `CALL 0005h`. It is a contract summary, not a full
implementation proof. For register-level evidence, handler locations, and
the complete dispatch table, see
[RE notes: OS internals](../re-notes/os-diposb.md) and
[RE notes: CP/M comparison](../re-notes/cp-m-comparison.md).

## Stability

* **Stable** — documented signature plus tested return value and side effects.
* **Provisional** — service exists and is exercised, but edge cases, error
  codes, or flag contracts are not yet frozen.
* **Not implementable / Do not use** — stub or unsafe global-state path;
  an application must not call it.

## Calling convention

Put the function number in **C**, place a pointer argument in **DE** when
the service requires one, and `CALL 0005h`. The gate is present in every
memory bank.

On return, `A` and `HL` carry the service result where documented; `BC`,
`DE`, `IX`, and `IY` are not preserved and reflect the handler's final
values. Flag state after `CALL 0005h` is derived from a kernel envelope
and is not a handler result — only the documented `A`/`HL` values are
portable. Any register or flag not listed as an output is unspecified.

For the byte-level envelope that establishes this rule, see
[RE notes: OS internals](../re-notes/os-diposb.md).

## Function table

| Function | Service | Stability | Notes |
|---:|---|---|---|
| 00h | system reset / warm boot | Provisional | Enters restart sequence; does not return in the normal sense |
| 01h, 02h, 06h | console input, output, direct I/O | Provisional | Device-routed; fn 06 poll with `E=FFh` is nonblocking. See [Extensions](extensions.md) for routing |
| 03h | reader input | Provisional | Barcode-reader byte stream; see [Barcode reader](barcode.md) |
| 04h, 05h | punch and list output | Provisional | Device-routed |
| 07h, 08h | get/set IOBYTE | Not implementable | Stub: setting has no routing effect |
| 09h, 0Ah | string output, line input | Provisional | `09h` terminates on `$`; `0Ah` uses `DE[0]` as max and writes `DE[1]` count |
| 0Bh | console status | Stable | `A=FFh` if input pending else `00h`; no wait |
| 0Ch | return version | Stable | `HL=0023h` |
| 0Dh | reset disk system | Not implementable | Unsafe shared diagnostic path — do not call |
| 0Eh | select disk | Stable | `E=00h..0Fh`; `A=00h` on success, `FFh` if `E>=10h` |
| 19h | get current drive | Provisional | Returns drive in `A` |
| 0Fh-17h | FCB open through rename | Provisional | `DE` points to FCB; see cards below |
| 18h | login vector | Not implementable | Stub `HL=FFFFh` |
| 1Ah | set DMA address | Provisional | Stores `DE` as DMA pointer |
| 1Bh, 1Dh | allocation / read-only vectors | Not implementable | Stub `HL=0000h` |
| 1Ch, 1Eh, 1Fh | write protect / attributes / DPB | Not implementable | Unsafe shared diagnostic path — do not call |
| 20h | get/set user code | Not implementable | Stub `A=00h` |
| 21h, 22h, 24h | random read/write/set record | Provisional | |
| 23h | compute file size | Provisional | Writes record count to FCB `+21h..+23h` |

Functions `25h-F2h` are not allocated. Calling an unallocated function
jumps through unrelated memory — **Not implementable, do not probe**.

## Verified contract cards

### 0Bh — console status

**Stability:** Stable

**In:** no input.

**Out:** `A=FFh` if input is pending (pending-event flag set or current
keyboard byte nonzero) else `A=00h`.

**Blocks:** no.

**Errors:** none.

### 0Ch — return version

**Stability:** Stable

**In:** none.

**Out:** `HL=0023h`.

**Blocks:** no.

### 0Eh — select disk

**Stability:** Stable

**In:** `E` is drive number `00h..0Fh` (A: through P:).

**Out:** `A=00h` on valid selection; `A=FFh` if `E>=10h`.

**Blocks:** no.

**Effects:** updates the current-drive selection visible in page zero.

### 23h — compute file size

**Stability:** Provisional

**In:** `DE` points to an FCB on a RAM drive.

**Out:** on success `A=00h` and FCB `+21h..+23h` receives the size in
128-byte records; missing entry returns `A=FFh`; non-RAM drive takes the
`2Bh` error path.

**Effects:** temporarily wildcards the extent and searches matching
directory entries.

For evidence and remaining limits, see
[RE notes: OS internals](../re-notes/os-diposb.md) and
[RE notes: CP/M comparison](../re-notes/cp-m-comparison.md).

### 06h — direct console I/O

**Stability:** Provisional

**In:** `E=FFh` selects the nonblocking poll; any other value is an output
byte routed through the active console device.

**Out (poll):** `A=1Eh` if a pending event was consumed, otherwise a ring
byte when present, otherwise the pending byte. `A` is the only reliable
result.

**Blocks:** poll does not wait. Output may retry.

**Errors:** routed output may return `A=FFh` on transport failure.

### Console and line I/O

* **00h warm restart** — transfers to restart sequence; not a normal return.
* **01h console input** — returns byte in `A`; may return `1Eh` when a pending
  event was consumed.
* **02h console output** — `E` is the output byte through the active route;
  success `A=00h`, routed failure `A=FFh`.
* **03h reader input** — staged reader stream; each scan arrives as `1Bh`,
  count, then data bytes. See [Barcode reader](barcode.md).
* **04h punch output** — `E` is the byte; descriptor `80h` selects the local
  path, otherwise routed. Success `A=00h`; routed error returns helper status.
* **05h list output** — `E` is the byte; result is path-dependent.
* **09h print string** — `DE` points to `$`-terminated bytes.
* **0Ah buffered line input** — `DE[0]` is max, `DE[1]` receives count, bytes
  from `DE[2]`; `7Fh` backspaces, `0Dh` terminates, `1Bh` introduces a counted
  literal block.

### FCB directory calls

`DE` points to a mutable FCB-like buffer.

* **0Fh/10h open/close** — success `A=00h`, failure `A=FFh`. Open copies
  directory bytes `+01h..+1Fh`; close writes them back.
* **11h/12h search first/next** — success returns a directory result index
  in `A`, failure `A=FFh`; result copied to DMA buffer. Search-next uses
  global continuation state.
* **13h delete** — success `A=00h`, no-match `A=FFh`.
* **16h make** — success `A=00h`, existing/failure `A=FFh`.
* **17h rename** — expects two adjacent FCB records, second at `DE+10h`.

### FCB record calls

* **14h/15h sequential read/write** — transfers one 128-byte record via the
  DMA buffer; success `A=00h`.
* **21h/22h random read/write** — addressing uses FCB `+21h` and `+22h`
  only; `+23h` is not interpreted. Success `A=00h`.
* **24h set random record** — writes three-byte little-endian value at
  `+21h..+23h` derived from `+0Ch` and `+20h`.

## Related

* [Programmer guide](../manual/programmer-guide.md) — CP/M differences and
  FCB context
* [Supported profile](../manual/supported-profile.md) — conservative portable
  subset
* [Devices and storage](../manual/devices-and-storage.md) — FE83/FE93 and
  active-device selector
* [RE notes: CP/M comparison](../re-notes/cp-m-comparison.md) — dispatch and
  deviation evidence
