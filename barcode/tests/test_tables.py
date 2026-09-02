"""The tables' own invariants, so a typo cannot hide behind a passing decode."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "tools"))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent / "analysis"))

from micronic.barcode import CODE39_PATTERNS          # noqa: E402
import upc                                            # noqa: E402


def runs(bits):
    out, last, n = [], bits[0], 0
    for b in bits:
        if b == last:
            n += 1
        else:
            out.append(n)
            last, n = b, 1
    return out + [n]


class TestCode39:
    def test_forty_four_distinct_patterns(self):
        assert len(CODE39_PATTERNS) == 44
        assert len(set(CODE39_PATTERNS.values())) == 44

    def test_every_character_is_nine_elements_three_wide(self):
        for ch, pat in CODE39_PATTERNS.items():
            assert len(pat) == 9, ch
            assert pat.count("W") == 3, ch

    def test_the_delimiter_does_not_reverse_to_itself(self):
        """The one property that makes a mirrored scan safe to refuse.

        Every Code 39 pattern is another valid pattern reversed, so if '*'
        reversed were also '*', a backwards scan would decode to a wrong
        string instead of being rejected.
        """
        back = {p: c for c, p in CODE39_PATTERNS.items()}
        assert back[CODE39_PATTERNS["*"][::-1]] != "*"


class TestUpcTables:
    def test_l_and_g_patterns_are_disjoint(self):
        """What makes parity -- and EAN-13's thirteenth digit -- recoverable."""
        def packed(r):
            return sum((w - 1) << (6 - 2 * i) for i, w in enumerate(r))
        fwd = {packed(runs(upc.L_CODE[d])) for d in range(10)}
        rev = {packed(list(reversed(runs(upc.L_CODE[d])))) for d in range(10)}
        assert not (fwd & rev)

    def test_every_digit_is_seven_modules_in_four_runs(self):
        for d, bits in upc.L_CODE.items():
            r = runs(bits)
            assert len(r) == 4 and sum(r) == 7, d

    def test_l_codes_have_odd_parity(self):
        for d, bits in upc.L_CODE.items():
            assert bits.count("1") % 2 == 1, d

    def test_ean_parity_patterns_are_distinct_and_start_with_l(self):
        seen = set()
        for d, pat in upc.PARITY.items():
            assert pat[0] == "L", d
            assert pat.count("G") == (0 if d == 0 else 3), d
            assert pat not in seen
            seen.add(pat)

    def test_upce_parity_never_collides_with_a_complement(self):
        """What makes the UPC-E number system recoverable."""
        keys = {c: int("".join("1" if x == "E" else "0" for x in p), 2)
                for c, p in upc.UPCE_PARITY.items()}
        seen = set()
        for c, k in keys.items():
            assert k not in seen and (k ^ 0x3F) not in seen, c
            seen.add(k)


class TestUpcExpansion:
    def test_every_last_digit_expands_and_checks_out(self):
        for last in range(10):
            six = [1, 2, 3, 4, 5, last]
            chk = upc.upce_check(0, six)
            exp = upc.upce_expand(0, six, chk)
            assert len(exp) == 12
            assert upc.check_digit(exp[:11]) == exp[11], last

    def test_upc_a_is_ean_13_with_a_leading_zero(self):
        eleven = [0, 3, 6, 0, 0, 0, 2, 9, 1, 4, 5]
        assert upc.check_digit(eleven) == upc.check_digit([0] + eleven)
