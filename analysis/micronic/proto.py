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

  port 4Ah  control latch (bit6/7 link online, bit1 = IR port line select)
  port 4Bh  status   (bit7 = TX buffer empty, bit0 = RX buffer full)
  port 4Ch  command/ACK latch (0x81 = present)
  port 4Dh  TX data byte  (write)
  port 4Eh  RX data byte  (read)
  port 4Fh  probe (0x1F)

## Frames

Every frame is a length-prefixed record:
   [len][type][cmd-id][payload...]
with type in {2,3,4} and the unit's link-id byte carried in the
frame for the software address filter (XOR-compared to fdd4).

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
        2. payload bytes, each gated on TX-empty (status bit7).
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
        port 4Eh gated on 4Bh bit0 = RX buffer full, with control
        latch strobes):
          1. prelude byte (peer's link id)
          2. up to `max_len` payload bytes, each gated on RX-full
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
                # RX not full yet
                if timeout is not None and timeout <= 0:
                    return None
                continue
            out.append(self.on_rx() & 0xFF)
        return bytes(out)

    @staticmethod
    def validate_header(wire, expect_id):
        """The firmware's LinkValidateFrameHeader: an id byte at
        offset +5 must match (XOR == 0)."""
        return len(wire) >= 6 and (wire[5] ^ (expect_id & 0xFF)) == 0