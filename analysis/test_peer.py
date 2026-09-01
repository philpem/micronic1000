#!/usr/bin/env python3
"""Tests for the protocol-aware Commstar peer.

Every expectation here is a byte string captured from real firmware in the
emulator, or the reply the existing phase-scripted responder feeds back at
that point. If this peer agrees with both, it can replace the script.

No emulator is needed to run these.
"""
from __future__ import annotations

import unittest

from micronic.peer import (
    CommstarPeer,
    ProtocolError,
    Request,
    iter_captures,
    link_id_from_prelude,
)

# Captures from the V24 mode-1 regression (prelude + logical frame).
INITIAL = bytes.fromhex("030c0001007f00000000000000")
STATE61 = bytes.fromhex("030c0001017f00610000000000")
STATE64 = bytes.fromhex("030c0001017f00640000000000")
STATE44 = bytes.fromhex("030c0001017f0044000000ff00")
STATE45 = bytes.fromhex(
    "03420001017f0045000100360000000000000000000000000000004c4f41"
    "443132333435363738000000000000000000000000000000000000000000"
    "00000000000000"
)

LINK_ID = 0x43  # the id that trace runs with

# Replies the phase-scripted responder feeds, for the same points.
CONTROL_REPLY = bytes.fromhex("00070002014300000201")
COMPLETION = bytes.fromhex("000600040143000401")
STATE44_OBJECT = bytes.fromhex("001400020143000000010006004f4ba55a3cc300000201")


class FramingTest(unittest.TestCase):
    def test_splits_a_stream_into_captures(self):
        stream = INITIAL + STATE61 + STATE45
        self.assertEqual(list(iter_captures(stream)), [INITIAL, STATE61, STATE45])

    def test_partial_capture_is_withheld_until_complete(self):
        peer = CommstarPeer(link_id=LINK_ID)
        peer.feed_tx(STATE45[:20])
        self.assertEqual(peer.requests, [])
        peer.feed_tx(STATE45[20:])
        self.assertEqual(len(peer.requests), 1)

    def test_rejects_an_implausible_length(self):
        peer = CommstarPeer(link_id=LINK_ID)
        with self.assertRaises(ProtocolError):
            peer.feed_tx(bytes([0x03, 0x02, 0x00, 0x00]))


class RequestDecodeTest(unittest.TestCase):
    def decode(self, capture: bytes) -> Request:
        peer = CommstarPeer(link_id=LINK_ID)
        peer.feed_tx(capture)
        self.assertEqual(len(peer.requests), 1)
        return peer.requests[0]

    def test_decodes_the_three_header_fields(self):
        for capture, state, arg, size in (
            (INITIAL, 0x0000, 0, 0x0000),
            (STATE61, 0x0061, 0, 0x0000),
            (STATE64, 0x0064, 0, 0x0000),
            (STATE44, 0x0044, 0, 0x00FF),
            (STATE45, 0x0045, 1, 0x0036),
        ):
            with self.subTest(state=state):
                r = self.decode(capture)
                self.assertEqual((r.state, r.arg, r.size), (state, arg, size))

    def test_state45_object_carries_the_operator_text(self):
        r = self.decode(STATE45)
        self.assertEqual(len(r.obj), r.size)          # size is the object length here
        self.assertEqual(r.obj[14:18], b"LOAD")       # object +14
        self.assertEqual(r.obj[18:26], b"12345678")   # object +18, the workstation

    def test_state44_size_is_not_an_object_length(self):
        # 0x00FF with no object: the third field is state-dependent.
        r = self.decode(STATE44)
        self.assertEqual(r.size, 0x00FF)
        self.assertEqual(r.obj, b"")


class ReplyTest(unittest.TestCase):
    def test_control_ack_matches_the_scripted_responder(self):
        peer = CommstarPeer(link_id=LINK_ID)
        peer.feed_tx(STATE61)
        self.assertEqual(peer.take_rx(), [CONTROL_REPLY])

    def test_data_object_matches_the_scripted_responder(self):
        payload = bytes.fromhex("4f4ba55a3cc3")
        peer = CommstarPeer(link_id=LINK_ID, on_request=lambda r: (1, payload))
        peer.feed_tx(STATE44)
        self.assertEqual(peer.take_rx(), [STATE44_OBJECT])

    def test_ack_from_the_handheld_draws_a_completion(self):
        peer = CommstarPeer(link_id=LINK_ID)
        peer.feed_tx(STATE61)
        peer.take_rx()
        peer.feed_tx(peer.expected_ack(0x01))
        self.assertEqual(peer.take_rx(), [COMPLETION])
        self.assertEqual(peer.acks, 1)

    def test_bare_bytes_answer_means_marker_zero(self):
        peer = CommstarPeer(link_id=LINK_ID, on_request=lambda r: b"\xc9\xc8")
        peer.feed_tx(STATE44)
        queue = peer.take_rx()[0]
        self.assertEqual(queue[9:11], bytes([0, 0]))   # marker field
        self.assertEqual(queue[11:13], bytes([2, 0]))  # length field

    def test_expected_ack_is_what_the_firmware_sends(self):
        peer = CommstarPeer(link_id=LINK_ID)
        self.assertEqual(peer.expected_ack(0x01), bytes.fromhex("03060003017f00"))


class SequenceTest(unittest.TestCase):
    """A full request/object/ack/completion round trip, as the firmware does."""

    def test_round_trip(self):
        seen = []
        peer = CommstarPeer(link_id=LINK_ID, on_request=lambda r: seen.append(r.state))
        peer.feed_tx(STATE64)
        self.assertEqual(seen, [0x0064])
        self.assertEqual(peer.take_rx(), [CONTROL_REPLY])
        peer.feed_tx(peer.expected_ack(0x01))
        self.assertEqual(peer.take_rx(), [COMPLETION])
        self.assertFalse(peer.pending)

    def test_several_requests_in_one_feed(self):
        peer = CommstarPeer(link_id=LINK_ID)
        peer.feed_tx(STATE61 + STATE64)
        self.assertEqual([r.state for r in peer.requests], [0x0061, 0x0064])
        self.assertEqual(peer.take_rx(), [CONTROL_REPLY, CONTROL_REPLY])


class LinkIdTest(unittest.TestCase):
    def test_reconstruction_matches_both_observed_ids(self):
        self.assertEqual(link_id_from_prelude(0x03, port_bit5=False), 0x43)
        self.assertEqual(link_id_from_prelude(0x03, port_bit5=True), 0x63)

    def test_id_is_adopted_from_the_first_capture(self):
        peer = CommstarPeer()
        peer.feed_tx(STATE61)
        self.assertEqual(peer.link_id, 0x43)          # 0x03 prelude -> 0x43
        self.assertEqual(peer.take_rx(), [CONTROL_REPLY])


if __name__ == "__main__":
    unittest.main()
