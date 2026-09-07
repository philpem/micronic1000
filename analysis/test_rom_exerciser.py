import hashlib
import pathlib
import sys


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


def test_exerciser_fits_all_guarded_regions():
    code, sym = _assembled()
    assert code
    for start, end, end_symbol in REGIONS:
        assert start <= sym[end_symbol] <= end + 1


def test_burn_image_has_a_locked_fingerprint():
    code, sym = _assembled()
    stock = ROM.read_bytes()
    image = bytearray(stock)
    for start, _, end_symbol in REGIONS:
        end = sym[end_symbol]
        image[start:end] = code[start - 0x0047:end - 0x0047]
    image[0x014B:0x014E] = bytes([0xC3]) + sym["start"].to_bytes(2, "little")

    assert len(image) == 0x8000
    assert sum(a != b for a, b in zip(image, stock)) == 674
    assert sum(image) & 0xFFFF == 0x1225
    assert hashlib.sha256(image).hexdigest() == (
        "9162097f6ca6bf56674d6cdcd2d3bcb25050902efc813d4eba3dcee3b019ffeb"
    )


def test_lcd_powerup_delegates_to_the_complete_stock_initializer():
    code, sym = _assembled()
    start = sym["power_lcd_init"] - 0x0047
    end = sym["mid_end"] - 0x0047

    # CTL_LATCH_2A=20h, a reset-equivalent delay, contrast shadow=40h,
    # then a tail call to the complete stock LcdInit at ROM00:1EEC.
    assert code[start:end] == bytes.fromhex(
        "3e20 d32a 328bf7 3e1e cdce35 3e40 3205fc c3ec1e"
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
