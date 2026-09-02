"""The decoder itself, on a bare Z80 with a synthetic width table.

A failure here is a bug in the assembly.  The end-to-end path through the
firmware is exercised separately by tools/run_tests.py --firmware, which is
slow and tests a different thing: that the hook is installed correctly and
the result comes back through BDOS 03h.
"""
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "tools"))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent / "analysis"))

from conftest import requires_emulator                # noqa: E402
from micronic.barcode import encode_code39            # noqa: E402
import upc                                            # noqa: E402

pytestmark = requires_emulator


def upca(eleven, **kw):
    d = [int(c) for c in eleven]
    d.append(upc.check_digit(d))
    return upc.widths(d, **kw), "".join(map(str, d)).encode()


def ean13(twelve, **kw):
    d = [int(c) for c in twelve]
    d.append(upc.check_digit(d))
    return upc.widths(d, **kw), "".join(map(str, d)).encode()


def upce(ns, six, **kw):
    d = [int(c) for c in six]
    chk = upc.upce_check(ns, d)
    return upc.upce_widths(ns, d, **kw), f"{ns}{six}{chk}".encode()


class TestCode39:
    @pytest.mark.parametrize("text", ["A1", "HELLO", "12345", "CODE-39",
                                      "$100.00", "Z", "0123456789"])
    def test_round_trip(self, decode, text):
        assert decode(encode_code39(text)) == text.encode()

    @pytest.mark.parametrize("text", ["A1", "HELLO", "CODE-39"])
    def test_reversed(self, decode, text):
        assert decode(encode_code39(text)[::-1]) == text.encode()

    def test_a_truncated_symbol_is_refused(self, decode):
        assert decode(encode_code39("A1")[:20]) == b""

    def test_the_delimiters_are_required(self, decode):
        """Strip the start character and the symbol must be refused.

        This is what stops a mirrored scan decoding to a wrong string, since
        every Code 39 pattern is another valid pattern reversed.
        """
        assert decode(encode_code39("A1")[10:]) == b""


class TestUpcA:
    @pytest.mark.parametrize("eleven", ["03600029145", "01234567890",
                                        "72527273070"])
    def test_round_trip(self, decode, eleven):
        widths, expect = upca(eleven)
        assert decode(widths) == expect

    def test_reversed(self, decode):
        widths, expect = upca("03600029145", reverse=True)
        assert decode(widths) == expect

    def test_a_slow_scan_still_decodes(self, decode):
        """Wider modules, same symbol: the decoder calibrates per symbol."""
        widths, expect = upca("03600029145", module=40)
        assert decode(widths) == expect

    def test_a_bad_check_digit_is_refused(self, decode):
        d = [int(c) for c in "03600029145"]
        d.append((upc.check_digit(d) + 5) % 10)
        assert decode(upc.widths(d, validate=False)) == b""


class TestEan13:
    @pytest.mark.parametrize("twelve", ["590123412345", "400638133393",
                                        "978030640615"])
    def test_round_trip(self, decode, twelve):
        widths, expect = ean13(twelve)
        assert decode(widths) == expect

    @pytest.mark.parametrize("lead", range(10))
    def test_every_leading_digit(self, decode, lead):
        """Walks the whole parity table.

        A leading zero is UPC-A, reported as twelve digits without the
        implied zero -- which is what a scanner gives you.
        """
        widths, expect = ean13(f"{lead}00000000000")
        assert decode(widths) == (expect[1:] if lead == 0 else expect)

    def test_reversed(self, decode):
        widths, expect = ean13("590123412345", reverse=True)
        assert decode(widths) == expect


class TestUpcE:
    @pytest.mark.parametrize("ns,six", [(0, "123456"), (0, "421005"),
                                        (1, "987653"), (0, "000000"),
                                        (0, "999995")])
    def test_round_trip(self, decode, ns, six):
        widths, expect = upce(ns, six)
        assert decode(widths) == expect

    @pytest.mark.parametrize("last", range(10))
    def test_every_expansion_layout(self, decode, last):
        """The last data digit selects where the suppressed zeros go."""
        widths, expect = upce(0, f"12345{last}")
        assert decode(widths) == expect

    @pytest.mark.parametrize("ns", [0, 1])
    def test_reversed(self, decode, ns):
        widths, expect = upce(ns, "123456" if ns == 0 else "987653",
                              reverse=True)
        assert decode(widths) == expect

    def test_a_bad_check_digit_is_refused(self, decode):
        six = [1, 2, 3, 4, 5, 6]
        bad = (upc.upce_check(0, six) + 5) % 10
        assert decode(upc.upce_widths(0, six, check=bad, validate=False)) == b""


class TestRejection:
    def test_uniform_widths(self, decode):
        assert decode([12] * 59) == b""

    def test_empty_capture(self, decode):
        assert decode([]) == b""

    def test_an_over_long_count_is_clamped(self, decode):
        """The firmware hands the hook an uncapped count; we must clamp.

        ROM00:1409 stores the raw count and ROM00:1446 passes it on, while
        only 128 entries were ever written.
        """
        assert decode(encode_code39("A1") + [12] * 200) == b""

    @pytest.mark.parametrize("n", [1, 2, 28, 34, 58, 60])
    def test_implausible_element_counts(self, decode, n):
        assert decode([12] * n) == b""


class TestItf:
    @pytest.mark.parametrize("digits", ["1234", "0000", "9999",
                                        "1234567890", "42"])
    def test_round_trip(self, decode, digits):
        assert decode(upc.itf_widths(digits)) == digits.encode()

    @pytest.mark.parametrize("digits", ["1234", "1234567890"])
    def test_reversed(self, decode, digits):
        assert decode(upc.itf_widths(digits, reverse=True)) == digits.encode()

    def test_a_slow_scan_still_decodes(self, decode):
        widths = upc.itf_widths("1234", narrow=40, wide=100)
        assert decode(widths) == b"1234"

    def test_a_clipped_start_is_refused(self, decode):
        """ITF's real hazard: a clipped symbol can look like a shorter one.

        Dropping the start pattern leaves something that still divides into
        whole pairs, so only checking the start and stop refuses it.
        """
        assert decode(upc.itf_widths("1234")[4:]) == b""

    def test_a_clipped_stop_is_refused(self, decode):
        assert decode(upc.itf_widths("1234")[:-3]) == b""
