#!/usr/bin/env python3
"""micronic.proto - re-usable model of the Micronic 1000 Commstar/IR
link protocol, as derived from firmware static analysis (ROM00/ROM01)
and the runtime trace (analysis/boot_hw.py).

This file is the "protocol description" you can reuse to build an IR
link adapter: it models the frame format, the reply-prefix set, the
software address filter, the two IR-port select and the session
command dispatch - all against the *firmware's* own semantics, not
an assumption.

## Hardware transport (the byte pump)

  port 4Ah  control latch (firmware drives bits 0/1/4/5)
  port 4Bh  status (firmware polls bits 7/4/6 for TX and 0-3 for RX)
  port 4Ch  latch (firmware writes 0x81 after a status-bit-7 poll)
  port 4Dh  TX data byte  (write)
  port 4Eh  RX data byte  (read)
  port 4Fh  probe (0x1F)

## Frames (RX logical buffer, CONFIRMED)

RX logical header (LinkValidateFrameHeader ROM00:30DC): [+0..1 LE total
length][+2 type][+3 per-link sequence][+4 active link id][+5 unread by ROM
link code][+6... payload]. Type in {2,3,4}; byte +4 is XOR-compared to
fdd4. TX via LinkFramePrefixWrite (316B) writes [+0..1 LE len][+2 type]
[+3 sequence][+4 0x7F] and leaves +5 untouched — 0x7F meaning is SUSPECTED.
Byte +5 is never read by ROM link code (may be writable by loaded code).
Link path no checksum verified.

## Replies (unit -> host), written into the FE14 frame:

  EE 01  idle / user-handled
  E0 02
  EE 02
  E0 04  link state 3 (connected) ACK
  E0 05  link state 2 (command) ACK
  EF 01  command-id mismatch (refused)

## Roles

The M1000 can be host (initiator) or unit (responder); the wire
record and reply set are symmetric. Exactly one side sends the first
frame; the other holds the per-link slot with the expected id.
"""
from __future__ import annotations

from collections import deque

# ------------------------------------------------------------------- consts
PORT_CTRL   = 0x4A
PORT_STATUS = 0x4B
PORT_CMD    = 0x4C
PORT_TX     = 0x4D
PORT_RX     = 0x4E
PORT_PROBE  = 0x4F

# fd84 event-table masks -> handler meaning (from firmware)
EVT_KBD      = 0x01
EVT_RTC      = 0x02
EVT_IR       = 0x04
EVT_BATTMAIN = 0x08
EVT_BATTBK   = 0x10

# frame type markers (FDE6)
TYPE_SESSION = 2
TYPE_ANSWER  = 3
TYPE_COMMAND = 4

# reply prefixes (FE14 words)
RPL_IDLE     = 0xEE01
RPL_A2       = 0x02E0
RPL_EE2      = 0x02EE
RPL_ACK3     = 0x04E0   # state 3 (connected)
RPL_ACK2     = 0x05E0   # state 2 (command)
RPL_MISMATCH = 0x01EF

# command-ids (the {key} tables the session dispatches on)
CMD_table = {
    0x4400: "abort/session",
    0x4500: "abort/session",
    0x6000: "abort/session",
    0x6100: "abort/session",
    0x6400: "abort/session",
    0x0000: "tx-continue",
    0x0400: "tx-continue",
    0x0900: "tx-continue",
    0x0C00: "tx-retry",
}


class Frame:
    """A wire frame: [prelude][payload] on the physical link.

    The physical TX (verified byte-for-byte against the firmware:
    analysis/comms_tx_test.py) is:
        port 4Dh <- link_id & 0x1F      (prelude / address word)
        port 4Dh <- payload bytes       (each gated on 4Bh bit7)

    A payload is built from `type` + `cmd` + raw payload:
        payload = [type][cmd_lo][cmd_hi][data...]
    """

    __slots__ = ("type", "cmd", "payload")

    def __init__(self, ftype=0, cmd=0, payload=b""):
        self.type = ftype
        self.cmd = cmd          # 16-bit command/sequence id
        self.payload = payload

    def build(self):
        """The payload bytes the session stores (what goes after the
        prelude on the wire). cmd is emitted BIG-ENDIAN on the wire
        (verified: firmware sent 44 00 for cmd 0x4400)."""
        body = bytes([self.type,
                      (self.cmd >> 8) & 0xFF, self.cmd & 0xFF])
        body += bytes(self.payload)
        return body

    def wire(self, link_id):
        """Full physical byte stream including the prelude."""
        return bytes([link_id & 0x1F]) + self.build()

    @classmethod
    def parse(cls, payload: bytes):
        if len(payload) < 3:
            return None
        # cmd is BIG-ENDIAN on the wire (verified: 44 00 for 0x4400)
        return cls(payload[0],
                   (payload[1] << 8) | payload[2],
                   payload[3:])


class LinkPeer:
    """Stateful byte-latch peer for a firmware or adapter implementation.

    The peer models only the firmware-observed register protocol. It queues
    bytes arriving at the M1000's RX latch, captures M1000 TX-latch writes,
    records control/command/probe writes, and synthesizes the status branches
    needed by ``LinkBlockTx`` and ``LinkBlockRx``. It deliberately assigns no
    electrical name to any control or status bit.

    ``firmware_status`` exposes bit 7 and RX bit 0 while inbound bytes remain.
    Optional ``status_bits`` and ``completion_bits`` let an adapter add
    observed status bits without giving them an inferred electrical name. The
    default completion value is zero, matching the directed firmware traces.
    """

    _TX_READY = 0x80  # Mechanical: established directed TX test status.
    _RX_DATA = 0x01

    def __init__(self, rx_bytes=b"", status_bits=0, completion_bits=0):
        self._rx_bytes = deque()
        self._tx_bytes = deque()
        self.status_bits = status_bits & 0x7C
        self.completion_bits = completion_bits & 0x7F
        self.ctrl_writes = []
        self.command_writes = []
        self.probe_writes = []
        self.feed_rx(rx_bytes)

    def feed_rx(self, data):
        """Queue bytes for the M1000 to read from LINK_RXD."""
        if isinstance(data, int):
            self._rx_bytes.append(data & 0xFF)
        else:
            self._rx_bytes.extend(bytes(data))

    def read_rx(self):
        """Read one byte from the M1000-facing LINK_RXD latch."""
        return self._rx_bytes.popleft() if self._rx_bytes else 0

    def write_tx(self, value):
        """Capture one byte written by the M1000 to LINK_TXD."""
        self._tx_bytes.append(value & 0xFF)

    def read_tx(self):
        """Read one byte captured from the M1000-facing LINK_TXD latch."""
        return self._tx_bytes.popleft() if self._tx_bytes else 0

    def drain_tx(self):
        """Return and clear all bytes captured from LINK_TXD."""
        data = bytes(self._tx_bytes)
        self._tx_bytes.clear()
        return data

    def peek_tx(self):
        """Return captured LINK_TXD bytes without consuming them."""
        return bytes(self._tx_bytes)

    @property
    def pending_tx(self):
        """Number of M1000 TX-latch bytes awaiting adapter consumption."""
        return len(self._tx_bytes)

    @property
    def pending_rx(self):
        """Number of bytes queued for the M1000 RX latch."""
        return len(self._rx_bytes)

    def firmware_status(self):
        """Return status for the M1000's LINK_STATUS reads."""
        return self._TX_READY | self.status_bits | (
            self._RX_DATA if self._rx_bytes else self.completion_bits
        )

    def adapter_status(self):
        """Return status for an adapter consuming captured M1000 bytes."""
        return 0x80 | (
            self._RX_DATA if self._tx_bytes else self.completion_bits
        )

    def write_control(self, value):
        self.ctrl_writes.append(value & 0xFF)

    def write_command(self, value):
        self.command_writes.append(value & 0xFF)

    def write_probe(self, value):
        self.probe_writes.append(value & 0xFF)

    def make_adapter_link(self, id_byte=0):
        """Return a :class:`Link` wired to this peer's adapter-facing side."""
        return Link(
            port_out=self.feed_rx,
            port_in=self.read_tx,
            port_status=self.adapter_status,
            port_ctrl=self.write_control,
            id_byte=id_byte,
        )


class Link:
    """The M1000 external-link byte transport (a side that must pump
    4x ports).  This is the reusable primitive for an adapter:

        link = proto.Link(tx_fn, rx_fn, status_fn, on_status_change)
        link.host_init() / link.respond() ...
    """

    def __init__(self, port_out, port_in, port_status, port_ctrl,
                 port_cmd=0x81, id_byte=0x00):
        self.on_tx = port_out
        self.on_rx = port_in
        self.on_st = port_status
        self.on_ctrl = port_ctrl
        self.id = id_byte & 0xFF            # our link id (low addr bits)
        self.port_bit5 = bool(id_byte & 0x20)

    def set_port_select(self, bit5):
        """Select the IR line (PLINTH line-state vs V24 line-state)."""
        self.port_bit5 = bool(bit5)

    def tx(self, frame: Frame) -> int:
        """Send a frame. Mirrors the firmware TX path:
        1. prelude: link-id low 5 bits -> TX port
        2. payload bytes, each gated on status bit 7.
        """
        # prelude = our id's low 5 bits (address/select word)
        self._wait_tx_ready()
        self.on_tx(self.id & 0x1F)
        for byte in frame.build():
            self._wait_tx_ready()
            self.on_tx(byte)
        return 1 + len(frame.build())

    def rx(self, max_len=64, timeout=None) -> Frame:
        """Receive a frame from the peer.

        Mirrors the firmware RX path (verified: LinkBlockRx reads
        port 4Eh when 4Bh bit0 is set, with control-latch strobes):
          1. prelude byte (peer's link id)
         2. up to `max_len` payload bytes, each gated on status bit 0
        Returns the parsed Frame, or None on timeout.
        """
        pre = self._read_bytes(1, timeout)
        if pre is None:
            return None
        payload = self._read_bytes(max_len, timeout)
        if payload is None:
            return None
        return Frame.parse(payload)

    def _wait_tx_ready(self):
        while not (self.on_st() & 0x80):
            pass

    def _read_bytes(self, n, timeout=None):
        out = bytearray()
        while len(out) < n:
            if not (self.on_st() & 0x01):
                # Firmware-observed RX data bit not asserted yet.
                if timeout is not None and timeout <= 0:
                    return None
                continue
            out.append(self.on_rx() & 0xFF)
        return bytes(out)

    @staticmethod
    def validate_header(wire, expect_id):
        """The firmware's LinkValidateFrameHeader ROM00:30DC: id byte at
        offset +4 (RX logical header) must match fdd4 (XOR == 0); offset +5
        is never read by ROM link code."""
        return len(wire) >= 6 and (wire[4] ^ (expect_id & 0xFF)) == 0
