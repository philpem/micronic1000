"""Build and exercise the host shim for the real Arduino emitter."""

from pathlib import Path
import shutil
import subprocess
import tempfile

import pytest


ROOT = Path(__file__).resolve().parent.parent
HARNESS = ROOT / "analysis" / "test_ir_emitter.cpp"


def compile_harness(output: Path, *defines: str) -> None:
    compiler = shutil.which("g++")
    if compiler is None:
        pytest.skip("g++ is unavailable")
    command = [
        compiler,
        "-std=c++11",
        "-Wall",
        "-Wextra",
        "-Werror",
        *(f"-D{define}" for define in defines),
        str(HARNESS),
        "-o",
        str(output),
    ]
    subprocess.run(command, cwd=ROOT, check=True)


def test_real_emitter_waveform_and_terminal_stuffing():
    with tempfile.TemporaryDirectory(prefix="m1000-ir-host-") as directory:
        executable = Path(directory) / "emitter"
        compile_harness(executable)
        result = subprocess.run(
            [str(executable)], cwd=ROOT, check=True, text=True,
            capture_output=True,
        )
    assert "chronology/phase/wrap/stuffing: ok" in result.stdout


@pytest.mark.parametrize(
    "defines",
    [
        ("LISTEN_ONLY=1", "RX_NARROW=0"),
        ("RECORD_READOUT=1", "LISTEN_ONLY=1", "RX_NARROW=0"),
        ("LOOPBACK_TEST=1", "RX_NARROW=0"),
        ("ORIENTATION_TEST=1", "RX_NARROW=0"),
        ("PULSE_TEST=1", "RX_NARROW=0"),
        ("ADDR_SWEEP=1", "PULSE_TEST=1", "RX_NARROW=0"),
        ("FREERUN_TEST=1", "RX_NARROW=0"),
        ("LADDER_TEST=1", "RX_NARROW=0"),
        ("RX_SWEEP=1", "RX_NARROW=0"),
        ("FREE_TX=1", "RX_NARROW=0"),
        ("RX_NARROW=1", "RX_NARROW_AXIS=0"),
        ("RX_NARROW=1", "RX_NARROW_AXIS=1"),
        ("RX_NARROW=1", "RX_NARROW_AXIS=3", "STOCK_CONTEXT_EVENTS=1"),
        ("FREE_TX=1", "RX_NARROW=0", "STOCK_CONTEXT_EVENTS=1",
         "STOCK_FIXED_CANDIDATE=1", "STOCK_TX_SWAP=1",
         "STOCK_CLOCK_INVERT=1", "STOCK_DATA_INVERT=1"),
    ],
)
def test_host_syntax_checks_all_sketch_modes(defines):
    with tempfile.TemporaryDirectory(prefix="m1000-ir-mode-") as directory:
        compile_harness(Path(directory) / "mode.o", "FEEDBACK_HARNESS=0", *defines)


def test_stock_capture_and_32_bit_width():
    with tempfile.TemporaryDirectory(prefix="m1000-stock-capture-") as directory:
        executable = Path(directory) / "capture"
        compile_harness(executable, "FEEDBACK_HARNESS=0", "LISTEN_ONLY=1",
                        "RX_NARROW=0", "STOCK_CONTEXT_EVENTS=1")
        subprocess.run([str(executable)], cwd=ROOT, check=True,
                       text=True, capture_output=True)


@pytest.mark.parametrize("stuffing,closing", [(0, 0), (0, 1),
                                                (1, 0), (1, 1),
                                                (2, 0), (2, 1)])
def test_fixed_stock_run_probe_framing(stuffing, closing):
    with tempfile.TemporaryDirectory(prefix="m1000-stock-frame-") as directory:
        executable = Path(directory) / "frame"
        compile_harness(executable, "FEEDBACK_HARNESS=0", "FREE_TX=1",
                        "RX_NARROW=0", "STOCK_FIXED_CANDIDATE=1",
                        "STOCK_CONTENT_IDX=3",
                        f"STOCK_STUFFING_MODE={stuffing}",
                        f"STOCK_CLOSE_FLAG={closing}")
        subprocess.run([str(executable)], cwd=ROOT, check=True,
                       text=True, capture_output=True)


@pytest.mark.parametrize(
    "defines",
    [
        ("RX_NARROW=1", "RX_NARROW_AXIS=3", "STOCK_TX_SWAP=1"),
        ("RX_NARROW=1", "RX_NARROW_AXIS=3", "STOCK_FIXED_CANDIDATE=1",
         "STOCK_FLAG_IDX=0", "STOCK_PHASE_IDX=4", "STOCK_POL_IDX=1",
         "STOCK_CONTENT_IDX=0", "STOCK_TX_SWAP=1",
         "STOCK_CLOCK_INVERT=1", "STOCK_DATA_INVERT=1"),
        ("RX_NARROW=1", "STOCK_FIXED_CANDIDATE=1",
         "STOCK_REPLY_DELAY_US=30000", "STOCK_REPLY_DELAY_STEP_US=1000",
         "STOCK_REPLY_DELAY_COUNT=7"),
        ("RX_NARROW=1", "STOCK_FIXED_CANDIDATE=1",
         "STOCK_REPLY_DELAY_US=33000", "STOCK_REPLY_EVERY_N=3"),
        ("RX_NARROW=0", "FREE_TX=1", "STOCK_FIXED_CANDIDATE=1",
         "STOCK_FLAG_IDX=0", "STOCK_PHASE_IDX=4", "STOCK_POL_IDX=1",
         "STOCK_CONTENT_IDX=0", "STOCK_TX_SWAP=1",
         "STOCK_CLOCK_INVERT=1", "STOCK_DATA_INVERT=1"),
    ],
)
def test_stock_mode_setup_and_candidate_progression(defines):
    with tempfile.TemporaryDirectory(prefix="m1000-stock-mode-") as directory:
        executable = Path(directory) / "mode"
        compile_harness(executable, "FEEDBACK_HARNESS=0",
                        "STOCK_CONTEXT_EVENTS=1", *defines)
        subprocess.run([str(executable)], cwd=ROOT, check=True,
                       text=True, capture_output=True)
