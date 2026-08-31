# Barcode reader — byte-stream API

This page states the **application contract** for the barcode-reader
input path. It describes what a portable application may rely on; the
sampling mechanics, timing table, and hook installation evidence live in
[RE notes: OS internals](../re-notes/os-diposb.md) and the RE barcode
note.

## Stability

| Use | Stability |
|---|---|
| Read scans via BDOS `RDR:` (function 03h) | **Stable** |
| Install a custom decode hook | **Provisional** — complete bank and lifetime contract is not yet frozen |

For evidence including port assignments, hook address, and width-table
layout, see [RE notes: OS internals](../re-notes/os-diposb.md).

## Hardware

The barcode pen is the 5-pin side-port peripheral. Its data/signal line
and secondary status line are sampled during a capture window; the
firmware counts level widths and delivers a table of widths to the decode
hook. The hardware identity of this port as the barcode front end is
owner-confirmed; the data-transfer wire for storage adapters is the
separate 4-wire byte transport, not this port.

## Reading scans — BDOS function 03h

Call `CALL 0005h` with `C=03h`. The call blocks until a scan is
available.

Each scan arrives as a byte stream:

1. `1Bh` — scan-arrived marker
2. `count` — number of data bytes
3. `count` data bytes — decoded string from the installed hook

Loop reading `C=03h` to consume all bytes of a scan. The stream is
delivered through the reader device routing; the active-device selector
controls which FE83 entries back the reader channels.

Additional detail and the `FBC9` completion event are in
[RE notes: OS internals](../re-notes/os-diposb.md).

## Decode hook

A program may replace the system decode hook that processes the raw
width table. The socket is a banked `RST 10h` stub; by default it
discards every capture.

**Hook contract (summary):**

* Called after each capture in OS context.
* On entry the hook receives a pointer to the width table, the element
  count, and a status byte.
* The hook may rewrite the table pointer and count to present its decoded
  bytes, or zero the count to reject the read and re-arm.

**Installation (resident code):**

```
LD  HL, my_hook
LD  (hook_ptr), HL
```

For a bank-switched hook, also update the bank byte. The full register
and stack layout, including return address and the exact parameter block,
is in [RE notes: OS internals](../re-notes/os-diposb.md).

A portable application should use the stable `RDR:` stream above rather
than polling the envelope directly.

## Open aspects

The ROM ships only a discard hook; no symbology decoder is resident. The
available FE83 wire-table entry for the alternate wire variant is noted
in the RE material but is not part of the stable reader contract.

## Related

* [BDOS calls](bdos.md) — calling convention and function 03h entry
* [DIPOS-B extensions](extensions.md) — device-selector mutation (F7h)
* [Programmer guide](../manual/programmer-guide.md) — reader usage context
* [RE notes: OS internals](../re-notes/os-diposb.md) — evidence
