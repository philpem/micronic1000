"""Regression tests for idle and edge-bearing scope segments."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from decode_ir_scope import decode_segment


def test_idle_segment_has_no_edges_or_cells():
    segment = [(index * 1e-6, 0.0, 0.0) for index in range(8)]
    decoded = decode_segment(segment, None, None, 0, 0)
    assert decoded["clock_rising_edges"] == 0
    assert decoded["clock_cells"] == 0
    assert decoded["bits"] == ""
    assert decoded["edge_times_s"] == []


def test_edge_segment_still_decodes_clock_sample():
    segment = [
        (0.0, 0.0, 0.0),
        (1e-6, 2.0, 3.0),
        (2e-6, 0.0, 0.0),
        (3e-6, 2.0, 0.0),
        (4e-6, 0.0, 0.0),
    ]
    decoded = decode_segment(segment, 1.0, 1.0, 0, 1)
    assert decoded["clock_rising_edges"] == 2
    assert decoded["bits"] == "10"
