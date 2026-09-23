"""Focused tests for passive stock-context serial log analysis."""
import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent))
from stock_context_log import analyze, correlate_lines, main


def test_correlates_preceding_tx_across_micros_wraparound():
    events = correlate_lines([
        "# TX flag=81 tx_start_us=4294967290 swap=1 emit_late_max=4",
        "# STOCK_YELLOW rise_us=12 low_us=5",
    ])
    assert events == [{
        "line": 2,
        "rise_us": 12,
        "low_us": 5,
        "event_start_us": 7,
        "tx_start_us": 4294967290,
        "tx_elapsed_us": 13,
        "swap": "1",
        "tx_line_number": 1,
        "tx_line": "# TX flag=81 tx_start_us=4294967290 swap=1 emit_late_max=4",
        "classification": "preceding TX",
    }]


def test_missing_or_garbled_tx_is_reported_as_silent_control():
    events = correlate_lines([
        "garbage from partial startup",
        "# TX flag=81 tx_start_us=not-a-number swap=0",
        "# STOCK_YELLOW rise_us=123 low_us=900",
    ])
    assert events == [{
        "line": 3,
        "rise_us": 123,
        "low_us": 900,
        "event_start_us": 4294966519,
        "tx": None,
        "classification": "no preceding TX (silent/control)",
    }]


def test_analyze_skips_malformed_json_and_reads_serial_lines(tmp_path):
    path = tmp_path / "capture.jsonl"
    path.write_text("\n".join([
        "not json",
        json.dumps({"line": "# STOCK_YELLOW rise_us=50 low_us=1000"}),
    ]) + "\n")
    assert analyze(path)[0]["classification"] == "no preceding TX (silent/control)"


def test_tx_from_future_half_range_is_not_correlated():
    events = correlate_lines([
        "# TX flag=81 tx_start_us=1000 swap=0",
        "# STOCK_YELLOW rise_us=900 low_us=1000",
    ])
    assert events[0]["tx"] is None
    assert events[0]["classification"] == "no preceding TX (silent/control)"


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


def test_analyze_missing_file_returns_concise_cli_error(tmp_path, capsys):
    missing = tmp_path / "absent.jsonl"
    assert main(["--log", str(missing), "--analyze"]) == 1
    captured = capsys.readouterr()
    assert str(missing) in captured.err
    assert "Traceback" not in captured.err
