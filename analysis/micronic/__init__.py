"""micronic - reusable model of the Micronic 1000 IR/link protocol.

Provides:
  rtc.RTC146818   - HD146818 register model (tick cadence from Reg A)
  proto.Frame     - the wire frame [len][type][cmd][payload]
  proto.Link      - the 4x byte transport (adapter-facing)
  proto constants - ports, reply prefixes, command ids

Intended consumers: the emulation harness (boot_hw.py) and a future
IR link adapter / host program that must talk to the M1000.
"""
from . import rtc
from . import proto

__all__ = ["rtc", "proto"]