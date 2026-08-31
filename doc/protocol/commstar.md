# Commstar link and session protocol

## Scope and implementation status

The Micronic 1000 external link is a byte-latch transport to an off-board
controller associated with two IR ports. This page states what a host-side
program **may rely on** at the M1000-facing latch boundary and what remains
blocked for a physical server.

**A historically interoperable Commstar server cannot yet be built from
this document, but the frame and object formats are largely recovered.**
The logical frame envelope, the request/response object grammar, and the
program-data block format are established from traces against real
firmware and are described below. What is missing is the IR wire framing,
a wire-visible session-arming signal, the meaning of several object
fields, and any handheld-to-host transfer. A peer built to this page
drives real firmware through a complete program download in the emulator;
it is not proven against historical hardware.

| Layer | Stability | Guidance |
|---|---|---|
| Z80-to-controller register protocol | **Stable** | Safe to emulate against the latch contract below |
| Controller byte transaction | **Provisional** | Ordering is stable; electrical bit meanings are not |
| Validated frame envelope | **Provisional** | Length, type, sequence, and target-id fields are stable; other bytes are not |
| Session request/response objects | **Provisional** | Envelope and length fields are consistent across all captures; several field meanings are open |
| Program-data block format | **Provisional** | Marker and length fields are confirmed; chunk maximum and EOF convention are open |
| Handheld-to-host record transfer | **Not implementable** | No exchange in this direction has been captured |
| IR wire framing | **Not implementable** | Requires a hardware capture |

The synthetic peer in the repository is regression infrastructure, not a
server profile. Its RAM and program-counter observations are unavailable
to a physical peer.

For the firmware evidence behind each claim, see
[RE notes: Commstar evidence](../re-notes/commstar-evidence.md).

### Server implementer summary

| Goal | Stability | Boundary |
|---|---|---|
| Model the M1000-facing `4Ah-4Fh` latches | **Provisional** | Emulator or controller model, not a physical adapter |
| Run the synthetic Load/Run peer | **Provisional** | Requires emulator access to M1000 RAM/execution state |
| Drive a COM/DIP download against real firmware | **Provisional** | Works in the emulator; needs RAM visibility for the receive arm |
| Download a COM/DIP image from a physical server | **Not implementable** | Blocked on the wire layer and a wire-visible arm |
| Receive records/files from a handheld | **Not implementable** | No handheld-to-host exchange is captured |
| Build the IR adapter hardware | **Not implementable** | Connector-facing modulation and timing are open |

## Roles and byte-level terminology

* **Handheld** — the M1000 firmware and its external-link controller.
* **Server** — an external system that would exchange data with a
  handheld through an IR adapter. No interoperable server exists yet.
* **Synthetic peer** — the emulator component that feeds the controller
  receive latch and observes firmware internals.
* **Wire bytes** — bytes on the physical IR interface. Framing and even
  correspondence to controller bytes are open.
* **Controller-queue bytes** — bytes supplied to the `LINK_RXD` latch by
  the synthetic peer. They can include an uncounted sync byte and two
  trailing excluded bytes.
* **Logical-frame bytes** — the counted buffer validated by the frame
  header check. They begin with the six-byte header below.

Byte strings are labelled by level where established. A
controller-boundary capture is not a claim about IR serialisation.

`u16` denotes a little-endian 16-bit field; bare hex pairs are literal
bytes in transmission order.

The two IR connectors are **V24 ADAPTOR (top)** and **PLINTH (back)**
(owner-confirmed). Firmware selects one of two line states using bit 5 of
the active link id; which bit value maps to which connector is open. The
5-pin side port is the barcode-reader front end and is not part of this
transport — see [Barcode reader](../reference/barcode.md).

## Layer model

```text
Commstar application/session          Provisional: object grammar; field meanings open
        │
Logical frame                         Provisional: length, type, sequence, id
        │
Controller queue / byte transaction   Provisional at M1000 boundary
        │
4Ah-4Fh controller interface          Stable as latch addresses
        │
IR wire layer and connector selection  Not implementable: framing/polarity open
```

The controller interface is a byte-latch transport, not an SCC/SIO/ADLC.
Firmware writes outgoing data at `LINK_TXD` (`4Dh`), reads incoming data
at `LINK_RXD` (`4Eh`), polls `LINK_STATUS` (`4Bh`), and drives
`LINK_CTRL` (`4Ah`). `LINK_CMD` receives `81h` during the ready
handshake. The exact port catalogue is in
[Memory and I/O map](../reference/memory-io.md).

## Controller transaction

The M1000 drives `LINK_CTRL` and polls `LINK_STATUS` through a fixed
ordering. No electrical names for status or control bits are proven.

**Transmit ordering (stable as latch sequence):**

1. The port-select latch follows active-link-id bit 5 (one of two IR
   line states; which state is V24 ADAPTOR vs PLINTH is open).
2. Toggle `LINK_CTRL` bits around a short delay.
3. Poll `LINK_STATUS` bit 7 and write `0x81` to `LINK_CMD` when ready.
4. Write the low five bits of the link id (`link_id & 1Fh`) to `LINK_TXD`
   as a controller prelude — excluded from the frame length.
5. Handshake on `LINK_STATUS` bits 4 and 6 via `LINK_CTRL` bits 5/4.
6. Stream payload bytes: each byte to `LINK_TXD` gated by `LINK_STATUS`
   bit 7.
7. Clear `LINK_CTRL` bits to idle.

**Turn-taking rule (provisional):** the synthetic peer asserts
`LINK_STATUS` bit 4 while inbound bytes remain; a controller model must
drain and deassert before accepting the next M1000 transmission or the
transmission fails. This is a latch-level constraint, not a proven
half-duplex wire rule.

Mechanically the payload source is a descriptor list of
`{count, pointer}` entries terminated by a zero count; descriptors are
not transmitted.

**Receive ordering (provisional):** clear bit 0, set bit 5, single read
from `LINK_RXD`, set bit 4 with delay, clear bit 5, then continue reading
while status bit 0 is set. Bits 1-3 participate in the decode. The
cleanup toggles bit 1, sets then clears bit 0, and clears bit 4.

An adapter emulator must model the stateful handshake, not merely present
a flat byte stream.

## Validated frame envelope

The buffer after the controller has delivered the prelude and payload
carries this header:

| Offset | Size | Field | Stability |
|---:|---:|---|---|
| 0 | 2 | total received length (`u16le`) — must equal byte count | **Stable** |
| 2 | 1 | frame type — values 2, 3, 4 are dispatched | **Provisional** |
| 3 | 1 | per-link sequence — compared with per-link slot | **Provisional** |
| 4 | 1 | active link id — equality-checked on receive | **Stable** |
| 5 | 1 | unread by examined ROM link code | **Not implementable** |
| 6 | n | session payload — request/response object, see below | **Provisional** |

Validation rejects frames shorter than six bytes, frames whose embedded
length differs from the received count, and frames whose byte 4 differs
from the active link id. The TX path writes `0x7F` at offset 4; the RX
path requires offset 4 to equal the link id. The meaning of `0x7F` on the
wire is open. The examined ROM path has no checksum.

The sequence-number lifecycle — who advances it, when, and whether
directions share a counter — is open.

For the comparison and the descriptor shapes that carry this envelope,
see [RE notes: Commstar evidence](../re-notes/commstar-evidence.md#validated-frame-envelope).

## Externally observable subset

From M1000 traffic alone an observer can obtain the controller prelude
`id & 1Fh` (five bits), the length at offset +0, type at +2, and sequence
at +3. It cannot obtain the full eight-bit link id, which a server must
reproduce at offset +4.

Captured length is `1 + u16le(tx[1:3])` including the prelude — the only
confirmed rule for delimiting a captured M1000 transmission.

| Link id bits | Observable from wire? | Source |
|---|---|---|
| 0-4 | Yes | Controller prelude |
| 5 | No | Port select; polarity is open |
| 6-7 | No | Never transmitted; two samples are not a rule |

The remaining three bits, the per-link sequence slot, and the
fresh program-receive arm are not wire-visible.

## Captured M1000 session requests (controller-boundary TX)

V24 Mode 1 captures of pre-stream requests. First byte is the
controller prelude; remaining bytes are the logical frame. These bytes
are **stable as observed traces for this harness**; their field
semantics beyond the envelope are provisional.

| Request | Prelude | Logical frame |
|---|---|---|
| Initial | `03` | `0C 00 01 00 7F 00 00 00 00 00 00 00` |
| State 61 | `03` | `0C 00 01 01 7F 00 61 00 00 00 00 00` |
| State 64 | `03` | `0C 00 01 01 7F 00 64 00 00 00 00 00` |
| State 45 | `03` | `42 00 01 01 7F 00 45 00 01 00 36 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 4C 4F 41 44 31 32 33 34 35 36 37 38 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00` |
| State 44 | `03` | `0C 00 01 01 7F 00 44 00 00 00 FF 00` |

### Request and response object format

Every captured exchange fits one grammar. **Provisional**: the shapes below
hold across all captured exchanges, but they rest on a handful of samples and
the meaning of individual fields is stated separately.

A type-1 request payload is three `u16` fields, optionally followed by an
object:

```text
frame:   [u16 length][u8 type=1][u8 seq][u8 7F][u8 00] payload
payload: [u16 state][u16 arg][u16 count] object[count]
```

| Request | length | state | arg | count | object |
|---|---:|---:|---:|---:|---|
| Initial | 12 | `0000` | 0 | 0 | none |
| State 61 | 12 | `0061` | 0 | 0 | none |
| State 64 | 12 | `0064` | 0 | 0 | none |
| State 45 | 66 | `0045` | 1 | 54 | 54 bytes |
| State 44 | 12 | `0044` | 0 | 255 | none |

`count` is the object length wherever an object follows, and the state-45
frame confirms it exactly: 54 = 66 − 12. On the state-44 receive request the
third field is `0x00FF` with no object; its role there is open, though a
requested-maximum reading is consistent with the observed capacity limit.

A type-2 response payload takes one of two shapes:

```text
control ack:  [u8 00]
data object:  [u16 status][u16 marker][u16 N] data[N] [u16 00]
```

| Response | length | status | marker | N |
|---|---:|---:|---:|---:|
| Control (states 61/64/45) | 7 | — | — | single `00` byte |
| State-44 control object | 20 | 0 | 1 | 6 |
| Program data chunk | variable | 0 | 0 or 1 | payload bytes |

`marker` 0 permits another refill; `marker` 1 ends the stream. `N` matched the
data length exactly in every captured object.

Within the state-45 object, offsets +14 and +18 (frame +26 and +30) carry
operator-entered ASCII — `LOAD` and the workstation number typed at the
banner. The remaining object bytes are zero in every capture, so their
layout is not established.

For harness provenance see
[RE notes: Commstar evidence](../re-notes/commstar-evidence.md#captured-session-requests).
For the experiment that would settle the object field offsets by measurement,
see [RE notes: Open questions](../re-notes/open-questions.md#state-45-payload-structure).

## Historical server readiness

| Responsibility | Stability | Known | Still blocked |
|---|---|---|---|
| Controller transport | **Provisional** | Latch handshake and validation | Connector timing if hardware is required |
| Type-2/3/4 exchange | **Provisional** | Request/reply/completion ordering | Why the queue repeats type/sequence |
| Session states 61,64,45,44 | **Provisional** | Progression to program receive, and the state value is carried in request payload +0 | Historical operation meanings |
| Request/response objects | **Provisional** | Three-`u16` request header, status/marker/length response object | Meaning of `arg`, the state-44 `00FF`, and the state-45 object layout |
| V24 form staging | **Provisional** | Buffers reach mode-dependent dispatch | Authentication encoding |
| Program stream | **Provisional** | Inner bytes reach loader unchanged; marker 0/1 delimits the stream | Chunk maximum and whether a historical EOF frame exists |
| Errors, aborts, retries | **Provisional** | Timeouts and a few result codes | Application-visible grammar |
| Physical port | **Not implementable** | Bit 5 selects a line state | Which state is V24 ADAPTOR vs PLINTH |

## Diagnostic reference

Firmware-observed results, not a server error protocol:

| Result | Context | Implication |
|---|---|---|
| `EBh` | Pre-payload ready wait expires | Queue/turn-taking prevented TX |
| `ECh` | Final status bit 5 set | Status-bit meaning is open |
| `EDh` then `0x1F76` Line failure | 16-byte type-4 queue exhausts fixed descriptor | Use only the six-byte type-4 shape in the synthetic path |
| `EEh` | Per-byte wait fails | Timing/status condition failed |
| `01EF` | Type-4 sequence mismatch | Sequence lifecycle is open |
| `0x1F75` Invalid reply | Control object not `OK`/`NO`/`DM` | Applies to the control caller, not program bytes |
| `0x1FAE` Line failure | Blank V24 form and oversized synthetic object | Separate paths; not a server precondition |

For the evidence and next captures that would unblock a server, see
[RE notes: Commstar evidence](../re-notes/commstar-evidence.md#blocking-evidence)
and [RE notes: Open questions](../re-notes/open-questions.md).
