"""Tests for the stock-ROM measurement hook (stock_instrument.py).

The hook is exercised in isolation: start at the patched stock bit6 wait
(0x32F0), let it run into the patched error path (0x3356 -> show), and check
the accumulators and the LCD writes.
"""
import importlib.util
import pathlib
import sys

import pytest

try:
    import z80
except ImportError:  # pragma: no cover - system pytest lacks the emulator
    z80 = None

ANALYSIS = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(ANALYSIS))

_SPEC = importlib.util.spec_from_file_location(
    "stockinstr", ANALYSIS / "rom_exerciser" / "stock_instrument.py")
si = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(si)


def _run(status4b, start_pc=0x32F0, break_label="show_loop", hl=0x1234):
    image, sym, _ = si.build_image()
    mem = bytearray([0x00] * 0x10000)
    mem[:0x8000] = image
    writes = []
    reads = []

    def inp(port):
        port &= 0xFF
        if port == 0x4B:
            return status4b() if callable(status4b) else status4b
        return 0

    def outp(port, value):
        writes.append((port & 0xFF, value & 0xFF))

    m = z80.Z80Machine()
    m.set_memory_block(0, bytes(mem))
    def read_mem(a):
        a &= 0xFFFF
        reads.append(a)
        return mem[a]

    m.set_read_callback(read_mem)
    m.set_write_callback(lambda a, v: mem.__setitem__(a & 0xFFFF, v & 0xFF))
    m.set_input_callback(inp)
    m.set_output_callback(outp)
    m.sp = 0xF000
    m.pc = start_pc
    m.hl = hl
    m.set_breakpoint(sym[break_label])
    for _ in range(4000):
        m.ticks_to_stop = 50000
        m.run()
        if m.pc == sym[break_label]:
            break
    assert m.pc == sym[break_label], f"never reached {break_label}"
    return m, mem, sym, writes


def test_patched_bytes_relocate_the_stock_poll_and_jump_to_show():
    image, sym, orig = si.build_image()
    # 32F0: JP hook6 + NOP pad; 3300: stock LD A,B / JR Z.
    assert image[0x32F0:0x32F3] == bytes([0xC3]) + sym["hook6"].to_bytes(2, "little")
    assert image[0x32F3:0x3300] == bytes(13)
    assert image[0x3300:0x3302] == bytes.fromhex("78 28")   # LD A,B / JR Z
    # The relocated poll is exactly the guarded stock bytes.  Only its final
    # branch target differs: it enters the post-decision snapshot instead of
    # falling straight through to 3300.
    assert image[sym["hook6"]:sym["h6_done"]] == orig[0x32F0:0x3300]
    assert image[0x3356:0x3359] == bytes([0xC3]) + sym["show"].to_bytes(2, "little")
    # hook code went into the free gap, not over the stock boot
    assert sym["hook6"] >= 0x7E96
    assert image[0x250:0x2FE] == orig[0x250:0x2FE]


def test_hook6_snapshots_status_and_stock_timeout_flags():
    m, mem, sym, writes = _run(0xC0)              # TXRDY + bit6 set
    assert mem[0xC7E0] == 0xC0                    # final LINK_STATUS
    assert mem[0xC7E1] & 0x41 == 0x40             # Z set, carry clear
    dat = [v for p, v in writes if p == 0x03]
    for ch in (0x4F, 0x46, 0x42, 0x31):           # 'O','F','B','1'
        assert ch in dat
    assert m.hl == 0x1234                         # HL preserved


def test_hook6_returns_nz_and_does_not_reach_show_when_bit6_clears():
    # 0x80: bit6 clear -> hook6 exits at once; stock falls through to 0x3303.
    m, mem, sym, writes = _run(0x80, break_label="h6_done")
    # run on a little to confirm it does NOT take the error path
    m.clear_breakpoint(sym["h6_done"])
    m.set_breakpoint(0x3303)
    for _ in range(200):
        m.ticks_to_stop = 50000
        m.run()
        if m.pc == 0x3303:
            break
    assert m.pc == 0x3303, "bit6 clear should fall through to the stock payload path"
    assert mem[0xC7E0] == 0x80
    assert not (mem[0xC7E1] & 0x41)               # stock success is NZ, NC


def test_hook6_obeys_the_stock_620_sample_boundary():
    calls = [0]

    def clear_on_last_stock_sample():
        calls[0] += 1
        return 0x80 if calls[0] == 620 else 0xC0

    m, mem, sym, writes = _run(clear_on_last_stock_sample,
                                break_label="h6_done")
    assert calls[0] == 620
    assert m.b == 0x80

    calls = [0]

    def clear_one_sample_too_late():
        calls[0] += 1
        return 0x80 if calls[0] == 621 else 0xC0

    m, mem, sym, writes = _run(clear_one_sample_too_late)
    assert calls[0] == 620
    assert mem[0xC7E0] == 0xC0
    assert mem[0xC7E1] & 0x40


def _run_rx(status4b, rxd):
    image, sym, _ = si.build_image("rx")
    mem = bytearray([0x00] * 0x10000)
    mem[:0x8000] = image
    writes = []

    def inp(port):
        port &= 0xFF
        if port == 0x4B:
            return status4b
        if port == 0x4E:
            return rxd
        return 0

    def outp(port, value):
        writes.append((port & 0xFF, value & 0xFF))

    m = z80.Z80Machine()
    m.set_memory_block(0, bytes(mem))
    m.set_read_callback(lambda a: mem[a & 0xFFFF])
    m.set_write_callback(lambda a, v: mem.__setitem__(a & 0xFFFF, v & 0xFF))
    m.set_input_callback(inp)
    m.set_output_callback(outp)
    m.sp = 0xF000
    m.pc = sym["hook_rx"]
    m.set_breakpoint(sym["rx_loop"])
    for _ in range(200):
        m.ticks_to_stop = 50000
        m.run()
        if m.pc == sym["rx_loop"]:
            break
    assert m.pc == sym["rx_loop"], "rx hook never halted"
    return m.memory, sym, writes


def test_rx_hook_patches_dispatcher_entry():
    image, sym, orig = si.build_image("rx")
    assert sym["hook_rx"] >= 0x7E96
    # 2FBD stock LD HL,(FDDC) -> JP hook_rx
    assert image[0x2FBD:0x2FC0] == bytes([0xC3]) + sym["hook_rx"].to_bytes(2, "little")
    # only the entry is patched; the rest of the dispatcher is stock
    assert image[0x2FC0:0x3065] == orig[0x2FC0:0x3065]


@pytest.mark.parametrize("start", [0x019E, 0x3812])
def test_rx_hook_force_coldstart_reaches_cold_body(start):
    image, _, orig = si.build_image("rx", force_coldstart=True)
    m = z80.Z80Machine()
    m.set_memory_block(0, image)
    m.memory[0xF81C] = 0x55       # stock reset would take the warm branch
    m.sp = 0xF000
    m.pc = start
    m.set_breakpoint(0x01A6)
    m.ticks_to_stop = 1000
    m.run()
    assert m.pc == 0x01A6
    assert image[0x2FBD:0x2FC0] == bytes([0xC3, 0xC5, 0x7E])
    assert orig[0x01A3:0x01A6] == bytes.fromhex("ca 4d 02")
    assert orig[0x3812:0x3815] == bytes.fromhex("c3 4d 02")


def test_rx_hook_force_coldstart_from_reset_vector():
    image, _, _ = si.build_image("rx", force_coldstart=True)
    m = z80.Z80Machine()
    m.set_memory_block(0, image)
    m.memory[0xF81C] = 0x55
    m.set_input_callback(lambda port: 0)
    m.set_output_callback(lambda port, value: None)
    m.sp = 0xF000
    m.pc = 0x0000
    m.set_breakpoint(0x01A6)
    for _ in range(20):
        m.ticks_to_stop = 100000
        m.run()
        if m.pc == 0x01A6:
            break
    assert m.pc == 0x01A6


def test_rx_hook_captures_status_and_byte():
    mem, sym, writes = _run_rx(0x13, 0x03)   # bit4 set, bit0 (byte ready) set
    assert mem[0xC7E0] == 0x13
    assert mem[0xC7E1] == 0x03
    dat = [v for p, v in writes if p == 0x03]
    assert 0x49 in dat                        # 'I'
    assert 0x31 in dat and 0x33 in dat        # hex digits of 13 and 03


def test_rx_hook_skips_rxd_without_byte_ready():
    mem, sym, writes = _run_rx(0x10, 0x55)   # bit0 clear -> RXD not read
    assert mem[0xC7E0] == 0x10
    assert mem[0xC7E1] == 0x00


def _run_rxb(status4b, rxd_seq):
    image, sym, _ = si.build_image("rxb")
    mem = bytearray([0x00] * 0x10000)
    mem[:0x8000] = image
    writes = []
    seq = list(rxd_seq)
    idx = [0]

    def inp(port):
        port &= 0xFF
        if port == 0x4B:
            return status4b
        if port == 0x4E:
            v = seq[idx[0]] if idx[0] < len(seq) else 0
            idx[0] += 1
            return v
        return 0

    def outp(port, value):
        writes.append((port & 0xFF, value & 0xFF))

    m = z80.Z80Machine()
    m.set_memory_block(0, bytes(mem))
    m.set_read_callback(lambda a: mem[a & 0xFFFF])
    m.set_write_callback(lambda a, v: mem.__setitem__(a & 0xFFFF, v & 0xFF))
    m.set_input_callback(inp)
    m.set_output_callback(outp)
    m.sp = 0xF000
    m.pc = sym["hook_rxb"]
    m.set_breakpoint(sym["rxb_halt"])
    for _ in range(3000):
        m.ticks_to_stop = 50000
        m.run()
        if m.pc == sym["rxb_halt"]:
            break
    assert m.pc == sym["rxb_halt"], "rxb hook never halted"
    return mem, sym, writes


def test_rxb_hook_patches_dispatcher_entry():
    image, sym, orig = si.build_image("rxb")
    assert sym["hook_rxb"] >= 0x7E96
    assert image[0x2FBD:0x2FC0] == bytes([0xC3]) + sym["hook_rxb"].to_bytes(2, "little")
    assert image[0x2FC0:0x3065] == orig[0x2FC0:0x3065]


def test_rxb_hook_captures_bytes():
    mem, sym, writes = _run_rxb(0x31, [0xAA, 0xBB, 0xCC])   # bit4 + bit0 set
    assert mem[0xC7E0] == 0x31
    assert mem[0xC7E1] == 3
    assert mem[0xC7E2] == 0xAA
    assert mem[0xC7E3] == 0xBB
    assert mem[0xC7E4] == 0xCC


def test_rxb_hook_reports_no_byte_on_timeout():
    mem, sym, writes = _run_rxb(0x10, [])                   # bit0 never sets
    assert mem[0xC7E0] == 0x10
    assert mem[0xC7E1] == 0


def _run_rxb2(ctrl_shadow, descriptor, payload, terminal_status=0x02,
              destination=0x9000, initial=b"\xD1\xD2\xD3"):
    """Run rxb2 against one descriptor and a controller-byte sequence.

    The first LINK_RXD read is the stock arm's dummy read.  `payload` is what
    follows it; status bit 1 ends the block before the descriptor limit.
    """
    image, sym, _ = si.build_image("rxb2")
    mem = bytearray([0x00] * 0x10000)
    mem[:0x8000] = image
    mem[0xF794] = ctrl_shadow
    mem[0xFDDC:0xFDDE] = (0x8000).to_bytes(2, "little")
    mem[0x8000:0x8000 + len(descriptor)] = descriptor
    mem[destination:destination + len(initial)] = initial
    writes = []
    reads = []
    chars = []
    lcd_reg = [None]
    payload = list(payload)
    rxd_reads = [0]

    def inp(port):
        port &= 0xFF
        if port == 0x4E:
            rxd_reads[0] += 1
            return 0 if rxd_reads[0] == 1 else (payload.pop(0) if payload else 0)
        if port == 0x4B:
            return 0x01 if payload else terminal_status
        return 0

    def outp(port, value):
        writes.append((port & 0xFF, value & 0xFF))
        if (port & 0xFF) == 0x23:
            lcd_reg[0] = value & 0xFF
        elif (port & 0xFF) == 0x03 and lcd_reg[0] == 0x0C:
            chars.append(value & 0xFF)

    m = z80.Z80Machine()
    m.set_memory_block(0, bytes(mem))
    def read_mem(a):
        a &= 0xFFFF
        reads.append(a)
        return mem[a]

    m.set_read_callback(read_mem)
    m.set_write_callback(lambda a, v: mem.__setitem__(a & 0xFFFF, v & 0xFF))
    m.set_input_callback(inp)
    m.set_output_callback(outp)
    m.sp = 0xF000
    m.pc = sym["hook_rxb2"]
    m.set_breakpoint(sym["rxb2_halt"])
    for _ in range(4000):
        m.ticks_to_stop = 50000
        m.run()
        if m.pc == sym["rxb2_halt"]:
            break
    assert m.pc == sym["rxb2_halt"], "rxb2 hook never halted"
    return mem, sym, writes, bytes(chars), reads


def test_rxb2_hook_uses_descriptor_destination_and_success_count():
    image, sym, orig = si.build_image("rxb2")
    assert sym["hook_rxb2"] >= 0x7E96
    assert image[0x2FBD:0x2FC0] == bytes([0xC3]) + sym["hook_rxb2"].to_bytes(2, "little")
    # Descriptor is {max 10, destination 9000, terminator}; the actual frame
    # has six bytes, so status bit 1 ends it before the descriptor limit.
    mem, sym, writes, chars, reads = _run_rxb2(
        0x10, bytes.fromhex("0A 00 00 90 00 00"),
        bytes.fromhex("11 22 33 44 55 66"))
    assert mem[0xC7E0] == 0x00                # Link_BlockRx return A
    assert not (mem[0xC7E2] & 0x01)           # carry clear
    assert mem[0xC7E3:0xC7E5] == bytes.fromhex("06 00")
    assert mem[0xC7E5:0xC7E8] == bytes.fromhex("11 22 33")
    assert mem[0x9000:0x9006] == bytes.fromhex("11 22 33 44 55 66")
    assert chars.endswith(b"0006112233")


def test_rxb2_error_marks_count_unavailable_and_never_renders_stale_bytes():
    # The descriptor and destination differ deliberately.  bit 3 causes the
    # stock reader's EC error return without accepting payload bytes.
    mem, sym, writes, chars, reads = _run_rxb2(
        0x10, bytes.fromhex("06 00 00 90 00 00"), b"", terminal_status=0x0A,
        initial=bytes.fromhex("DE AD BE"))
    assert mem[0xC7E0] == 0xEC
    assert mem[0xC7E2] & 0x01                 # raw carry diagnoses error
    assert mem[0xC7E3:0xC7E5] == bytes.fromhex("FF FF")
    assert mem[0x9000:0x9003] == bytes.fromhex("DE AD BE")
    assert chars.endswith(b"FFFF------")
    assert b"DEADBE" not in chars


def test_rxb2_preview_is_bounded_by_the_first_descriptor_not_total_count():
    # A chained descriptor accepts six controller bytes in total, but its first
    # destination is one byte long.  The diagnostic may report total count 6,
    # yet it must render only that first byte, never bytes beyond 9000h.
    mem, sym, writes, chars, reads = _run_rxb2(
        0x10, bytes.fromhex("01 00 00 90 0A 00 00 91 00 00"),
        bytes.fromhex("11 22 33 44 55 66"))
    assert mem[0xC7E3:0xC7E5] == bytes.fromhex("06 00")
    assert mem[0xC7E8:0xC7EA] == bytes.fromhex("01 00")
    assert mem[0x9000] == 0x11
    assert mem[0x9100:0x9105] == bytes.fromhex("22 33 44 55 66")
    assert chars.endswith(b"000611----")
    assert 0x9001 not in reads
    assert 0x9002 not in reads
