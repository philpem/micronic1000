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


def test_reject_invalid_or_ambiguous_capture(tmp_path):
    capture = tmp_path / "invalid.csv"
    capture.write_text("x-axis,D0-D7\nsecond,\n0,0\n1e-6,4\n1e-6,8\n")
    with pytest.raises(ValueError, match="time order"):
        feedback_scope.measure(capture, 2, 3, 5, 0x7E, 122)
    capture.write_text("x-axis,D0-D7\nsecond,\n0,0\n1e-6,4\n2e-6,8\n")
    with pytest.raises(ValueError, match="distinct"):
        feedback_scope.measure(capture, 2, 2, 5, 0x7E, 122)
