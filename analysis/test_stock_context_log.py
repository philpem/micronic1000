"""Focused tests for passive stock-context serial log analysis."""
import json
from pathlib import Path
import sys
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent))
from stock_context_log import analyze, correlate_lines, main


def test_correlates_preceding_tx_across_micros_wraparound():
    events = correlate_lines([
        "# TX flag=81 tx_start_us=4294967290 swap=1 emit_late_max=4",
        "# STOCK_YELLOW rise_us=12 low_us=5",
    ])
    assert events == [{
        "line": 2,
        "epoch": 0,
        "rise_us": 12,
        "low_us": 5,
        "event_start_us": 7,
        "pulse_class": "unclassified",
        "schema": "legacy",
        "tx_start_us": 4294967290,
        "tx_elapsed_us": 13,
        "swap": "1",
        "tx_line_number": 1,
        "tx_line": "# TX flag=81 tx_start_us=4294967290 swap=1 emit_late_max=4",
        "classification": "preceding TX",
    }]


def test_missing_or_garbled_tx_is_unmatched_not_silent():
    events = correlate_lines([
        "garbage from partial startup",
        "# TX flag=81 tx_start_us=not-a-number swap=0",
        "# STOCK_YELLOW rise_us=123 low_us=900",
    ])
    assert events == [{
        "line": 3,
        "epoch": 0,
        "rise_us": 123,
        "low_us": 900,
        "event_start_us": 4294966519,
        "pulse_class": "carry_set_candidate",
        "schema": "legacy",
        "tx": None,
        "classification": "unmatched: no TX timestamp in window",
    }]


def test_analyze_rejects_malformed_json_instead_of_silently_losing_evidence(tmp_path):
    path = tmp_path / "capture.jsonl"
    path.write_text("\n".join([
        "not json",
        json.dumps({"line": "# STOCK_YELLOW rise_us=50 low_us=1000"}),
    ]) + "\n")
    with pytest.raises(ValueError, match="capture is incomplete"):
        analyze(path)


def test_tx_from_future_half_range_is_not_correlated():
    events = correlate_lines([
        "# TX flag=81 tx_start_us=1000 swap=0",
        "# STOCK_YELLOW rise_us=900 low_us=1000",
    ])
    assert events[0]["tx"] is None
    assert events[0]["classification"] == "unmatched: no TX timestamp in window"


def test_delayed_event_uses_timestamp_history_and_pulse_fall():
    events = correlate_lines([
        "# TX flag=81 tx_start_us=1000 swap=0 emit_late_max=4",
        # This emitted later and its log was printed while the old pulse was
        # still low; the pulse fall predates this newer TX start.
        "# TX flag=81 tx_start_us=2000 swap=1 emit_late_max=4",
        "# STOCK_YELLOW rise_us=2500 low_us=1000",
    ])
    assert events[0]["event_start_us"] == 1500
    assert events[0]["tx_start_us"] == 1000
    assert events[0]["tx_elapsed_us"] == 500
    assert events[0]["swap"] == "0"
    assert events[0]["tx_line_number"] == 1


def test_rx_narrow_burst_report_is_tx_candidate():
    burst = "burst 12 bits=32 flag=81 tx_start_us=4000 swap=1"
    events = correlate_lines([
        burst,
        "# STOCK_YELLOW rise_us=5600 low_us=600",
    ])
    assert events[0]["event_start_us"] == 5000
    assert events[0]["tx_start_us"] == 4000
    assert events[0]["tx_elapsed_us"] == 1000
    assert events[0]["swap"] == "1"
    assert events[0]["tx_line"] == burst


def test_rx_narrow_tx_at_end_of_bracketed_report():
    events = correlate_lines([
        "burst 17 cells [reply_sent=1 swap=0 tx_start_us=4000]",
        "# STOCK_YELLOW rise_us=6000 low_us=916",
    ])
    assert events[0]["tx_start_us"] == 4000
    assert events[0]["tx_elapsed_us"] == 1084


def test_nearest_timestamp_wins_across_free_tx_and_rx_narrow_reports():
    events = correlate_lines([
        "# TX flag=81 tx_start_us=1000 swap=0",
        "burst 12 bits=32 flag=81 tx_start_us=1400 swap=1",
        "# STOCK_YELLOW rise_us=2100 low_us=500",
    ])
    assert events[0]["tx_start_us"] == 1400
    assert events[0]["swap"] == "1"


def test_association_window_bounds_old_tx_history():
    events = correlate_lines([
        "# TX flag=81 tx_start_us=1000 swap=0",
        "# STOCK_YELLOW rise_us=252000 low_us=0",
    ], association_window_us=250_000)
    assert events[0]["tx"] is None


def test_boot_starts_new_micros_epoch_and_clears_tx_history():
    events = correlate_lines([
        "BOOT",
        "# TX flag=81 phase(data-clock)=-2/8cell pol=0 content_idx=2 tx_start_us=4000 swap=1 emit_late_max=4",
        "# STOCK_YELLOW rise_us=5600 low_us=600",
        "BOOT",
        "# STOCK_YELLOW rise_us=5600 low_us=600",
    ])
    assert events[0]["epoch"] == 1
    assert events[0]["classification"] == "preceding TX"
    assert events[1]["epoch"] == 2
    assert events[1]["tx"] is None


def test_drop_report_after_event_marks_whole_epoch_incomplete():
    events = correlate_lines([
        "BOOT",
        "# STOCK_YELLOW rise_us=2500 low_us=500",
        "# STOCK_YELLOW_DROPS 3",
    ])
    assert events[0]["capture_incomplete"] is True
    assert events[0]["dropped_events"] == 3
    assert events[0]["classification"] == "unmatched: no TX timestamp in window"


def test_v3_accepts_65535_as_real_width_and_classifies_known_bands():
    events = correlate_lines([
        "STOCK_CONTEXT_V3 width_us=32 drops=16",
        "# TX flag=81 tx_start_us=1000 swap=0 emit_late_max=4",
        "# STOCK_YELLOW rise_us=67000 low_us=65535",
        "# STOCK_YELLOW rise_us=68000 low_us=900",
        "# STOCK_YELLOW rise_us=70000 low_us=1800",
        "# STOCK_YELLOW rise_us=74000 low_us=3600",
    ])
    assert events[0]["schema"] == "v3"
    assert events[0]["low_us"] == 65535
    assert "width_saturated" not in events[0]
    assert events[0]["pulse_class"] == "unclassified"
    assert [e["pulse_class"] for e in events[1:]] == [
        "carry_set_candidate", "carry_clear_candidate", "boot_signature_candidate"
    ]


def test_legacy_startup_banner_begins_new_epoch_and_legacy_cap_is_noted():
    events = correlate_lines([
        "# TX flag=81 tx_start_us=1000 swap=0",
        "M1000 IR probe. Expecting 17- or 22-cell bursts at 93.75 ms.",
        "# STOCK_YELLOW rise_us=67000 low_us=65535",
    ])
    assert events[0]["epoch"] == 1
    assert events[0]["schema"] == "legacy"
    assert events[0]["width_saturated"] is True
    assert events[0]["tx"] is None


def test_arbitrary_width_remains_unclassified():
    event = correlate_lines(["# STOCK_YELLOW rise_us=5000 low_us=1200"])[0]
    assert event["pulse_class"] == "unclassified"


def test_delayed_tx_report_can_follow_event_in_serial_log():
    events = correlate_lines([
        "# STOCK_YELLOW rise_us=3000 low_us=900",
        "# TX flag=7E tx_start_us=1000 swap=1",
    ])
    assert events[0]["tx_start_us"] == 1000
    assert events[0]["tx_elapsed_us"] == 1100


def test_saturated_legacy_width_and_init_signature_never_match_tx():
    events = correlate_lines([
        "# TX flag=7E tx_start_us=1000 swap=1",
        "# STOCK_YELLOW rise_us=67535 low_us=65535",
        "# STOCK_YELLOW rise_us=8000 low_us=3600",
    ])
    assert all(event["tx"] is None for event in events)
    assert events[0]["event_start_us"] is None


def test_drop_only_capture_is_not_silent_and_zero_drops_are_not_loss():
    events = correlate_lines(["# STOCK_YELLOW_DROPS 5"])
    assert events[0]["capture_incomplete"]
    assert events[0]["dropped_events"] == 5
    event = correlate_lines([
        "# STOCK_YELLOW rise_us=3000 low_us=900",
        "# STOCK_YELLOW_DROPS 0",
    ])[0]
    assert "capture_incomplete" not in event


def test_analyze_missing_file_returns_concise_cli_error(tmp_path, capsys):
    missing = tmp_path / "absent.jsonl"
    assert main(["--log", str(missing), "--analyze"]) == 1
    captured = capsys.readouterr()
    assert str(missing) in captured.err
    assert "Traceback" not in captured.err


def test_valid_json_with_missing_line_and_oversized_width_are_rejected(tmp_path):
    path = tmp_path / "capture.jsonl"
    path.write_text('{}\n')
    with pytest.raises(ValueError, match="string line"):
        analyze(path)
    with pytest.raises(ValueError, match="uint32"):
        correlate_lines(["# STOCK_YELLOW rise_us=10 low_us=4294967296"])
