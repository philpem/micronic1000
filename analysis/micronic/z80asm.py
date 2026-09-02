"""z80asm - a small two-pass Z80 assembler.

Exists so that Z80 payloads injected into the emulator harness (decode
hooks, call trampolines) can live in the repository as readable source
rather than as hand-assembled hex blobs.  It implements the subset of the
instruction set those payloads use, not the whole architecture; an
unsupported mnemonic raises AsmError rather than silently emitting
something wrong.

Syntax
------
  label:              a label definition (colon optional if in column 1)
  NAME equ EXPR       a constant
  org EXPR            set the assembly address
  db  EXPR[,EXPR...]  bytes; a 'string' emits its characters
  dw  EXPR[,EXPR...]  little-endian words
  ds  COUNT[,FILL]    reserve COUNT bytes
  ; comment           to end of line

Expressions accept decimal, 0xNN, NNh, $NN, 'c', labels, $ (current
address) and the operators + - * / % ( ) << >> & | ^ ~.

Usage
-----
  code, symbols = assemble(SOURCE, origin=0x9000)
"""

import re

__all__ = ["AsmError", "assemble"]


class AsmError(Exception):
    pass


R8 = {"B": 0, "C": 1, "D": 2, "E": 3, "H": 4, "L": 5, "(HL)": 6, "A": 7}
RP_SP = {"BC": 0, "DE": 1, "HL": 2, "SP": 3}
RP_AF = {"BC": 0, "DE": 1, "HL": 2, "AF": 3}
CC = {"NZ": 0, "Z": 1, "NC": 2, "C": 3, "PO": 4, "PE": 5, "P": 6, "M": 7}
CC_SHORT = {"NZ": 0, "Z": 1, "NC": 2, "C": 3}
ALU = {"ADD": 0, "ADC": 1, "SUB": 2, "SBC": 3, "AND": 4, "XOR": 5, "OR": 6, "CP": 7}
ALU_IMM = {"ADD": 0xC6, "ADC": 0xCE, "SUB": 0xD6, "SBC": 0xDE,
           "AND": 0xE6, "XOR": 0xEE, "OR": 0xF6, "CP": 0xFE}
CB_ROT = {"RLC": 0, "RRC": 1, "RL": 2, "RR": 3,
          "SLA": 4, "SRA": 5, "SLL": 6, "SRL": 7}
NO_OPERAND = {
    "NOP": (0x00,), "HALT": (0x76,), "DI": (0xF3,), "EI": (0xFB,),
    "RET": (0xC9,), "EXX": (0xD9,), "SCF": (0x37,), "CCF": (0x3F,),
    "CPL": (0x2F,), "DAA": (0x27,), "RLCA": (0x07,), "RRCA": (0x0F,),
    "RLA": (0x17,), "RRA": (0x1F,), "NEG": (0xED, 0x44),
    "LDI": (0xED, 0xA0), "LDIR": (0xED, 0xB0),
    "LDD": (0xED, 0xA8), "LDDR": (0xED, 0xB8),
    "CPI": (0xED, 0xA1), "CPIR": (0xED, 0xB1),
    "RETI": (0xED, 0x4D), "RETN": (0xED, 0x45),
}


def _norm_number(text):
    """Rewrite the assembler's number spellings into Python literals."""
    text = re.sub(r"\$([0-9A-Fa-f]+)\b", r"0x\1", text)
    text = re.sub(r"\b([0-9][0-9A-Fa-f]*)[Hh]\b", r"0x\1", text)
    text = re.sub(r"\b([01]+)[Bb]\b", r"0b\1", text)
    return text


_CHAR = re.compile(r"'(\\?.)'")


def _expr(text, symbols, here, lenient=False):
    """Evaluate one expression in the context of the current symbol table."""
    text = text.strip()
    if not text:
        raise AsmError("empty expression")

    def char_sub(m):
        s = m.group(1)
        if s.startswith("\\"):
            s = {"n": "\n", "r": "\r", "t": "\t", "0": "\0",
                 "\\": "\\", "'": "'"}.get(s[1], s[1])
        return str(ord(s))

    text = _CHAR.sub(char_sub, text)
    text = _norm_number(text)
    text = re.sub(r"(?<![\w)])\$(?![\w(])", str(here), text)
    env = dict(symbols)
    env["__builtins__"] = {}
    try:
        value = eval(text, env)  # noqa: S307 - repo-local assembly source only
    except NameError as exc:
        if lenient:
            return 0   # pass 1: forward reference, resolved on pass 2
        raise AsmError(f"undefined symbol in {text!r}: {exc}") from None
    except Exception as exc:
        raise AsmError(f"bad expression {text!r}: {exc}") from None
    if not isinstance(value, int):
        raise AsmError(f"expression {text!r} is not an integer")
    return value


def _split_operands(text):
    """Split on commas that are not inside quotes or parentheses."""
    out, depth, cur, quote = [], 0, "", None
    for ch in text:
        if quote:
            cur += ch
            if ch == quote:
                quote = None
            continue
        if ch in "'\"":
            quote = ch
            cur += ch
        elif ch == "(":
            depth += 1
            cur += ch
        elif ch == ")":
            depth -= 1
            cur += ch
        elif ch == "," and depth == 0:
            out.append(cur.strip())
            cur = ""
        else:
            cur += ch
    if cur.strip():
        out.append(cur.strip())
    return out


def _parse(line):
    """Split one source line into (label, mnemonic, operands)."""
    line = line.split(";", 1)[0].rstrip()
    if not line.strip():
        return None, None, []
    label = None
    if line[:1] not in " \t":
        m = re.match(r"^([.\w]+)\s*:?\s*(.*)$", line)
        if not m:
            raise AsmError(f"cannot parse {line!r}")
        word, rest = m.group(1), m.group(2)
        had_colon = ":" in line[:len(line) - len(rest)]
        if had_colon or not _is_mnemonic(word):
            label, line = word, rest
        else:
            line = word + " " + rest
    line = line.strip()
    if not line:
        return label, None, []
    parts = line.split(None, 1)
    mnem = parts[0]
    operands = _split_operands(parts[1]) if len(parts) > 1 else []
    return label, mnem, operands


_MNEMONICS = (set(NO_OPERAND) | set(ALU) | set(CB_ROT) | {
    "LD", "INC", "DEC", "PUSH", "POP", "JP", "JR", "DJNZ", "CALL", "RET",
    "RST", "BIT", "RES", "SET", "EX", "IN", "OUT", "IM",
    "ORG", "EQU", "DB", "DW", "DS", "DEFB", "DEFW", "DEFS", "END",
})


def _is_mnemonic(word):
    return word.upper() in _MNEMONICS


def _mem(op):
    """Return the inside of a (…) operand, or None."""
    op = op.strip()
    if op.startswith("(") and op.endswith(")"):
        return op[1:-1].strip()
    return None


def _idx(op):
    """Match (IX+d)/(IY-d); return ('IX', 'd-expr') or None."""
    inner = _mem(op)
    if inner is None:
        return None
    m = re.match(r"^(I[XY])\s*([+-].*)?$", inner, re.I)
    if not m:
        return None
    return m.group(1).upper(), (m.group(2) or "+0")


def assemble(source, origin=0, symbols=None):
    """Assemble SOURCE at ORIGIN.  Returns (bytes, symbol table)."""
    syms = dict(symbols or {})
    lines = source.splitlines()
    code = bytearray()
    base = origin

    for pass_no in (0, 1):
        code = bytearray()
        pc = origin
        for lineno, raw in enumerate(lines, 1):
            label, mnem, ops = _parse(raw)
            if label is not None and (mnem is None or mnem.lower() != "equ"):
                if pass_no == 0 and label in syms and syms[label] != pc:
                    raise AsmError(f"line {lineno}: duplicate label {label}")
                syms[label] = pc
            if mnem is None:
                continue
            try:
                emitted = _encode(mnem, ops, syms, pc, label, pass_no)
            except AsmError as exc:
                raise AsmError(f"line {lineno}: {raw.strip()!r}: {exc}") from None
            if emitted is None:          # directive that moved pc itself
                continue
            if isinstance(emitted, int):  # org
                if emitted < pc and pass_no == 1:
                    raise AsmError(f"line {lineno}: org moves backwards")
                code.extend(b"\x00" * (emitted - pc))
                pc = emitted
                continue
            code.extend(emitted)
            pc += len(emitted)
        base = origin
    return bytes(code), syms


def _encode(mnem, ops, syms, pc, label, pass_no):
    m = mnem.upper()
    ev = lambda t: _expr(t, syms, pc, lenient=(pass_no == 0))  # noqa: E731

    # ---- directives ----
    if m == "EQU":
        if label is None:
            raise AsmError("equ without a label")
        syms[label] = ev(ops[0])
        return b""
    if m == "ORG":
        return ev(ops[0])
    if m == "END":
        return b""
    if m in ("DB", "DEFB"):
        out = bytearray()
        for op in ops:
            t = op.strip()
            if len(t) >= 2 and t[0] == '"' and t[-1] == '"':
                out.extend(t[1:-1].encode("ascii"))
            elif len(t) > 3 and t[0] == "'" and t[-1] == "'":
                out.extend(t[1:-1].encode("ascii"))
            else:
                out.append(ev(t) & 0xFF)
        return bytes(out)
    if m in ("DW", "DEFW"):
        out = bytearray()
        for op in ops:
            v = ev(op) & 0xFFFF
            out.extend((v & 0xFF, v >> 8))
        return bytes(out)
    if m in ("DS", "DEFS"):
        n = ev(ops[0])
        fill = ev(ops[1]) & 0xFF if len(ops) > 1 else 0
        return bytes([fill]) * n

    # ---- no-operand ----
    if m in NO_OPERAND and not ops:
        return bytes(NO_OPERAND[m])

    up = [o.upper() for o in ops]

    # ---- LD ----
    if m == "LD":
        if len(ops) != 2:
            raise AsmError("LD needs two operands")
        dst, src = ops[0].strip(), ops[1].strip()
        D, S = up[0], up[1]
        if D == "SP" and S == "HL":
            return b"\xf9"
        if D in R8 and S in R8:
            if D == "(HL)" and S == "(HL)":
                raise AsmError("LD (HL),(HL)")
            return bytes([0x40 | (R8[D] << 3) | R8[S]])
        if D in R8:
            idx = _idx(src)
            if idx:
                pre = 0xDD if idx[0] == "IX" else 0xFD
                return bytes([pre, 0x46 | (R8[D] << 3), ev(idx[1]) & 0xFF])
            inner = _mem(src)
            if inner is None:
                return bytes([0x06 | (R8[D] << 3), ev(src) & 0xFF])
            if D == "A":
                if inner.upper() == "BC":
                    return b"\x0a"
                if inner.upper() == "DE":
                    return b"\x1a"
                a = ev(inner) & 0xFFFF
                return bytes([0x3A, a & 0xFF, a >> 8])
            raise AsmError(f"unsupported LD {dst},{src}")
        idx = _idx(dst)
        if idx:
            pre = 0xDD if idx[0] == "IX" else 0xFD
            d = ev(idx[1]) & 0xFF
            if S in R8 and S != "(HL)":
                return bytes([pre, 0x70 | R8[S], d])
            return bytes([pre, 0x36, d, ev(src) & 0xFF])
        inner = _mem(dst)
        if inner is not None:
            iu = inner.upper()
            if iu == "BC" and S == "A":
                return b"\x02"
            if iu == "DE" and S == "A":
                return b"\x12"
            a = ev(inner) & 0xFFFF
            lo, hi = a & 0xFF, a >> 8
            if S == "A":
                return bytes([0x32, lo, hi])
            if S == "HL":
                return bytes([0x22, lo, hi])
            if S in ("BC", "DE", "SP"):
                return bytes([0xED, 0x43 | (RP_SP[S] << 4), lo, hi])
            if S in ("IX", "IY"):
                return bytes([0xDD if S == "IX" else 0xFD, 0x22, lo, hi])
            raise AsmError(f"unsupported LD ({inner}),{src}")
        if D in ("IX", "IY"):
            pre = 0xDD if D == "IX" else 0xFD
            inner = _mem(src)
            if inner is None:
                v = ev(src) & 0xFFFF
                return bytes([pre, 0x21, v & 0xFF, v >> 8])
            a = ev(inner) & 0xFFFF
            return bytes([pre, 0x2A, a & 0xFF, a >> 8])
        if D in RP_SP:
            inner = _mem(src)
            if inner is None:
                v = ev(src) & 0xFFFF
                return bytes([0x01 | (RP_SP[D] << 4), v & 0xFF, v >> 8])
            a = ev(inner) & 0xFFFF
            if D == "HL":
                return bytes([0x2A, a & 0xFF, a >> 8])
            return bytes([0xED, 0x4B | (RP_SP[D] << 4), a & 0xFF, a >> 8])
        raise AsmError(f"unsupported LD {dst},{src}")

    # ---- INC / DEC ----
    if m in ("INC", "DEC"):
        o = up[0]
        if o in R8:
            return bytes([(0x04 if m == "INC" else 0x05) | (R8[o] << 3)])
        if o in RP_SP:
            return bytes([(0x03 if m == "INC" else 0x0B) | (RP_SP[o] << 4)])
        if o in ("IX", "IY"):
            return bytes([0xDD if o == "IX" else 0xFD,
                          0x23 if m == "INC" else 0x2B])
        idx = _idx(ops[0])
        if idx:
            pre = 0xDD if idx[0] == "IX" else 0xFD
            return bytes([pre, 0x34 if m == "INC" else 0x35, ev(idx[1]) & 0xFF])
        raise AsmError(f"unsupported {m} {ops[0]}")

    # ---- ALU ----
    if m in ALU:
        if m in ("ADD", "ADC", "SBC") and len(ops) == 2 and up[0] == "HL":
            rp = RP_SP.get(up[1])
            if rp is None:
                raise AsmError(f"{m} HL,{ops[1]}")
            if m == "ADD":
                return bytes([0x09 | (rp << 4)])
            return bytes([0xED, (0x4A if m == "ADC" else 0x42) | (rp << 4)])
        if len(ops) == 2 and up[0] == "A":
            ops, up = ops[1:], up[1:]
        elif len(ops) == 2:
            raise AsmError(f"unsupported {m} {ops[0]},{ops[1]}")
        o = up[0]
        if o in R8:
            return bytes([0x80 | (ALU[m] << 3) | R8[o]])
        idx = _idx(ops[0])
        if idx:
            pre = 0xDD if idx[0] == "IX" else 0xFD
            return bytes([pre, 0x86 | (ALU[m] << 3), ev(idx[1]) & 0xFF])
        return bytes([ALU_IMM[m], ev(ops[0]) & 0xFF])

    # ---- stack ----
    if m in ("PUSH", "POP"):
        o = up[0]
        if o in RP_AF:
            return bytes([(0xC5 if m == "PUSH" else 0xC1) | (RP_AF[o] << 4)])
        if o in ("IX", "IY"):
            return bytes([0xDD if o == "IX" else 0xFD,
                          0xE5 if m == "PUSH" else 0xE1])
        raise AsmError(f"unsupported {m} {ops[0]}")

    # ---- control flow ----
    if m == "JP":
        if len(ops) == 1:
            if up[0] == "(HL)":
                return b"\xe9"
            if up[0] in ("(IX)", "(IY)"):
                return bytes([0xDD if "IX" in up[0] else 0xFD, 0xE9])
            v = ev(ops[0]) & 0xFFFF
            return bytes([0xC3, v & 0xFF, v >> 8])
        cc = CC.get(up[0])
        if cc is None:
            raise AsmError(f"bad condition {ops[0]}")
        v = ev(ops[1]) & 0xFFFF
        return bytes([0xC2 | (cc << 3), v & 0xFF, v >> 8])
    if m in ("JR", "DJNZ"):
        target = ops[-1]
        base = 0x18
        if m == "DJNZ":
            base = 0x10
        elif len(ops) == 2:
            cc = CC_SHORT.get(up[0])
            if cc is None:
                raise AsmError(f"{ops[0]} is not a short-jump condition")
            base = 0x20 | (cc << 3)
        dest = ev(target)
        delta = dest - (pc + 2)
        if pass_no == 1 and not -128 <= delta <= 127:
            raise AsmError(f"relative jump out of range ({delta})")
        return bytes([base, delta & 0xFF])
    if m == "CALL":
        if len(ops) == 1:
            v = ev(ops[0]) & 0xFFFF
            return bytes([0xCD, v & 0xFF, v >> 8])
        cc = CC.get(up[0])
        if cc is None:
            raise AsmError(f"bad condition {ops[0]}")
        v = ev(ops[1]) & 0xFFFF
        return bytes([0xC4 | (cc << 3), v & 0xFF, v >> 8])
    if m == "RET":
        cc = CC.get(up[0])
        if cc is None:
            raise AsmError(f"bad condition {ops[0]}")
        return bytes([0xC0 | (cc << 3)])
    if m == "RST":
        v = ev(ops[0])
        if v & ~0x38:
            raise AsmError(f"bad RST target {v:#x}")
        return bytes([0xC7 | v])

    # ---- CB group ----
    if m in CB_ROT:
        o = up[0]
        if o not in R8:
            raise AsmError(f"unsupported {m} {ops[0]}")
        return bytes([0xCB, (CB_ROT[m] << 3) | R8[o]])
    if m in ("BIT", "RES", "SET"):
        b = ev(ops[0])
        o = up[1]
        if o not in R8 or not 0 <= b <= 7:
            raise AsmError(f"unsupported {m} {ops[0]},{ops[1]}")
        base = {"BIT": 0x40, "RES": 0x80, "SET": 0xC0}[m]
        return bytes([0xCB, base | (b << 3) | R8[o]])

    # ---- misc ----
    if m == "EX":
        if up == ["DE", "HL"]:
            return b"\xeb"
        if up == ["AF", "AF'"] or up == ["AF", "AF"]:
            return b"\x08"
        if up == ["(SP)", "HL"]:
            return b"\xe3"
        raise AsmError(f"unsupported EX {ops}")
    if m == "IN":
        inner = _mem(ops[1])
        if up[0] == "A" and inner and inner.upper() != "C":
            return bytes([0xDB, ev(inner) & 0xFF])
        if inner and inner.upper() == "C" and up[0] in R8:
            return bytes([0xED, 0x40 | (R8[up[0]] << 3)])
        raise AsmError(f"unsupported IN {ops}")
    if m == "OUT":
        inner = _mem(ops[0])
        if inner and inner.upper() != "C" and up[1] == "A":
            return bytes([0xD3, ev(inner) & 0xFF])
        if inner and inner.upper() == "C" and up[1] in R8:
            return bytes([0xED, 0x41 | (R8[up[1]] << 3)])
        raise AsmError(f"unsupported OUT {ops}")
    if m == "IM":
        return bytes([0xED, {0: 0x46, 1: 0x56, 2: 0x5E}[ev(ops[0])]])

    raise AsmError(f"unknown mnemonic {mnem!r}")
