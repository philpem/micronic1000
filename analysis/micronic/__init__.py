"""micronic - reusable model of the Micronic 1000 IR/link protocol.

Provides:
  rtc.RTC146818   - HD146818 register model (tick cadence from Reg A)
  proto.LinkPeer/Link - raw byte-latch scaffold for the 4x transport
    (no frame/session grammar; numeric types 2,3,4 and reply words
    are observed numeric triggers only)
  proto constants - ports, observed numeric types/reply words

Intended consumers: the emulation harnesses and evidence-scoped host tools.
"""
from . import rtc
from . import proto

__all__ = ["rtc", "proto"]
