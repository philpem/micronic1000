"""Release gates for the one-shot diagnostic, using the project z80 emulator."""
import pathlib
import sys

import pytest

sys.path.insert(0, str(pathlib.Path(__file__).parent / 'rom_exerciser'))
import stock_context_v4 as v4
from test_stock_context_v3 import _machine, _run_to


@pytest.mark.parametrize('status,frame,capacity', [(0x0A, b'', 10), (0, b'', 10),
    (None, bytes.fromhex('112233445566'), 10),
    (None, bytes.fromhex('112233445566'), 2)])
def test_real_stock_rx_result_and_order(status, frame, capacity):
    image, sym, stock = v4.build_image()
    def run(rom, end):
        cpu, mem = _machine(rom)
        mem[0xF794] = 0x10
        mem[0xF78B] = 0x20
        mem[0xFDDC:0xFDDE] = bytes.fromhex('0080')
        mem[0x8000:0x8006] = bytes([capacity, 0, 0, 0x90, 0, 0])
        payload = list(frame)
        events = []
        reads = 0
        def inp(port):
            nonlocal reads
            port &= 255
            events.append(('in', port))
            if port == 0x4E:
                reads += 1
                return 0 if reads == 1 or not payload else payload.pop(0)
            if port == 0x4B:
                return status if status is not None else (1 if payload else 2)
            return 0
        cpu.set_input_callback(inp)
        cpu.set_output_callback(lambda p, v: events.append(('out', p & 255, v)))
        cpu.pc = 0x2FBD
        cpu.sp = 0xF81A
        _run_to(cpu, end)
        return cpu, mem, events
    original_cpu, original_mem, original_events = run(stock, 0x2FC4)
    cpu, mem, events = run(image, sym['stopped'])
    assert mem[0xC7E0:0xC7E2] == bytes.fromhex('0080')
    assert mem[0xC7E2:0xC7E4] == bytes([original_cpu.f, original_cpu.a])
    assert events[:len(original_events)] == original_events
    # LCD register selector 0C identifies characters, excluding cursor data.
    text = []
    reg = None
    for event in events[len(original_events):]:
        if event[:2] == ('out', 0x23):
            reg = event[2]
        if event[:2] == ('out', 3) and reg == 0x0C:
            text.append(event[2])
    assert bytes(text) == f'R4I{original_cpu.a:02X}{original_cpu.f:02X}'.encode()
    assert mem[0x9000:0x9006] == original_mem[0x9000:0x9006]


@pytest.mark.parametrize('bootkeys,stock_end', [(0, 0x01A6), (1, 0x024D), (3, 0x17A5)])
def test_reset_differential(bootkeys, stock_end):
    image, _, stock = v4.build_image()
    for rom, expected in [(stock, stock_end), (image, 0x01A6)]:
        cpu, mem = _machine(rom)
        mem[0xF81C] = 0x55
        cpu.set_input_callback(lambda p: bootkeys if p & 255 == 0x49 else 0)
        cpu.set_output_callback(lambda p, v: None)
        cpu.pc = 0
        for addr in (0x01A6, 0x024D, 0x17A5):
            cpu.set_breakpoint(addr)
        _run_to(cpu, expected)


@pytest.mark.parametrize('start', [0x019E, 0x17A5, 0x3812, 0xF2F5])
def test_direct_warm_entries_and_copied_kernel(start):
    image, _, _ = v4.build_image()
    cpu, mem = _machine(image)
    mem[0xF180:0xF180 + 0x50D] = image[0x369D:0x369D + 0x50D]
    mem[0xF81C] = 0x55
    cpu.pc = start
    _run_to(cpu, 0x01A6)
    assert mem[0xF1EB:0xF1ED] == bytes.fromhex('a601')


def test_boot_witness_and_release_reproduction():
    image, sym, stock = v4.build_image()
    cpu, mem = _machine(image)
    events = []
    cpu.set_output_callback(lambda p, v: events.append((p & 255, v, cpu.ticks_to_stop)))
    cpu.pc = 0x0252
    cpu.sp = 0xF81A
    cpu.a = 0x20
    cpu.f = 0x44
    cpu.bc, cpu.de, cpu.hl = 0x1234, 0x5678, 0x9ABC
    _run_to(cpu, 0x0257)
    assert (cpu.a, cpu.f, cpu.bc, cpu.de, cpu.hl, cpu.sp) == (0x20, 0x44, 0x1234, 0x5678, 0x9ABC, 0xF81A)
    assert [e[:2] for e in events] == [(0x2A,0x20),(0x2A,0x20),(0x2A,0x21),(0x2A,0x20),(0x2A,0x20)]
    assert events[2][2] - events[3][2] == 20095
    assert mem[0xF78B] == 0x20
    release = v4.HERE / 'releases/stock-context-v4/micron1_stock_context_v4.bin'
    assert release.read_bytes() == image
    allowed = set(range(v4.v3.CODE_ORG, v4.v3.CODE_END + 1))
    for addr, data in [*v4.si.WARMSTART_JUMPS, (0x3708, b'xx'),
                       (0x0252, b'xxxxx'), (0x2FC1, b'xxx')]:
        allowed.update(range(addr, addr + len(data)))
    assert {i for i, (a,b) in enumerate(zip(image, stock)) if a != b} <= allowed


@pytest.mark.parametrize('state,target', [(0, 0x1758), (1, 0x9000), (2, 0x1758)])
def test_copied_nmi_keeps_suspend_and_ignore_semantics(state, target):
    image, _, _ = v4.build_image()
    cpu, mem = _machine(image)
    mem[0xF180:0xF180 + 0x50D] = image[0x369D:0x369D + 0x50D]
    mem[0xFBD5] = state
    mem[0xF81A:0xF81C] = bytes.fromhex('0090')
    cpu.set_input_callback(lambda p: 0)
    cpu.set_output_callback(lambda p,v: None)
    cpu.sp = 0xF81A
    cpu.pc = 0xF5F6
    _run_to(cpu, target)


def test_bdos_zero_dispatches_through_copied_table_to_cold_entry():
    image, _, _ = v4.build_image()
    cpu, mem = _machine(image)
    mem[0xF180:0xF180 + 0x50D] = image[0x369D:0x369D + 0x50D]
    outputs = []
    cpu.set_input_callback(lambda p: 0)
    cpu.set_output_callback(lambda p,v: outputs.append((p & 255, v)))
    cpu.pc = 0xF183
    cpu.sp = 0xF81A
    cpu.c = 0
    _run_to(cpu, 0x01A6)
    assert (0x47, 0) in outputs
