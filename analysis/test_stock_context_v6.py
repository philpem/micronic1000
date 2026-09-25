"""Guard and differential checks for the terminal status/count diagnostic."""
import pathlib
import sys

import pytest

sys.path.insert(0, str(pathlib.Path(__file__).parent / "rom_exerciser"))
import stock_context_v5 as v5
import stock_context_v6 as v6
from test_stock_context_v3 import _machine, _run_to


def _run(image, symbols, statuses, descriptor=bytes.fromhex("0a 00 00 90 00 00"),
         *, stop_at_sample=False):
    cpu, mem = _machine(image)
    mem[0xF794] = 0x10
    mem[0xF78B] = 0x20
    mem[0xFDDC:0xFDDE] = bytes.fromhex("00 80")
    mem[0x8000:0x8000 + len(descriptor)] = descriptor
    events = []
    status_index = 0
    data_reads = 0

    def inp(port):
        nonlocal status_index, data_reads
        port &= 0xFF
        events.append(("in", port))
        if port == 0x4B:
            value = statuses[min(status_index, len(statuses) - 1)]
            status_index += 1
            return value
        if port == 0x4E:
            data_reads += 1
            return 0 if data_reads == 1 else data_reads
        return 0

    cpu.set_input_callback(inp)
    cpu.set_output_callback(lambda port, value:
                            events.append(("out", port & 0xFF, value)))
    cpu.pc = 0x2FBD
    cpu.sp = 0xF81A
    if stop_at_sample:
        _run_to(cpu, v6.STATUS_HOOK_SITE)
    else:
        _run_to(cpu, symbols["stopped"])
    return cpu, mem, events


def _lcd_text(events):
    register = None
    chars = []
    for event in events:
        if event[:2] == ("out", 0x23):
            register = event[2]
        if event[:2] == ("out", 0x03) and register == 0x0C:
            chars.append(event[2])
    return bytes(chars).decode("ascii")


def test_v6_changes_only_guarded_terminal_site_and_cave():
    image, symbols, stock = v6.build_image()
    prior, prior_symbols, same_stock = v5.build_image()
    assert stock == same_stock
    assert image[v6.STATUS_HOOK_SITE:v6.STATUS_HOOK_SITE + 4] == (
        b"\xC3" + symbols["terminal_hook"].to_bytes(2, "little") + b"\x00")
    assert stock[v6.STATUS_HOOK_SITE:v6.STATUS_HOOK_SITE + 4] == v6.STATUS_HOOK_BYTES
    assert symbols["end"] <= v6.v5.v4.v3.CODE_END + 1
    allowed = set(range(v6.v5.v4.v3.CODE_ORG, v6.v5.v4.v3.CODE_END + 1))
    allowed.update(range(v6.STATUS_HOOK_SITE, v6.STATUS_HOOK_SITE + 4))
    assert {i for i, (before, after) in enumerate(zip(prior, image))
            if before != after} <= allowed
    # The receive wrapper and boot witness run unchanged until the new
    # post-return readout. Only the terminal-status path gains work.
    start = v6.v5.v4.v3.CODE_ORG
    assert image[start:prior_symbols["show_result"]] == prior[
        start:prior_symbols["show_result"]]
    for address, original in v5.RESET_SITES:
        assert image[address:address + len(original)] == original


def test_receive_io_and_registers_match_v5_through_terminal_sample():
    old, old_symbols, _ = v5.build_image()
    new, new_symbols, _ = v6.build_image()
    statuses = [1, 1, 1, 0x0A]
    old_cpu, old_mem, old_io = _run(old, old_symbols, statuses, stop_at_sample=True)
    new_cpu, new_mem, new_io = _run(new, new_symbols, statuses, stop_at_sample=True)
    assert old_io == new_io
    assert (old_cpu.a, old_cpu.f, old_cpu.bc, old_cpu.de, old_cpu.hl,
            old_cpu.ix, old_cpu.sp) == (
            new_cpu.a, new_cpu.f, new_cpu.bc, new_cpu.de, new_cpu.hl,
            new_cpu.ix, new_cpu.sp)
    assert old_mem[0x9000:0x900A] == new_mem[0x9000:0x900A]

    _run_to(old_cpu, old_symbols["stopped"])
    _run_to(new_cpu, new_symbols["stopped"])
    assert old_mem[0xC7E2:0xC7E4] == new_mem[0xC7E2:0xC7E4]
    assert old_mem[0xC7E2:0xC7E4] == bytes.fromhex("29 ec")
    assert _lcd_text(new_io) == "R6IEC29S0AN0003"


@pytest.mark.parametrize("statuses,descriptor,expected", [
    ([0x0A], bytes.fromhex("0a 00 00 90 00 00"), "R6IEC2DS0AN0000"),
    ([0x02], bytes.fromhex("0a 00 00 90 00 00"), "R6IECA9S02N0000"),
    ([0x0E], bytes.fromhex("0a 00 00 90 00 00"), "R6IEC2DS0EN0001"),
    ([1, 1, 1, 1, 1, 0x0A],
     bytes.fromhex("03 00 00 90 05 00 10 90 00 00 00 00"),
     "R6IEC2DS0AN0005"),
    ([0], bytes.fromhex("0a 00 00 90 00 00"), "R6IEE6D"),
    ([0x0A], bytes.fromhex("00 00 00 90 00 00"), "R6IED6D"),
])
def test_status_count_readout_and_nonterminal_returns(statuses, descriptor, expected):
    image, symbols, _ = v6.build_image()
    _, _, events = _run(image, symbols, statuses, descriptor)
    assert _lcd_text(events) == expected


def test_release_reproduces_guarded_builder():
    image, _, _ = v6.build_image()
    release = (v6.v5.v4.v3.HERE / "releases/stock-context-v6/"
               "micron1_stock_context_v6.bin")
    assert release.read_bytes() == image
