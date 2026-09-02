#!/usr/bin/env python3
"""Test the assembled decoder.

Two levels, because they fail differently:

  bare      the decoder alone on a bare CPU, fed a synthetic width table.
            Fast, and a failure here is a bug in the decoder.
  firmware  the whole path -- wand model, the ROM's capture loop, the hook,
            then BDOS 03h.  Slow, and a failure here with `bare` passing
            points at the installation or the contract, not the algorithm.

    python3 tools/run_tests.py --binary build/decoder.bin --origin 0x9000
    python3 tools/run_tests.py --binary build/decoder.bin --firmware

Must be run with the interpreter that has the `z80` module -- that is
../analysis/venv/bin/python3, which the Makefile uses.
"""
import argparse
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent.parent
sys.path.insert(0, str(ROOT / "analysis"))
sys.path.insert(0, str(HERE))

import upc as upcmod                                   # noqa: E402
from micronic.barcode import encode_code39             # noqa: E402

WIDTH_TABLE = 0xF9B5      # where the firmware leaves the captured widths
PARAM_PTR = 0xFBB9
PARAM_COUNT = 0xFBBB
SENTINEL = 0xE000


def bare_run(code, origin, widths):
    """Run the decoder on a bare CPU; returns the bytes it published."""
    import z80
    mem = bytearray(0x10000)
    mem[origin:origin + len(code)] = code
    for i, w in enumerate(widths):
        mem[WIDTH_TABLE + 2 * i] = w & 0xFF
        mem[WIDTH_TABLE + 2 * i + 1] = w >> 8
    mem[PARAM_PTR] = WIDTH_TABLE & 0xFF
    mem[PARAM_PTR + 1] = WIDTH_TABLE >> 8
    mem[PARAM_COUNT] = len(widths) & 0xFF
    mem[PARAM_COUNT + 1] = len(widths) >> 8
    mem[SENTINEL] = SENTINEL & 0xFF
    mem[SENTINEL + 1] = SENTINEL >> 8

    m = z80.Z80Machine()
    m.set_memory_block(0, bytes(mem))
    m.set_read_callback(lambda a: mem[a & 0xFFFF])
    m.set_write_callback(lambda a, v: mem.__setitem__(a & 0xFFFF, v & 0xFF))
    m.sp = SENTINEL
    m.pc = origin
    m.set_breakpoint(SENTINEL)
    for _ in range(20000):
        m.ticks_to_stop = 2000
        m.run()
        if (m.pc & 0xFFFF) == SENTINEL:
            break
    else:
        raise AssertionError(f"decoder never returned (pc={m.pc:04X})")

    n = mem[PARAM_COUNT] | (mem[PARAM_COUNT + 1] << 8)
    p = mem[PARAM_PTR] | (mem[PARAM_PTR + 1] << 8)
    return bytes(mem[p:p + n])


def upc_widths(eleven, module=12, break_check=False):
    d = [int(c) for c in eleven]
    check = upcmod.check_digit(d)
    d.append((check + 5) % 10 if break_check else check)
    return upcmod.widths(d, module=module, validate=not break_check), \
        "".join(str(x) for x in d).encode()


def bare_suite(code, origin):
    cases = []
    for text in ("A1", "HELLO", "12345", "CODE-39", "$100.00"):
        cases.append((f"Code 39 {text!r}", encode_code39(text), text.encode()))
    for eleven in ("03600029145", "01234567890", "72527273070"):
        w, expect = upc_widths(eleven)
        cases.append((f"UPC-A {expect.decode()}", w, expect))
    # A slow scan: same symbol, wider modules.  Exercises the fact that the
    # decoder calibrates from the symbol rather than assuming a width.
    w, expect = upc_widths("03600029145", module=40)
    cases.append((f"UPC-A {expect.decode()} (slow scan)", w, expect))
    w, _ = upc_widths("03600029145", break_check=True)
    cases.append(("UPC-A with a bad check digit", w, b""))
    cases += [
        ("59 equal-width elements", [12] * 59, b""),
        ("truncated Code 39", encode_code39("A1")[:20], b""),
        ("empty capture", [], b""),
        ("over-long count is clamped", encode_code39("A1") + [12] * 200, b""),
    ]

    bad = 0
    for name, widths, expect in cases:
        try:
            got = bare_run(code, origin, widths)
        except AssertionError as exc:
            print(f"  FAIL  {name}: {exc}")
            bad += 1
            continue
        if got == expect:
            print(f"  ok    {name}" + (f" -> {got.decode()}" if got else " -> rejected"))
        else:
            print(f"  FAIL  {name}: expected {expect!r}, got {got!r}")
            bad += 1
    return bad


def firmware_suite(binary, text="A1", widths=None):
    """Drive the whole path in the emulator, as an application would see it.

    `widths` feeds raw element widths instead of a Code 39 encoding, which
    is how a UPC symbol gets in: the harness's --barcode-scan only speaks
    Code 39.
    """
    harness = ROOT / "analysis" / "boot_hw.py"
    hexed = binary.read_bytes().hex()
    # The machine has to be walked past its banner and workstation prompt
    # before a scan means anything; without these steps the run simply
    # stalls at "To Continue Press>>" and reports nothing.
    boot = ["--no-lcd", "--max-slices", "60000", "--expect-timeout", "45000",
            "--expect", "To Continue Press>>:\r",
            "--expect", "Enter the,Workstation:\r12345678\r",
            "--expect", "Main Menu"]
    feed = (["--barcode-widths", ",".join(str(w) for w in widths)]
            if widths else ["--barcode-scan", text])
    cmd = ([sys.executable, str(harness)] + boot + feed +
           ["--barcode-hook", hexed, "--barcode-bdos",
            "--barcode-expect", text])
    proc = subprocess.run(cmd, cwd=ROOT, text=True, stdout=subprocess.PIPE,
                          stderr=subprocess.STDOUT, timeout=900, check=False)
    ok = "[barcode] PASS" in proc.stdout
    for line in proc.stdout.splitlines():
        if "[barcode]" in line:
            print("  " + line.strip())
    return 0 if ok else 1


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--binary", type=Path, required=True)
    ap.add_argument("--origin", type=lambda s: int(s, 0), default=0x9000)
    ap.add_argument("--firmware", action="store_true",
                    help="also drive the full path in the emulator (slow)")
    args = ap.parse_args()

    code = args.binary.read_bytes()
    print(f"{args.binary} ({len(code)} bytes, linked for {args.origin:04X}h)")
    print("bare CPU:")
    bad = bare_suite(code, args.origin)

    if args.firmware:
        print("through the firmware:")
        print("  Code 39 'A1':")
        bad += firmware_suite(args.binary, "A1")
        w, expect = upc_widths("03600029145")
        print(f"  UPC-A {expect.decode()}:")
        bad += firmware_suite(args.binary, expect.decode(), widths=w)

    print("FAILED" if bad else "all passed")
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
