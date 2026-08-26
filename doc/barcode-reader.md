# Barcode-reader port — edge-capture + user decode hook

State: updated 2026-08-24 (root AGENTS.md §3). The side port identity
is **owner-adjudicated**: the 5-pin side port is a **barcode pen
input**, and the port-2D capture front end described below is the
**barcode reader front end**. The mechanics below are verified from
disassembly and remain identity-neutral. The **EXT STORAGE ADAPTER is
NOT bound to wire 0x2B**: its attachment point is unadjudicated, and
its data flows over the 4x byte transport.

## Hardware / signalling

| Signal | Port | Role |
|--------|------|------|
| `EXTBUS_EDGE` bit0 | 2Dh R | data/signal line (edges timed) |
| `EXTBUS_EDGE` bit1 | 2Dh R | secondary/status line |
| CTL_2A bit1 | 2Ah W | attention/trigger for the 0x2A wire variant |
| CTL_2C bit1/bit0 | 2Ch W | attention strobe for the default (2B) front-end |
| OUT_LATCH bit5 | 04h W | drive during an acquisition window |
| SOUND | 2Bh W | 0 (quiet) before timing |

Selector: **`fdca` (active external wire-id)**. `LinkCommandCheck`
(2F7D) → `LinkCommandLookup` (31C6) matches `fdca` against
`{2B,2A,23,03}` → `0x1221` (ExtBusArm/AcquireEdge) for 2B/2A, else
`0x1893` (dead stub) for 23/03.

> EXT STORAGE **data** transfers do NOT use this 2D front-end — they go
> over the 4x byte transport (4A/4B/4D/4E) via `LinkTransferService`/
> `LinkBlockTx/Rx`. The 2A/2C/2D edge-bang below is the **barcode
> reader front end** (owner-adjudicated 2026-08-24); the EXT STORAGE
> ADAPTER is NOT bound to wire 0x2B — its attachment point is
> unadjudicated, its data flows over the 4x byte transport.

## The capture pipeline (ExtBusAcquireEdge, 13B8)

1. Arm: `ExtBusArm` (1221) — caller `DE`=envelope buffer → `fbb7`(buf
   ptr), `A`=wire → `f9aa`; enable the 2A/2C attention line per wire.
2. Idle/arm window (1317): poll `EXTBUS_EDGE` bit0; on an edge start.
3. Time levels: count CPU loops while bit0 holds; record each
   bar/space width into f9B5, pulse count into f9B4; reverse order.
4. Delivery (1443–14A2): call the **decode hook** at `fbc2` (banked
   via fbc1/rst-10 stub at fbc0), passing `&fbb9` = {table ptr fbb9,
   count fbbb, status fbb5}. The hook may rewrite the table ptr/count
   to "decode in place" or zero the count to reject the read.
5. Copy result to the caller envelope: status @+0, count word @+4/+5,
   data @+6.

## The decoder hook — how to tie software into the OS

* Socket = **fbc2** (ptr), fbc1 (bank byte), fbc0 (RST-10 stub opcode
  `D7`). Installed by `ExtDecodeHookInstall` (156E) to the DEFAULT
  `ExtDecodeHookDiscard` (1567) at cold start:
  ```
  ExtDecodeHookDiscard:
      LD HL,0 ; LD (fbbb),HL ; RET      ; zero count -> discard
  ```
  So by default every capture is discarded. **A symbology/external
  decoder replaces fbc2 (and fbc1 if banked) with its own handler.**

* Hook contract (called in OS context after each capture):
   - on entry `fbc0?`/stack: return address 1468, then &fbb9 param
   - `fbb9`(word) = width-table ptr, `fbbb`(word) = count, `fbb5` = status
   - return with `fbb9`/`fbbb` updated: the OS copies @+4/+5 count and
     `@+6` data into the caller envelope.

* A COM/DIP program installs it:
  ```
  LD  HL, my_hook
  LD  (0FBC2h), HL      ; (resident code >=8000h needs no bank switch)
  ```
  Then BDOS **fn 03 (RDR: input)** = `BdosReaderInChar` (1080) returns
  the scan:
  ```
  loop: CALL 5, C=03h  ; blocks; returns A=1B when a scan arrives
        CALL 5, C=03h  ; next byte = count
        ; count more fn-3 reads -> the data bytes (hook's output)
  ```

## What a symbology decoder does

1. Install a hook at `fbc2` that reads the width table (`fbb9`/`fbbb`),
   normalises widths, classifies the symbology, and rewrites `fbb9` to
   its decoded string + `fbbb` to its length.
2. Zero the count to reject bad reads (auto re-arm).
3. Read the result either via BDOS fn 3 (per-byte) or by polling the
   envelope.

## Open

* The 2A/2C/2D edge front end is the **barcode reader**
  (owner-adjudicated 2026-08-24). Still open: no firmware strings for
  a symbology decoder; fn F8/FA can rewrite the FE83 wire table to
  point 0x2A.
* **Negative finding (CONFIRMED search 2026-08-25)**: the ROM contains
  no writer of the fn-03 ring (f95c/f95e) outside init/read — the
  ASCII producer must be a loaded-software decode hook; only the
  discard hook (1567) ships in ROM.
* The **EXT STORAGE ADAPTER is NOT bound to wire 0x2B** — its
  attachment point is unadjudicated; its data flows over the 4x byte
  transport.

## Completion event (end-to-end loop, closed 2026-08-24)

`fn 03 → BdosReaderInChar → (ring empty) → ConsoleMsgToLink →
LinkTransportCall → EventWaitForLink(mask)` HALTs on `fbc9 & mask`.
On capture completion `ExtBusComplete` (14A3) → `LinkResetSession`
(30BD) does **`fbc9 |= 0x01`** (event bit0) and clears `fdca` (frees
the wire) → the fn-03 waiter wakes, returns A=mask(bit0), then reads
count (f95c) + streams data (f95E). This closes the previously-open
follow-up "who posts the reader event bit".

Other `fbc9` bits (CONFIRMED map 2026-08-25): bit0 = session/link
event posted by LinkResetSession (OR 01 @30C0), cleared by
LinkTransportCall (AND FE @2F30); bit1 = RTC date-changed (OR 02
@2235, RtcDateChangedCheck; tested/cleared by DeviceLinkStatusPending
@1073/1077); bit2 = keyboard char available (OR 04 @18E0/1968; cleared
by KeyboardReadChar @18CE); bit3 = date-change wait ack (OR 08 @170B,
a deferred work-item callback queued via fbcc/2189; cleared by
EventWaitForLink @169A). Bits 4-7: no setters found.