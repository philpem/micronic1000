#!/usr/bin/env python3
"""Decode every InlineTableDispatch (ram:E0B2) inline table in the M1000 images.

`InlineTableDispatch` is a switch helper whose jump table is stored inline,
immediately after the CALL, instead of in a separate data block. Every call
site therefore carries its own table, and Ghidra shows those table bytes as
stray data unless they are decoded by hand. This script decodes all of them.

Table format (see doc/re-notes/inline-dispatch.md):

    CALL E0B2
    u16 count
    { u16 case_value, u16 handler } * count
    u16 default_handler

The switch value arrives in HL. The dispatcher tail-jumps to the handler, so
the handler returns to the *caller's caller*, not to the call site.

Usage:
    analysis/decode_inline_tables.py                  # all images it can find
    analysis/decode_inline_tables.py --json out.json
    analysis/decode_inline_tables.py --image ROM00=micronic/micron1.bin@0

The battery-RAM image is optional and is gitignored like the other RAM dumps.
Regenerate it from the Ghidra database with:

    getMemory().getBytes(ram:8000, buf)   # 0x8000 bytes -> analysis/battery_ram.bin
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

# CALL E0B2
CALL_DISPATCH = bytes([0xCD, 0xB2, 0xE0])
DISPATCH_ADDR = 0xE0B2

# name, path, base address the image is mapped at
DEFAULT_IMAGES = [
    ("ROM00", "micronic/micron1.bin", 0x0000),
    ("ROM01", "micronic/micron2.bin", 0x0000),
    ("RAM", "analysis/battery_ram.bin", 0x8000),
]

# A table is rejected if it fails these; a real table is small and its
# handlers point at code in the same bank or in the fixed upper RAM.
MAX_PLAUSIBLE_CASES = 64


class Image:
    def __init__(self, name: str, data: bytes, base: int):
        self.name = name
        self.data = data
        self.base = base

    def __contains__(self, addr: int) -> bool:
        return self.base <= addr < self.base + len(self.data)

    def u8(self, addr: int) -> int:
        return self.data[addr - self.base]

    def u16(self, addr: int) -> int:
        return self.u8(addr) | (self.u8(addr + 1) << 8)


def find_call_sites(image: Image) -> list[int]:
    """Return the addresses of every `CALL E0B2` in the image."""
    out = []
    start = 0
    while True:
        i = image.data.find(CALL_DISPATCH, start)
        if i < 0:
            return out
        out.append(image.base + i)
        start = i + 1


def decode_table(image: Image, call_addr: int) -> dict:
    """Decode the inline table that follows a CALL at ``call_addr``."""
    table_addr = call_addr + 3
    result = {
        "call": call_addr,
        "table": table_addr,
        "ok": False,
        "reason": None,
        "count": None,
        "cases": [],
        "default": None,
        "end": None,
    }
    try:
        count = image.u16(table_addr)
    except IndexError:
        result["reason"] = "table start past end of image"
        return result

    result["count"] = count
    if count > MAX_PLAUSIBLE_CASES:
        result["reason"] = f"implausible case count {count}"
        return result

    entries_end = table_addr + 2 + count * 4
    if (entries_end + 2) - image.base > len(image.data):
        result["reason"] = "table runs past end of image"
        return result

    for n in range(count):
        entry = table_addr + 2 + n * 4
        result["cases"].append(
            {"value": image.u16(entry), "handler": image.u16(entry + 2)}
        )
    result["default"] = image.u16(entries_end)
    result["end"] = entries_end + 2
    result["ok"] = True
    return result


def classify_target(addr: int, images: dict[str, Image], home: str) -> str:
    """Describe where a handler address lives, given the calling image."""
    if addr >= 0x8000:
        return "RAM"
    # 0000-7FFF is the banked window; a handler from ROM00 code is ROM00.
    return home


def report(images: dict[str, Image], tables: list[dict]) -> None:
    for t in tables:
        home = t["image"]
        tag = "OK " if t["ok"] else "BAD"
        print(f"\n[{tag}] {home}:{t['call']:04X}  table at {t['table']:04X}")
        if not t["ok"]:
            print(f"        rejected: {t['reason']}")
            continue
        span = t["end"] - t["table"]
        print(f"        {t['count']} case(s), {span} bytes of inline data "
              f"({t['table']:04X}-{t['end'] - 1:04X})")
        for c in t["cases"]:
            where = classify_target(c["handler"], images, home)
            print(f"          case {c['value']:#06x} ({c['value']:5d}) "
                  f"-> {where}:{c['handler']:04X}")
        where = classify_target(t["default"], images, home)
        print(f"          default            -> {where}:{t['default']:04X}")


def main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--image", action="append", default=[],
                    metavar="NAME=PATH@BASE",
                    help="override/add an image, e.g. ROM00=micronic/micron1.bin@0")
    ap.add_argument("--json", metavar="PATH", help="also write results as JSON")
    ap.add_argument("--markdown", metavar="PATH",
                    help="write a Markdown table of every site (for the RE notes)")
    ap.add_argument("--quiet", action="store_true", help="summary only")
    args = ap.parse_args(argv)

    specs = list(DEFAULT_IMAGES)
    for raw in args.image:
        name, _, rest = raw.partition("=")
        path, _, base = rest.partition("@")
        specs = [s for s in specs if s[0] != name]
        specs.append((name, path, int(base or "0", 0)))

    images: dict[str, Image] = {}
    for name, path, base in specs:
        p = ROOT / path if not Path(path).is_absolute() else Path(path)
        if not p.exists():
            print(f"[skip] {name}: {p} not found", file=sys.stderr)
            continue
        images[name] = Image(name, p.read_bytes(), base)
        print(f"[load] {name}: {p.relative_to(ROOT) if p.is_relative_to(ROOT) else p} "
              f"({len(images[name].data)} bytes @ {base:04X})")

    if not images:
        print("no images loaded", file=sys.stderr)
        return 2

    tables: list[dict] = []
    for name, img in images.items():
        for call in find_call_sites(img):
            t = decode_table(img, call)
            t["image"] = name
            tables.append(t)

    if not args.quiet:
        report(images, tables)

    good = [t for t in tables if t["ok"]]
    bad = [t for t in tables if not t["ok"]]
    total_cases = sum(t["count"] for t in good)
    print(f"\n=== {len(tables)} call sites: {len(good)} decoded, {len(bad)} rejected; "
          f"{total_cases} cases total ===")
    for name in images:
        n = sum(1 for t in tables if t["image"] == name)
        print(f"      {name}: {n} site(s)")
    for t in bad:
        print(f"      REJECTED {t['image']}:{t['call']:04X}: {t['reason']}")

    if args.json:
        Path(args.json).write_text(json.dumps(tables, indent=1))
        print(f"wrote {args.json}")

    if args.markdown:
        lines = [
            "| Call | Table | Cases | Case values | Default |",
            "|---|---|---:|---|---|",
        ]
        for t in sorted(tables, key=lambda x: (x["image"], x["call"])):
            if not t["ok"]:
                lines.append(f"| `{t['image']}:{t['call']:04X}` | — | — | "
                             f"rejected: {t['reason']} | — |")
                continue
            vals = ", ".join(f"`{c['value']:#x}`" for c in t["cases"]) or "—"
            lines.append(
                f"| `{t['image']}:{t['call']:04X}` | `{t['table']:04X}-"
                f"{t['end'] - 1:04X}` | {t['count']} | {vals} | "
                f"`{t['default']:04X}` |"
            )
        Path(args.markdown).write_text("\n".join(lines) + "\n")
        print(f"wrote {args.markdown}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
