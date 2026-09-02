"""Shared fixtures: build the decoder once, run it on a bare Z80.

The suite needs the `z80` module, which lives in ../analysis/venv.  Run it
with that interpreter:

    make test                       # does this for you
    ../analysis/venv/bin/python3 -m pytest tests/

Tests that need the emulator skip cleanly without it, so a plain
`pytest tests/` still checks the pure-Python parts (tables, encoders,
expansion rules).
"""
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))
sys.path.insert(0, str(ROOT.parent / "analysis"))

ORIGIN = 0x9000
WIDTH_TABLE = 0xF9B5      # where the firmware leaves the captured widths
PARAM_PTR = 0xFBB9
PARAM_COUNT = 0xFBBB
SENTINEL = 0xE000

try:
    import z80
except ImportError:                                   # pragma: no cover
    z80 = None

requires_emulator = pytest.mark.skipif(
    z80 is None,
    reason="needs the z80 module; run with ../analysis/venv/bin/python3")


@pytest.fixture(scope="session")
def decoder():
    """The assembled decoder, built once for the whole session."""
    build = ROOT / "build-test"
    r = subprocess.run(["make", f"ORIGIN={ORIGIN:#06x}", f"BUILD={build.name}"],
                       cwd=ROOT, capture_output=True, text=True)
    if r.returncode:
        pytest.fail(f"build failed:\n{r.stdout}\n{r.stderr}")
    return (build / "decoder.bin").read_bytes()


@pytest.fixture
def decode(decoder):
    """Run the decoder over a list of element widths; return the bytes."""
    def run(widths):
        mem = bytearray(0x10000)
        mem[ORIGIN:ORIGIN + len(decoder)] = decoder
        for i, w in enumerate(widths):
            mem[WIDTH_TABLE + 2 * i] = w & 0xFF
            mem[WIDTH_TABLE + 2 * i + 1] = w >> 8
        mem[PARAM_PTR] = WIDTH_TABLE & 0xFF
        mem[PARAM_PTR + 1] = WIDTH_TABLE >> 8
        mem[PARAM_COUNT] = len(widths) & 0xFF
        mem[PARAM_COUNT + 1] = len(widths) >> 8
        mem[SENTINEL] = SENTINEL & 0xFF
        mem[SENTINEL + 1] = SENTINEL >> 8

        m = z80.Z80Machine()
        m.set_memory_block(0, bytes(mem))
        m.set_read_callback(lambda a: mem[a & 0xFFFF])
        m.set_write_callback(lambda a, v: mem.__setitem__(a & 0xFFFF, v & 0xFF))
        m.sp = SENTINEL
        m.pc = ORIGIN
        m.set_breakpoint(SENTINEL)
        for _ in range(40000):
            m.ticks_to_stop = 2000
            m.run()
            if (m.pc & 0xFFFF) == SENTINEL:
                break
        else:
            raise AssertionError(f"the decoder never returned (pc={m.pc:04X})")

        n = mem[PARAM_COUNT] | (mem[PARAM_COUNT + 1] << 8)
        p = mem[PARAM_PTR] | (mem[PARAM_PTR + 1] << 8)
        return bytes(mem[p:p + n])
    return run
