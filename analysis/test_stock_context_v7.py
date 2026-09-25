"""Release gates for the post-sample terminal-byte/descriptor diagnostic."""
import hashlib
import json
import pathlib
import sys

import pytest

sys.path.insert(0, str(pathlib.Path(__file__).parent / "rom_exerciser"))
import stock_context_v6 as v6
import stock_context_v7 as v7
from test_stock_context_v3 import _machine
from test_stock_context_v6 import _lcd_text


def _run(image, symbols, statuses, descriptor=bytes.fromhex("0a0000900000"),
         data=b"\xA5", *, stop=None, scratch_seed=0xCC):
    cpu, mem = _machine(image)
    mem[0xF794], mem[0xF78B] = 0x10, 0x20
    mem[0xFDDC:0xFDDE] = bytes.fromhex("0080")
    mem[0x8000:0x8000 + len(descriptor)] = descriptor
    mem[0xC7E4:0xC7F3] = bytes([scratch_seed]) * 15
    events = []
    index = 0
    reads = 0

    def inp(port):
        nonlocal index, reads
        port &= 255
        value = 0
        if port == 0x4B:
            value = statuses[min(index, len(statuses) - 1)]
            index += 1
        elif port == 0x4E:
            # Setup read deliberately differs from all terminal byte fixtures.
            value = 0xD3 if reads == 0 else data[(reads - 1) % len(data)]
            reads += 1
        events.append(("in", port, value, 1_000_000 - cpu.ticks_to_stop))
        return value

    cpu.set_input_callback(inp)
    cpu.set_output_callback(lambda p, v: events.append(
        ("out", p & 255, v, 1_000_000 - cpu.ticks_to_stop)))
    cpu.pc, cpu.sp = 0x2FBD, 0xF81A
    target = symbols["stopped"] if stop is None else stop
    cpu.set_breakpoint(target)
    cpu.ticks_to_stop = 1_000_000
    for _ in range(100):
        cpu.run()
        if cpu.pc == target:
            break
        assert cpu.ticks_to_stop > 0
    cpu.clear_breakpoint(target)
    assert cpu.pc == target, f"PC={cpu.pc:04X}, wanted {target:04X}"
    return cpu, mem, events


def _registers(cpu):
    return (cpu.a, cpu.f, cpu.bc, cpu.de, cpu.hl, cpu.ix, cpu.iy, cpu.sp)


def test_guarded_patch_scope_and_unchanged_boot_and_presample_wrapper():
    image, symbols, stock = v7.build_image()
    old, old_symbols, _ = v6.build_image()
    allowed = set(range(v7.v3.CODE_ORG, v7.v3.CODE_END + 1))
    for address, original in ((v7.v3.RX_CALL_SITE, v7.v3.RX_CALL_BYTES),
                              (v7.v3.INIT_SITE, v7.v3.INIT_BYTES),
                              (v7.STATUS_HOOK_SITE, v7.STATUS_HOOK_BYTES)):
        assert stock[address:address + len(original)] == original
        allowed.update(range(address, address + len(original)))
    assert {i for i, (a, b) in enumerate(zip(stock, image)) if a != b} <= allowed
    assert symbols["end"] <= v7.v3.CODE_END + 1
    assert image[v7.v3.CODE_ORG:symbols["show_result"]] == old[
        v7.v3.CODE_ORG:old_symbols["show_result"]]
    for address, original in v7.v5.RESET_SITES:
        assert image[address:address + len(original)] == original


@pytest.mark.parametrize("statuses", [[0xCA], [0x8E], [1, 1, 0x8E], [0x02], [1, 1, 0x02]])
def test_identical_io_cycles_and_registers_through_terminal_sample(statuses):
    old, old_symbols, _ = v6.build_image()
    new, symbols, _ = v7.build_image()
    a, am, ae = _run(old, old_symbols, statuses, stop=v7.STATUS_HOOK_SITE)
    b, bm, be = _run(new, symbols, statuses, stop=v7.STATUS_HOOK_SITE)
    assert ae == be  # Includes every I/O value and its cycle timestamp.
    assert _registers(a) == _registers(b)
    assert am[0x9000:0x9010] == bm[0x9000:0x9010]


@pytest.mark.parametrize("statuses", [[0xCA], [0x8E], [1, 1, 0x8E], [0x02], [1, 1, 0x02], [0]])
def test_stock_return_registers_and_all_link_io_preserved(statuses):
    old, old_symbols, _ = v6.build_image()
    new, symbols, _ = v7.build_image()
    stop = symbols["rx_wrapper"] + 6  # Immediately after stock CALL returns.
    a, am, ae = _run(old, old_symbols, statuses, stop=stop)
    b, bm, be = _run(new, symbols, statuses, stop=stop)
    assert _registers(a) == _registers(b)
    assert [e[:3] for e in ae] == [e[:3] for e in be]
    assert am[0x9000:0x9010] == bm[0x9000:0x9010]


@pytest.mark.parametrize("statuses,delta,low", [
    ([0xCA], 109, 3383), ([0x8E], 136, 3383),
    ([0x02], 109, 3383), ([1, 1, 0x02], 109, 6739), ([0], 0, 3383),
])
def test_postdecision_delay_is_bounded_and_marker_width_unchanged(statuses, delta, low):
    yellow = []
    for module in (v6, v7):
        image, symbols, _ = module.build_image()
        _, _, events = _run(image, symbols, statuses)
        yellow.append([e for e in events if e[:2] == ("out", 0x2A)])
    assert [e[:3] for e in yellow[0]] == [e[:3] for e in yellow[1]]
    assert yellow[1][0][3] - yellow[0][0][3] == delta
    for events in yellow:
        assert [events[i + 1][3] - events[i][3] for i in range(3)] == [1719, low, 1701]


@pytest.mark.parametrize("value", [0x00, 0x7E, 0x81, 0xFF])
def test_terminal_byte_and_descriptor_readout(value):
    image, symbols, _ = v7.build_image()
    _, mem, events = _run(image, symbols, [0x8E], data=bytes([value]))
    text = _lcd_text(events)
    assert len(text) == 40
    assert text[:20] == f"R7IEC2D:8E{value:02X}0A000090"
    assert text[20:] == "X0080019000000A0009 "
    decoded = v7.decode_readout(text[:20] + "\n" + text[20:])
    record = decoded["terminal_record"]
    assert record["terminal_byte"] == f"{value:02X}"
    assert record["terminal_byte_valid"]
    assert record["descriptor_address"] == "8000"
    assert record["descriptor_length"] == 10
    assert record["buffer_address"] == "9000"
    assert record["next_write_address"] == "9001"
    assert record["active_descriptor_pointer_advance_mod65536"] == 1
    assert len([e for e in events if e[:2] == ("in", 0x4E)]) == 2
    assert mem[0x9000] == value


def test_no_terminal_ini_does_not_read_stale_buffer_byte():
    image, symbols, _ = v7.build_image()
    _, _, events = _run(image, symbols, [0xCA], scratch_seed=0xA5)
    record = v7.decode_readout(_lcd_text(events))["terminal_record"]
    assert record["terminal_byte"] is None
    assert not record["terminal_byte_valid"]
    assert record["next_write_address"] == "9000"
    assert len([e for e in events if e[:2] == ("in", 0x4E)]) == 1


def test_active_descriptor_is_not_the_chain_head():
    image, symbols, _ = v7.build_image()
    chain = bytes.fromhex("03000090 05001090 00000000")
    _, _, events = _run(image, symbols, [1, 1, 1, 0x8E], descriptor=chain,
                        data=bytes.fromhex("1122337E"))
    record = v7.decode_readout(_lcd_text(events))["terminal_record"]
    assert record["descriptor_address"] == "8004"
    assert record["descriptor_length"] == 5
    assert record["buffer_address"] == "9010"
    assert record["next_write_address"] == "9011"
    assert record["total_requested_through_active_descriptor"] == 8
    assert record["terminal_byte"] == "7E"


@pytest.mark.parametrize("status,expected_write,residual,valid", [
    (0xCA, "9000", "00", False), (0x8E, "9001", "FF", True)])
def test_256_byte_descriptor_ambiguity_exposed(status, expected_write, residual, valid):
    image, symbols, _ = v7.build_image()
    _, _, events = _run(image, symbols, [status],
                        descriptor=bytes.fromhex("00010090 00000000"))
    record = v7.decode_readout(_lcd_text(events))["terminal_record"]
    assert record["descriptor_length"] == 256
    assert record["next_write_address"] == expected_write
    assert record["residual_b"] == residual
    assert record["terminal_byte_valid"] == valid
    assert record["saved_bc"] == "0000"


@pytest.mark.parametrize("statuses,descriptor,prefix", [
    ([0], bytes.fromhex("0a0000900000"), "R7IEE"),
    ([0xCA], bytes.fromhex("000000900000"), "R7IED"),
    ([1, 1, 0x02], bytes.fromhex("0a0000900000"), "R7I00"),
])
def test_non_ec_readouts_do_not_publish_stale_terminal_snapshot(statuses, descriptor, prefix):
    image, symbols, _ = v7.build_image()
    _, _, events = _run(image, symbols, statuses, descriptor=descriptor)
    text = _lcd_text(events)
    assert text.startswith(prefix)
    assert len(text) == 7
    assert v7.decode_readout(text)["terminal_record"] is None


def test_wrong_stock_or_terminal_patch_and_cave_are_rejected(tmp_path, monkeypatch):
    stock = bytearray(v7.v3.DEFAULT_ROM.read_bytes())
    path = tmp_path / "bad.bin"
    for address, message in ((0x1234, "verified stock"),
                             (v7.STATUS_HOOK_SITE, "terminal-status"),
                             (v7.v3.CODE_END, "cave")):
        bad = stock.copy()
        bad[address] ^= 1
        path.write_bytes(bad)
        with monkeypatch.context() as patch:
            if address != 0x1234:
                patch.setattr(v7.v3, "STOCK_SHA256", hashlib.sha256(bad).hexdigest())
            with pytest.raises(ValueError, match=message):
                v7.build_image(path)


@pytest.mark.parametrize("text", ["R7IECA9", "R7IEE6D:8E000A000090X0080019000000A0009", "R6IEC29SCAN0000"])
def test_decoder_rejects_incomplete_or_mismatched_rows(text):
    with pytest.raises(ValueError):
        v7.decode_readout(text)


def test_release_reproduces_builder_and_manifest():
    image, symbols, _ = v7.build_image()
    release = v7.v3.HERE / "releases/stock-context-v7/micron1_stock_context_v7.bin"
    assert release.read_bytes() == image
    manifest = json.loads(release.with_suffix(".json").read_text())
    assert manifest["checksums"] == v7.v3.fingerprint(image)
    assert manifest["symbols"] == symbols
    assert manifest["assembly_sha256"] == hashlib.sha256(v7.HOOK_SOURCE.encode("ascii")).hexdigest()


def test_cli_does_not_overwrite_source(tmp_path):
    source = tmp_path / "source.bin"
    source.write_bytes(v7.v3.DEFAULT_ROM.read_bytes())
    with pytest.raises(SystemExit):
        v7.main(["--rom", str(source), "-o", str(source)])
    assert source.read_bytes() == v7.v3.DEFAULT_ROM.read_bytes()
    with pytest.raises(SystemExit):
        v7.main(["-o", str(tmp_path / "collision.json")])
