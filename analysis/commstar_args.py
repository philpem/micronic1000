#!/usr/bin/env python3
"""Sweep the Commstar entry points for their caller arguments.

A wrapper reads an argument with ``LD HL,off / ADD HL,SP``, so ``off`` is
relative to SP *at that instant*, not to the frame base. Argument marshalling
pushes as it goes, so a naive ``off - 0Ch`` is wrong wherever a push is
outstanding -- the mistake that put C-RX-BLK's pointer at the wrong slot.

This tracks the stack delta from the routine's prologue and reports
``off - 0Ch - depth``, which is the caller's slot.
"""
import bisect

ROM = open('micronic/micron1.bin', 'rb').read()
VECTORS = 0x7D88        # ROM00 table of initial stub targets, slot i at +2i
SLOT_BASE = 0xED1C      # ram:ED1C + 4*i is the stub for slot i
FRAME = 0x0C            # SP+0Ch is the caller's last-pushed word

# SP-relative effects, by opcode.
PUSH = {0xE5, 0xD5, 0xC5, 0xF5}
POP = {0xE1, 0xD1, 0xC1, 0xF1}

# Slot -> what the routine actually dispatches. Derived, not assumed: each of
# the fifteen SessionStartDataMode (ROM00:452D) call sites pushes a distinct
# literal command index, so the mapping is one-to-one. Five slots dispatch no
# command at all -- an earlier version of this table wrongly labelled them as
# duplicate C_ABORT / C-SHUT-DOWN wrappers.
NAMES = {57: "C_ABORT", 58: "C-ANSWER", 59: "C-BEGIN-FILE", 60: "C-COMMAND",
         61: "C-DIAL", 62: "C-DROP-LINE", 63: "C-END-FILE", 64: "C-END-TX",
         65: "C-INIT-COMMS", 66: "(init session)", 67: "C-MANUAL",
         68: "C-RX-BLK", 69: "(message box)", 70: "C-RX-REC",
         71: "(solicit data block)", 72: "C-SHUT-DOWN", 73: "C-TX-BLK",
         74: "C-TX-REC", 75: "(message box)", 76: "(send data block)"}


def prologues(lo=0x3000, hi=0x7000):
    """Routine entries: LD DE,nnnn / CALL D837, the frame prologue."""
    return [a for a in range(lo, hi)
            if ROM[a] == 0x11 and ROM[a + 3:a + 6] == b'\xcd\x37\xd8']


def scan(start, end):
    """Walk a routine linearly, tracking SP, and yield its argument reads.

    Linear decoding is sound here because these wrappers are straight-line
    argument marshalling; a mis-step would show up as an absurd slot, which
    is reported rather than hidden.
    """
    a, depth = start, 0          # depth: bytes SP has moved below the frame
    while a < end:
        op = ROM[a]
        # LD HL,nnnn (21 lo hi)
        if op == 0x21:
            off = ROM[a + 1] | (ROM[a + 2] << 8)
            if ROM[a + 3] == 0x39:               # ADD HL,SP -> argument read
                if ROM[a + 4] == 0xF9:           # LD SP,HL -> stack cleanup
                    depth -= off
                    a += 5
                    continue
                yield a, off, off - FRAME - depth
                a += 4
                continue
            a += 3
            continue
        if op in PUSH:
            depth += 2
        elif op in POP:
            depth -= 2
        a += {0xCD: 3, 0xC3: 3, 0x11: 3, 0x01: 3, 0xC2: 3, 0xCA: 3,
              0xD2: 3, 0xDA: 3, 0x22: 3, 0x2A: 3, 0x32: 3, 0x3A: 3,
              0x06: 2, 0x0E: 2, 0x16: 2, 0x1E: 2, 0x26: 2, 0x2E: 2,
              0x3E: 2, 0x18: 2, 0x20: 2, 0x28: 2, 0x30: 2, 0x38: 2,
              }.get(op, 2 if op == 0xED else 1)
    return


def main():
    pro = prologues()
    for slot in range(57, 77):
        target = ROM[VECTORS + 2 * slot] | (ROM[VECTORS + 2 * slot + 1] << 8)
        i = bisect.bisect_right(pro, target) - 1
        start = pro[i] if i >= 0 and pro[i] <= target else target
        end = pro[i + 1] if i + 1 < len(pro) else start + 0x100
        args = [(a, off, s) for a, off, s in scan(start, end) if s >= 0]
        print(f"{SLOT_BASE + 4 * slot:04X}  {NAMES[slot]:14} ROM00:{target:04X} "
              f"[{start:04X}..{end - 1:04X}]")
        if not args:
            print("        no caller arguments")
        for a, off, s in sorted(args, key=lambda t: t[2]):
            print(f"        SP+{s:<3} (read at {a:04X}, off {off:#06x})")


if __name__ == '__main__':
    main()
