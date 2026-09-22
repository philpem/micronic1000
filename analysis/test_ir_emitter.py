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
    ],
)
def test_host_syntax_checks_all_sketch_modes(defines):
    with tempfile.TemporaryDirectory(prefix="m1000-ir-mode-") as directory:
        compile_harness(Path(directory) / "mode.o", *defines)
