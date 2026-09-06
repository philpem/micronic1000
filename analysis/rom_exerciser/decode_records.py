#!/usr/bin/env python3
"""Decode the link exerciser's record stream.

Input is either an MSO CSV (the same four-channel format scope_ir_decode.py
reads) or, with --hex, a file of whitespace-separated hex bytes such as an
Arduino serial log, one frame per line.  Every frame the exerciser emits
begins on a record boundary, so alignment is structural rather than guessed.

    record   COUNT OR AND RXD SIDE CTRL

OR and AND are the sticky OR and AND of every LINK_STATUS sample taken during
the record's window, so for each bit the three possibilities are
distinguishable and exhaustive: always 1, always 0, or changed.  COUNT's top
two bits are the phase.

The bit that matters is 6, HSBUSY.  The firmware asserts it by arming the
handshake and then waits at ROM00:32F3 for it to go CLEAR, giving up after
9.92 ms and reporting 238.  So the reading to look for is phase 1:

    high throughout   the handshake never completes -- exactly the state the
                      firmware dies in, now directly observed
    goes low          it completes; if it took longer than 9.92 ms the
                      firmware's timeout is the whole problem
    never high        our arm is not what asserts it

Usage:  decode_records.py CAPTURE.csv
        decode_records.py --hex bytes.txt
"""
import sys, pathlib

HERE = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))

MAGIC = (0xA5, 0x5A)
RECLEN = 8
VER = 10

PHASES = {0: "baseline", 1: "TX armed", 2: "RX armed", 3: "CTRL sweep"}

# LINK_STATUS bits, all named from the firmware's own polls.
BITNAMES = {7: "TXRDY", 6: "HSBUSY", 0: "RX byte"}


def frames_from_csv(path):
    from scope_ir_decode import load, decode, unframe
    dt, segs = load(path)
    out = []
    for a, b in segs:
        r = decode(a, b, dt)
        if r is None:
            continue
        u = unframe(r[0])
        if u is not None:
            out.append(u[1])
    return out


def frames_from_hex(path):
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


def verdict(recs, bit):
    """(text, saw_high, saw_low) for one LINK_STATUS bit over some records."""
    m = 1 << bit
    high = any(r[1] & m for r in recs)
    low = any(not (r[2] & m) for r in recs)
    both = sum(1 for r in recs if (r[1] & m) and not (r[2] & m))
    text = ("changes" if high and low else "always 1" if high else "always 0")
    if both:
        text += f" ({both} record{'s' if both != 1 else ''} saw it both ways)"
    return text, high, low


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
        ver, lid, pstat, st = preamble[2:6]
        print(f"\npreamble  version {ver}  LINK_ID {lid:02X}  "
              f"LINK_STATUS after reset {pstat:02X}, after frame open {st:02X}")
        if ver != VER:
            print(f"  ! this decoder is written for version {VER}")
    else:
        print("\nno preamble frame in this capture "
              "(fine if it started after power-up)")

    if not records:
        return

    lost = sum(1 for p, c in zip(records, records[1:])
               if (p[0] + 1) & 0xFF != c[0])
    print(f"counter discontinuities: {lost}")
    trips = sum(1 for p, c in zip(records, records[1:]) if p[6] != c[6])
    print(f"watchdog trips: {trips}"
          + ("   <- some LINK_CTRL value stalled the transmitter"
             if trips else "   (no LINK_CTRL value stopped the controller)"))

    # --- LINK_STATUS per port per phase.  The phase is the top two bits of
    # COUNT; the port is LINK_CTRL bit 1, which LinkPortSelect sets: bit 1 set
    # means the wire id had bit 5 CLEAR (the 43h path), bit 1 clear means it
    # had bit 5 SET (the 63h path).  Which physical window each drives is what
    # the run is measuring -- watch the unit, not this output.
    for portbit, idname in ((0, "id bit5 SET (63h) = V24 ADAPTOR, top port"),
                            (2, "id bit5 clear (43h) = PLINTH, back port")):
        pr = [r for r in records if (r[5] & 2) == portbit]
        if not pr:
            continue
        print(f"\n=== LINK_CTRL bit 1 {'set' if portbit else 'clear'}"
              f" -- {idname}, {len(pr)} records ===")
        report_phases(pr)

    sweep_report(records)
    side = sorted({r[4] for r in records})
    print(f"\nport 2Dh: {' '.join(f'{v:02X}' for v in side)}")
    keys = sorted({r[7] for r in records} - {0xFF})
    if keys:
        print("keypad indices seen (col*6+row): "
              + " ".join(f"{k}=c{k//6}r{k%6}" for k in keys))
    else:
        print("keypad: no key seen held during the capture")


def report_phases(records):
    for ph in range(4):
        recs = [r for r in records if r[0] >> 6 == ph]
        if not recs:
            continue
        ctrls = sorted({r[5] for r in recs})
        print(f"  phase {ph}  {PHASES[ph]}  ({len(recs)} records, "
              f"LINK_CTRL {' '.join(f'{c:02X}' for c in ctrls[:8])}"
              f"{' ...' if len(ctrls) > 8 else ''})")
        for bit in range(7, -1, -1):
            text, high, low = verdict(recs, bit)
            if text == "always 0" and bit not in BITNAMES:
                continue                # keep the unknown-and-idle bits quiet
            print(f"      bit {bit} {BITNAMES.get(bit,''):<8s} {text}")
        rxd = {r[3] for r in recs}
        if rxd != {0}:
            print(f"      LINK_RXD  {' '.join(f'{v:02X}' for v in sorted(rxd))}")
        wd = sum(1 for a, b in zip(recs, recs[1:]) if a[6] != b[6])
        if wd:
            print(f"      watchdog  {wd} trip(s) in this phase")


def sweep_report(records):
    # --- phase 3 wants a per-CTRL-value breakdown, not a per-phase one
    sweep = [r for r in records if r[0] >> 6 == 3]
    if sweep:
        base = {}
        for r in sweep:
            base.setdefault(r[5], []).append(r)
        odd = [(c, rs) for c, rs in sorted(base.items())
               if verdict(rs, 6)[0] != verdict(sweep, 6)[0]
               or any(r[3] for r in rs) or verdict(rs, 0)[1]
               or any(a[6] != b[6] for a, b in zip(rs, rs[1:]))]
        print(f"\nCTRL sweep: {len(base)} value(s) seen, "
              f"{len(odd)} that did something")
        for c, rs in odd[:32]:
            wd = sum(1 for a, b in zip(rs, rs[1:]) if a[6] != b[6])
            print(f"    {c:02X}: OR {max(r[1] for r in rs):02X}  "
                  f"AND {min(r[2] for r in rs):02X}  "
                  f"RXD {' '.join(f'{v:02X}' for v in sorted({r[3] for r in rs}))}"
                  f"{f'  STALLED ({wd} watchdog trips)' if wd else ''}")


if __name__ == "__main__":
    main()
