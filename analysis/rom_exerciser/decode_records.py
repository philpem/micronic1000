#!/usr/bin/env python3
"""Decode the link exerciser's record stream.

Input is either an MSO CSV (the same four-channel format scope_ir_decode.py
reads) or, with --hex, a file of whitespace-separated hex bytes such as an
Arduino serial log.  Every frame the exerciser emits begins on a record
boundary, so alignment is structural rather than guessed.

The headline output is the per-bit summary of LINK_STATUS.  Each record
carries the OR and the AND of every sample taken during its window, so for
each bit the three possibilities are distinguishable and exhaustive:

    always 1        OR set and AND set in every record
    always 0        OR clear in every record
    changes         some record has OR set and AND clear, or the records
                    disagree with each other

Bit 6 (HSBUSY) reading "always 0" is the negative result: the bit the
firmware waits on at ROM00:32F3 never asserts, and no external stimulus can
make it.  Anything else is the positive result, and the record counter says
when.

Usage:  decode_records.py CAPTURE.csv
        decode_records.py --hex bytes.txt
"""
import sys, pathlib

HERE = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))

MAGIC = (0xA5, 0x5A)
RECLEN = 5

# LINK_STATUS bits.  7 and 4 are named from the firmware's own tests
# (LinkWaitReady polls bit 7; ROM00:34E7 tests bit 4); 6 from ROM00:32F3.
BITNAMES = {7: "TXRDY", 6: "HSBUSY", 4: "RXBUSY"}


def frames_from_csv(path):
    from scope_ir_decode import load, decode, unframe
    dt, segs = load(path)
    out = []
    for a, b in segs:
        r = decode(a, b, dt)
        if r is None:
            continue
        u = unframe(r[0])
        if u is None:
            continue
        out.append(u[1])
    return out


def frames_from_hex(path):
    """One frame per line; blank lines and '#' comments ignored."""
    out = []
    for line in pathlib.Path(path).read_text().splitlines():
        line = line.split("#", 1)[0].strip()
        if not line:
            continue
        try:
            out.append([int(t, 16) for t in line.replace(",", " ").split()])
        except ValueError:
            continue                    # a log line that isn't hex
    return out


def main():
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    if not args:
        sys.exit(__doc__)
    frames = (frames_from_hex(args[0]) if "--hex" in sys.argv
              else frames_from_csv(args[0]))

    records, preamble, short = [], None, 0
    for f in frames:
        if len(f) >= 2 and tuple(f[:2]) == MAGIC:
            preamble = f
            continue
        if len(f) % RECLEN:
            short += 1                  # truncated by the capture window
        for i in range(len(f) // RECLEN):
            records.append(tuple(f[i*RECLEN:(i+1)*RECLEN]))

    print(f"{len(frames)} frames, {len(records)} records"
          f"{f', {short} not a whole number of records' if short else ''}")

    if preamble:
        magic, ver, lid, probe, st = (preamble[:2], *preamble[2:6])
        print(f"\npreamble  version {ver}  LINK_ID {lid:02X}  "
              f"LINK_PROBE {probe:02X}  LINK_STATUS {st:02X}")
        if ver != 4:
            print(f"  ! this decoder is written for version 4")
    else:
        print("\nno preamble frame in this capture "
              "(fine if it started after power-up)")

    if not records:
        return

    # --- counter continuity.  A gap means records were lost, not that the
    # handheld stopped: the counter is the only reliable time base.
    lost = sum(1 for p, c in zip(records, records[1:])
               if (p[0] + 1) & 0xFF != c[0])
    print(f"counter discontinuities: {lost}")

    # --- per-bit verdict
    print("\nLINK_STATUS, over every sample in every record:")
    for bit in range(7, -1, -1):
        m = 1 << bit
        ever_high = any(r[1] & m for r in records)
        ever_low = any(not (r[2] & m) for r in records)
        within = sum(1 for r in records if (r[1] & m) and not (r[2] & m))
        verdict = ("changes" if ever_high and ever_low else
                   "always 1" if ever_high else "always 0")
        note = (f"  ({within} record{'s' if within != 1 else ''} saw it both ways)" if within else "")
        print(f"  bit {bit} {BITNAMES.get(bit,''):<7s} {verdict}{note}")

    rxd = {r[3] for r in records}
    print(f"\nLINK_RXD: {len(rxd)} distinct value(s): "
          f"{' '.join(f'{v:02X}' for v in sorted(rxd)[:16])}"
          f"{' ...' if len(rxd) > 16 else ''}")

    # --- change log.  With a constant controller this is one line, which is
    # the point: it makes a negative result readable at a glance.
    side = {r[4] for r in records}
    print(f"port 2Dh: {len(side)} distinct value(s): "
          f"{' '.join(f'{v:02X}' for v in sorted(side))}")

    print("\nchanges (count: OR AND RXD SIDE):")
    prev = None
    shown = 0
    for r in records:
        key = r[1:]
        if key != prev:
            print(f"  {r[0]:02X}: {r[1]:02X} {r[2]:02X} {r[3]:02X} {r[4]:02X}")
            prev = key
            shown += 1
            if shown == 200:
                print("  ... (truncated at 200)")
                break


if __name__ == "__main__":
    main()
