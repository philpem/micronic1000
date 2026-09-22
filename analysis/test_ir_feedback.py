"""Compile and run the Arduino feedback state machine against fake hardware."""

from pathlib import Path
import os
import shutil
import subprocess
import tempfile

import pytest


ROOT = Path(__file__).resolve().parent.parent
HARNESS = ROOT / "analysis" / "test_ir_feedback.cpp"


def test_feedback_public_state_machine_with_uart_waveforms():
    compiler = shutil.which("g++")
    if compiler is None:
        pytest.skip("g++ is unavailable")
    with tempfile.TemporaryDirectory(prefix="m1000-feedback-") as directory:
        executable = Path(directory) / "feedback"
        subprocess.run(
            [
                compiler,
                "-std=c++11",
                "-Wall",
                "-Wextra",
                "-Werror",
                "-fsanitize=address,undefined",
                "-fno-omit-frame-pointer",
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
    assert "feedback public state-machine integration: ok" in result.stdout
