#!/usr/bin/env python3
"""Unit tests for the digital IR experiment capture decoder."""

import unittest

from scope_ir_experiments import (
    FLAG_BITS,
    cadence_reacted,
    parse_segment,
    response_address,
)


def stuffed_byte(value: int) -> str:
    output = []
    zero_run = 0
    for shift in range(7, -1, -1):
        if zero_run == 5:
            output.append("1")
            zero_run = 0
        encoded = "1" if value & (1 << shift) else "0"
        output.append(encoded)
        zero_run = zero_run + 1 if encoded == "0" else 0
    return "".join(output)


class ScopeIrExperimentTest(unittest.TestCase):
    def test_retry_cadence_population_boundaries(self):
        self.assertFalse(cadence_reacted(93.75))
        self.assertTrue(cadence_reacted(109.375))
        self.assertIsNone(cadence_reacted(102.0))
        self.assertIsNone(cadence_reacted(200.0))

    def test_address_decoder_accepts_optional_dc_preamble_edge(self):
        for address in (*range(0x40), 0x7F, 0xFF):
            with self.subTest(address=address):
                frame = FLAG_BITS + stuffed_byte(address)
                self.assertEqual(response_address(frame), address)
                self.assertEqual(response_address("1" + frame), address)

    def test_scope_pod_channel_mapping(self):
        # Scope D1 is handheld clock and D0 is handheld data.  Scope D2 is
        # Arduino clock and D3 is Arduino data.  Each high sample is followed
        # by a low sample so it contributes one rising edge.
        samples = [
            0,
            0b0011,
            0,
            0b0010,
            0,
            0b1100,
            0,
        ]
        times = [-0.002 + index * 0.001 for index in range(len(samples))]
        segment = parse_segment(0, times, samples)
        self.assertEqual(segment.handheld_bits, "10")
        self.assertEqual(segment.arduino_bits, "1")
        self.assertEqual(segment.arduino_clock_rises, 1)
        self.assertEqual(segment.arduino_data_rises, 1)
        self.assertAlmostEqual(segment.arduino_end_ms, 3.0)


if __name__ == "__main__":
    unittest.main()
