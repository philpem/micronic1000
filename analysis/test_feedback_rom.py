"""Host checks for the standalone combined IR feedback ROM.

These tests exercise the ROM's boot, black command guard, stock-order
witness, and the bounded raw Link_BlockRx wrapper.  They deliberately do not
interpret controller status as a received or accepted protocol frame.
"""
from pathlib import Path
import hashlib
import json
import sys

import pytest

try:
    import z80
except ImportError:  # pragma: no cover - test environment supplies pyz80
    z80 = None

pytestmark = pytest.mark.skipif(z80 is None, reason="pyz80 is unavailable")

ANALYSIS = Path(__file__).resolve().parent
sys.path.insert(0, str(ANALYSIS))
from rom_exerciser import feedback


def test_release_manifest_matches_fresh_build_without_local_binary():
    path = ANALYSIS / "rom_exerciser/releases/feedback-v1/micron1_feedback_v1.json"
    image, symbols, original = feedback.build_image()
    expected = json.loads(path.read_text())
    assert feedback.manifest(image, symbols, original, expected["image"]) == expected


class Probe:
    def __init__(self, dirty=0xA5, edge=lambda: 0xFF, status=lambda: 0,
                 rxd=lambda: 0):
        self.image, self.sym, _ = feedback.build_image()
        self.mem = bytearray([dirty] * 65536)
        self.mem[:32768] = self.image
        self.cpu = z80.Z80Machine()
        self.cpu.set_memory_block(0, bytes(self.mem))
        self.cpu.set_read_callback(lambda a: self.mem[a & 0xffff])
        self.cpu.set_write_callback(lambda a, v: self.mem.__setitem__(a & 0xffff, v & 255))
        self.edge, self.status, self.rxd = edge, status, rxd
        self.writes = []
        self.drive = 0
        self.lcd_reg = 0
        self.cursor = 0
        self.screen = bytearray(b" " * 256)
        self.cpu.set_input_callback(self.read_port)
        self.cpu.set_output_callback(self.write_port)
        self.cpu.pc = feedback.BOOT

    def read_port(self, port):
        port &= 255
        if port == 0x2D:
            return self.edge() & 255
        if port == 0x4B:
            return self.status() & 255
        if port == 0x4E:
            return self.rxd() & 255
        return 0

    def write_port(self, port, value):
        port, value = port & 255, value & 255
        self.writes.append((port, value))
        if port == 2:
            self.drive = value
        elif port == 0x23:
            self.lcd_reg = value
        elif port == 3:
            if self.lcd_reg == 0x0A:
                self.cursor = (self.cursor & 0xff00) | value
            elif self.lcd_reg == 0x0B:
                self.cursor = (self.cursor & 0xff) | (value << 8)
            elif self.lcd_reg == 0x0C:
                if self.cursor < len(self.screen):
                    self.screen[self.cursor] = value
                self.cursor = (self.cursor + 1) & 0xffff

    def run_to(self, name, chunks=500):
        addr = self.sym[name]
        self.cpu.set_breakpoint(addr)
        for _ in range(chunks):
            self.cpu.ticks_to_stop = 100000
            self.cpu.run()
            if self.cpu.pc == addr:
                break
        self.cpu.clear_breakpoint(addr)
        assert self.cpu.pc == addr, f"never reached {name}: {self.cpu.pc:04x}"

    def call(self, name, a=None, chunks=500):
        if a is not None:
            self.cpu.a = a
        self.cpu.sp = 0xC8FE
        self.mem[0xC8FE:0xC900] = b"\x00\x80"
        self.cpu.pc = self.sym[name]
        self.cpu.set_breakpoint(0x8000)
        for _ in range(chunks):
            self.cpu.ticks_to_stop = 100000
            self.cpu.run()
            if self.cpu.pc == 0x8000:
                break
        self.cpu.clear_breakpoint(0x8000)
        assert self.cpu.pc == 0x8000, f"{name} did not return: {self.cpu.pc:04x}"

    def value(self, name):
        return self.mem[self.sym[name]]


def sequence(values, fallback=0xFF):
    values = list(values)
    return lambda: values.pop(0) if values else fallback


def test_image_is_guarded_and_changes_only_boot_and_private_program(tmp_path):
    image, sym, original = feedback.build_image()
    assert sym["start"] == feedback.ORIGIN
    assert sym["end"] <= feedback.LIMIT
    changed = [i for i, (a, b) in enumerate(zip(image, original)) if a != b]
    assert all(feedback.BOOT <= i < feedback.BOOT + 3 or
               feedback.ORIGIN <= i < sym["end"] for i in changed)
    bad = bytearray(original)
    bad[0x3378] ^= 1
    path = tmp_path / "bad.bin"
    path.write_bytes(bad)
    with pytest.raises(ValueError, match="verified stock"):
        feedback.build_image(path)
    assert feedback.fingerprint(image)["md5"] == hashlib.md5(image).hexdigest()


@pytest.mark.parametrize("dirty", [0, 0xA5, 0xFF])
def test_boot_initialises_poisoned_ram_nmi_and_quiet_idle_gate(dirty):
    p = Probe(dirty)
    p.run_to("idle")
    assert p.mem[0xF5F6:0xF5F8] == b"\xed\x45"
    assert p.value("S_MODE") == p.value("S_ERR") == 0
    assert p.value("SHADOW2A") == 0x22       # yellow released, black gate on
    assert p.value("SHADOW2C") == 0x00       # black gate's bit5 is clear
    assert p.value("S_P4") == p.value("S_P6") == 0xFF
    assert (0x2A, 0x22) in p.writes and (0x2C, 0x00) in p.writes


@pytest.mark.parametrize("ticks,expected", [(14, 0), (15, 1), (30, 1),
                                               (31, 0), (50, 2), (70, 2),
                                               (71, 0), (90, 3), (110, 3),
                                               (111, 0), (130, 4), (150, 4),
                                               (151, 0)])
def test_command_windows_are_inclusive_and_disjoint(ticks, expected):
    p = Probe()
    p.run_to("idle")
    p.mem[p.sym["S_TICKS"]] = ticks
    p.call("classify_command")
    assert p.value("S_MODE") == expected


def test_invalid_black_pulse_acks_then_reports_width_error_without_start_guard():
    # Five low samples then release is outside every accepted window.  The
    # routine's final port state proves it restored the input gate before UART.
    p = Probe(edge=sequence([0] * 5 + [1] * 1000))
    p.run_to("command_begin", chunks=30)
    p.run_to("command_error", chunks=500)
    # ACK is a yellow sink.  The malformed pulse reaches the error path before
    # any stock-link output, so it cannot have emitted a START/IR trial.
    assert p.value("S_MODE") == 0
    yellow = [v for port, v in p.writes if port == 0x2A]
    assert 0x23 in yellow
    assert not [x for x in p.writes if x[0] in (0x4A, 0x4C, 0x4D)]


def test_stuck_black_low_aborts_and_refuses_to_rearm_until_release():
    edge_values = [0] * 161 + [1] * 1000
    p = Probe(edge=sequence(edge_values))
    p.run_to("command_begin", chunks=30)
    p.run_to("command_error", chunks=1000)
    assert p.cpu.a == 2                    # E_STUCK is passed into handler
    assert not [x for x in p.writes if x[0] in (0x4A, 0x4C, 0x4D)]


def test_witness_keeps_stock_open_poll_arm_and_teardown_order():
    # LinkPresent first needs status bit4 set; both stock clear polls then see
    # it clear.  This checks the observed mechanical sequence only.
    # Bit7 satisfies both stock ready calls; bits4/6 remain clear through the
    # two copied stock polls.
    p = Probe(status=lambda: 0x80)
    p.run_to("idle")
    p.call("reset_trial")
    p.writes.clear()
    p.call("run_witness", chunks=1000)
    assert p.value("S_ERR") == 0
    assert p.value("S_P4") == 0x10
    assert p.value("S_P6") == 0x40
    assert p.value("S_ARM") == 1
    ctrl = [v for port, v in p.writes if port == 0x4A]
    assert 0x23 in ctrl and 0x33 in ctrl and 0x13 in ctrl
    assert ctrl[-4:] == [0x03, 0x02, 0x42, 0xC2]
    assert [v for port, v in p.writes if port == 0x4D] == [0x03]
    assert [v for port, v in p.writes if port == 0x4C] == [0x81]


@pytest.mark.parametrize(
    ("status", "error", "p4", "p6", "arm"),
    [
        # Bit 4 remains set: stock_wait_p4 expires before arming, so the
        # second poll must not run.
        (0x90, 5, 0x00, 0xFF, 0),
        # Bit 4 clears but bit 6 remains set: the arm happens, then the
        # copied stock bit-6 wait expires.
        (0xC0, 6, 0x10, 0x00, 1),
    ],
)
def test_witness_stock_poll_timeouts_preserve_their_distinct_state(status, error,
                                                                    p4, p6, arm):
    p = Probe(status=lambda: status)
    p.run_to("idle")
    p.call("reset_trial")
    p.call("run_witness", chunks=3000)
    assert p.value("S_ERR") == error
    assert p.value("S_P4") == p4 and p.value("S_P6") == p6
    assert p.value("S_ARM") == arm


def test_witness_ready_timeout_skips_the_stock_polls_and_arm():
    # LinkPresent never sees its ready condition.  This must be E_READY, not
    # an invented poll failure, and no stock poll/arm side effect may follow.
    p = Probe(status=lambda: 0)
    p.run_to("idle")
    p.call("reset_trial")
    p.call("run_witness", chunks=3000)
    assert p.value("S_ERR") == 4
    assert p.value("S_P4") == p.value("S_P6") == 0xFF
    assert p.value("S_ARM") == 0


def test_pending_mode_times_out_without_calling_stock_rx():
    # G waits for LINK_STATUS bit 4 after reset/select.  A clear bit over the
    # whole 100-ms bound creates only E_PENDING; stale RX fields stay reset.
    rx_reads = []
    p = Probe(status=lambda: 0, rxd=lambda: rx_reads.append(1) or 0)
    p.run_to("idle")
    p.call("reset_trial")
    p.call("run_pending_rx", chunks=3000)
    assert p.value("S_ERR") == 8
    assert p.value("S_RXA") == p.value("S_RXF") == 0
    assert p.value("S_RXL") == p.value("S_RXH") == p.value("S_PREVLEN") == 0
    assert not rx_reads


def test_pending_mode_enters_the_bounded_stock_rx_on_bit4_pending():
    payload = [0x11, 0x22, 0x33, 0x44, 0x55, 0x66]
    reads = [0]

    def rxd():
        reads[0] += 1
        return 0 if reads[0] == 1 else (payload.pop(0) if payload else 0)

    # Bit 4 is asserted for G's pending test.  The remaining status bits use
    # the same terminal sequence as the ordinary bounded RX exercise.
    p = Probe(status=lambda: 0x91 if payload else 0x92, rxd=rxd)
    p.run_to("idle")
    p.call("reset_trial")
    p.call("run_pending_rx", chunks=3000)
    assert p.value("S_ERR") == 0
    assert (p.value("S_RXL"), p.value("S_RXH")) == (4, 0)
    assert p.value("S_PREVLEN") == 4
    assert p.mem[p.sym["S_PREVIEW"]:p.sym["S_PREVIEW"] + 4] == bytes.fromhex("11 22 33 44")


def test_keypad_trial_requires_the_same_six_released_black_samples():
    p = Probe(edge=lambda: 0)
    p.run_to("idle")
    # A physical black low prevents a keypad W from reaching START/IR.
    p.cpu.a = 1
    p.cpu.sp = 0xC8FE
    p.mem[0xC8FE:0xC900] = b"\x00\x80"
    p.cpu.pc = p.sym["manual_trial"]
    p.run_to("manual_blocked", chunks=50)
    assert p.value("S_MODE") == 1
    assert not [x for x in p.writes if x[0] in (0x4A, 0x4C, 0x4D)]


def test_raw_rx_records_only_bounded_descriptor_bytes_and_raw_error():
    payload = [0x11, 0x22, 0x33, 0x44, 0x55, 0x66]
    rxd_reads = [0]
    def rxd():
        rxd_reads[0] += 1
        return 0 if rxd_reads[0] == 1 else (payload.pop(0) if payload else 0)

    # LINK_STATUS bit 0 takes precedence over bit 1. Feed all six ordinary
    # bytes, then bit 1 terminal while room remains in the private descriptor.
    p = Probe(status=lambda: 0x81 if payload else 0x82, rxd=rxd)
    p.run_to("idle")
    p.call("reset_trial")
    p.call("run_rx", chunks=2000)
    assert p.value("S_ERR") == 0
    # Link_BlockRx's raw carry-clear DE is the stock return (six received
    # bytes less two), retained verbatim instead of being relabelled.
    assert p.value("S_RXL") == 4 and p.value("S_RXH") == 0
    assert p.value("S_PREVLEN") == 4
    assert p.mem[p.sym["S_PREVIEW"]:p.sym["S_PREVIEW"] + 4] == bytes.fromhex("11 22 33 44")

    # Controller bit3 forces the stock error exit.  Old RXBUF bytes cannot
    # become a preview and count remains the reset zero (not a made-up frame).
    p = Probe(status=lambda: 0x0A)
    p.run_to("idle")
    p.call("reset_trial")
    p.mem[p.sym["RXBUF"]:p.sym["RXBUF"] + 8] = b"stale!!!"
    p.call("run_rx", chunks=2000)
    assert p.value("S_ERR") == 7
    assert p.value("S_PREVLEN") == 0
    assert p.mem[p.sym["S_PREVIEW"]:p.sym["S_PREVIEW"] + 8] == bytes(8)


def test_raw_rx_accepts_full_terminal_private_descriptor_and_previews_eight():
    payload = list(range(134))
    reads = [0]
    def rxd():
        reads[0] += 1
        return 0 if reads[0] == 1 else (payload.pop(0) if payload else 0)
    # On the final byte bit0 is clear, bit1 is terminal and bit2 selects the
    # stock extra INI at 33F3.  This exercises the terminating full descriptor
    # instead of the ordinary byte-ready path that exhausts it with ED.
    p = Probe(status=lambda: 0x86 if len(payload) == 1 else
              (0x81 if payload else 0x82), rxd=rxd)
    p.run_to("idle")
    p.call("reset_trial")
    p.call("run_rx", chunks=3000)
    assert p.value("S_ERR") == 0
    assert (p.value("S_RXL"), p.value("S_RXH")) == (132, 0)
    assert p.value("S_PREVLEN") == 8
    assert p.mem[p.sym["S_PREVIEW"]:p.sym["S_PREVIEW"] + 8] == bytes(range(8))


def test_raw_rx_full_ordinary_ready_descriptor_reports_stock_ed_error():
    payload = list(range(134))
    reads = [0]
    def rxd():
        reads[0] += 1
        return 0 if reads[0] == 1 else (payload.pop(0) if payload else 0)
    p = Probe(status=lambda: 0x81 if payload else 0x82, rxd=rxd)
    p.run_to("idle")
    p.call("reset_trial")
    p.call("run_rx", chunks=3000)
    assert p.value("S_ERR") == 7
    assert p.value("S_RXA") == 0xED
    assert p.value("S_PREVLEN") == 0
    assert p.mem[p.sym["S_PREVIEW"]:p.sym["S_PREVIEW"] + 8] == bytes(8)


def test_result_is_exact_30_bytes_with_zero_sum_and_final_gate_fields():
    p = Probe()
    p.run_to("idle")
    p.call("reset_trial")
    p.mem[p.sym["S_MODE"]] = 2
    p.mem[p.sym["S_SEQLO"]:p.sym["S_SEQHI"] + 1] = b"\x34\x12"
    p.mem[p.sym["S_RXA"]] = 0xEC
    p.mem[p.sym["S_RXF"]] = 1
    p.mem[p.sym["S_RAW2D"]] = 0x23  # obsolete command-time reading
    p.call("restore_gate")
    p.edge = lambda: 0x22  # changed after the command; sample restored gate
    p.call("make_result")
    record = bytes(p.mem[p.sym["RESULT"]:p.sym["RESULT"] + 30])
    assert record[:6] == bytes.fromhex("A5 5A 01 02 34 12")
    assert len(record) == 30 and sum(record) & 255 == 0
    assert record[26:28] == bytes([0x22, 0])
    assert record[28] == 0x22


def test_result_display_renders_raw_fields_only_after_record_formatting():
    p = Probe()
    p.run_to("idle")
    p.call("reset_trial")
    p.mem[p.sym["S_MODE"]] = 2
    p.mem[p.sym["S_BEFORE"]:p.sym["S_AFTER"] + 1] = b"\x34\x56"
    p.mem[p.sym["S_PROBE"]] = 0x12
    p.mem[p.sym["S_P4"]:p.sym["S_P6"] + 1] = b"\x10\x40"
    p.mem[p.sym["S_RXA"]:p.sym["S_RXF"] + 1] = b"\xEC\x01"
    p.mem[p.sym["S_RXL"]] = 4
    p.mem[p.sym["S_PREVLEN"]] = 8
    p.mem[p.sym["S_RAW2D"]] = 0xFE
    p.mem[p.sym["S_PREVIEW"]:p.sym["S_PREVIEW"] + 8] = bytes(range(8))
    p.call("show_result")
    rows = [bytes(p.screen[n:n + 20]) for n in range(0, 80, 20)]
    assert rows[0] == b"M2 S0000 E00 B34A56 "
    assert rows[1] == b"Q=121040EC010400    "
    assert rows[2] == b"D08=0001020304050607"
    assert rows[3] == b"A22C00IFE           "
