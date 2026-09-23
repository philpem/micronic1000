"""Check pulse extraction and pairing against an independent synthetic CSV."""

from pathlib import Path
import sys

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent))
import feedback_scope


def test_archived_trial5_capture_reproduces_bench_measurement():
    capture = Path(__file__).resolve().parent / "captures" / "feedback-trial5-keysight.csv"
    result = feedback_scope.measure(capture, 2, 3, 5, 0x7E, 122)
    assert result["samples"] == 2000
    assert result["sample_step_us"] == pytest.approx(2.5)
    assert (len(result["clock"]), len(result["data"])) == (13, 6)
    assert result["sampled_flag_hex"] == "7E"
    assert result["lead_interval_median_us"] == pytest.approx(90)
    assert result["later_interval_median_us"] == pytest.approx(130)


def test_archived_trial6_capture_meets_emitter_timing_targets():
    capture = Path(__file__).resolve().parent / "captures" / "feedback-trial6-keysight.csv"
    result = feedback_scope.measure(capture, 2, 3, 5, 0x7E, 122)
    assert result["samples"] == 2000
    assert (len(result["clock"]), len(result["data"])) == (13, 6)
    assert result["sampled_flag_hex"] == "7E"
    assert all(abs(period - 122) <= 8 for period in result["clock_intervals_us"])
    assert all(abs(pulse["width_us"] - 61) <= 8 for pulse in result["clock"])
    assert all(abs(pulse["width_us"] - 76) <= 8 for pulse in result["data"])


def test_archived_trial8_capture_swaps_clock_and_data_channels():
    capture = Path(__file__).resolve().parent / "captures" / "feedback-trial8-keysight.csv"
    result = feedback_scope.measure(capture, 3, 2, 5, 0x7E, 122)
    assert result["samples"] == 2000
    assert (len(result["clock"]), len(result["data"])) == (13, 6)
    assert result["sampled_flag_hex"] == "7E"
    assert all(abs(period - 122) <= 8 for period in result["clock_intervals_us"])
    assert all(abs(pulse["width_us"] - 61) <= 8 for pulse in result["clock"])
    assert all(abs(pulse["width_us"] - 76) <= 8 for pulse in result["data"])


def test_mso_packed_capture_measures_complete_candidate(tmp_path):
    capture = tmp_path / "capture.csv"
    rows = ["x-axis,D0-D7", "second,"]
    for sample in range(1000):
        time_us = -250 + sample * 2.5
        mask = 0
        for cell in range(13):
            if cell * 122 + 30 <= time_us < cell * 122 + 91:
                mask |= 1 << 2
        for cell in range(6, 12):
            if cell * 122 <= time_us < cell * 122 + 76:
                mask |= 1 << 3
        rows.append(f"{time_us / 1e6:.9f},{mask}")
    capture.write_text("\n".join(rows) + "\n")
    result = feedback_scope.measure(capture, 2, 3, 5, 0x7E, 122)
    assert (len(result["clock"]), len(result["data"])) == (13, 6)
    assert result["lead_interval_median_us"] == pytest.approx(122, abs=2.5)
    assert result["later_interval_median_us"] == pytest.approx(122, abs=2.5)
    assert result["clock"][0]["width_us"] == pytest.approx(61, abs=2.5)
    assert [p["clock_index"] for p in result["data_clock_pairs"]] == list(range(6, 12))
    assert result["sampled_flag_hex"] == "7E"
    assert all(p["data_minus_clock_us"] == pytest.approx(-30, abs=2.5)
               for p in result["data_clock_pairs"])
    assert "13/13 pulses" in feedback_scope.report(result)


def _write_cells_capture(path, cells, lead=2):
    rows = ["x-axis,D0-D7", "second,"]
    for sample in range(1500):
        time_us = -250 + sample * 2.5
        mask = 0
        for cell in range(lead + len(cells)):
            if cell * 122 + 30 <= time_us < cell * 122 + 91:
                mask |= 1 << 2
            if cell >= lead and cells[cell - lead]:
                if cell * 122 <= time_us < cell * 122 + 76:
                    mask |= 1 << 3
        rows.append(f"{time_us / 1e6:.9f},{mask}")
    path.write_text("\n".join(rows) + "\n")


def test_payload03_samples_complete_flag_and_payload(tmp_path):
    capture = tmp_path / "payload03.csv"
    # Raw 7E flag followed by the eight MSB-first bits of payload 03.
    cells = [0, 1, 1, 1, 1, 1, 1, 0, 0, 0, 0, 0, 0, 0, 1, 1]
    _write_cells_capture(capture, cells)
    result = feedback_scope.measure(capture, 2, 3, 2, 0x7E, 122,
                                    bytes.fromhex("03"))
    assert result["expected_cells"] == 16
    assert result["expected_clock_pulses"] == 18
    assert result["sampled_flag_hex"] == "7E"
    assert result["sampled_bits"] == "0111111000000011"
    assert result["expected_data_pulses"] == 8
    assert [p["clock_index"] for p in result["data_clock_pairs"]] == [3, 4, 5, 6, 7, 8, 16, 17]


@pytest.mark.parametrize(("payload", "stuffing", "cells"), [
    (bytes.fromhex("F8"), 1, "111110000"),  # insert zero after five ones
    (bytes.fromhex("07"), 2, "000001111"),  # insert one after five zeros
])
def test_payload_stuffing_cells_are_sampled(tmp_path, payload, stuffing, cells):
    capture = tmp_path / f"stuff{stuffing}.csv"
    flag_cells = "01111110"
    all_cells = [int(bit) for bit in flag_cells + cells]
    _write_cells_capture(capture, all_cells)
    result = feedback_scope.measure(capture, 2, 3, 2, 0x7E, 122,
                                    payload, stuffing)
    assert result["sampled_bits"] == flag_cells + cells
    assert result["expected_cells"] == len(all_cells)
    assert result["expected_clock_pulses"] == 2 + len(all_cells)


def test_closing_flag_is_counted_and_sampled(tmp_path):
    capture = tmp_path / "closed.csv"
    cells = [int(bit) for bit in "01111110" + "00000011" + "01111110"]
    _write_cells_capture(capture, cells)
    result = feedback_scope.measure(capture, 2, 3, 2, 0x7E, 122,
                                    bytes.fromhex("03"), 1, True)
    assert result["expected_cells"] == 24
    assert result["sampled_bits"] == "011111100000001101111110"


def test_reject_invalid_or_ambiguous_capture(tmp_path):
    capture = tmp_path / "invalid.csv"
    capture.write_text("x-axis,D0-D7\nsecond,\n0,0\n1e-6,4\n1e-6,8\n")
    with pytest.raises(ValueError, match="time order"):
        feedback_scope.measure(capture, 2, 3, 5, 0x7E, 122)
    capture.write_text("x-axis,D0-D7\nsecond,\n0,0\n1e-6,4\n2e-6,8\n")
    with pytest.raises(ValueError, match="distinct"):
        feedback_scope.measure(capture, 2, 2, 5, 0x7E, 122)
