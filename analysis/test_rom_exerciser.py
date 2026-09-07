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
    assert sum(a != b for a, b in zip(image, stock)) == 715
    assert sum(image) & 0xFFFF == 0x27E8
    assert hashlib.sha256(image).hexdigest() == (
        "f02073d9743faab7b69c1ff85bdabc018a328000507ecf51574bba95e03814ca"
    )


def test_lcd_powerup_delegates_to_the_complete_stock_initializer():
    code, sym = _assembled()
    start = sym["power_lcd_init"] - 0x0047
    end = sym["contrast_keys"] - 0x0047

    # CTL_LATCH_2A=20h, the exact reset delay loop, and the normal cold-start
    # IRQ_STATUS acknowledge / IRQ_MASK=FFh / SOUND=00h sequence, LCD contrast
    # shadow=C0h, then a tail call to the pre-init wrapper.
    assert code[start:end] == (
        bytes.fromhex(
            "3e20 328bf7 d32a 01a00f 00 0b 78 b1 20fa "
            "db05 3eff d304 3e00 d32b 3ec0 3205fc c3"
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

    setup = sym["contrast_setup"] - 0x0047
    assert code[setup:sym["vec_end"] - 0x0047] == (
        bytes([0xCD]) + sym["lcd_home"].to_bytes(2, "little")
        + bytes([0x21]) + sym["str_contrast"].to_bytes(2, "little")
        + bytes.fromhex("7e b7 2806")
        + bytes([0xCD]) + sym["lcd_putc"].to_bytes(2, "little")
        + bytes.fromhex("23 18f6 3a05fc")
        + bytes([0xCD]) + sym["lcd_hex"].to_bytes(2, "little")
        + bytes([0xCD]) + sym["kbd_scan"].to_bytes(2, "little")
        + bytes.fromhex("fe16 c8 32edc7")
        + bytes([0xCD]) + sym["contrast_keys"].to_bytes(2, "little")
        + bytes([0xCD]) + sym["pm_delay"].to_bytes(2, "little")
        + bytes.fromhex("18d9")
    )
    string = sym["str_contrast"] - 0x0047
    assert code[string:sym["hi_end"] - 0x0047] == b"CONTRAST\0"

    start = sym["start"] - 0x0047
    assert code[start:start + 13] == (
        bytes.fromhex("f3 3100c9 cd7800")
        + bytes([0xCD]) + sym["power_lcd_init"].to_bytes(2, "little")
        + bytes([0xCD]) + sym["contrast_setup"].to_bytes(2, "little")
    )


@pytest.mark.skipif(z80 is None, reason="needs the z80 module")
def test_contrast_screen_handles_no_then_enter_before_returning():
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
        if key_stage[0] == 0 and drive[0] == 0x20:
            key_stage[0] = 1
            return 0x04  # NO: sense bit 2, drive bit 5 -> index 17
        if key_stage[0] == 1 and drive[0] == 0x10:
            key_stage[0] = 2
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
        elif port == 0x46:
            contrast_writes.append(value)

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
    assert mem[0xFC05] == 0xBE
    assert contrast_writes == [0xBE]
    assert bytes(lcd_chars) == b"CONTRASTC0CONTRASTBE"


@pytest.mark.skipif(z80 is None, reason="needs the z80 module")
@pytest.mark.parametrize(
    ("pressed_drive", "sense_bits", "expected_index"),
    (
        (0x20, 0x04, 0x11),  # NO: 6*sense-index 2 + drive-index 5
        (0x20, 0x08, 0x17),  # YES: 6*sense-index 3 + drive-index 5
        (None, 0x00, 0xFF),  # no key
    ),
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
    assert driven == ([1, 2, 4, 8, 16, 32] if pressed_drive in (None, 0x20)
                      else [])


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


def test_stack_has_interrupt_headroom_above_state():
    _, sym = _assembled()
    assert sym["STACK"] - sym["V_KEY"] >= 0x100


def test_rotated_sweep_covers_128_states_on_each_port():
    seen = {0: set(), 2: set()}
    for counter in range(1, 257):
        raw = counter & 0xFF
        rotated = ((raw << 1) | (raw >> 7)) & 0xFF  # Z80 RLCA
        port_bit = 0 if counter & 1 else 2
        seen[port_bit].add((rotated & 0xFD) | port_bit)

    assert len(seen[0]) == 128
    assert len(seen[2]) == 128
    assert all(value & 2 == 0 for value in seen[0])
    assert all(value & 2 == 2 for value in seen[2])
