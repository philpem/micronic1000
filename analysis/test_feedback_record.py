"""Feedback record layout and checksum checks, including v2 status slots."""
from pathlib import Path
import sys

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent))
from feedback_record import decode_record, records_from_lines


def frame(version=2, mode=5, slot=b"\x91\x81\x02\x00\xFF\xFF\xE8\x03"):
    record = bytearray(30)
    record[:4] = [0xA5, 0x5A, version, mode]
    record[4:6] = [0x34, 0x12]
    record[17] = 8
    record[18:26] = slot
    record[26:29] = [0x22, 0x00, 0x23]
    record[29] = -sum(record) & 0xFF
    return bytes(record)


def test_v2_status_slot_stops_before_port_shadows():
    result = decode_record(frame())
    assert result["rom_sequence"] == 0x1234
    assert result["status_capture"] == {
        "link_status_or": 0x91, "link_status_and": 0x81,
        "first_link_status_bit4_sample": 2,
        "first_link_status_bit0_sample": None, "sample_count": 1000,
    }
    assert (result["port_2a_shadow"], result["port_2c_shadow"],
            result["port_2d_input"]) == (0x22, 0, 0x23)


def test_v1_preview_remains_distinct_from_v2_capture():
    result = decode_record(frame(version=1, mode=2))
    assert result["rx_preview"] == "91810200FFFFE803"
    assert "status_capture" not in result


def test_k_watcher_and_count_are_decoded():
    raw = bytearray(frame(mode=7, slot=b"\x10\x00\x03\x00\xFF\xFF\x58\x02"))
    raw[10] = 0x10
    raw[29] = -sum(raw[:29]) & 0xFF
    result = decode_record(bytes(raw))
    assert result["status_capture"]["sample_count"] == 600
    assert result["status_capture"]["watcher_saw_link_status_bit4"] is True

    with pytest.raises(ValueError, match="sample count"):
        decode_record(frame(mode=7))


def test_existing_capture_log_decodes_without_reinterpreting_preview():
    path = Path(__file__).resolve().parent / "captures/feedback-repeat-pending-55-60.jsonl"
    records = [record for _, record in records_from_lines(path.read_text().splitlines())]
    assert [r["rom_sequence"] for r in records] == list(range(58, 64))
    assert all(r["version"] == 1 and r["mode"] == 4 and r["error"] == 8
               for r in records)


def test_bad_checksum_and_inconsistent_status_are_rejected():
    bad = bytearray(frame())
    bad[29] ^= 1
    with pytest.raises(ValueError, match="checksum"):
        decode_record(bytes(bad))
    with pytest.raises(ValueError, match="inconsistent"):
        decode_record(frame(slot=b"\x00\x10\x00\x00\xFF\xFF\xE8\x03"))
