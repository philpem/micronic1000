#!/usr/bin/env python3
"""UPC-A encoding, for generating test scans.

Kept beside the decoder rather than in the emulator harness: this is test
scaffolding for *this* package, and it is the counterpart of upc_table.inc
-- if one changes the other must.
"""

# Left-hand ("L") codes, seven modules each.  The right-hand codes are the
# bitwise complement, which is why the run lengths are the same in both
# halves and one decoder table serves both.
L_CODE = {
    0: "0001101", 1: "0011001", 2: "0010011", 3: "0111101", 4: "0100011",
    5: "0110001", 6: "0101111", 7: "0111011", 8: "0110111", 9: "0001011",
}


def check_digit(first11):
    """The twelfth digit of a UPC-A, given the first eleven."""
    if len(first11) != 11 or any(d not in range(10) for d in first11):
        raise ValueError("UPC-A needs eleven digits before the check digit")
    total = sum(d * (3 if i % 2 == 0 else 1) for i, d in enumerate(first11))
    return (10 - total % 10) % 10


def modules(digits, validate=True):
    """The 95-module bit string for a full twelve-digit UPC-A.

    `validate=False` builds a symbol whose check digit is deliberately
    wrong, so a decoder's rejection path can be exercised.
    """
    if len(digits) != 12:
        raise ValueError("UPC-A is twelve digits")
    if validate and check_digit(digits[:11]) != digits[11]:
        raise ValueError("check digit does not agree")
    bits = "101"                                     # left guard
    for d in digits[:6]:
        bits += L_CODE[d]
    bits += "01010"                                  # centre guard
    for d in digits[6:]:
        bits += "".join("1" if c == "0" else "0" for c in L_CODE[d])
    return bits + "101"                              # right guard


def widths(digits, module=12, validate=True):
    """Element widths for a UPC-A, in the units the capture records.

    The first element is a bar, which is what the capture expects: it arms
    on the quiet-to-dark edge, so element 0 is always dark.
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
    return out


if __name__ == "__main__":
    import sys
    d = [int(c) for c in (sys.argv[1] if len(sys.argv) > 1 else "03600029145")]
    if len(d) == 11:
        d.append(check_digit(d))
    w = widths(d)
    print("digits:", "".join(str(x) for x in d))
    print("elements:", len(w))
    print("widths:", ",".join(str(x) for x in w))
