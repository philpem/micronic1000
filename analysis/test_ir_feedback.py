"""Compile and run the Arduino feedback state machine against fake hardware."""

from pathlib import Path
import os
import shutil
import subprocess
import tempfile

import pytest


ROOT = Path(__file__).resolve().parent.parent
HARNESS = ROOT / "analysis" / "test_ir_feedback.cpp"


@pytest.mark.parametrize(
    ("black_use_npn", "mode_name"),
    [(1, "NPN"), (0, "DIRECT_TTL")],
)
def test_feedback_public_state_machine_with_uart_waveforms(
    black_use_npn, mode_name
):
    compiler = shutil.which("g++")
    if compiler is None:
        pytest.skip("g++ is unavailable")
    with tempfile.TemporaryDirectory(prefix="m1000-feedback-") as directory:
        executable = Path(directory) / f"feedback-{mode_name.lower()}"
        subprocess.run(
            [
                compiler,
                "-std=c++11",
                "-Wall",
                "-Wextra",
                "-Werror",
                "-fsanitize=address,undefined",
                "-fno-omit-frame-pointer",
                f"-DBLACK_USE_NPN={black_use_npn}",
                str(HARNESS),
                "-o",
                str(executable),
            ],
            cwd=ROOT,
            check=True,
            timeout=30,
        )
        sanitizer_environment = os.environ.copy()
        sanitizer_environment["ASAN_OPTIONS"] = "detect_leaks=0"
        result = subprocess.run(
            [str(executable)],
            cwd=ROOT,
            check=True,
            env=sanitizer_environment,
            text=True,
            capture_output=True,
            timeout=30,
        )
    assert (
        f"feedback public state-machine integration ({mode_name}): ok"
        in result.stdout
    )


def test_feedback_rejects_invalid_black_interface_setting():
    compiler = shutil.which("g++")
    if compiler is None:
        pytest.skip("g++ is unavailable")
    with tempfile.TemporaryDirectory(prefix="m1000-feedback-") as directory:
        result = subprocess.run(
            [
                compiler,
                "-std=c++11",
                "-DBLACK_USE_NPN=2",
                str(HARNESS),
                "-o",
                str(Path(directory) / "feedback-invalid"),
            ],
            cwd=ROOT,
            text=True,
            capture_output=True,
            timeout=30,
        )
    assert result.returncode != 0
    assert "BLACK_USE_NPN must be 0" in result.stderr
