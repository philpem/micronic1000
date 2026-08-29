#!/usr/bin/env python3
"""Regressions for the evidence-scoped external-link scaffold."""

import unittest

from micronic import proto


class LinkPeerTest(unittest.TestCase):
    def test_adapter_moves_opaque_bytes_in_both_directions(self):
        peer = proto.LinkPeer()
        adapter = peer.make_adapter_link()

        adapter.tx(b"\x01\x7f\xff")
        self.assertEqual(peer.pending_rx, 3)
        self.assertEqual(bytes(peer.read_rx() for _ in range(3)), b"\x01\x7f\xff")

        peer.write_tx(0x12)
        peer.write_tx(0x34)
        self.assertEqual(adapter.rx(2, timeout=1), b"\x12\x34")

    def test_adapter_read_timeout(self):
        adapter = proto.LinkPeer().make_adapter_link()
        self.assertIsNone(adapter.rx(1, timeout=1))

    def test_confirmed_header_checks(self):
        frame = b"\x08\x00\x04\x21\x45\xaaOK"
        self.assertTrue(proto.Link.validate_header(frame, 0x45))
        self.assertFalse(proto.Link.validate_header(frame, 0x44))
        self.assertFalse(proto.Link.validate_header(frame, 0x45, logical_count=7))
        self.assertFalse(proto.Link.validate_header(frame[:5], 0x45))


if __name__ == "__main__":
    unittest.main()
