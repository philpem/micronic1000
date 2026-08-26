# RTC (HD146818) — the indexed peripheral 08h/28h

The HD146818 is on ports 08h (register select / address latch) and
28h (data). RtcRegWrite: OUT(08)=index, OUT(28)=data. RtcRegRead:
OUT(08)=index, IN(28)=data.

## The interface (CONFIRMED at byte level)

    RtcRegWrite: OUT(08h)=index(B); OUT(28h)=data(A)
    RtcRegRead:  OUT(08h)=index(B); IN(28h)=data

I.e. port 08h = register select (address latch), port 28h = data —
exactly the 146818 programming model.

## Register map proven by firmware sequences

| Index | Function | Value/evidence |
|-------|----------|----------------|
| 00 02 04 06 07 08 09 | seconds, minutes, hours, day, month, year, weekday | written by RtcWriteTime (22AB) from buffer |
| 0A | Reg A | 0x26 periodic rate, 0x2A, 0x7A divider |
| 0B | Reg B | 0x40=PIE, 0x46=PIE+24h+binary |
| 0C | Reg C (IRQ flags, read-clears) | "tick poke" in clock self-test |
| 0D | Reg D | unused |
| 00-0F | register file block | read by RtcReadRegisterFile (ex-"CommsRxBurst16") into FD50 |

## Key routines

- RtcInit (ROM00:2084): Reg B <- 0x46 (enable periodic IRQ, binary,
  24h); calls RtcSetTimeFromBuffer with HL=20A7 boot-default block.
- RtcSetTimeFromBuffer (ROM00:20AC): DI; RegB.SET; RegA stop(0x7A);
  RtcWriteTime; RegA start(0x2A); clear SET; CALL f54e.
- RtcWriteTime (ROM00:22AB): writes 09,08,07,04,02,00,06.
- ClockSelftestTickWindow (2828): installs tick handler, counts
  periodic interrupts from the RTC -> CPU-vs-RTC-rate check.
- RtcReadRegisterFile (ex-"CommsRxBurst16", 20EF): waits RegA.UIP
  clear, then reads regs 00-09 (the time file) into FD50.
- RtcInit path writes Reg B = 0x46 (PIE + binary + 24h).
- Wake/resume (1805): reads Reg C (clear pending), then 229E
  enables PIE again (Reg B | 0x40).

## Periodic interrupt rate (from register A + self-test math)

Register A (0x0A) rate-select bits drive the periodic interrupt:

  | RegA value | DV(6:4) | RS(3:0) | periodic freq |
  | 0x26 (self-test/boot) | 010 (32.768k) | 0110 | **1024 Hz** |
  | 0x2A (divider restart after set-time) | 010 | 1010 | 64 Hz |
  | 0x7A (write-time freeze) | 111 (reset) | - | none |

ClockSelftestTickWindow verifies the rate: it arms 130 ticks (fda8),
counts inner-loop iterations (24 T-state each at 3.579545 MHz =
6.703 us), and requires the elapsed count to land in 0x4502..0x4C46
(17666..19526). At **1024 Hz** 130 ticks = 126.95 ms = **18935
iterations** - inside the window. At 64 Hz it would be 302956
iterations - far outside. So the running periodic rate is
**1024 Hz** (period ~976.6 us; 32.768 kHz / 32).

0x2A (64 Hz) appears only transiently when the time-set routine
restarts the divider; the active rate the OS measures against is
1024 Hz.

## Live-capture confirmation (emulator, Z80 + MAME-accurate io_stub)

The full set-clock / RTC-init write sequence was captured live from the
emulated firmware (`analysis/boot_hw.py`; full trace at
`/tmp/opencode/micronic_boot_io.txt`). This is the definitive,
runtime-proven register write (matches the static analysis exactly):

```
F445 47=04..00        bank selects (RAM probing)
22DF 08=0B 28=46      Reg B = 0x46  (PIE | binary | 24-hour)
22E6 08=0B            read-back verify
22DF 08=0B 28=80      Reg B SET bit (freeze update)
22DF 08=0A 28=7A      Reg A = 0x7A  (divider STOP)
22DF 08=09 28=54      WEEKDAY = 0x54   <- boot-default time
22DF 08=08 28=01      YEAR    = 0x01
22DF 08=07 28=01      MONTH   = 0x01
22DF 08=04 28=00      HOURS   = 0x00
22DF 08=02 28=00      MINUTES = 0x00
22DF 08=00 28=00      SECONDS = 0x00
22DF 08=06 28=00      DAY-OF-MONTH = 0x00
22DF 08=0A 28=2A      Reg A = 0x2A  (divider START, 1024Hz pending)
22E6 08=0C            Reg C read (tick/interrupt acknowledge)
0257                 latch restore + LCD redraw (banner path)
```

This confirms: 08h=register select, 28h=data, the exact register set
(09/08/07/04/02/00/06) and the freeze/stop/write/start sequence. The
1024Hz periodic interrupt drives the CPU INT (MAME-correct
I/O stub returns port5=0x19). With the RTC tick injected at 1024Hz
cadence the firmware boots through reset, LCD init, RTC init, link
probe and the clock self-test; the same path that stalled at HALT
previously now completes the RTC write and returns to the banner.

## Open items

- Whether RTC Reg C periodic interrupt is the sole IRQ source, and
  how the periodic-rate config gives 1024 Hz against the 130-tick
  window.
- Registers 0x0E-0x3F (146818 battery RAM, 50 bytes) - the firmware
  may use this for non-volatile data; check overlap with the FD-lands
  config copies (FE83/FE93/FC05).

Note: the external link (PLINTH/V24/side port) does NOT share the
08/28 RTC bus — it uses the 4x cluster (4Ah ctrl, 4Bh status, 4Dh TX
data, 4Eh RX data). See io-map.md and LinkBlockTx/LinkBlockRx.
## Complete RTC register map (CONFIRMED from all call sites)

| Index | HD146818 reg | Access | Code sites |
|-------|--------------|--------|------------|
| 00 | seconds | write | RtcWriteTime (22AB) |
| 01 | alarm-seconds | write | RtcSetAlarm (2158-62, B=5/3/1 loop) |
| 02 | minutes | write | RtcWriteTime |
| 03 | alarm-minutes | write | RtcSetAlarm |
| 04 | hours | write | RtcWriteTime |
| 05 | alarm-hours | write | RtcSetAlarm |
| 06 | day-of-month | write | RtcWriteTime |
| 07 | month | write | RtcWriteTime |
| 08 | year | write | RtcWriteTime |
| 09 | weekday | write | RtcWriteTime |
| 0A | Reg A (ctrl) | write 0x26=1024Hz /0x2A /0x7A stop; poll UIP bit7 | 20AC,20D9,2100 |
| 0B | Reg B (ctrl) | write 0x40(PIE)/0x46(PIE+bin+24h); read-mod-write AIE/SET | 2295/229E/20AF,20DD,216D,217B |
| 0C | Reg C (IRQ flags, read clears) | read (ack + EF00/17FD poke) | 0277,17FD,2206 |
| 0D | Reg D | unused | - |

Alarm feature: RtcSetAlarm (ROM00:2141) writes alarm regs 5/3/1 and
sets AIE (Reg B | 0x20); RtcClearAlarmInterrupt (217B) clears AIE.
The user-visible "alarm clock" in the UI drives this.
