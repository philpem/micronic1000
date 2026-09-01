#!/usr/bin/env python3
"""Decode the Commstar session state machine from ROM and emit its diagram.

The transition matrix at ROM00:692A is indexed ``table[state * 17 + command]``.
Bit 7 set marks an illegal transition; bit 7 clear means legal, and the low
seven bits are the next state. State names come from the pointer table at
ROM00:6A4A, command names from ROM00:6B67.

Everything here is read out of the ROM image, so the report and the diagram
cannot drift from the firmware.

Usage:
    analysis/decode_state_machine.py                 # report
    analysis/decode_state_machine.py --mermaid       # just the diagram
    analysis/decode_state_machine.py --check         # exit 1 on a surprise
"""
from __future__ import annotations

import argparse
import sys
from collections import deque
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
ROM00 = ROOT / "micronic" / "micron1.bin"

TABLE = 0x692A          # transition matrix
STATE_NAMES = 0x6A4A    # 16 pointers to state-name strings
CMD_NAMES = 0x6B67      # 17 pointers to command-name strings
NCMD = 17
NSTATE = 14             # rows; 6A18 onward is unrelated data

OPS = 0x731B            # {char name[5]; u8 target_state;} until an all-zero
OPS_VIA = 2             # C-COMMAND is legal from CONNECTED, so ops start there


def read_names(rom: bytes, table: int, count: int) -> list[str]:
    """Follow a pointer table to its NUL-terminated strings."""
    out = []
    for i in range(count):
        p = rom[table + 2 * i] | (rom[table + 2 * i + 1] << 8)
        end = rom.index(b"\x00", p)
        out.append(rom[p:end].decode("ascii").strip())
    return out


def operations(rom: bytes, table: int = OPS) -> list[tuple[str, int]]:
    """Read the operation table C-COMMAND indexes.

    Each 6-byte record names an operation and the session state it enters.
    ``C-COMMAND`` stages the state byte in ``ram:E491`` (ROM00:4B3D) and
    commits it with ``Session_SetState`` on a successful logon (ROM00:4C69),
    consulting neither the transition table nor the ``E48D`` mode gate. This
    is how states the matrix cannot reach are entered.
    """
    out = []
    for i in range(64):
        rec = rom[table + 6 * i:table + 6 * i + 6]
        if not any(rec):
            break
        out.append((rec[:5].split(b"\x00")[0].decode("ascii"), rec[5]))
    return out


def load(rom_path: Path = ROM00):
    rom = rom_path.read_bytes()
    states = read_names(rom, STATE_NAMES, 16)
    cmds = read_names(rom, CMD_NAMES, NCMD)
    cell = lambda s, c: rom[TABLE + s * NCMD + c]  # noqa: E731
    return rom, states, cmds, cell


def legal_edges(cell, nstate: int = NSTATE):
    """Yield (from_state, command, to_state) for every legal transition."""
    for s in range(nstate):
        for c in range(NCMD):
            v = cell(s, c)
            if not v & 0x80:
                yield s, c, v


def reachable(cell, start: int = 0, nstate: int = NSTATE) -> dict[int, list[int]]:
    """Breadth-first over legal transitions; returns state -> command path."""
    paths = {start: []}
    q = deque([start])
    while q:
        s = q.popleft()
        for c in range(NCMD):
            v = cell(s, c)
            if v & 0x80 or v in paths or v >= nstate:
                continue
            paths[v] = paths[s] + [c]
            q.append(v)
    return paths


def universal(cell, command: int, nstate: int = NSTATE):
    """States from which ``command`` is a legal transition, and its target."""
    ok, targets = [], set()
    for s in range(nstate):
        v = cell(s, command)
        if not v & 0x80:
            ok.append(s)
            targets.add(v)
    return ok, targets


def mermaid(states, cmds, cell, ops=()) -> str:
    """Render the machine, folding the two near-universal commands into a note."""
    # Commands legal from (almost) every state clutter the graph; fold them.
    fold = {}
    for c in range(NCMD):
        ok, targets = universal(cell, c)
        if len(ok) >= NSTATE - 2 and len(targets) == 1:
            fold[c] = (ok, targets.pop())

    ids = {s: states[s].replace("-", "_") for s in range(NSTATE)}
    reach = reachable(cell)

    out = ["stateDiagram-v2", "    [*] --> NOT_STARTED"]
    for s in range(NSTATE):
        out.append(f"    {ids[s]}: {states[s]}")
    for s, c, v in legal_edges(cell):
        if c in fold:
            continue
        out.append(f"    {ids[s]} --> {ids[v]}: {cmds[c]}")
    # C-COMMAND's own entries, which do not go through the table at all.
    for name, target in ops:
        if target < NSTATE:
            out.append(f'    {ids[OPS_VIA]} --> {ids[target]}: C-COMMAND "{name}"')
    # Mark the states the table alone cannot reach.
    dead = [s for s in range(NSTATE) if s not in reach]
    if dead:
        out.append("    classDef offtable stroke-dasharray: 4 4")
        out.append("    class " + ",".join(ids[s] for s in dead) + " offtable")
    return "\n".join(out)


def report(states, cmds, cell, ops=()) -> int:
    reach = reachable(cell)
    print(f"transition matrix ROM00:{TABLE:04X}, {NSTATE} states x {NCMD} commands\n")
    print("legal transitions:")
    for s, c, v in legal_edges(cell):
        print(f"  {states[s]:14} --{cmds[c]:14}--> {states[v]}")
    print("\nreachable from NOT-STARTED:")
    for s in sorted(reach):
        path = " -> ".join(cmds[c] for c in reach[s]) or "(start)"
        print(f"  {states[s]:14} {path}")
    dead = [s for s in range(NSTATE) if s not in reach]
    print("\nnot reachable through the table:")
    for s in dead:
        print(f"  {states[s]}")
    if ops:
        print(f"\noperation table ROM00:{OPS:04X} -- C-COMMAND sets these directly,")
        print("bypassing the table (ROM00:4B3D stages, ROM00:4C69 commits):")
        for i, (name, target) in enumerate(ops):
            note = "" if target in reach else "   <- off-table entry"
            print(f"  {i}  {name:6} -> {states[target]}{note}")
    # No cell may produce a state that nothing can enter -- including the
    # illegal path, where the low seven bits still become the new state.
    produced = {cell(s, c) & 0x7F for s in range(NSTATE) for c in range(NCMD)}
    never = [s for s in dead if s not in produced]
    print(f"\nof those, never produced by ANY cell (legal or illegal): "
          f"{', '.join(states[s] for s in never) or 'none'}")
    for c in (4, 16):
        ok, targets = universal(cell, c)
        print(f"\n{cmds[c]}: legal from {len(ok)}/{NSTATE} states -> "
              f"{', '.join(states[t] for t in targets)}")
        if len(ok) < NSTATE:
            missing = [states[s] for s in range(NSTATE) if s not in ok]
            print(f"  illegal from: {', '.join(missing)}")
    return 0


def main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--mermaid", action="store_true", help="emit only the diagram")
    ap.add_argument("--rom", type=Path, default=ROM00)
    args = ap.parse_args(argv)

    rom, states, cmds, cell = load(args.rom)
    ops = operations(rom)
    if args.mermaid:
        print(mermaid(states, cmds, cell, ops))
        return 0
    return report(states, cmds, cell, ops)


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
