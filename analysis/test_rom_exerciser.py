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
    assert sum(a != b for a, b in zip(image, stock)) == 713
    assert sum(image) & 0xFFFF == 0x2692
    assert hashlib.sha256(image).hexdigest() == (
        "cf2474dbd4be30a04998382f8e9946522cb2f87f91a7b516f40ff3119ae04c65"
    )


def test_lcd_powerup_delegates_to_the_complete_stock_initializer():
    code, sym = _assembled()
    start = sym["power_lcd_init"] - 0x0047
    end = sym["contrast_keys"] - 0x0047

    # CTL_LATCH_2A=20h, the exact reset delay loop, and the normal cold-start
    # IRQ_STATUS acknowledge / IRQ_MASK=FFh / SOUND=00h sequence, LCD contrast
    # shadow=00h, then a tail call to the complete stock LcdInit.
    assert code[start:end] == bytes.fromhex(
        "3e20 328bf7 d32a 01a00f 00 0b 78 b1 20fa "
        "db05 3eff d304 3e00 d32b "
        "3e00 3205fc c3ec1e"
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

    # V_KEY matrix index 17 (NO) -> lighter; index 23 (YES) -> darker.
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

    # kbd_scan clobbers BC/DE.  The pin walk must poll contrast before it
    # establishes D=port bit and C=pulse count, never inside pm_bit.
    portmap = sym["portmap"] - 0x0047
    assert code[portmap:portmap + 7] == (
        bytes([0xCD])
        + sym["dead_adjust"].to_bytes(2, "little")
        + bytes.fromhex("1601 0e01")
    )


@pytest.mark.skipif(z80 is None, reason="needs the z80 module")
@pytest.mark.parametrize(
    ("key_index", "initial", "expected", "writes"),
    (
        (0x11, 0x40, 0x3E, [0x3E]),  # NO: lighter
        (0x11, 0x00, 0x00, [0x00]),  # lighter endpoint saturates
        (0x17, 0x40, 0x42, [0x42]),  # YES: darker
        (0x17, 0xFE, 0xFF, [0xFF]),  # darker endpoint saturates
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
