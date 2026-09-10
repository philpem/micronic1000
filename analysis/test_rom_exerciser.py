import hashlib
import pathlib
import sys

import pytest

try:
    import z80
except ImportError:  # pragma: no cover - system pytest lacks the emulator
    z80 = None


ANALYSIS = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(ANALYSIS))

from micronic.z80asm import assemble


ASM = ANALYSIS / "rom_exerciser" / "exerciser.asm"
ROM = ANALYSIS.parent / "micronic" / "micron1.bin"
REGIONS = (
    (0x0047, 0x0065, "isr_end"),
    (0x0069, 0x007F, "nmi_end"),
    (0x00A2, 0x00FF, "vec_end"),
    (0x724C, 0x7302, "lo_end"),
    (0x7CE0, 0x7D0F, "mid_end"),
    (0x7E96, 0x7FF9, "hi_end"),
)


def _assembled():
    return assemble(ASM.read_text(), origin=0x0047)


def _burn_image():
    code, sym = _assembled()
    image = bytearray(ROM.read_bytes())
    for start, _, end_symbol in REGIONS:
        end = sym[end_symbol]
        image[start:end] = code[start - 0x0047:end - 0x0047]
    image[0x014B:0x014E] = bytes([0xC3]) + sym["start"].to_bytes(2, "little")
    return image, sym


def test_exerciser_fits_all_guarded_regions():
    code, sym = _assembled()
    assert code
    for start, end, end_symbol in REGIONS:
        assert start <= sym[end_symbol] <= end + 1


def test_burn_image_has_a_locked_fingerprint():
    stock = ROM.read_bytes()
    image, _ = _burn_image()

    assert len(image) == 0x8000
    assert sum(a != b for a, b in zip(image, stock)) == 698
    assert sum(image) & 0xFFFF == 0x2726
    assert hashlib.sha256(image).hexdigest() == (
        "813006c23f350142c83abe1deb495286a62e7eece4e9e0b49c97bdb225b60827"
    )


def test_lcd_powerup_delegates_to_the_complete_stock_initializer():
    code, sym = _assembled()
    start = sym["power_lcd_init"] - 0x0047
    end = sym["contrast_keys"] - 0x0047

    # CTL_LATCH_2A=20h, the exact reset delay loop, and the normal cold-start
    # IRQ_STATUS acknowledge / IRQ_MASK=FFh / SOUND=00h sequence, LCD contrast
    # shadow=A4h, then a tail call to the pre-init wrapper.
    assert code[start:end] == (
        bytes.fromhex(
            "3e20 328bf7 d32a 01a00f 00 0b 78 b1 20fa "
            "db05 3eff d304 3e00 d32b 3ea4 3205fc c3"
        )
        + sym["lcd_preinit"].to_bytes(2, "little")
    )

    stock = ROM.read_bytes()
    assert stock[0x1EEC:0x1EFB] == bytes.fromhex(
        "3e08 3246fd 3ea0 3247fd 3e64 cdce35"
    )
    assert stock[0x1F33:0x1F6D] == bytes.fromhex(
        "3e00 063c cd6d1f 3e01 0675 cd6d1f 3e02 0613 cd6d1f "
        "3e03 063f cd6d1f 3e04 0607 cd6d1f 3e08 0600 cd6d1f "
        "3e09 cd6d1f 3e0a cd6d1f 3e0b cd6d1f c9"
    )


def test_contrast_keys_tail_call_stock_saturating_adjusters():
    code, sym = _assembled()
    start = sym["contrast_keys"] - 0x0047
    end = sym["mid_end"] - 0x0047

    # V_KEY matrix index 17 (NO) -> decrement; index 23 (YES) -> increment.
    assert code[start:end] == bytes.fromhex(
        "3aedc7 fe11 ca4a1d fe17 ca601d c9"
    )

    dead = sym["dead_adjust"] - 0x0047
    assert code[dead:sym["lo_end"] - 0x0047] == (
        bytes([0xCD])
        + sym["kbd_scan"].to_bytes(2, "little")
        + bytes.fromhex("32 edc7 cd")
        + sym["contrast_keys"].to_bytes(2, "little")
        + bytes([0xC3])
        + sym["pm_delay"].to_bytes(2, "little")
    )

    arm = sym["kbd_irq_arm"] - 0x0047
    assert code[arm:arm + 3] == (
        bytes([0xC3]) + sym["KbdStrobe"].to_bytes(2, "little")
    )


def test_preinit_settle_then_contrast_screen_wrap_stock_init():
    code, sym = _assembled()
    preinit = sym["lcd_preinit"] - 0x0047
    assert code[preinit:sym["contrast_setup"] - 0x0047] == (
        bytes.fromhex("d346 0604")
        + bytes([0xCD]) + sym["pm_delay"].to_bytes(2, "little")
        + bytes.fromhex("10fb")
        + bytes([0xC3]) + sym["LcdInit"].to_bytes(2, "little")
    )

    start = sym["start"] - 0x0047
    assert code[start:start + 13] == (
        bytes.fromhex("f3 3100c9 cd") + sym["nmi_safe"].to_bytes(2, "little")
        + bytes([0xCD]) + sym["power_lcd_init"].to_bytes(2, "little")
        + bytes([0xCD]) + sym["contrast_setup"].to_bytes(2, "little")
    )


@pytest.mark.skipif(z80 is None, reason="needs the z80 module")
@pytest.mark.parametrize("sense,index,contrast", [(4, 0x11, 0xBE),
                                               (8, 0x17, 0xC2),
                                               (0, 0xFF, 0xC0)])
def test_contrast_screen_handles_key_then_enter_before_returning(sense, index, contrast):
    image, sym = _burn_image()
    mem = bytearray(0x10000)
    mem[:0x8000] = image
    mem[0xFC05] = 0xC0
    mem[0xEFFE:0xF000] = bytes.fromhex("0080")
    drive = [0]
    key_stage = [0]
    lcd_reg = [None]
    lcd_chars = []
    contrast_writes = []

    machine = z80.Z80Machine()
    machine.set_memory_block(0, bytes(mem))
    machine.set_read_callback(lambda address: mem[address & 0xFFFF])
    machine.set_write_callback(
        lambda address, value: mem.__setitem__(address & 0xFFFF, value & 0xFF)
    )

    def input_port(*args):
        port = args[0]
        if isinstance(port, tuple):
            port = port[0]
        if port & 0xFF != 0x00:
            return 0x00
        if key_stage[0] == 1 and drive[0] == 0x20:
            return sense
        if key_stage[0] == 2 and drive[0] == 0x10:
            return 0x08  # ENTER: sense bit 3, drive bit 4 -> index 22
        return 0x00

    def output_port(*args):
        port, value = args[:2]
        if isinstance(port, tuple):
            port = port[0]
        port &= 0xFF
        value &= 0xFF
        if port == 0x02:
            drive[0] = value & 0x3F
        elif port == 0x23:
            lcd_reg[0] = value
        elif port == 0x03 and lcd_reg[0] == 0x0C:
            lcd_chars.append(value)
        elif port == 0x03 and lcd_reg[0] == 0x0B:
            key_stage[0] += 1  # new screen: cursor high set by lcd_home
        elif port == 0x46:
            contrast_writes.append(value)
        assert port not in range(0x4A, 0x50), "IR touched before setup returns"

    machine.set_input_callback(input_port)
    machine.set_output_callback(output_port)
    machine.sp = 0xEFFE
    machine.pc = sym["contrast_setup"]
    machine.set_breakpoint(0x8000)
    for _ in range(20):
        machine.ticks_to_stop = 500000
        machine.run()
        if machine.pc & 0xFFFF == 0x8000:
            break

    assert machine.pc & 0xFFFF == 0x8000
    assert key_stage[0] == 2
    assert mem[0xFC05] == contrast
    assert contrast_writes == ([contrast] if sense else [])
    assert bytes(lcd_chars) == (
        f"CC0{index:02X}010000000000{sense:02X}"
        f"C{contrast:02X}1602000000000800"
    ).encode("ascii")
    assert machine.sp == 0xF000


@pytest.mark.skipif(z80 is None, reason="needs the z80 module")
@pytest.mark.parametrize(
    ("pressed_drive", "sense_bits", "expected_index"),
    [(1 << drive, 1 << sense, 6 * sense + drive)
     for sense in range(6) for drive in range(6)] + [(None, 0, 0xFF)],
)
def test_kbd_scan_matches_stock_matrix_coordinate_order(
        pressed_drive, sense_bits, expected_index):
    image, sym = _burn_image()
    mem = bytearray(0x10000)
    mem[:0x8000] = image
    mem[0xEFFE:0xF000] = bytes.fromhex("0080")
    drive = [0]
    driven = []

    machine = z80.Z80Machine()
    machine.set_memory_block(0, bytes(mem))
    machine.set_read_callback(lambda address: mem[address & 0xFFFF])
    machine.set_write_callback(
        lambda address, value: mem.__setitem__(address & 0xFFFF, value & 0xFF)
    )

    def input_port(*args):
        port = args[0]
        if isinstance(port, tuple):
            port = port[0]
        if port & 0xFF == 0x00 and drive[0] == pressed_drive:
            return sense_bits
        return 0x00

    def output_port(*args):
        port, value = args[:2]
        if isinstance(port, tuple):
            port = port[0]
        if port & 0xFF == 0x02:
            drive[0] = value & 0x3F
            driven.append(drive[0])

    machine.set_input_callback(input_port)
    machine.set_output_callback(output_port)
    machine.sp = 0xEFFE
    machine.pc = sym["kbd_scan"]
    machine.set_breakpoint(0x8000)
    machine.ticks_to_stop = 10000
    machine.run()

    assert machine.pc & 0xFFFF == 0x8000
    assert machine.a == expected_index
    masks = [1, 2, 4, 8, 16, 32]
    assert driven == (masks if pressed_drive is None
                      else masks[:masks.index(pressed_drive) + 1])


@pytest.mark.skipif(z80 is None, reason="needs the z80 module")
@pytest.mark.parametrize(
    ("key_index", "initial", "expected", "writes"),
    (
        (0x11, 0x40, 0x3E, [0x3E]),  # NO: decrement
        (0x11, 0x00, 0x00, [0x00]),  # lower endpoint saturates
        (0x17, 0x40, 0x42, [0x42]),  # YES: increment
        (0x17, 0xFE, 0xFF, [0xFF]),  # upper endpoint saturates
        (0xFF, 0x40, 0x40, []),      # no key: no contrast write
    ),
)
def test_contrast_keys_execute_real_stock_adjusters(
        key_index, initial, expected, writes):
    image, sym = _burn_image()
    mem = bytearray(0x10000)
    mem[:0x8000] = image
    mem[0xC7ED] = key_index
    mem[0xFC05] = initial
    mem[0xEFFE:0xF000] = bytes.fromhex("0080")
    port46 = []

    machine = z80.Z80Machine()
    machine.set_memory_block(0, bytes(mem))
    machine.set_read_callback(lambda address: mem[address & 0xFFFF])
    machine.set_write_callback(
        lambda address, value: mem.__setitem__(address & 0xFFFF, value & 0xFF)
    )

    def output(*args):
        port, value = args[:2]
        if isinstance(port, tuple):
            port = port[0]
        if port & 0xFF == 0x46:
            port46.append(value & 0xFF)

    machine.set_output_callback(output)
    machine.sp = 0xEFFE
    machine.pc = sym["contrast_keys"]
    machine.set_breakpoint(0x8000)
    machine.ticks_to_stop = 10000
    machine.run()

    assert machine.pc & 0xFFFF == 0x8000
    assert mem[0xFC05] == expected
    assert port46 == writes


def test_lcd_home_always_writes_cursor_low_then_cursor_high():
    code, sym = _assembled()
    start = sym["lcd_home"] - 0x0047
    end = sym["lcd_putc"] - 0x0047

    # HD61830 R10=00h must be followed by R11=00h.  R10 alone can carry
    # into R11 when R10 bit 7 changes from set to clear.
    assert code[start:end] == bytes.fromhex(
        "3e0a d323 af d303 3e0b d323 3e00 d303 c9"
    )


@pytest.mark.skipif(z80 is None, reason="needs the z80 module")
@pytest.mark.parametrize("ram_fill", [0x00, 0xFF, 0xA5])
def test_cold_boot_reaches_live_setup_with_dirty_battery_ram(ram_fill):
    image, sym = _burn_image()
    mem = bytearray([ram_fill] * 0x10000)
    mem[:0x8000] = image
    outputs = []
    machine = z80.Z80Machine()
    machine.set_memory_block(0, bytes(mem))
    machine.set_read_callback(lambda address: mem[address & 0xFFFF])
    machine.set_write_callback(
        lambda address, value: mem.__setitem__(address & 0xFFFF, value & 0xFF)
    )
    machine.set_input_callback(lambda *args: 0)
    machine.set_output_callback(
        lambda port, value: outputs.append((port & 0xFF, value & 0xFF))
    )
    machine.pc = 0x014B
    # Stop after one whole screen (including both scans), before the delay.
    machine.set_breakpoint(sym["pm_delay"])
    for _ in range(4):  # four pre-LCD settling calls
        for _ in range(100):
            machine.ticks_to_stop = 100000
            machine.run()
            if machine.pc == sym["pm_delay"]:
                break
        assert machine.pc == sym["pm_delay"]
        machine.clear_breakpoint(sym["pm_delay"])
        machine.ticks_to_stop = 4  # execute one instruction past breakpoint
        machine.run()
        machine.set_breakpoint(sym["pm_delay"])
    for _ in range(100):
        machine.ticks_to_stop = 100000
        machine.run()
        if machine.pc == sym["pm_delay"]:
            break
    assert machine.pc == sym["pm_delay"]
    assert mem[sym["V_COUNT"]] == (ram_fill + 1) & 0xFF
    assert mem[sym["V_KEY"]] == 0xFF
    assert mem[0xFC05] == 0xA4
    assert [value for port, value in outputs if port == 0x46] == [0xA4, 0xA4]
    assert [value for port, value in outputs if port == 0x02] == [1, 2, 4, 8, 16, 32] * 2
    assert not any(0x4A <= port <= 0x4F for port, _ in outputs)
    assert mem[0xF5F6:0xF5F8] == bytes.fromhex("ed45")


def test_stack_has_interrupt_headroom_above_state():
    _, sym = _assembled()
    assert sym["STACK"] - sym["V_KEY"] >= 0x100


def test_startup_diagnostic_does_not_run_the_old_sweep():
    _, sym = _assembled()
    assert sym["VERSION"] == 0x0E
    assert sym["LINK_ID"] == 0x43  # XOR A at selection is fixed to this state
    assert not {"sweep", "tx_arm", "rx_arm", "port_swap"} & sym.keys()


@pytest.mark.skipif(z80 is None, reason="needs the z80 module")
@pytest.mark.parametrize("stop_after,status,stage", [
    (-1, 0x40, 3),  # never ready, including the initial open
    (0, 0x40, 4),   # command accepted; first preamble byte cannot be sent
    (2, 0x01, 4),   # two preamble bytes accepted, then stall
    (5, 0x00, 5),   # complete preamble; first record-frame flag cannot be sent
    (16, 0x00, 5),  # complete first record; fail in the next record's emit
    (None, 0x80, 5),  # always ready: complete records at the baseline
])
def test_boot_enter_and_link_timeout_paths(stop_after, status, stage):
    image, sym = _burn_image()
    mem = bytearray([0xA5] * 0x10000)
    mem[:0x8000] = image
    drive, lcd_reg, cursor = [0], [0], [0]
    screen = bytearray(b"?" * 256)
    screens, data, commands, controls, port2c = [], [], [], [], []
    contrast = []
    error_key = [None]
    machine = z80.Z80Machine()
    machine.set_memory_block(0, bytes(mem))
    machine.set_read_callback(lambda address: mem[address & 0xFFFF])
    machine.set_write_callback(
        lambda address, value: mem.__setitem__(address & 0xFFFF, value & 0xFF)
    )

    def input_port(port):
        port &= 0xFF
        if port == 0:
            if error_key[0] is None:
                return 8 if drive[0] == 16 else 0  # ENTER
            return error_key[0] if drive[0] == 32 else 0
        if port == 0x4B:
            if stop_after == -1 or (stop_after is not None and commands
                                    and len(data) >= stop_after):
                return status
            return 0x80
        return 0

    def output_port(port, value):
        port &= 0xFF
        if port == 2:
            drive[0] = value
        elif port == 0x23:
            lcd_reg[0] = value
        elif port == 3:
            if lcd_reg[0] == 0x0A:
                cursor[0] = value
            elif lcd_reg[0] == 0x0B:
                cursor[0] |= value << 8
            elif lcd_reg[0] == 0x0C:
                screen[cursor[0] & 255] = value
                cursor[0] += 1
                if cursor[0] == 20:
                    screens.append(bytes(screen[:20]))
        elif port == 0x46:
            contrast.append(value)
        elif port == 0x4A:
            controls.append(value)
        elif port == 0x2C:
            port2c.append(value)
        elif port == 0x4C:
            commands.append(value)
        elif port == 0x4D:
            data.append(value)

    machine.set_input_callback(input_port)
    machine.set_output_callback(output_port)
    machine.pc = 0x014B
    target = sym["stream"] if stop_after is None else sym["failure_loop"]
    machine.set_breakpoint(target)
    for _ in range(100):
        machine.ticks_to_stop = 100000
        machine.run()
        if machine.pc == target:
            break
    assert machine.pc == target, "startup failed to finish within CPU budget"
    assert mem[sym["V_STAGE"]] == stage
    assert port2c == [0, 0x20]  # probe reset, then top V24, never alternated
    assert mem[sym["CTRL_SHADOW"]] == 3
    for n in range(1, stage + 1):
        assert f"{n:02X}".encode() + b" " * 18 in screens
    if stop_after is not None:
        count = max(stop_after, 0)
        assert len(data) == count
        expected_commands = 0 if stop_after == -1 else (2 if stop_after > 5 else 1)
        assert commands == [0x81] * expected_commands
        assert mem[sym["V_FAIL"]] == status
        assert screen[:20] == f"EE{stage:02X}{status:02X}03{count:02X}".encode() + b" " * 10
        assert machine.sp == sym["STACK"]
        machine.clear_breakpoint(target)
        machine.set_breakpoint(sym["pm_delay"])
        error_key[0] = 4  # NO still works in the terminal error loop
        machine.ticks_to_stop = 100000
        machine.run()
        assert machine.pc == sym["pm_delay"]
        assert contrast[-1] == 0xA2
        assert mem[0xFC05] == 0xA2
        assert len(data) == count
    else:
        assert data == [0xA5, 0x5A, 0x0E, 0x80, 0x80]
        machine.clear_breakpoint(target)
        machine.ticks_to_stop = 1000000
        machine.run()
        assert len(data) >= 5 + 11
        assert set(controls) <= {0, 1, 2, 3}


def test_decoder_does_not_invent_phases_for_startup_diagnostic(capsys):
    from rom_exerciser.decode_records import report_phases
    records = [(count, 0x80, 0x80, 0, 0, 3, 0, 0xFF, 0, 0, 0)
               for count in (0, 64, 128, 192)]
    report_phases(records, phased=False)
    output = capsys.readouterr().out
    assert "4 records" in output
    assert "TX armed" not in output
    assert "RX armed" not in output
    assert "CTRL sweep" not in output
