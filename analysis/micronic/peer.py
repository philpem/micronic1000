"""Protocol-aware Commstar peer.

This is the host side of a Commstar session: it parses what the handheld
transmits and generates the replies the protocol calls for. It is deliberately
**transport independent** -- it knows nothing about the emulator, the 4Ah-4Fh
latches, or a serial port. Feed it the bytes the handheld sent and take the
bytes to send back:

    peer = CommstarPeer(link_id=0x43)
    peer.feed_tx(captured_bytes)        # what the handheld transmitted
    for reply in peer.take_rx():        # what to hand back to it
        ...

That makes the same object usable behind the emulator's byte-latch model and
behind a real IR adapter driving a physical M1000.

What it implements is the exchange shape established in
doc/protocol/commstar.md: the handheld sends a type-1 request; the peer
answers with a type-2 frame (a one-byte control ack, or a length-prefixed
object); the handheld acknowledges with type 3; the peer closes with type 4.

Framing (all little-endian):

    capture:       [u8 prelude = id & 1Fh] logical-frame
    logical frame: [u16 length][u8 type][u8 seq][u8 id-or-7Fh][u8 spare] payload
    request body:  [u16 state][u16 arg][u16 size] object[size]

Known limits, kept explicit rather than papered over:

* The handheld transmits only the low five bits of its link id (as the
  prelude) and puts the constant 7Fh at frame offset +4, so a peer cannot
  learn the full eight-bit id from the wire. Supply it, or accept the
  reconstruction described on ``link_id_from_prelude``.
* ``size`` in a request is not a general length: it is the object length for
  some states and a capacity for others. The peer does not interpret it.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Callable, Iterator

# Logical frame types seen on the wire.
TYPE_REQUEST = 1        # handheld -> peer, carries a state/arg/size body
TYPE_OBJECT = 2         # peer -> handheld, control ack or data object
TYPE_ACK = 3            # handheld -> peer, acknowledges the type 2
TYPE_COMPLETE = 4       # peer -> handheld, closes the exchange

HEADER_LEN = 6          # length, type, seq, id, spare
TX_ID_CONSTANT = 0x7F   # what the handheld writes at offset +4


# Wire states a peer has to recognise (doc/protocol/commstar.md).
STATE_LINK_INIT = 0x0000
STATE_LINK_CONFIG = 0x0006
STATE_BLOCK_QUERY = 0x0043   # short query preceding an 0044
STATE_BLOCK_IN = 0x0044      # handheld solicits a block from the peer
STATE_BLOCK_OUT = 0x0045     # handheld sends a block to the peer
STATE_BEGIN_TX = 0x0064
STATE_END_TRANSACTION = 0x0065

# A type-2 data object's marker: 0 means "more follows", 1 means "this is the
# last one". CONFIRMED from the ROM: marker 1 surfaces as read status 8, the
# value ROM00:3D59 turns into the end-of-stream flag ram:E44A and ROM00:3FEC
# routes to the OK/NO/DM comparison.
MARKER_MORE = 0
MARKER_LAST = 1

# The most object data one type-2 reply may carry. The handheld advertises 128
# in the size field of its 0044 request (ROM00:4FAD pushes 0080h), but its
# receive descriptor is smaller: ROM00:620B passes 86h = 134 as the descriptor
# size and the object body lands 8 bytes into it at ram:E5C4, leaving 126.
# CONFIRMED by experiment -- 126 completes a download, 127 is dropped without
# an acknowledgement, the handheld retries and the session ends "Session
# aborted". Never send more than this.
MAX_OBJECT_DATA = 126

# The 54-byte command record C-COMMAND transmits at state 0045.
COMMAND_RECORD_LEN = 0x36
_CMD_FIELDS = {           # name -> (offset, length), from ROM00:4B84-4C05
    "identity1": (0, 8),
    "identity2": (8, 6),
    "operation": (14, 4),
    "workstation": (18, 8),
    "identity4": (26, 8),
    "identity5": (34, 8),
    "parameter": (42, 12),
}

# The three replies C-COMMAND accepts, from the table copied to ram:E22F.
REPLY_OK = b"OK"
REPLY_NO = b"NO"
REPLY_DM = b"DM"


def link_id_from_prelude(prelude: int, port_bit5: bool = False) -> int:
    """Best-effort reconstruction of the full link id from a prelude byte.

    The prelude carries only ``id & 0x1F``. Both link ids ever observed
    (0x43 and 0x63) have bit 6 set and bit 7 clear, differing only in bit 5,
    which selects the port. That is two samples, not a rule -- prefer passing
    the id explicitly when you know it.
    """
    return (prelude & 0x1F) | 0x40 | (0x20 if port_bit5 else 0x00)


@dataclass(frozen=True)
class Request:
    """A decoded type-1 request from the handheld."""

    seq: int
    state: int
    arg: int
    size: int
    obj: bytes
    frame: bytes = field(repr=False)

    @property
    def state_name(self) -> str:
        return f"{self.state:#06x}"


class ProtocolError(ValueError):
    """The handheld sent something this peer cannot parse."""


class CommstarPeer:
    """Parses handheld transmissions and produces the replies to send back.

    :param link_id: the handheld's full 8-bit link id, echoed at offset +4 of
        every frame the peer sends. If omitted it is reconstructed from the
        first prelude seen -- see :func:`link_id_from_prelude`.
    :param on_request: called with each decoded :class:`Request`. Return
        ``None`` for a minimal control acknowledgement, or ``(marker, data)``
        to answer with an object. Returning bare ``bytes`` means marker 0.
    """

    def __init__(
        self,
        link_id: int | None = None,
        on_request: Callable[[Request], object] | None = None,
    ):
        self.link_id = link_id
        self._on_request = on_request
        self._tx = bytearray()      # bytes the handheld has sent us
        self._rx: list[bytes] = []  # queues waiting to go back
        self.requests: list[Request] = []
        self.acks = 0

    # ------------------------------------------------------------------ input
    def feed_tx(self, data: bytes) -> None:
        """Absorb bytes transmitted by the handheld, replying where due."""
        self._tx.extend(data)
        while True:
            frame = self._take_capture()
            if frame is None:
                return
            self._dispatch(frame)

    def _take_capture(self) -> bytes | None:
        """Split off one complete capture: prelude plus its logical frame."""
        if len(self._tx) < 3:
            return None
        total = 1 + (self._tx[1] | (self._tx[2] << 8))
        if total < 1 + HEADER_LEN:
            raise ProtocolError(f"implausible frame length {total}")
        if len(self._tx) < total:
            return None
        capture = bytes(self._tx[:total])
        del self._tx[:total]
        return capture

    def _dispatch(self, capture: bytes) -> None:
        prelude, frame = capture[0], capture[1:]
        if self.link_id is None:
            self.link_id = link_id_from_prelude(prelude)

        ftype, seq = frame[2], frame[3]
        if ftype == TYPE_ACK:
            # The handheld has taken our type-2; close the exchange.
            self.acks += 1
            self._rx.append(self.completion(seq))
            return
        if ftype != TYPE_REQUEST:
            raise ProtocolError(f"unexpected frame type {ftype} from handheld")

        body = frame[HEADER_LEN:]
        if len(body) < 6:
            raise ProtocolError("request body shorter than its three u16 fields")
        request = Request(
            seq=seq,
            state=body[0] | (body[1] << 8),
            arg=body[2] | (body[3] << 8),
            size=body[4] | (body[5] << 8),
            obj=bytes(body[6:]),
            frame=frame,
        )
        self.requests.append(request)

        answer = self._on_request(request) if self._on_request else None
        if answer is None:
            self._rx.append(self.control_ack(seq))
        else:
            marker, data = (0, answer) if isinstance(answer, (bytes, bytearray)) else answer
            self._rx.append(self.data_object(seq, bytes(data), marker))

    # ----------------------------------------------------------------- output
    def take_rx(self) -> list[bytes]:
        """Return and clear the reply queues waiting to go to the handheld."""
        out, self._rx = self._rx, []
        return out

    @property
    def pending(self) -> bool:
        return bool(self._rx)

    # ------------------------------------------------------- frame generators
    def _logical(self, ftype: int, seq: int, payload: bytes) -> bytes:
        """Wrap a payload as a controller queue: sync, frame, trailing copies.

        The leading 00h is the uncounted sync byte the controller expects; the
        two trailing bytes repeat the frame's type and sequence and are
        excluded from its length. Both are documented as controller-level
        conventions whose purpose is open.
        """
        if self.link_id is None:
            raise ProtocolError("link id unknown; pass link_id or feed a capture first")
        length = HEADER_LEN + len(payload)
        frame = bytes([length & 0xFF, length >> 8, ftype, seq, self.link_id, 0x00])
        return bytes([0x00]) + frame + payload + bytes([ftype, seq])

    def control_ack(self, seq: int) -> bytes:
        """Minimal type-2 reply: a single zero payload byte."""
        return self._logical(TYPE_OBJECT, seq, bytes([0x00]))

    def data_object(self, seq: int, data: bytes, marker: int = 0) -> bytes:
        """Type-2 reply carrying an object: status, marker, length, data."""
        n = len(data)
        payload = bytes([0, 0, marker & 0xFF, marker >> 8, n & 0xFF, n >> 8])
        return self._logical(TYPE_OBJECT, seq, payload + data + bytes([0, 0]))

    def completion(self, seq: int) -> bytes:
        """Type-4 reply closing an exchange."""
        return self._logical(TYPE_COMPLETE, seq, b"")

    def expected_ack(self, seq: int) -> bytes:
        """The type-3 capture the handheld should send after a type-2.

        Useful for asserting in tests and for a real adapter to resynchronise.
        """
        if self.link_id is None:
            raise ProtocolError("link id unknown")
        return bytes([self.link_id & 0x1F, HEADER_LEN, 0x00,
                      TYPE_ACK, seq, TX_ID_CONSTANT, 0x00])


def iter_captures(stream: bytes) -> Iterator[bytes]:
    """Split a recorded handheld byte stream into individual captures."""
    offset = 0
    while offset + 3 <= len(stream):
        total = 1 + (stream[offset + 1] | (stream[offset + 2] << 8))
        if offset + total > len(stream):
            return
        yield stream[offset:offset + total]
        offset += total


@dataclass(frozen=True)
class CommandRecord:
    """The 54-byte record ``C-COMMAND`` transmits at wire state ``0045``.

    Field offsets are the ROM's own, from the ``ram:DB89`` bounded copies at
    ``ROM00:4B84``-``4C05``; the padding conventions are measured (workstation
    right-justified space-padded, parameter left-justified NUL-padded).
    """

    raw: bytes

    @classmethod
    def parse(cls, obj: bytes) -> "CommandRecord":
        if len(obj) != COMMAND_RECORD_LEN:
            raise ProtocolError(
                f"command record is {len(obj)} bytes, expected {COMMAND_RECORD_LEN}"
            )
        return cls(bytes(obj))

    def field(self, name: str) -> bytes:
        offset, length = _CMD_FIELDS[name]
        return self.raw[offset:offset + length]

    def text(self, name: str) -> str:
        return self.field(name).rstrip(b"\x00").strip().decode("latin-1")

    @property
    def operation(self) -> str:
        """``LOAD``, ``PROG``, ``SEND``, ``RCV1``, ``RCV2``, ``TIME``, ``ENDC``."""
        return self.text("operation")

    @property
    def workstation(self) -> str:
        return self.text("workstation")

    @property
    def parameter(self) -> str:
        """The per-command parameter -- the program name on ``LOAD``/``PROG``."""
        return self.text("parameter")


class ProgramDownloadPolicy:
    """Serve a program image to a handheld that asked for one.

    This is the host half of the download the firmware's Load/Run screen runs
    and that an application drives with ``C-COMMAND`` + a ``C-RX-BLK`` loop.
    Install it as a :class:`CommstarPeer` ``on_request`` policy::

        policy = ProgramDownloadPolicy({"HELLO": image_bytes})
        peer = CommstarPeer(on_request=policy)

    The exchange it implements, in the order the handheld produces it:

    * ``0045`` carrying a 54-byte record -- the command. The policy remembers
      it and, when the operation is ``LOAD``, selects the named image.
    * the **first** ``0044`` after a command is that command's *reply*, and it
      must carry ``OK`` with marker 1: ``ROM00:3F20`` reads it as a counted
      buffer and ``ROM00:3F65`` compares the first two bytes against the
      ``OK``/``NO``/``DM`` table at ``ram:E22F``. Marker 1 is what makes the
      read return status 8, the only status that reaches that comparison.
    * every later ``0044`` is a block request from ``C-RX-BLK``: answer with
      up to ``chunk`` bytes of the image, marker 0 while more follows and
      marker 1 on the last one. ``ROM00:3D59`` turns marker 1 into the
      end-of-stream flag ``ram:E44A``, which is what finally makes ``C-RX-BLK``
      return 8.

    Anything else gets a plain control acknowledgement.

    :param images: program name -> bytes. A name of ``""`` is the fallback for
        a request that names an image this peer does not have; without one, an
        unknown name is refused with ``NO``.
    :param chunk: bytes per block, capped at :data:`MAX_OBJECT_DATA` because
        the handheld silently drops anything larger -- see that constant. The
        policy also never exceeds the maximum the request itself names.
    """

    def __init__(self, images: dict[str, bytes] | bytes,
                 chunk: int = MAX_OBJECT_DATA):
        if isinstance(images, (bytes, bytearray)):
            images = {"": bytes(images)}
        self.images = {name: bytes(data) for name, data in images.items()}
        self.chunk = min(chunk, MAX_OBJECT_DATA)
        self.commands: list[CommandRecord] = []
        self.served: list[bytes] = []       # every block payload, in order
        self._reply_due = False             # next 0044 is a command reply
        self._reply = REPLY_OK
        self._stream: bytes | None = None
        self._offset = 0
        self.finished = False

    # ------------------------------------------------------------------ policy
    def __call__(self, request: Request):
        if request.state == STATE_BLOCK_OUT and len(request.obj) == COMMAND_RECORD_LEN:
            return self._on_command(CommandRecord.parse(request.obj))
        if request.state == STATE_BLOCK_IN:
            if self._reply_due:
                self._reply_due = False
                return (MARKER_LAST, self._reply)
            return self._next_block(request.size)
        return None

    def _on_command(self, record: CommandRecord):
        self.commands.append(record)
        self._reply_due = True
        if record.operation in ("LOAD", "PROG"):
            image = self.images.get(record.parameter)
            if image is None:
                image = self.images.get("")
            if image is None:
                self._reply, self._stream = REPLY_NO, None
            else:
                self._reply, self._stream, self._offset = REPLY_OK, image, 0
                self.finished = False
        else:
            self._reply = REPLY_OK
        return None      # the command record itself gets a control ack

    def _next_block(self, requested: int):
        if self._stream is None:
            raise ProtocolError("handheld asked for a block before any LOAD command")
        limit = min(self.chunk, requested) if requested else self.chunk
        payload = self._stream[self._offset:self._offset + limit]
        self._offset += len(payload)
        last = self._offset >= len(self._stream)
        if last:
            self.finished = True
        self.served.append(payload)
        return (MARKER_LAST if last else MARKER_MORE, payload)
