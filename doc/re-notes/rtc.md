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
| 00 | seconds | written by RtcWriteTime (22AB) |
| 01 | alarm seconds | written by RtcSetAlarm (2158-62) |
| 02 | minutes | written by RtcWriteTime |
| 03 | alarm minutes | written by RtcSetAlarm |
| 04 | hours | written by RtcWriteTime |
| 05 | alarm hours | written by RtcSetAlarm |
| 06 | day-of-week (weekday) | written by RtcWriteTime |
| 07 | day-of-month | written by RtcWriteTime |
| 08 | month | written by RtcWriteTime |
| 09 | year | written by RtcWriteTime |
| 0A | Reg A | 0x26 periodic rate, 0x2A, 0x7A divider; UIP bit7 polled |
| 0B | Reg B | 0x40=PIE, 0x46=PIE+24h+binary |
| 0C | Reg C (IRQ flags, read-clears) | "tick poke" in clock self-test |
| 0D | Reg D | unused |
| 00-09 | time register file | read by RtcReadRegisterFile (20EF) into g_abRtcRegisterSnapshot (FD50) — 10 bytes |

`RtcWriteTime` (ROM00:22AB) writes registers 09,08,07,04,02,00,06
(year/month/day-of-month/hours/min/sec/day-of-week) from the caller
buffer. `RtcSetTimeFromBuffer` (ROM00:20AC) wraps it with the standard
SET-bit freeze → stop → write → restart → clear step. `RtcInit`
(ROM00:2084) writes Reg B <- 0x46 and loads a default time block
(source ROM00:20A7).

## BDOS eight-byte RTC record

Canonical layout used by BDOS FCh/FDh/FFh (`DE` points to an 8-byte
buffer; see `../manual/bdos-reference.md` and
`../manual/programmer-guide.md` which link here). Offsets are
little-endian byte indices in that buffer.

| Offset | BDOS FCh (set, ROM00:1150) | BDOS FDh (get, ROM00:113E) | BDOS FFh (alarm, ROM00:112D) |
|--------|----------------------------|----------------------------|------------------------------|
| +0 | metadata: byte copied to RTC scratch state but **RTC ignored** (not written to any RTC register) | metadata: byte returned from `g_bRtcRecordMetadata` (initialized `13h` at `ROM00:2084` / `RtcInit`) | metadata: byte copied but unused (FF path copies it, never programs RTC) — mechanics CONFIRMED, **LIKELY century `19`**, exact meaning **OPEN** |
| +1 | **year** → RTC reg `09h` | **year** ← RTC reg `09h` | copied unused |
| +2 | **month** → RTC reg `08h` | **month** ← RTC reg `08h` | software date gate — compared by `RTC_AlarmDateMatches` (`ROM00:223E`, formerly `Link_StatusCompare_FD4B`) against current date via `g_bRtcAlarmDayOfMonth`/`g_bRtcAlarmMonth` |
| +3 | **day-of-month** → RTC reg `07h` | **day-of-month** ← RTC reg `07h` | software date gate — same `RTC_AlarmDateMatches` comparison |
| +4 | **hour** → RTC reg `04h` | **hour** ← RTC reg `04h` | **alarm hours** → RTC reg `05h` |
| +5 | **minute** → RTC reg `02h` | **minute** ← RTC reg `02h` | **alarm minutes** → RTC reg `03h` |
| +6 | **second** → RTC reg `00h` | **second** ← RTC reg `00h` | **alarm seconds** → RTC reg `01h` |
| +7 | **day-of-week** → RTC reg `06h` | **day-of-week** ← RTC reg `06h` | copied unused — exact weekday convention **OPEN**, `0=Sunday` **LIKELY** from default `1984-01-01` (Sunday) |

**ABI properties (CONFIRMED):**

* Normal initialized ABI is **raw binary, 24-hour**. `RtcInit`
  (`ROM00:2084`) programs Reg B = `46h` (`PIE | binary | 24h`), and
  firmware performs **no conversion or range validation** on any
  field.
* Service identities from dispatch bytes (wrapped table `ROM00:36EE` →
  `ram:F1D1`): `FCh=ROM00:1150` set, `FDh=ROM00:113E` get,
  `FEh=ROM00:1122` timed wait (`Bdos_InternalTimedWait`), `FFh=ROM00:112D`
  alarm (`BdosFfAlarmControl`).
* `FFh` both paths poll UIP: `DE=0` clears `AIE` (Reg B bit5 clear) and
  non-zero `DE` programs alarm regs `01h/03h/05h` then sets `AIE`;
  **both poll `UIP` (Reg A bit7) before touching Reg B** — permanent
  `UIP` blocks either path (no return).
* Alarm preamble after `UIP` clears: firmware attempts
  `Reg A <- Reg A | 80h` (read-modify-write Reg A setting bit7), then
  `Reg A <- 2Ah` (divider restart). Intended effect **OPEN** / likely
  ineffective because `UIP` is read-only on the HD146818 — the `|80h`
  write has no documented effect — then `2Ah` is written regardless.

Evidence: `RtcInit` `ROM00:2084-20D0` (Reg B `46h`, `g_bRtcRecordMetadata`
init `13h`), `RtcSetTimeFromBuffer` `ROM00:20AC` (SET freeze, Reg A
`7Ah` stop / `2Ah` start), `RtcWriteTime` `ROM00:22AB` (writes
`09/08/07/04/02/00/06`), `RtcReadRegisterFile` `ROM00:20EF` (UIP poll,
reads `00h..09h` → `g_abRtcRegisterSnapshot`), `BdosSetRtcTime`
`ROM00:1150`, `BdosGetRtcTime` `ROM00:113E`, `Bdos_InternalTimedWait`
`ROM00:1122`, `BdosFfAlarmControl` `ROM00:112D` (UIP poll both paths,
`DE=0` clear vs program `01/03/05` + `AIE`), `RTC_AlarmDateMatches`
`ROM00:223E` (`g_bRtcAlarmDayOfMonth`/`g_bRtcAlarmMonth` date gate),
`RtcClearAlarmInterrupt` `ROM00:217B` (AIE clear).

## Key routines

- RtcInit (ROM00:2084): Reg B <- 0x46 (enable periodic IRQ, binary,
  24h); calls RtcSetTimeFromBuffer with HL=20A7 boot-default block;
  initializes `g_bRtcRecordMetadata` to `13h`.
- RtcSetTimeFromBuffer (ROM00:20AC): DI; RegB.SET; RegA stop(0x7A);
  RtcWriteTime; RegA start(0x2A); clear SET; CALL f54e.
- RtcWriteTime (ROM00:22AB): writes 09,08,07,04,02,00,06.
- ClockSelftestTickWindow (2828): installs tick handler, counts
  periodic interrupts from the RTC -> CPU-vs-RTC-rate check.
- RtcReadRegisterFile (ex-"CommsRxBurst16", 20EF): waits RegA.UIP
  clear, then reads regs 00h..09h (10 bytes, the time file) into
  g_abRtcRegisterSnapshot (FD50).
- RtcInit path writes Reg B = 0x46 (PIE + binary + 24h).
- Wake/resume (1805): reads Reg C (clear pending), then 229E
  enables PIE again (Reg B | 0x40).

## Periodic interrupt rate (from register A + self-test math)

Register A (0x0A) rate-select bits drive the periodic interrupt:

  | RegA value | DV(6:4) | RS(3:0) | periodic freq |
  | 0x26 (self-test/boot) | 010 (32.768k) | 0110 | **1024 Hz** |
  | 0x2A (divider restart after set-time) | 010 | 1010 | 64 Hz |
  | 0x7A (write-time freeze) | 111 (reset) | - | none |

The owner supplies the **3.6864 MHz** Z80 clock rate (corrected 2026-09-03;
this passage previously said 3.579545 MHz). ClockSelftestTickWindow verifies
the periodic interrupt rate: it arms 130 ticks (fda8) and counts inner-loop
iterations at `ROM00:2844` (`INC BC / LD A,B / OR C / JP NZ` = 6+4+4+10 =
24 T-states, byte-verified), requiring the elapsed count to land in
0x4502..0x4C46 (17666..19526). At **1024 Hz**, 130 ticks = 126.953 ms =
**19500 iterations** ignoring interrupt overhead. At 64 Hz it would be 312000
iterations - far outside. So the running periodic rate is **1024 Hz**
(period ~976.6 us; 32.768 kHz / 32).

Note that 19500 sits only 26 counts below the window's upper bound, which
looks tight until the interrupt cost is included: the 1024 Hz handler fires
130 times during the measured interval, and at a plausible ~150 T-states per
entry that removes ~810 iterations, putting the expected count near 18700 -
close to the window's midpoint of 18596. The naive figure is therefore **not**
a usable cross-check on the clock rate in either direction without accounting
for the ISR, and none is attempted here.

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
22DF 08=09 28=54      YEAR    = 0x54   <- boot-default time
22DF 08=08 28=01      MONTH   = 0x01
22DF 08=07 28=01      DAY-OF-MONTH = 0x01
22DF 08=04 28=00      HOURS   = 0x00
22DF 08=02 28=00      MINUTES = 0x00
22DF 08=00 28=00      SECONDS = 0x00
22DF 08=06 28=00      DAY-OF-WEEK = 0x00
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
- `g_bRtcRecordMetadata` byte +0 exact meaning (LIKELY century `19`,
  possibly related to `FC05` config) — **OPEN**.
- Day-of-week numbering convention for reg `06h` (LIKELY `0=Sunday`)
  — **OPEN**; default `1984-01-01 Sunday` suggests it but no handler
  enforces it.
- Firmware performs no range validation on any RTC field — **OPEN**
  whether callers may program out-of-range values.

Note: the external link (PLINTH/V24/side port) does NOT share the
08/28 RTC bus — it uses the 4x cluster (4Ah ctrl, 4Bh status, 4Dh TX
data, 4Eh RX data). See io-map.md and LinkBlockTx/LinkBlockRx.
## Complete RTC register map (CONFIRMED from all call sites)

| Index | HD146818 reg | Access | Code sites |
|-------|--------------|--------|------------|
| 00 | seconds | read/write | RtcWriteTime (22AB), RtcReadRegisterFile (20EF) |
| 01 | alarm-seconds | write | RtcSetAlarm (2158-62, B=5/3/1 loop) |
| 02 | minutes | read/write | RtcWriteTime, RtcReadRegisterFile |
| 03 | alarm-minutes | write | RtcSetAlarm |
| 04 | hours | read/write | RtcWriteTime, RtcReadRegisterFile |
| 05 | alarm-hours | write | RtcSetAlarm |
| 06 | day-of-week (weekday) | read/write | RtcWriteTime, RtcReadRegisterFile |
| 07 | day-of-month | read/write | RtcWriteTime, RtcReadRegisterFile; RTC_AlarmDateMatches date gate |
| 08 | month | read/write | RtcWriteTime, RtcReadRegisterFile; RTC_AlarmDateMatches date gate |
| 09 | year | read/write | RtcWriteTime, RtcReadRegisterFile |
| 0A | Reg A (ctrl) | write 0x26=1024Hz /0x2A /0x7A stop; poll UIP bit7; read-mod-write `|80h` in FF preamble | 20AC,20D9,2100, FF preamble |
| 0B | Reg B (ctrl) | write 0x40(PIE)/0x46(PIE+bin+24h); read-mod-write AIE/SET | 2295/229E/20AF,20DD,216D,217B |
| 0C | Reg C (IRQ flags, read clears) | read (ack + EF00/17FD poke) | 0277,17FD,2206 |
| 0D | Reg D | unused | - |

Alarm feature: RtcSetAlarm (ROM00:2141) writes alarm regs 05/03/01 and
sets AIE (Reg B | 0x20); RtcClearAlarmInterrupt (217B) clears AIE.
The FF alarm path's date fields (+2/+3 month/day-of-month) are
**software-gated** by `RTC_AlarmDateMatches` (`g_bRtcAlarmDayOfMonth`/
`g_bRtcAlarmMonth`), not by RTC hardware. The user-visible "alarm
clock" in the UI drives this.
