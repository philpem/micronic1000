"""Single-variable ROM comparison for the stock-reset v5 diagnostic."""
import pathlib
import sys

import pytest

sys.path.insert(0, str(pathlib.Path(__file__).parent / "rom_exerciser"))
import stock_context_v4 as v4
import stock_context_v5 as v5
from test_stock_context_v3 import _machine, _run_to


def test_only_v4_reset_routes_are_restored():
    image, symbols, stock = v5.build_image()
    old, old_symbols, _ = v4.build_image()
    assert symbols == old_symbols
    allowed = set()
    for address, expected in v5.RESET_SITES:
        allowed.update(range(address, address + len(expected)))
        assert image[address:address + len(expected)] == expected
    assert {i for i, (a, b) in enumerate(zip(image, old)) if a != b} <= allowed
    assert image[v4.v3.CODE_ORG:symbols["end"]] == old[v4.v3.CODE_ORG:symbols["end"]]
    assert image[v4.v3.RX_CALL_SITE:v4.v3.RX_CALL_SITE + 3] == old[v4.v3.RX_CALL_SITE:v4.v3.RX_CALL_SITE + 3]
    assert image[v4.v3.INIT_SITE:v4.v3.INIT_SITE + 5] == old[v4.v3.INIT_SITE:v4.v3.INIT_SITE + 5]
    assert image != stock


@pytest.mark.parametrize("bootkeys,expected", [(0, 0x01A6), (1, 0x024D), (3, 0x17A5)])
def test_stock_reset_classification(bootkeys, expected):
    image, _, _ = v5.build_image()
    cpu, mem = _machine(image)
    mem[0xF81C] = 0x55
    cpu.set_input_callback(lambda p: bootkeys if p & 255 == 0x49 else 0)
    cpu.set_output_callback(lambda p, v: None)
    cpu.pc = 0
    for address in (0x01A6, 0x024D, 0x17A5):
        cpu.set_breakpoint(address)
    _run_to(cpu, expected)
