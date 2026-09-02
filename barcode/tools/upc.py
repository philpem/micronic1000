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
