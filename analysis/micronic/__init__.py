"""micronic - reusable model of the Micronic 1000 IR/link protocol.

Provides:
  rtc.RTC146818   - HD146818 register model (tick cadence from Reg A)
  proto.LinkPeer/Link - raw byte-latch scaffold for the 4x transport
    (no frame/session grammar; numeric types 2,3,4 and reply words
    are observed numeric triggers only)
  proto constants - ports, observed numeric types/reply words
  barcode         - port-2Dh wand model, Code 39 codec, and a Code 39
                    decode hook in Z80 for the FBC2 hook vector
  z80asm          - small two-pass Z80 assembler for injected payloads

Intended consumers: the emulation harnesses and evidence-scoped host tools.
"""
from . import rtc
from . import proto
from . import z80asm
from . import barcode

__all__ = ["rtc", "proto", "z80asm", "barcode"]
