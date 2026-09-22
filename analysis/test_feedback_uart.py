"""Black-box timing tests for the feedback ROM's yellow UART result path.

The decoder sees only port-2Ah writes and elapsed Z80 cycles.  It samples at
the external receiver's fixed 1200-baud clock and never uses assembler delay
constants as an oracle.
"""
from __future__ import annotations

from pathlib import Path
import statistics
import sys
import time

import pytest

try:
    import z80
except ImportError:  # pragma: no cover - supplied by the analysis venv
    z80 = None

ANALYSIS = Path(__file__).resolve().parent
sys.path.insert(0, str(ANALYSIS))
from rom_exerciser import feedback


CPU_HZ = 3_686_400
UART_BAUD = 1200
UART_TSTATES = CPU_HZ / UART_BAUD


class YellowProbe:
    """Execute feedback code and timestamp physical yellow levels at port 2Ah."""

    def __init__(self, edge=lambda: 0xFF):
        image, self.sym, _ = feedback.build_image()
        self.image = image
        self.mem = bytearray(0x10000)
        self.mem[:0x8000] = image
        self.cpu = z80.Z80Machine()
        self.cpu.set_memory_block(0, bytes(self.mem))
        self.cpu.set_read_callback(lambda address: self.mem[address & 0xFFFF])
        self.cpu.set_write_callback(
            lambda address, value: self.mem.__setitem__(address & 0xFFFF,
                                                         value & 0xFF))
        self.cpu.set_input_callback(lambda port: edge() if (port & 0xFF) == 0x2D else 0)
        self.writes: list[tuple[int, int, int]] = []
        self.elapsed = 0
        self._slice_start = 0
        self._slice_budget = 0
        self.cpu.set_output_callback(self._write_port)

    def _write_port(self, port, value):
        # The extension's ticks_to_stop is not valid during a callback. Exact
        # timestamps are captured at the OUT instruction breakpoint below.
        self.writes.append((0, port & 0xFF, value & 0xFF))

    def _used(self, budget):
        raw = self.cpu.ticks_to_stop & 0xFFFFFF
        # The low 24 bits are a remaining-cycle count.  A one-instruction
        # run may overshoot a small budget, represented as a wrapped negative
        # remainder.
        used = (budget + (1 << 24) - raw) if raw & 0x800000 else budget - raw
        assert 0 <= used <= budget + 32
        return used

    def capture_yellow(self, entry, stop, *, a=None):
        """Timestamp port writes at single-instruction execution boundaries."""
        if a is not None:
            self.cpu.a = a
        if stop == 0x8000:
            self.cpu.sp = 0xC8FE
            self.mem[0xC8FE:0xC900] = b"\x00\x80"
        self.cpu.pc = self.sym[entry]
        self.cpu.set_breakpoint(stop)
        edges = []
        deadline = time.monotonic() + 25
        for _ in range(1_000_000):
            if time.monotonic() >= deadline:
                break
            before = len(self.writes)
            pc = self.cpu.pc
            self._slice_budget = 1
            self.cpu.ticks_to_stop = self._slice_budget
            self.cpu.run()
            self.elapsed += _z80_tstates(self.image, pc, self.cpu.pc)
            for _, port, value in self.writes[before:]:
                if port == 0x2A:
                    edges.append((self.elapsed, value & 1, value))
            if self.cpu.pc == stop:
                break
        self.cpu.clear_breakpoint(stop)
        assert self.cpu.pc == stop, f"{entry} did not reach {stop:04X}"
        return edges

    def run_to(self, name: str, *, a: int | None = None, chunks: int = 1000):
        if a is not None:
            self.cpu.a = a
        self.cpu.sp = 0xC8FE
        self.mem[0xC8FE:0xC900] = b"\x00\x80"
        self.cpu.pc = self.sym[name]
        target = 0x8000
        self.cpu.set_breakpoint(target)
        deadline = time.monotonic() + 25
        for _ in range(chunks):
            if time.monotonic() >= deadline:
                break
            self._slice_start = self.elapsed
            self._slice_budget = 100_000
            self.cpu.ticks_to_stop = self._slice_budget
            self.cpu.run()
            self.elapsed += self._used(self._slice_budget)
            if self.cpu.pc == target:
                break
        self.cpu.clear_breakpoint(target)
        assert self.cpu.pc == target, f"{name} did not return: {self.cpu.pc:04X}"

    def run_until(self, entry: str, stop: str, *, a: int | None = None,
                  chunks: int = 2000):
        if a is not None:
            self.cpu.a = a
        self.cpu.pc = self.sym[entry]
        target = self.sym[stop]
        self.cpu.set_breakpoint(target)
        deadline = time.monotonic() + 25
        for _ in range(chunks):
            if time.monotonic() >= deadline:
                break
            self._slice_start = self.elapsed
            self._slice_budget = 100_000
            self.cpu.ticks_to_stop = self._slice_budget
            self.cpu.run()
            self.elapsed += self._used(self._slice_budget)
            if self.cpu.pc == target:
                break
        self.cpu.clear_breakpoint(target)
        assert self.cpu.pc == target, f"{entry} did not reach {stop}: {self.cpu.pc:04X}"

    def set_result_state(self, *, shadow2a=0xB6, shadow2c=0xA5):
        # Bit 0 is released high; every other 2Ah bit is deliberately nonzero
        # so UART writes prove they preserve their owning latch value.
        self.mem[self.sym["SHADOW2A"]] = shadow2a & 0xFE
        self.mem[self.sym["SHADOW2C"]] = shadow2c
        values = {
            "S_MODE": 2, "S_SEQLO": 0x34, "S_SEQHI": 0x12,
            "S_ERR": 0, "S_PROBE": 0x9C, "S_BEFORE": 0x53,
            "S_AFTER": 0xCA, "S_P4": 0x10, "S_P6": 0x40,
            "S_ARM": 1, "S_RXA": 0xEC, "S_RXF": 0xA5,
            "S_RXL": 0x86, "S_RXH": 0, "S_PREVLEN": 8,
            "S_RAW2D": 0xFE,
        }
        for name, value in values.items():
            self.mem[self.sym[name]] = value
        self.mem[self.sym["S_PREVIEW"]:self.sym["S_PREVIEW"] + 8] = bytes(
            [0x00, 0xFF, 0x55, 0xAA, 0x81, 0x7E, 0x01, 0x80])

    def yellow(self):
        return [(tick, value & 1, value) for tick, port, value in self.writes
                if port == 0x2A]


def _line_at(events, at):
    level = 0  # released/high before the direct send_result call
    for tick, low, _ in events:
        if tick > at:
            break
        level = low
    return level


def _z80_tstates(memory, pc, next_pc):
    """T-states for the opcodes executed by this bounded result/guard path.

    pyz80's stop counter is an instruction budget.  This tiny dynamic counter
    instead uses the emitted machine instruction and observed branch target,
    so all timing assertions remain in physical Z80 T-states.
    """
    op = memory[pc]
    fixed = {
        0x00: 4, 0x01: 10, 0x06: 7, 0x0B: 6, 0x0E: 7, 0x0F: 4, 0x10: None, 0x11: 10,
        0x12: 7, 0x13: 6, 0x16: 7, 0x18: 12, 0x1A: 7, 0x1E: 7, 0x1F: 4, 0x20: None,
        0x21: 10, 0x23: 6, 0x26: 7, 0x28: None, 0x2A: 16, 0x2E: 7,
        0x30: None, 0x32: 13, 0x34: 11, 0x36: 10, 0x38: None, 0x3A: 13, 0x3E: 7,
        0xAF: 4, 0xA7: 4, 0xB0: 4, 0xB1: 4, 0xB7: 4, 0xC1: 10,
            0xC3: 10, 0xC5: 11, 0xC6: 7, 0xC9: 10, 0xCD: 17, 0xD1: 10, 0xD3: 11,
            0xDB: 11,
        0xD5: 11, 0xE1: 10, 0xE5: 11, 0xE6: 7, 0xEE: 7, 0xF1: 10,
        0xF5: 11, 0xF6: 7, 0xF9: 6, 0xFE: 7,
    }
    if op in (0x10, 0x20, 0x28, 0x30, 0x38):
        target = (pc + 2 + ((memory[pc + 1] + 0x80) & 0xFF) - 0x80) & 0xFFFF
        return 13 if op == 0x10 and next_pc == target else (
            8 if op == 0x10 else (12 if next_pc == target else 7))
    if 0x40 <= op <= 0x7F:
        # LD r,r': an operand encoded as (HL) costs the extra memory cycles.
        return 7 if ((op & 7) == 6 or ((op >> 3) & 7) == 6) else 4
    if 0x80 <= op <= 0xBF:
        return 7 if (op & 7) == 6 else 4
    if op == 0xED and memory[pc + 1] == 0x44:  # NEG
        return 8
    if op == 0xCB and memory[pc + 1] == 0x47:  # BIT 0,A
        return 8
    if op == 0xC8:  # RET Z
        return 5 if next_pc == pc + 1 else 11
    if op in fixed and fixed[op] is not None:
        return fixed[op]
    raise AssertionError(f"unmapped opcode {op:02X} at {pc:04X}")


def _uart_period(events):
    """Estimate a cell from observed output cadence, never from ROM constants."""
    deltas = [b[0] - a[0] for a, b in zip(events, events[1:]) if b[0] > a[0]]
    assert deltas
    # Inter-byte bookkeeping adds a small high gap; the repeated cell cadence
    # is the dominant population.  Median is robust to those gaps and to runs
    # of equal data bits, because uart_byte writes every cell explicitly.
    return statistics.median(deltas)


def _decode_8n1(events, period=UART_TSTATES):
    starts = []
    previous = 0
    for tick, low, _ in events:
        if low and not previous:
            starts.append(tick)
        previous = low
    decoded = []
    search_after = events[0][0]
    for start in starts:
        if start < search_after:
            continue
        assert _line_at(events, start + period * 0.50) == 1  # start low
        value = 0
        for bit in range(8):
            # UART high/released is logical one; sink/low is logical zero.
            value |= (not _line_at(events, start + period * (1.5 + bit))) << bit
        assert _line_at(events, start + period * 9.50) == 0  # stop high
        decoded.append(value)
        search_after = start + period * 9.75
    return bytes(decoded)


@pytest.mark.skipif(z80 is None, reason="pyz80 is required")
def test_send_result_is_external_1200baud_8n1_and_preserves_latches():
    p = YellowProbe()
    p.set_result_state()
    events = p.capture_yellow("send_result", 0x8000)
    record = _decode_8n1(events)

    expected = bytes(p.mem[p.sym["RESULT"]:p.sym["RESULT"] + 30])
    assert record == expected
    assert len(record) == 30
    assert record[:6] == bytes.fromhex("A5 5A 01 02 34 12")
    assert sum(record) & 0xFF == 0
    # This is the receiver's independent physical baud expectation, rather
    # than an assertion about bit_delay's source literals.
    measured = _uart_period(events)
    assert UART_TSTATES * 0.98 <= measured <= UART_TSTATES * 1.02

    # All data patterns occur in one record.  Decode at a deliberately
    # perturbed receiver clock too, proving start/data/stop margins rather
    # than merely grouping assembler writes.
    assert {0x00, 0xFF, 0x55, 0xAA, 0x81, 0x7E, 0x01, 0x80} <= set(record)
    for tolerance in (0.98, 1.02):
        assert _decode_8n1(events, UART_TSTATES * tolerance) == expected

    assert all((value & 0xFE) == 0xB6 for _, _, value in events)
    assert not any(port == 0x2C for _, port, _ in p.writes)
    assert p.mem[p.sym["SHADOW2A"]] == 0xB6
    assert p.mem[p.sym["SHADOW2C"]] == 0xA5


@pytest.mark.skipif(z80 is None, reason="pyz80 is required")
def test_start_guard_and_result_leadin_are_distinct_physical_windows():
    # Mode zero avoids a stock trial but retains accepted_trial's actual
    # 50-ms START guard and its 2-ms marker.  Decode timing from port writes.
    start = YellowProbe()
    start.set_result_state(shadow2a=0x22, shadow2c=0)
    start.mem[start.sym["S_MODE"]] = 0
    start_events = start.capture_yellow("accepted_trial", start.sym["idle"])
    # The preceding high selected here is the last write before UART, so find
    # the first low after entering accepted_trial instead of a data-bit edge.
    first_start_low = next(tick for tick, low, _ in start_events if low)
    start_guard = first_start_low - min(tick for tick, low, _ in start_events if not low)

    error = YellowProbe(edge=lambda: 0xFF)
    error.set_result_state(shadow2a=0x22, shadow2c=0)
    error_events = error.capture_yellow("command_error", error.sym["idle"], a=1)
    first_uart_low = next(tick for tick, low, _ in error_events if low)
    result_leadin = first_uart_low - min(tick for tick, low, _ in error_events if not low)

    # The physical interface promises roughly 50 ms and 20 ms.  Broad bounds
    # leave room for call/port overhead while rejecting a wrong loop scale.
    assert CPU_HZ * 0.040 <= start_guard <= CPU_HZ * 0.065
    assert CPU_HZ * 0.015 <= result_leadin <= CPU_HZ * 0.030
    assert start_guard > result_leadin * 1.8
