#!/usr/bin/env python3
"""Reusable byte-latch scaffold for the Micronic 1000 external link.

This module models only directed reads/writes at the M1000-facing latches.
It does not implement the controller transaction, validated frame envelope,
or Commstar session grammar. See ``doc/protocol/commstar.md`` for the
byte-verified mechanics and explicitly open fields.

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
The examined ROM transport/header path performs no checksum.

The observed numeric types and reply words below are not a command grammar.
Their complete envelopes and session-level meanings remain open.
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

OBSERVED_FRAME_TYPES = (2, 3, 4)
OBSERVED_REPLY_WORDS = (
    0x01EE, 0x02E0, 0x02EE, 0x03EE, 0x04E0, 0x05E0, 0x01EF,
)


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

    def make_adapter_link(self):
        """Return a raw byte-latch scaffold for the adapter-facing side."""
        return Link(
            port_out=self.feed_rx,
            port_in=self.read_tx,
            port_status=self.adapter_status,
            port_ctrl=self.write_control,
        )


class Link:
    """Simplified directed byte-latch scaffold.

    This class deliberately omits the confirmed control, completion, timeout,
    and descriptor behavior. It is useful for bounded harness plumbing, not as
    a controller-transaction or Commstar protocol implementation.
    """

    def __init__(self, port_out, port_in, port_status, port_ctrl):
        self.on_tx = port_out
        self.on_rx = port_in
        self.on_st = port_status
        self.on_ctrl = port_ctrl

    def tx(self, data) -> int:
        """Write opaque bytes while mechanical status bit 7 is set."""
        data = bytes(data)
        for byte in data:
            self._wait_tx_ready()
            self.on_tx(byte)
        return len(data)

    def rx(self, count, timeout=None):
        """Read exactly ``count`` opaque bytes using mechanical status bit 0."""
        return self._read_bytes(count, timeout)

    def _wait_tx_ready(self):
        while not (self.on_st() & 0x80):
            pass

    def _read_bytes(self, n, timeout=None):
        out = bytearray()
        remaining = timeout
        while len(out) < n:
            if not (self.on_st() & 0x01):
                # Firmware-observed RX data bit not asserted yet.
                if remaining is not None:
                    if remaining <= 0:
                        return None
                    remaining -= 1
                continue
            out.append(self.on_rx() & 0xFF)
        return bytes(out)

    @staticmethod
    def validate_header(frame, expect_id, logical_count=None):
        """Apply the confirmed ROM header checks to a logical RX buffer."""
        frame = bytes(frame)
        if logical_count is None:
            logical_count = len(frame)
        return (
            len(frame) >= 6
            and int.from_bytes(frame[:2], "little") == logical_count
            and frame[4] == (expect_id & 0xFF)
        )
