#!/usr/bin/env python3
"""Decode the M1000 V24-adaptor IR link from an Agilent MSO-X scope capture.

Channel 1 is the IR clock, channel 2 the IR data.  Accepts either the
segmented CSV export (`points/segment = N` header) or the .h5 export.

The link is synchronous: ch1 is a free-running bit clock that only runs
while a burst is in progress, and ch2 carries one return-to-zero pulse per
'1' bit, centred on the clock's rising edge.  Bits are therefore sampled in
the middle of each clock-high period.

Above that the controller runs a bit-stuffed HDLC-like framer with the line
sense inverted, which is what you would choose for an IR link: idle is 0 so
the LED is dark, the flag is 1000_0001 (the complement of HDLC's 0x7E, and
likewise the only pattern carrying six consecutive 0s), and the framer
inserts a 1 after five consecutive 0s.  Data is MSB-first.

Usage: scope_ir_decode.py CAPTURE.csv [--raw]
"""
import sys
import numpy as np

BIT_PERIOD = 122.07e-6          # 8192 bit/s
GLITCH_US = 20e-6               # pulses shorter than this are ringing
V_LO, V_HI = 1.0, 3.5           # Schmitt thresholds


def load(path):
    """Return (dt, [(ch1, ch2), ...]) — one tuple per acquisition segment."""
    if path.endswith(".h5"):
        import h5py
        with h5py.File(path, "r") as f:
            a = f["Waveforms/Channel 1/Channel 1 Data"][:]
            b = f["Waveforms/Channel 2/Channel 2 Data"][:]
            dt = float(f["Waveforms/Channel 1"].attrs["XInc"])
        return dt, [(a, b)]

    with open(path) as f:
        head = f.readline()
    npts = int(head.split("=")[1])
    d = np.loadtxt(path, delimiter=",", skiprows=3)
    dt = float(np.median(np.diff(d[:npts, 0])))
    nseg = len(d) // npts
    return dt, [(d[i * npts:(i + 1) * npts, 1],
                 d[i * npts:(i + 1) * npts, 2]) for i in range(nseg)]


def schmitt(x):
    out = np.zeros(len(x), np.int8)
    state = 0
    for i, v in enumerate(x):
        if state == 0 and v > V_HI:
            state = 1
        elif state == 1 and v < V_LO:
            state = 0
        out[i] = state
    return out


def deglitch(b, minw):
    idx = np.flatnonzero(np.diff(b)) + 1
    out = b.copy()
    for s, e in zip(np.r_[0, idx], np.r_[idx, len(b)]):
        if e - s < minw and 0 < s and e < len(b):
            out[s:e] = out[s - 1]
    return out


def decode(ch1, ch2, dt):
    """Return (bits, cells, period) for one segment, or None if idle."""
    minw = int(GLITCH_US / dt)
    clk = deglitch(schmitt(ch1), minw)
    dat = deglitch(schmitt(ch2), minw)
    rise = np.flatnonzero(np.diff(clk) == 1) + 1
    if len(rise) < 2:
        return None
    fall = np.flatnonzero(np.diff(clk) == -1) + 1
    t = rise * dt

    # least-squares fit of the bit grid, so dropped clock cells keep their slot
    k = np.round((t - t[0]) / BIT_PERIOD)
    period, origin = np.linalg.lstsq(
        np.vstack([k, np.ones_like(k)]).T, t, rcond=None)[0]

    ncell = int(round((t[-1] - origin) / period)) + 1
    bits = ["0"] * ncell
    for r in rise:                      # sample mid clock-high
        nxt = fall[fall > r]
        mid = (r + nxt[0]) // 2 if len(nxt) else r + int(30e-6 / dt)
        bits[int(round((r * dt - origin) / period))] = str(int(dat[mid]))
    # a data pulse whose clock cell was dropped still marks its slot
    for r in np.flatnonzero(np.diff(dat) == 1) + 1:
        slot = int(round((r * dt - origin) / period + 0.26))
        if 0 <= slot < ncell:
            bits[slot] = "1"
    return "".join(bits), ncell, period


FLAG = "10000001"        # = ~0x7E: six 0s bracketed by 1s


def destuff(bits):
    """Drop the 1 the framer inserts after five consecutive 0s."""
    out, run = [], 0
    i = 0
    while i < len(bits):
        if run == 5:                    # this bit was inserted, not data
            run = 0
            i += 1
            continue
        out.append(bits[i])
        run = run + 1 if bits[i] == "0" else 0
        i += 1
    return "".join(out)


def unframe(bits):
    """Return (lead_in, [byte, ...], leftover_bits) for one burst."""
    i = bits.find(FLAG)
    if i < 0:
        return None
    field = destuff(bits[i + len(FLAG):])
    whole = len(field) // 8
    return bits[:i], [int(field[j*8:(j+1)*8], 2) for j in range(whole)], field[whole*8:]


def main():
    path = sys.argv[1]
    dt, segs = load(path)
    forms = {}
    for i, (a, b) in enumerate(segs):
        r = decode(a, b, dt)
        if r is None:
            continue
        bits, ncell, period = r
        forms.setdefault(bits, []).append(i)
        if "--raw" in sys.argv:
            print(f"seg{i:3d} {ncell:3d} cells  {period*1e6:7.3f} us/bit  {bits}")

    print(f"\n{len(segs)} segments, {len(forms)} distinct bursts, "
          f"bit period {BIT_PERIOD*1e6:.2f} us ({1/BIT_PERIOD:.0f} bit/s)\n")
    for bits, segs_ in sorted(forms.items(), key=lambda kv: -len(kv[1])):
        print(f"{len(bits):3d} cells x{len(segs_):3d}  {bits}")
        u = unframe(bits)
        if u is None:
            print("                 no flag found")
            continue
        lead, data, tail = u
        print(f"                 lead-in {lead or '-':<6} flag {FLAG} "
              f"data {' '.join(f'{v:02X}' for v in data) or '-'}"
              f"{'  +' + tail if tail else ''}")


if __name__ == "__main__":
    main()
