#!/usr/bin/env python3
"""Tests for the wand model, the Code 39 codec, and the Z80 decode hook.

The pure-Python and bare-CPU tests run unconditionally and take under a
second.  The emulator integration tests boot the real firmware and are
opt-in, like the rest of the harness tests:

  MICRONIC_RUN_EMULATOR_TESTS=1 analysis/venv/bin/python3 \
    analysis/test_barcode.py
"""

from __future__ import annotations

import os
import subprocess
import unittest
from pathlib import Path

try:                      # the emulator module lives in analysis/venv
    import z80            # and pytest lives in the system interpreter, so
except ImportError:       # neither one alone can both collect and emulate.
    z80 = None            # Import lazily and skip, rather than failing to
                          # collect the pure-Python tests under either.

from micronic import barcode
from micronic.z80asm import assemble, AsmError

ROOT = Path(__file__).resolve().parent.parent
PYTHON = ROOT / "analysis" / "venv" / "bin" / "python3"
HARNESS = ROOT / "analysis" / "boot_hw.py"
RUN_EMULATOR = os.environ.get("MICRONIC_RUN_EMULATOR_TESTS") == "1"

BOOT_STEPS = [
    "--expect", "To Continue Press>>:\r",
    "--expect", "Enter the,Workstation:\r12345678\r",
    "--expect", "Main Menu",
]


class Code39TableTest(unittest.TestCase):
    """The symbology's own invariants, so a typo in the table cannot hide."""

    def test_forty_four_distinct_characters(self):
        self.assertEqual(len(barcode.CODE39_PATTERNS), 44)
        self.assertEqual(len(set(barcode.CODE39_PATTERNS.values())), 44)

    def test_every_character_is_nine_elements_with_three_wide(self):
        for ch, pattern in barcode.CODE39_PATTERNS.items():
            self.assertEqual(len(pattern), 9, ch)
            self.assertEqual(pattern.count("W"), 3, ch)
            self.assertEqual(set(pattern) - {"N", "W"}, set(), ch)

    def test_wide_elements_follow_the_two_bar_one_space_rule(self):
        # 40 characters have two wide bars and one wide space; the four
        # punctuation characters $ / + % have three wide spaces and no wide
        # bar. Nothing else is a legal Code 39 pattern.
        specials = set()
        for ch, pattern in barcode.CODE39_PATTERNS.items():
            bars = [pattern[i] for i in (0, 2, 4, 6, 8)].count("W")
            spaces = [pattern[i] for i in (1, 3, 5, 7)].count("W")
            self.assertIn((bars, spaces), ((2, 1), (0, 3)), ch)
            if bars == 0:
                specials.add(ch)
        self.assertEqual(specials, {"$", "/", "+", "%"})


class Code39CodecTest(unittest.TestCase):
    def test_round_trip(self):
        for text in ("A", "A1", "HELLO", "12345", "AB-12.", "Z$/+%", "X Y"):
            widths = barcode.encode_code39(text)
            self.assertEqual(barcode.decode_code39(widths), text)

    def test_element_count_is_ten_per_character_minus_one(self):
        for text, chars in (("A", 3), ("A1", 4), ("HELLO", 7)):
            widths = barcode.encode_code39(text)
            self.assertEqual(len(widths), 10 * chars - 1)

    def test_narrow_below_the_firmware_minimum_is_refused(self):
        # ROM00:13FA SUB 8 / JR C restarts the capture below 8.
        with self.assertRaises(barcode.Code39Error):
            barcode.encode_code39("A", narrow=7)

    def test_symbol_longer_than_the_reverse_copy_limit_is_refused(self):
        # ROM00:140F CP 80h caps the reverse copy at 128 elements.
        with self.assertRaises(barcode.Code39Error):
            barcode.encode_code39("ABCDEFGHIJKLMN")

    def test_star_cannot_be_data(self):
        with self.assertRaises(barcode.Code39Error):
            barcode.encode_code39("A*B")


def _simulate_capture(wand, limit=200000):
    """A faithful Python model of the capture loop at ROM00:13BB.

    Returns the width table the firmware would have recorded.  Its only
    purpose is to check the Wand's off-by-one compensation without booting
    the emulator; the authoritative check is the integration test, which
    runs the real ROM code.
    """
    reads = 0
    while (wand.read() & 1) == 0:            # ROM00:13CB arm loop
        reads += 1
        if reads > limit:
            raise AssertionError("wand never asserted the line")
    level, table, hl = 1, [], 1
    for _ in range(limit):
        hl += 1                              # ROM00:13E8 INC HL
        if hl >> 8 == 0x18:                  # ROM00:13EA CP D (D=18h)
            return table
        sample = wand.read() & 1             # ROM00:13ED IN A,(2Dh)
        if sample == level:
            continue
        level = sample
        if hl < 0x100 and (hl & 0xFF) < 8:   # ROM00:13FA SUB 8 / JR C
            raise AssertionError(f"element {len(table)} below the minimum width")
        table.append(hl)
        hl = 1                               # ROM00:13E5 LD HL,1
    raise AssertionError("capture did not terminate")


class WandModelTest(unittest.TestCase):
    def test_recorded_widths_equal_the_widths_asked_for(self):
        widths = [8, 12, 30, 9, 255, 256, 300, 12]
        self.assertEqual(_simulate_capture(barcode.Wand(widths)), widths)

    def test_a_code39_symbol_survives_the_capture_loop(self):
        widths = barcode.encode_code39("HELLO")
        self.assertEqual(_simulate_capture(barcode.Wand(widths)), widths)

    def test_the_quiet_line_is_the_level_the_arm_loop_waits_on(self):
        wand = barcode.Wand([12, 12], idle=3)
        self.assertEqual(wand.idle_byte() & 1, 0)

    def test_second_line_is_reported_on_bit1(self):
        self.assertEqual(barcode.Wand([12], line2=1).idle_byte(), 0x02)

    def test_widths_outside_the_firmware_limits_are_refused(self):
        with self.assertRaises(barcode.Code39Error):
            barcode.Wand([7])
        with self.assertRaises(barcode.Code39Error):
            barcode.Wand([barcode.MAX_WIDTH + 1])


class AssemblerTest(unittest.TestCase):
    def test_known_rom_encodings(self):
        # Byte-for-byte against instructions read out of micron1.bin:
        # ROM00:13BB ED 73 BD FB, ROM00:13BF 31 B5 FB, ROM00:145B CB 7C.
        code, _ = assemble("ld (0xfbbd),sp\nld sp,0xfbb5\nbit 7,h\n")
        self.assertEqual(code.hex(), "ed73bdfb31b5fbcb7c")

    def test_relative_jumps_resolve_forwards_and_backwards(self):
        code, syms = assemble("a:\n jr b\n nop\nb:\n jr a\n", origin=0x9000)
        self.assertEqual(code.hex(), "18010018fb")
        self.assertEqual(syms["b"], 0x9003)

    def test_unknown_mnemonic_is_an_error(self):
        with self.assertRaises(AsmError):
            assemble("frobnicate a,b\n")


@unittest.skipIf(z80 is None, "needs the z80 module (analysis/venv)")
class Z80DecoderTest(unittest.TestCase):
    """Run the real decode hook on a bare CPU, with no firmware around it."""

    ORIGIN = 0x9000
    TABLE = 0xF9B5
    SENTINEL = 0x0000

    def _run(self, widths):
        code, _ = barcode.assemble_decoder(self.ORIGIN)
        mem = bytearray(0x10000)
        mem[self.ORIGIN:self.ORIGIN + len(code)] = code
        for i, w in enumerate(widths):
            mem[self.TABLE + 2 * i] = w & 0xFF
            mem[self.TABLE + 2 * i + 1] = w >> 8
        mem[0xFBB9] = self.TABLE & 0xFF
        mem[0xFBBA] = self.TABLE >> 8
        mem[0xFBBB] = len(widths) & 0xFF
        mem[0xFBBC] = len(widths) >> 8
        mem[0xF000] = self.SENTINEL & 0xFF
        mem[0xF001] = self.SENTINEL >> 8
        machine = z80.Z80Machine()
        machine.set_memory_block(0, bytes(mem))
        machine.set_read_callback(lambda a: mem[a & 0xFFFF])
        machine.set_write_callback(
            lambda a, v: mem.__setitem__(a & 0xFFFF, v & 0xFF))
        machine.sp = 0xF000
        machine.pc = self.ORIGIN
        machine.set_breakpoint(self.SENTINEL)
        for _ in range(4000):
            machine.ticks_to_stop = 2000
            machine.run()
            if (machine.pc & 0xFFFF) == self.SENTINEL:
                break
        else:
            self.fail("the decode hook never returned")
        count = mem[0xFBBB] | (mem[0xFBBC] << 8)
        pointer = mem[0xFBB9] | (mem[0xFBBA] << 8)
        return bytes(mem[pointer:pointer + count])

    def test_decodes_what_the_encoder_produced(self):
        for text in ("A", "A1", "HELLO", "12345", "AB-12.", "Z$/+%"):
            self.assertEqual(self._run(barcode.encode_code39(text)),
                             text.encode("ascii"), text)

    def test_tolerates_the_usual_narrow_to_wide_ratios(self):
        for narrow, wide in ((8, 16), (10, 25), (12, 36), (20, 60)):
            widths = barcode.encode_code39("TEST", narrow=narrow, wide=wide)
            self.assertEqual(self._run(widths), b"TEST", (narrow, wide))

    def test_rejects_by_returning_a_zero_count(self):
        # Zero in FBBB is what ROM00:146E tests to discard a scan.
        cases = {
            "uniform widths": [12] * 29,
            "truncated symbol": barcode.encode_code39("A")[:-1],
            "no start/stop": barcode.encode_code39("A", start_stop=False),
            "too few elements": [12] * 9,
        }
        for why, widths in cases.items():
            self.assertEqual(self._run(widths), b"", why)


@unittest.skipUnless(RUN_EMULATOR, "set MICRONIC_RUN_EMULATOR_TESTS=1")
class EmulatorIntegrationTest(unittest.TestCase):
    """Drive the real ROM capture loop through the wand model."""

    def _run_harness(self, extra, timeout=540):
        proc = subprocess.run(
            [str(PYTHON), str(HARNESS), "--no-lcd",
             "--max-slices", "60000", "--expect-timeout", "45000"]
            + BOOT_STEPS + extra,
            cwd=ROOT, text=True, stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT, timeout=timeout, check=False)
        self.assertEqual(proc.returncode, 0, proc.stdout)
        return proc.stdout

    def test_widths_in_widths_out(self):
        """The acceptance test: what the wand feeds is what F9B5 records."""
        widths = barcode.encode_code39("A1")
        out = self._run_harness(
            ["--barcode-scan", "A1", "--barcode-probe",
             "--watch-mem", "f9b5:fbb4", "--watch-mem-limit", "4"])
        self.assertIn("[barcode] widths match input: True", out)
        self.assertIn(f"[barcode] recorded widths ({len(widths)}): {widths}",
                      out)
        # The width table is written by PUSH from the capture loop and then
        # by the reverse-copy; 1402 is the PUSH, 142C-1435 the copy.
        self.assertIn("1402x", out)
        self.assertIn("barcode_status=succeeded", out)

    def test_hook_entry_contract(self):
        """The hook is entered with the return address and the block ptr."""
        out = self._run_harness(["--barcode-scan", "A1", "--barcode-probe"])
        self.assertIn("[barcode] stack at hook entry: 1468 FBB9", out)
        self.assertIn("(table F9B5, count 39)", out)
        self.assertIn("[barcode] hook entered 1 time(s)", out)

    def test_cross_bank_hook_returns_through_the_bank_thunk(self):
        """A hook whose thunk names another bank returns through D762."""
        out = self._run_harness(
            ["--barcode-scan", "A1", "--barcode-probe",
             "--barcode-hook-bank", "2"])
        self.assertIn("[barcode] stack at hook entry: D762 FBB9", out)
        self.assertIn("F791=02", out)

    def test_bdos_function_03h_yields_esc_count_data(self):
        """CALL 0005h with C=03h: 1Bh, then the count, then the bytes."""
        out = self._run_harness(
            ["--barcode-scan", "A1", "--barcode-decode", "--barcode-bdos",
             "--barcode-expect", "A1"])
        self.assertIn("FE83+5 = wire 2B", out)
        self.assertIn(r"[barcode] fn 03h returned 1b024131", out)
        self.assertIn("[barcode] PASS", out)

    def test_code39_hook_delivers_ascii(self):
        out = self._run_harness(
            ["--barcode-scan", "A1", "--barcode-decode",
             "--barcode-expect", "A1"])
        self.assertIn("[barcode] envelope: status=00 count=2 data=b'A1'", out)
        self.assertIn("[barcode] PASS", out)
        self.assertIn("barcode_status=succeeded", out)


if __name__ == "__main__":
    unittest.main()
