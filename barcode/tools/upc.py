#!/usr/bin/env python3
"""EAN-13 and UPC-A encoding, for generating test scans.

Kept beside the decoder rather than in the emulator harness: this is test
scaffolding for *this* package, and it is the counterpart of upc_table.inc
and ean_parity.inc -- if one changes the others must.

UPC-A is EAN-13 with a leading zero, and the two check-digit rules agree
under that reading, so everything here works in thirteen digits and the
twelve-digit form falls out.
"""

# Left-hand odd-parity ("L") codes, seven modules each.
L_CODE = {
    0: "0001101", 1: "0011001", 2: "0010011", 3: "0111101", 4: "0100011",
    5: "0110001", 6: "0101111", 7: "0111011", 8: "0110111", 9: "0001011",
}

# The right-hand ("R") codes are the bitwise complement of L, which leaves
# the run lengths unchanged -- that is why one width table decodes both
# halves.  The left-hand even-parity ("G") codes are R reversed, so their
# run lengths are the L run lengths reversed, which is how the decoder
# tells L from G without a second table.
R_CODE = {d: "".join("1" if c == "0" else "0" for c in b)
          for d, b in L_CODE.items()}
G_CODE = {d: b[::-1] for d, b in R_CODE.items()}

# Which left-hand positions use G, per leading digit.  This pattern is the
# only place the thirteenth digit is recorded.
PARITY = {
    0: "LLLLLL", 1: "LLGLGG", 2: "LLGGLG", 3: "LLGGGL", 4: "LGLLGG",
    5: "LGGLLG", 6: "LGGGLL", 7: "LGLGLG", 8: "LGLGGL", 9: "LGGLGL",
}


def check_digit(first12):
    """The thirteenth digit of an EAN-13, given the first twelve.

    Pass eleven digits for a UPC-A and a leading zero is assumed, which is
    what makes the two standards' check rules the same rule.
    """
    d = list(first12)
    if len(d) == 11:
        d = [0] + d
    if len(d) != 12 or any(x not in range(10) for x in d):
        raise ValueError("need twelve digits (or eleven for UPC-A)")
    total = sum(x * (1 if i % 2 == 0 else 3) for i, x in enumerate(d))
    return (10 - total % 10) % 10


def modules(digits, validate=True):
    """The 95-module bit string for a full thirteen-digit EAN-13.

    Twelve digits are accepted as a UPC-A and get the leading zero.
    `validate=False` builds a symbol whose check digit is deliberately
    wrong, so a decoder's rejection path can be exercised.
    """
    d = list(digits)
    if len(d) == 12:
        d = [0] + d
    if len(d) != 13:
        raise ValueError("EAN-13 is thirteen digits (or twelve for UPC-A)")
    if validate and check_digit(d[:12]) != d[12]:
        raise ValueError("check digit does not agree")

    parity = PARITY[d[0]]
    bits = "101"                                     # left guard
    for code, digit in zip(parity, d[1:7]):
        bits += (L_CODE if code == "L" else G_CODE)[digit]
    bits += "01010"                                  # centre guard
    for digit in d[7:]:
        bits += R_CODE[digit]
    return bits + "101"                              # right guard


def widths(digits, module=12, validate=True, reverse=False):
    """Element widths for the symbol, in the units the capture records.

    The first element is a bar, which is what the capture expects: it arms
    on the quiet-to-dark edge, so element 0 is always dark.  `reverse`
    gives the widths a wand drawn right-to-left would produce -- the
    symbol is structurally symmetric, so this is just the list backwards.
    """
    bits = modules(digits, validate)
    out, last, n = [], bits[0], 0
    for b in bits:
        if b == last:
            n += 1
        else:
            out.append(n * module)
            last, n = b, 1
    out.append(n * module)
    return out[::-1] if reverse else out


if __name__ == "__main__":
    import sys
    text = sys.argv[1] if len(sys.argv) > 1 else "590123412345"
    d = [int(c) for c in text]
    if len(d) in (11, 12):
        d.append(check_digit(d))
    w = widths(d)
    print("digits:  ", "".join(str(x) for x in d))
    print("parity:  ", PARITY[d[0]] if len(d) == 13 else "(UPC-A)")
    print("elements:", len(w))
    print("widths:  ", ",".join(str(x) for x in w))


# ---------------------------------------------------------------------------
# UPC-E.  Six digits in 51 modules, which the capture sees as 33 elements:
# left guard (3), six digits (24), and a six-module end guard (6).
#
# There are no R codes: every digit is L or G, and the *parity pattern*
# carries both the number system and the check digit -- neither is drawn.
# ---------------------------------------------------------------------------

# Parity for number system 0, indexed by check digit.  E = even = G code.
# Number system 1 is the same table complemented, which is why the decoder
# needs only these ten.
UPCE_PARITY = {
    0: "EEEOOO", 1: "EEOEOO", 2: "EEOOEO", 3: "EEOOOE", 4: "EOEEOO",
    5: "EOOEEO", 6: "EOOOEE", 7: "EOEOEO", 8: "EOEOOE", 9: "EOOEOE",
}


def upce_expand(ns, six, check):
    """Expand a UPC-E to its twelve-digit UPC-A.

    The last data digit says where the suppressed zeros go -- that is the
    whole trick of the format.
    """
    x = list(six)
    if len(x) != 6:
        raise ValueError("UPC-E carries six data digits")
    last = x[5]
    if last in (0, 1, 2):
        body = [x[0], x[1], last, 0, 0, 0, 0, x[2], x[3], x[4]]
    elif last == 3:
        body = [x[0], x[1], x[2], 0, 0, 0, 0, 0, x[3], x[4]]
    elif last == 4:
        body = [x[0], x[1], x[2], x[3], 0, 0, 0, 0, 0, x[4]]
    else:
        body = [x[0], x[1], x[2], x[3], x[4], 0, 0, 0, 0, last]
    return [ns] + body + [check]


def upce_check(ns, six):
    """The check digit of a UPC-E: that of the UPC-A it expands to."""
    return check_digit(upce_expand(ns, six, 0)[:11])


def upce_modules(ns, six, check=None, validate=True):
    """The 51-module bit string for a UPC-E."""
    if ns not in (0, 1):
        raise ValueError("UPC-E number system is 0 or 1")
    real = upce_check(ns, six)
    if check is None:
        check = real
    elif validate and check != real:
        raise ValueError("check digit does not agree")
    parity = UPCE_PARITY[check]
    if ns == 1:                                  # complement for system 1
        parity = "".join("O" if c == "E" else "E" for c in parity)
    bits = "101"                                 # left guard
    for code, digit in zip(parity, six):
        bits += (G_CODE if code == "E" else L_CODE)[digit]
    return bits + "010101"                       # end guard


def upce_widths(ns, six, module=12, check=None, validate=True, reverse=False):
    """Element widths for a UPC-E scan."""
    bits = upce_modules(ns, six, check, validate)
    out, last, n = [], bits[0], 0
    for b in bits:
        if b == last:
            n += 1
        else:
            out.append(n * module)
            last, n = b, 1
    out.append(n * module)
    return out[::-1] if reverse else out


# ---------------------------------------------------------------------------
# Interleaved 2 of 5.  Digits in pairs: five bars carry the first, five
# spaces the second, woven together.  Two of each five are wide.
# ---------------------------------------------------------------------------

ITF_PATTERNS = {
    0: "NNWWN", 1: "WNNNW", 2: "NWNNW", 3: "WWNNN", 4: "NNWNW",
    5: "WNWNN", 6: "NWWNN", 7: "NNNWW", 8: "WNNWN", 9: "NWNWN",
}


def itf_widths(digits, narrow=12, wide=30, reverse=False):
    """Element widths for an ITF symbol.

    Start is four narrow elements, stop is wide-narrow-narrow, and every
    pair of digits contributes ten interleaved elements.  An odd number of
    digits cannot be encoded -- that is a property of the symbology, not a
    limitation here.
    """
    d = [int(c) for c in digits] if isinstance(digits, str) else list(digits)
    if len(d) % 2:
        raise ValueError("ITF encodes digits in pairs")
    out = [narrow, narrow, narrow, narrow]              # start
    for i in range(0, len(d), 2):
        bars, spaces = ITF_PATTERNS[d[i]], ITF_PATTERNS[d[i + 1]]
        for b, s in zip(bars, spaces):
            out.append(wide if b == "W" else narrow)
            out.append(wide if s == "W" else narrow)
    out += [wide, narrow, narrow]                       # stop
    return out[::-1] if reverse else out


# ---------------------------------------------------------------------------
# Codabar.  Seven elements per character -- four bars, three spaces -- with
# a narrow gap between characters.  Start and stop are drawn from A-D.
# ---------------------------------------------------------------------------

CODABAR_PATTERNS = {
    "0": "NNNNNWW", "1": "NNNNWWN", "2": "NNNWNNW", "3": "WWNNNNN",
    "4": "NNWNNWN", "5": "WNNNNWN", "6": "NWNNNNW", "7": "NWNNWNN",
    "8": "NWWNNNN", "9": "WNNWNNN", "-": "NNNWNWN", "$": "NNWWNNN",
    ":": "WNNNWNW", "/": "WNWNNNW", ".": "WNWNWNN", "+": "NNWNWNW",
    "A": "NNWWNWN", "B": "NWNWNNW", "C": "NNNWWNW", "D": "NNNWWWN",
}


def codabar_widths(text, narrow=12, wide=30, gap=None, reverse=False):
    """Element widths for a Codabar symbol.

    `text` must begin and end with a start/stop character, A to D.
    """
    if len(text) < 3 or text[0] not in "ABCD" or text[-1] not in "ABCD":
        raise ValueError("Codabar needs an A-D start and stop character")
    gap = narrow if gap is None else gap
    out = []
    for i, ch in enumerate(text):
        if i:
            out.append(gap)                             # inter-character gap
        for w in CODABAR_PATTERNS[ch]:
            out.append(wide if w == "W" else narrow)
    return out[::-1] if reverse else out


# ---------------------------------------------------------------------------
# Code 128.  Eleven modules per symbol character in six elements -- three
# bars, three spaces -- except the stop, which is thirteen modules in seven.
#
# A delta code: element widths are 1..4 modules and mean nothing absolutely.
# Three code sets share the 107 patterns; a checksum mod 103 closes it.
# ---------------------------------------------------------------------------

# Element widths for symbol values 0..106, bar first.  Every row sums to 11
# except the stop (value 106), which is the seven-element terminator.
CODE128_WIDTHS = [
    "212222", "222122", "222221", "121223", "121322", "131222", "122213",
    "122312", "132212", "221213", "221312", "231212", "112232", "122132",
    "122231", "113222", "123122", "123221", "223211", "221132", "221231",
    "213212", "223112", "312131", "311222", "321122", "321221", "312212",
    "322112", "322211", "212123", "212321", "232121", "111323", "131123",
    "131321", "112313", "132113", "132311", "211313", "231113", "231311",
    "112133", "112331", "132131", "113123", "113321", "133121", "313121",
    "211331", "231131", "213113", "213311", "213131", "311123", "311321",
    "331121", "312113", "312311", "332111", "314111", "221411", "431111",
    "111224", "111422", "121124", "121421", "141122", "141221", "112214",
    "112412", "122114", "122411", "142112", "142211", "241211", "221114",
    "413111", "241112", "134111", "111242", "121142", "121241", "114212",
    "124112", "124211", "411212", "421112", "421211", "212141", "214121",
    "412121", "111143", "111341", "131141", "114113", "114311", "411113",
    "411311", "113141", "114131", "311141", "411131", "211412", "211214",
    "211232", "2331112",
]

START_A, START_B, START_C, STOP = 103, 104, 105, 106


def code128_values(text, codeset="B"):
    """Symbol values for TEXT: start, data, checksum, stop.

    Code set B covers printable ASCII 32..127, which is what a decoder for
    this device is most likely to meet.  Code set C, two digits per symbol,
    is used when the text is an even run of digits.
    """
    if codeset == "C":
        if len(text) % 2 or not text.isdigit():
            raise ValueError("code set C takes an even number of digits")
        values = [START_C] + [int(text[i:i + 2]) for i in range(0, len(text), 2)]
    else:
        for ch in text:
            if not 32 <= ord(ch) <= 127:
                raise ValueError(f"code set B cannot carry {ch!r}")
        values = [START_B] + [ord(ch) - 32 for ch in text]
    check = values[0]
    for i, v in enumerate(values[1:], start=1):
        check += i * v
    return values + [check % 103, STOP]


def code128_widths(text, codeset="B", module=12, reverse=False):
    """Element widths for a Code 128 symbol, plus the quiet-zone-free tail."""
    out = []
    for v in code128_values(text, codeset):
        out += [int(c) * module for c in CODE128_WIDTHS[v]]
    return out[::-1] if reverse else out
