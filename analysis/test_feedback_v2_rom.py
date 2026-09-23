"""Emulator checks for the separate feedback-v2 ROM source."""
from pathlib import Path
import json
import sys

import pytest

try:
    import z80
except ImportError:  # pragma: no cover
    z80 = None

ANALYSIS = Path(__file__).resolve().parent
sys.path.insert(0, str(ANALYSIS))
from rom_exerciser import feedback_v2
import test_feedback_rom as v1_tests

NEEDS_EMULATOR = pytest.mark.skipif(z80 is None, reason="pyz80 is unavailable")


class Probe(v1_tests.Probe):
    """Reuse the proven I/O harness with the v2 image and symbols."""
    def __init__(self, *args, **kwargs):
        old = v1_tests.feedback
        v1_tests.feedback = feedback_v2
        try:
            super().__init__(*args, **kwargs)
        finally:
            v1_tests.feedback = old


@pytest.mark.parametrize("ticks,mode", [
    (70, 2), (71, 7), (89, 7), (90, 3), (110, 3),
    (111, 5), (119, 5), (120, 6), (129, 6), (130, 4),
])
@NEEDS_EMULATOR
def test_v2_h_j_command_windows_are_disjoint_from_p_and_g(ticks, mode):
    p = Probe()
    p.run_to("idle")
    p.mem[p.sym["S_TICKS"]] = ticks
    p.call("classify_command")
    assert p.value("S_MODE") == mode


@NEEDS_EMULATOR
def test_fast_sampler_runs_full_window_and_records_raw_status_summary():
    p = Probe(status=lambda: 0x91)
    p.run_to("idle")
    p.call("reset_trial")
    p.call("fast_sample", chunks=1000)
    summary = bytes(p.mem[p.sym["S_PREVIEW"]:p.sym["S_PREVIEW"] + 8])
    assert summary == bytes([0x91, 0x91, 0, 0, 0, 0, 0xE8, 0x03])
    assert p.value("S_PREVLEN") == 8
    assert p.value("S_ERR") == 0


@NEEDS_EMULATOR
def test_fast_sampler_indices_first_bit4_and_bit0_samples():
    reads = iter([0x00, 0x10, 0x01] + [0x00] * 997)
    p = Probe(status=lambda: next(reads, 0))
    p.run_to("idle")
    p.call("reset_trial")
    p.call("fast_sample", chunks=1000)
    data = p.mem[p.sym["S_PREVIEW"]:p.sym["S_PREVIEW"] + 8]
    # The pre-window BEFORE read consumes element zero; index zero of the
    # sampled window then sees bit4, followed by bit0 at index one.
    assert data[2:4] == bytes([0, 0])
    assert data[4:6] == bytes([1, 0])
    assert data[6:8] == bytes([0xE8, 0x03])


@pytest.mark.parametrize("entry,mode,active_bits,count", [
    ("run_fast_h", 5, 0xC0, 1000),
    ("run_fast_j", 6, 0x00, 1000),
    ("run_fast_k", 7, None, 600),
])
@NEEDS_EMULATOR
def test_mode_entry_selects_state_then_restores_idle(entry, mode, active_bits, count):
    observed = []
    p = None

    def status():
        observed.append(p.value("CTRL_SHADOW") & 0xC0)
        return 0

    p = Probe(status=status)
    p.run_to("idle")
    p.call("reset_trial")
    p.mem[p.sym["S_MODE"]] = mode
    p.mem[p.sym["S_P4"]] = 0xFF
    observed.clear()
    p.call(entry, chunks=1000)
    assert p.value("CTRL_SHADOW") & 0xC0 == 0xC0
    assert p.value("S_AFTER") == 0
    assert p.mem[p.sym["S_PREVIEW"] + 6:p.sym["S_PREVIEW"] + 8] == bytes(
        [count & 255, count >> 8])
    if active_bits is not None:
        assert observed[-(count + 1):-1] == [active_bits] * count
    else:
        assert p.value("S_P4") == 0  # K clears the not-run sentinel


@NEEDS_EMULATOR
def test_k_repeats_stock_clear_test_rearm_without_dispatching_rx():
    rx_reads = []
    p = Probe(status=lambda: 0, rxd=lambda: rx_reads.append(1) or 0)
    p.run_to("idle")
    p.call("reset_trial")
    p.mem[p.sym["S_MODE"]] = 7
    p.mem[p.sym["S_P4"]] = 0  # run_fast_k's mode-specific initialization
    p.writes.clear()
    p.call("fast_sample", chunks=1000)
    data = p.mem[p.sym["S_PREVIEW"]:p.sym["S_PREVIEW"] + 8]
    assert data[:2] == bytes([0, 0])
    assert data[6:8] == bytes([0x58, 0x02])
    control = [v & 0xC0 for port, v in p.writes if port == 0x4A]
    # Each watcher-like turn clears bit 6, clears bit 7, then restores them
    # when no pending status was observed. The initial shadow is zero, so
    # its first clear writes 00h twice; later turns begin at C0h.
    assert control[:4] == [0, 0, 0x40, 0xC0]
    assert control[4:-2] == [0x80, 0, 0x40, 0xC0] * 599
    assert control[-2:] == [0xC0, 0xC0]  # final idle restoration
    assert not rx_reads
    assert p.value("CTRL_SHADOW") & 0xC0 == 0xC0
    assert p.value("S_P4") == 0


@NEEDS_EMULATOR
def test_k_records_pending_from_the_same_full_byte_used_by_summary():
    p = Probe(status=lambda: 0x10)
    p.run_to("idle")
    p.call("reset_trial")
    p.mem[p.sym["S_MODE"]] = 7
    p.mem[p.sym["S_P4"]] = 0
    p.call("fast_sample", chunks=1000)
    data = p.mem[p.sym["S_PREVIEW"]:p.sym["S_PREVIEW"] + 8]
    assert p.value("S_P4") == 0x10
    assert data[0] == data[1] == 0x10
    assert data[2:4] == bytes([0, 0])
    assert data[6:8] == bytes([0x58, 0x02])


@NEEDS_EMULATOR
def test_v2_result_version_and_fast_slots_are_checksummed():
    p = Probe()
    p.run_to("idle")
    p.call("reset_trial")
    p.mem[p.sym["S_MODE"]] = 5
    p.mem[p.sym["S_PREVLEN"]] = 8
    p.mem[p.sym["S_PREVIEW"]:p.sym["S_PREVIEW"] + 8] = bytes(range(8))
    p.call("make_result")
    record = bytes(p.mem[p.sym["RESULT"]:p.sym["RESULT"] + 30])
    assert record[:4] == bytes([0xA5, 0x5A, 2, 5])
    assert record[18:26] == bytes(range(8))
    assert sum(record) & 0xFF == 0


@pytest.mark.parametrize("mode,entry,released", [
    (1, "run_witness", False),
    (2, "run_rx", False),
    (3, "run_probe", False),
    (4, "run_pending_rx", False),
    (5, "run_fast_h", True),
    (6, "run_fast_j", True),
    (7, "run_fast_k", True),
])
@NEEDS_EMULATOR
def test_fast_modes_release_start_after_two_ms_but_legacy_modes_keep_it(mode,
                                                                         entry,
                                                                         released):
    p = Probe()
    p.run_to("idle")
    p.call("reset_trial")
    p.mem[p.sym["S_MODE"]] = mode
    p.writes.clear()
    p.cpu.pc = p.sym["accepted_trial"]
    p.run_to(entry, chunks=3000)
    writes = [v for port, v in p.writes if port == 0x2A]
    marker = writes.index(0x23)
    after_marker = writes[marker + 1:]
    if released:
        assert after_marker and after_marker[0] == 0x22
    else:
        assert not after_marker


@NEEDS_EMULATOR
def test_lcd_fast_modes_label_status_summary_not_rx_preview():
    p = Probe()
    p.run_to("idle")
    p.call("reset_trial")
    p.mem[p.sym["S_MODE"]] = 5
    p.mem[p.sym["S_PREVIEW"]:p.sym["S_PREVIEW"] + 8] = bytes(
        [0x91, 0x11, 0x34, 0x12, 0x78, 0x56, 0xE8, 0x03])
    p.call("show_result")
    assert p.screen[40:60] == b"O91 A11 41234 05678 "


@NEEDS_EMULATOR
def test_boot_banner_identifies_v2():
    p = Probe()
    p.run_to("idle")
    assert b"IR FEEDBACK V2 W..K" in p.screen


def test_sample_window_budget_is_below_100ms_at_stock_cpu_clock():
    # Owner-supplied clock is 3.6864 MHz. These conservative upper bounds
    # are exact cycle sums of the branch buckets documented in feedback_v2.asm.
    assert feedback_v2.FAST_SAMPLE_AUDITED_TSTATES == 321_261
    assert feedback_v2.FAST_K_SAMPLE_AUDITED_TSTATES == 327_468
    assert feedback_v2.FAST_SAMPLE_MAX_TSTATES == 340_000
    assert feedback_v2.FAST_K_SAMPLE_MAX_TSTATES == 360_000
    assert feedback_v2.FAST_SAMPLE_AUDITED_TSTATES <= feedback_v2.FAST_SAMPLE_MAX_TSTATES
    assert feedback_v2.FAST_K_SAMPLE_AUDITED_TSTATES <= feedback_v2.FAST_K_SAMPLE_MAX_TSTATES
    assert feedback_v2.FAST_SAMPLE_MAX_TSTATES < 3_686_400 * 0.100
    assert feedback_v2.FAST_K_SAMPLE_MAX_TSTATES < 3_686_400 * 0.100


def test_v2_manifest_rebuilds_from_source():
    path = ANALYSIS / "rom_exerciser/releases/feedback-v2/micron1_feedback_v2.json"
    image, symbols, original = feedback_v2.build_image()
    expected = json.loads(path.read_text())
    assert feedback_v2.manifest(image, symbols, original, expected["image"]) == expected
