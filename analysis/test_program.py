#!/usr/bin/env python3
"""Golden regression tests for micronic.program (COM/DIP validator).

Self-contained, stdlib only. Run with:

  analysis/venv/bin/python3 analysis/test_program.py
  python3 analysis/test_program.py
  analysis/venv/bin/python3 -m unittest analysis.test_program
  python3 -m unittest analysis.test_program

Covers the CONFIRMED grammar from doc/manual/program-formats.md:

  - COM/DIP discrimination by first-chunk rule
  - DIP 14-byte LE header, magic C9 C8, system ID {0, E5 00}, block count <=5
  - Block parsing, payload length validation, type-1 multiple-of-4
  - COM max 0xCF81
  - Image size clamping (NOT rejected)
  - Error identifiers matching loader codes where applicable
"""
from __future__ import annotations

import sys
import unittest
from pathlib import Path

# Ensure `analysis/micronic` is importable when run as script
sys.path.insert(0, str(Path(__file__).resolve().parent))

from micronic.program import (
    COM_MAX,
    DIP_HEADER_SIZE,
    DIP_MAGIC,
    DIP_MAGIC_BYTES,
    ERR_COM_TOO_BIG,
    ERR_DIP_BAD_FILE,
    ERR_DIP_TOO_MANY_BLOCKS,
    ERR_DIP_WRONG_SYSTEM,
    ERR_DIP_TYPE1_ALIGN,
    classify,
    validate,
    validate_com,
    validate_dip,
    build_dip_header,
    build_dip_block,
    build_dip_file,
)

# ---------------------------------------------------------------- helpers
def _dip(*, system_id=0x00E5, blocks=None, **hdr_kw):
    if blocks is None:
        blocks = []
    return build_dip_file(header_kwargs=dict(system_id=system_id, **hdr_kw), blocks=blocks)

class TestClassify(unittest.TestCase):
    def test_short_file_is_com(self):
        self.assertEqual(classify(b""), "COM")
        self.assertEqual(classify(b"\xC9"), "COM")
        self.assertEqual(classify(b"\xC9\xC8\x00"), "COM")
        self.assertEqual(classify(b"\x00" * 13), "COM")
        # 13 bytes even if starts with magic -> still COM (first chunk <14)
        self.assertEqual(classify(DIP_MAGIC_BYTES + b"\x00" * 11), "COM")

    def test_magic_mismatch_is_com(self):
        # 14+ bytes but first word != C8C9 -> COM
        self.assertEqual(classify(b"\x00\x00" + b"\x00" * 12), "COM")
        self.assertEqual(classify(b"\xC9\xC9" + b"\x00" * 12), "COM")
        self.assertEqual(classify(b"\xC8\xC9" + b"\x00" * 12), "COM")

    def test_magic_match_is_dip(self):
        hdr = build_dip_header(system_id=0, block_count=0)
        self.assertEqual(classify(hdr), "DIP")
        hdr2 = build_dip_header(system_id=0x00E5, block_count=0)
        self.assertEqual(classify(hdr2), "DIP")

    def test_validate_routes_via_classify(self):
        # Short magic prefix but <14 -> validates as COM, not DIP
        data = DIP_MAGIC_BYTES + b"\x00" * 5  # 7 bytes starting with C9 C8
        res = validate(data)
        self.assertEqual(res.kind, "COM")
        self.assertTrue(res.valid)

class TestCom(unittest.TestCase):
    def test_empty_com_valid(self):
        self.assertTrue(validate(b"").valid)
        self.assertEqual(validate(b"").kind, "COM")

    def test_com_under_limit_valid(self):
        data = b"\x00" * COM_MAX
        res = validate(data)
        self.assertEqual(res.kind, "COM")
        self.assertTrue(res.valid)

    def test_com_over_limit_invalid(self):
        data = b"\x00" * (COM_MAX + 1)
        res = validate(data)
        self.assertEqual(res.kind, "COM")
        self.assertFalse(res.valid)
        self.assertTrue(res.has_error(ERR_COM_TOO_BIG))
        # also check via direct validate_com
        res2 = validate_com(data)
        self.assertFalse(res2.valid)

    def test_com_exact_limit_valid(self):
        data = b"A" * COM_MAX
        self.assertTrue(validate(data).valid)

    def test_com_large_over_limit(self):
        data = b"\xFF" * (COM_MAX + 100)
        res = validate(data)
        self.assertFalse(res.valid)
        self.assertTrue(any(e.code == ERR_COM_TOO_BIG for e in res.errors))

class TestDipHeader(unittest.TestCase):
    def test_minimal_dip_zero_blocks(self):
        data = build_dip_file(blocks=[])
        res = validate(data)
        self.assertEqual(res.kind, "DIP")
        self.assertTrue(res.valid)
        self.assertEqual(res.header.block_count, 0)
        self.assertEqual(len(res.blocks), 0)

    def test_system_id_wildcard_zero(self):
        data = _dip(system_id=0, blocks=[])
        self.assertTrue(validate(data).valid)

    def test_system_id_e5(self):
        data = _dip(system_id=0x00E5, blocks=[])
        self.assertTrue(validate(data).valid)

    def test_system_id_rejected(self):
        for bad in (0x0001, 0x00E6, 0xFFFF, 0x1234):
            data = _dip(system_id=bad, blocks=[])
            res = validate(data)
            self.assertFalse(res.valid, f"system_id {bad:#06x} should be rejected")
            self.assertTrue(res.has_error(ERR_DIP_WRONG_SYSTEM))

    def test_block_count_at_max(self):
        blocks = [(0, 0, 0x1000 + i * 0x100, b"") for i in range(5)]
        data = _dip(blocks=blocks)
        res = validate(data)
        self.assertTrue(res.valid)
        self.assertEqual(len(res.blocks), 5)

    def test_block_count_too_many(self):
        hdr = build_dip_header(system_id=0, block_count=6)
        # file is just header claiming 6 blocks, no blocks follow -> should error on count
        res = validate(hdr)
        self.assertFalse(res.valid)
        self.assertTrue(res.has_error(ERR_DIP_TOO_MANY_BLOCKS))
        # 10 also
        hdr2 = build_dip_header(system_id=0, block_count=10)
        self.assertTrue(validate(hdr2).has_error(ERR_DIP_TOO_MANY_BLOCKS))

    def test_image_size_clamped_not_rejected(self):
        # Loader clamps to 0x8000, does NOT reject. Validator must not error.
        for size in (0x8000, 0x8001, 0x9000, 0xFFFF):
            data = build_dip_header(system_id=0, image_size=size, block_count=0)
            res = validate(data)
            self.assertTrue(res.valid, f"image_size {size:#06x} should not be rejected")
            self.assertEqual(res.header.image_size, size)
            expected_clamped = size if size <= 0x8000 else 0x8000
            self.assertEqual(res.header.image_size_clamped, expected_clamped)

    def test_header_fields_round_trip(self):
        hdr = build_dip_header(system_id=0x00E5, entry_bank_offset=0x1234, image_size=0x4000,
                               run_bank_offset=0x5678, entry_address=0x9ABC, block_count=0)
        res = validate(hdr)
        self.assertTrue(res.valid)
        self.assertEqual(res.header.entry_bank_offset, 0x1234)
        self.assertEqual(res.header.image_size, 0x4000)
        self.assertEqual(res.header.run_bank_offset, 0x5678)
        self.assertEqual(res.header.entry_address, 0x9ABC)

class TestDipBlocks(unittest.TestCase):
    def test_type0_block_valid(self):
        data = _dip(blocks=[(0, 0, 0x1000, b"hello")])
        res = validate(data)
        self.assertTrue(res.valid)
        self.assertEqual(res.blocks[0].type, 0)
        self.assertEqual(res.blocks[0].payload, b"hello")

    def test_type1_block_valid_multiple_of_4(self):
        # 2 items: 8 bytes = 2*4
        payload = b"\x00\x00\x10\x00\x34\x12\x34\x12"
        data = _dip(blocks=[(1, 0, 0x2000, payload)])
        res = validate(data)
        self.assertTrue(res.valid)

    def test_type1_payload_not_multiple_of_4(self):
        for bad_len in (1, 2, 3, 5, 6, 7, 9):
            payload = b"\x00" * bad_len
            data = _dip(blocks=[(1, 0, 0x2000, payload)])
            res = validate(data)
            self.assertFalse(res.valid, f"payload_len {bad_len} should be rejected for type 1")
            self.assertTrue(res.has_error(ERR_DIP_TYPE1_ALIGN))

    def test_type1_empty_payload_valid(self):
        # 0 % 4 == 0, so empty type-1 block is aligned
        data = _dip(blocks=[(1, 0, 0x2000, b"")])
        self.assertTrue(validate(data).valid)

    def test_type0_payload_any_length(self):
        for ln in (1, 2, 3, 5, 7):
            data = _dip(blocks=[(0, 0, 0x1000, b"x" * ln)])
            self.assertTrue(validate(data).valid, f"type 0 len {ln} should be allowed")

    def test_payload_truncated(self):
        # Header says payload 10 but only 5 bytes follow
        hdr = build_dip_header(system_id=0, block_count=1)
        blk_hdr = build_dip_block(0, 0, 0x1000, b"12345")  # would be 5
        # Patch payload_len to 10 without adding bytes
        import struct
        blk_hdr_patched = struct.pack("<HHHH", 0, 0, 0x1000, 10) + b"12345"
        data = hdr + blk_hdr_patched
        res = validate(data)
        self.assertFalse(res.valid)
        self.assertTrue(res.has_error(ERR_DIP_BAD_FILE))

    def test_block_header_truncated(self):
        hdr = build_dip_header(system_id=0, block_count=1)
        # Only 3 bytes of block header instead of 8
        data = hdr + b"\x00\x00\x01"
        res = validate(data)
        self.assertFalse(res.valid)
        self.assertTrue(res.has_error(ERR_DIP_BAD_FILE))

    def test_second_block_header_truncated(self):
        # First block valid, second block header truncated
        hdr = build_dip_header(system_id=0, block_count=2)
        b1 = build_dip_block(0, 0, 0x1000, b"hi")
        # second header truncated
        data = hdr + b1 + b"\x01\x00"
        res = validate(data)
        self.assertFalse(res.valid)
        self.assertTrue(res.has_error(ERR_DIP_BAD_FILE))
        # First block should still be parsed
        self.assertEqual(len(res.blocks), 1)

    def test_second_block_payload_truncated(self):
        hdr = build_dip_header(system_id=0, block_count=2)
        b1 = build_dip_block(0, 0, 0x1000, b"hi")
        import struct
        b2_hdr = struct.pack("<HHHH", 0, 0, 0x2000, 20) + b"short"
        data = hdr + b1 + b2_hdr
        res = validate(data)
        self.assertFalse(res.valid)
        self.assertTrue(res.has_error(ERR_DIP_BAD_FILE))

    def test_multiple_blocks_mixed_types(self):
        blocks = [
            (0, 0, 0x1000, b"raw data"),
            (1, 1, 0x2000, b"\x00\x00\x01\x00\x02\x00\x03\x00"),  # 8 bytes, 2 items
            (0, 2, 0x3000, b""),
        ]
        data = _dip(blocks=blocks)
        res = validate(data)
        self.assertTrue(res.valid)
        self.assertEqual(len(res.blocks), 3)

    def test_unknown_block_type_allowed(self):
        # Only types 0 and 1 have handlers; other values take default path
        # with no error. Validator must not reject unknown types.
        for t in (2, 3, 99, 0xFFFF):
            data = _dip(blocks=[(t, 0, 0x1000, b"payload")])
            res = validate(data)
            self.assertTrue(res.valid, f"type {t} should not be rejected")

    def test_empty_payload_blocks(self):
        data = _dip(blocks=[(0, 0, 0x1000, b""), (0, 0, 0x1100, b"")])
        self.assertTrue(validate(data).valid)

class TestGoldenVectors(unittest.TestCase):
    """Hand-crafted byte vectors that match the CONFIRMED grammar exactly."""

    def test_golden_valid_dip_two_blocks(self):
        # Build a realistic DIP: header + 2 blocks (type0 + type1)
        blocks = [
            (0, 0x0000, 0x4000, b"\x01\x02\x03\x04"),
            (1, 0x0001, 0x5000, b"\x00\x00\x10\x00"),  # one 4-byte item
        ]
        data = build_dip_file(
            header_kwargs=dict(system_id=0x00E5, entry_bank_offset=0, image_size=0x1000,
                               run_bank_offset=0, entry_address=0x1000, block_count=2),
            blocks=blocks,
        )
        # Verify raw bytes manually
        self.assertEqual(data[0:2], b"\xC9\xC8")
        self.assertEqual(data[2:4], b"\xE5\x00")
        res = validate(data)
        self.assertTrue(res.valid)
        self.assertEqual(res.header.block_count, 2)
        self.assertEqual(len(res.blocks), 2)

    def test_golden_bad_dip_too_many_blocks(self):
        hdr = build_dip_header(system_id=0, block_count=6)
        res = validate(hdr)
        self.assertFalse(res.valid)
        # Error text must contain the documented string
        err_text = str(res.errors[0])
        self.assertIn("0x2334", err_text)
        self.assertIn("9012", err_text)  # decimal is same numeric value 0x2334=9012

    def test_golden_bad_system_id(self):
        hdr = build_dip_header(system_id=0x1234, block_count=0)
        res = validate(hdr)
        self.assertFalse(res.valid)
        self.assertIn("0x2331", str(res.errors[0]))

    def test_golden_com_too_big(self):
        data = b"A" * (COM_MAX + 1)
        res = validate(data)
        self.assertFalse(res.valid)
        self.assertIn("0x232C", str(res.errors[0]))

    def test_golden_dip_bad_payload(self):
        import struct
        hdr = build_dip_header(system_id=0, block_count=1)
        # Declare 8 but provide 3
        hdr2 = struct.pack("<HHHH", 1, 0, 0x1000, 8) + b"\x00\x00\x00"
        data = hdr + hdr2
        res = validate(data)
        self.assertFalse(res.valid)
        self.assertIn("0x232B", str(res.errors[0]))

    def test_golden_image_size_clamp_vector(self):
        # Exactly the case the docs warn not to invent: size 0x9000 must pass
        hdr = build_dip_header(system_id=0, image_size=0x9000, block_count=0)
        res = validate(hdr)
        self.assertTrue(res.valid)
        self.assertEqual(res.header.image_size_clamped, 0x8000)

# ---------------------------------------------------------------- run
if __name__ == "__main__":
    # Support both `python3 analysis/test_program.py` and `python3 -m unittest`
    unittest.main()
