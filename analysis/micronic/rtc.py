#!/usr/bin/env python3
"""micronic.rtc - MC146818/HD146818 model used by the Micronic 1000.

This is the real-time-clock model behind the firmware's "tick" source.
It is deliberately hardware-accurate so that ANY consumer (emulator,
test harness, or a real IR-link adapter that must reproduce the clock)
gets the same *periodic interrupt* cadence the firmware programs.

The firmware writes Register A (0x0A) with a rate-select nibble RS[3:0]
and Register B (0x0B) control bits including PIE (bit6, periodic
interrupt enable). The periodic output pulses once per RS-selected
period; that pulse is what drives the Z80 INT line (MAME wires
mc146818.irq -> cpu INT, and the firmware's own clock self-test
measures the same rate).

The table below is the standard MC146818/DS12887 rate table.
"""

# MC146818 periodic-rate table: RS[3:0] -> period in seconds when the
# divider is 32.768kHz (DV2..0 = 010). Row 0 disables the output.
# Standard MC146818 datasheet values.
PERIODIC_PERIODS = {
    # RS: period (seconds), frequency (Hz)
    0x0: None,            # none / disabled
    0x1: 1 / 32768.0,     # 30.5176 us -> 32768 Hz
    0x2: 1 / 16384.0,     # 61.035 us  -> 16384 Hz
    0x3: 1 / 8192.0,      # 122.07 us  -> 8192 Hz
    0x4: 1 / 4096.0,      # 244.14 us  -> 4096 Hz
    0x5: 1 / 2048.0,      # 488.28 us  -> 2048 Hz
    0x6: 1 / 1024.0,      # 976.56 us  -> 1024 Hz   <-- firmware default
    0x7: 1 / 512.0,
    0x8: 1 / 256.0,
    0x9: 1 / 128.0,
    0xA: 1 / 64.0,
    0xB: 1 / 32.0,
    0xC: 1 / 16.0,
    0xD: 1 / 8.0,
    0xE: 1 / 4.0,
    0xF: 0.5,             # 2 Hz
}


class RTC146818:
    """Minimal HD146818 register model exposing the periodic tick.

    Only the fields the Micronic firmware exercises are modelled:
      reg 0x0A  Register A:  DV divider bits + RS rate-select nibble
      reg 0x0B  Register B:  PIE + SET + 24/12 + DM + SQWE ...
      reg 0x0C  Register C:  IRQF/PF flags (cleared on read)
    The 64-byte clock/RAM file is stored but not time-flowing; the
    firmware drives this chip as a tick source + write-once store.
    """

    class Reg:
        # Register A (0x0A): bits
        RS   = 0x0F   # rate select
        DV   = 0x70   # divider / oscillator control
        UIP  = 0x80   # update in progress (bit7)
        # Register B (0x0B): bits
        PIE  = 0x40   # periodic interrupt enable
        SET  = 0x80   # update ended / free-run yes.
        AIE  = 0x20   # alarm interrupt enable
        UIE  = 0x10
        SQWE = 0x08
        DM   = 0x04   # binary (vs BCD)
        H24  = 0x02   # 24h
        DSE  = 0x01

    def __init__(self, reg_a=0x26, reg_b=0x46):
        self._a = reg_a & 0xFF
        self._b = reg_b & 0xFF
        self._c = 0x00
        # clock file: [0]=sec,[2]=min,[4]=hr,[6]=day,[7]=mon,[8]=year,[9]=weekday
        self.file = bytearray(64)
        self._set_boot_time()

    def _set_boot_time(self):
        # match the firmware's boot-default time file from the trace:
        # weekday=0x54 year=1 month=1 hours=0 min=0 sec=0 day=1
        self.file[9] = 0x54
        self.file[8] = 0x01
        self.file[7] = 0x01
        self.file[6] = 0x01
        self.file[4] = 0x00
        self.file[2] = 0x00
        self.file[0] = 0x00

    @property
    def rate_select(self):
        return self._a & self.Reg.RS

    @property
    def periodic_period(self):
        return PERIODIC_PERIODS.get(self.rate_select)

    @property
    def periodic_hz(self):
        p = self.periodic_period
        return 1.0/p if p else 0.0

    @property
    def pie_enabled(self):
        return bool(self._b & self.Reg.PIE)

    @property
    def set_bit(self):
        return bool(self._b & self.Reg.SET)

    def addr_port_w(self, val):
        """Select register (port 08h)."""
        self.sel = val & 0xFF

    def data_w(self, val):
        raise NotImplementedError("use reg_addr/reg_write")

    def reg_write(self, idx, val):
        val &= 0xFF
        idx &= 0xFF
        if idx == 0x0A:
            self._a = val
        elif idx == 0x0B:
            self._b = val
        elif 0 <= idx <= 0x0F:
            self.file[idx] = val
        # other addresses are RAM/RTC RAM - ignore for cadence

    def reg_read(self, idx):
        idx &= 0xFF
        if idx == 0x0A:
            return self._a
        if idx == 0x0B:
            return self._b
        if idx == 0x0C:
            # reg C: on read, return flags then clear (PIE-fired)
            pf = self._c
            self._c = 0
            return pf
        if idx == 0x0D:
            return 0x80  # valid RAM/battery
        return self.file[idx] & 0xFF

    def push_tick(self):
        """Called by a periodic timer at the programmed period."""
        if self.pie_enabled and not self.set_bit:
            self._c |= 0xC0   # IRQF + PF