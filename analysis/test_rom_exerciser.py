import pathlib
import sys


ANALYSIS = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(ANALYSIS))

from micronic.z80asm import assemble


ASM = ANALYSIS / "rom_exerciser" / "exerciser.asm"


def test_exerciser_fits_all_guarded_regions():
    code, sym = assemble(ASM.read_text(), origin=0x0047)
    regions = (
        (0x0047, 0x0065, "isr_end"),
        (0x0069, 0x007F, "nmi_end"),
        (0x00A2, 0x00FF, "vec_end"),
        (0x724C, 0x7302, "lo_end"),
        (0x7CE0, 0x7D0F, "mid_end"),
        (0x7E96, 0x7FF9, "hi_end"),
    )
    assert code
    for start, end, end_symbol in regions:
        assert start <= sym[end_symbol] <= end + 1


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
