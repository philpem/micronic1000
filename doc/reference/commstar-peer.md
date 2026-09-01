# Commstar peer library

`micronic.peer.CommstarPeer` is the host side of a Commstar session: it parses
what a handheld transmits and produces the replies the protocol calls for.

**Stability: Provisional.** Verified against real firmware in the emulator; the
per-operation argument and result contract is still open.

It is deliberately **transport independent** — it knows nothing about the
emulator, the `4Ah`-`4Fh` latches, or a serial port:

```python
from micronic.peer import CommstarPeer

peer = CommstarPeer(link_id=0x43, on_request=my_policy)
peer.feed_tx(bytes_the_handheld_sent)
for reply in peer.take_rx():
    send_to_handheld(reply)
```

So the same object drives the emulator's byte-latch model today and a real IR
adapter tomorrow. Only the two lines that move bytes change.

## What it implements

The exchange shape from [the protocol page](../protocol/commstar.md): the
handheld sends a type-1 request; the peer answers with a type-2 frame — a
one-byte control acknowledgement, or a length-prefixed object; the handheld
acknowledges with type 3; the peer closes with type 4.

```text
capture:       [u8 prelude = id & 1Fh] logical-frame
logical frame: [u16 length][u8 type][u8 seq][u8 id-or-7Fh][u8 spare] payload
request body:  [u16 state][u16 arg][u16 size] object[size]
```

Requests are decoded into a `Request` carrying `state`, `arg`, `size` and the
object. Your `on_request` callback returns `None` for a control
acknowledgement, or `(marker, data)` to answer with an object — which is the
whole of the application policy.

## Verification

The peer runs in **shadow mode** inside the emulator harness: alongside the
existing hand-written phase script, asked at each point what it would have
replied. On a live firmware trace it agrees everywhere:

| Route | Agreed | Differed |
|---|---:|---:|
| V24 mode 1 | 12 | 0 |
| PLINTH | 13 | 0 |

Pinned by `CommstarShadowPeerTest`. `analysis/test_peer.py` additionally
checks the framing and decode against captured bytes with no emulator at all.

The counts also report *unsolicited* feeds — queues the script pushes without
a preceding request. Those are peer-initiated type-2 frames, a real protocol
feature, and the peer correctly does not generate them as replies.

## Using it against real hardware

Two things the wire cannot tell you, so supply them:

* **The link id.** The handheld transmits only its low five bits, as the
  prelude, and writes the constant `7Fh` at frame offset +4. Pass `link_id`
  if you know it; otherwise the peer reconstructs it as
  `(prelude & 1Fh) | 40h`, which matches both ids ever observed but rests on
  two samples.
* **The status bits.** An adapter must also drive `LINK_STATUS` as the
  handheld expects — see
  [how the IR hardware works](../protocol/commstar.md#how-the-ir-hardware-works).
  The peer produces byte queues; it does not model the latch handshake.

## What it does not do

* Interpret `size`. It is the object length for some states and a capacity for
  others, so the peer reports it and leaves the meaning to you.
* Validate transitions. The handheld's own table is a partial validator that
  the firmware bypasses; the peer does not second-guess it.
* Drive an upload. The command sequence is known
  (`C-BEGIN-FILE` / `C-TX-REC` / `C-END-FILE` / `C-END-TX`) but no capture of
  one exists yet.
