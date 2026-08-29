# I/O map

Z80 I/O ports as used by the firmware (both ROM banks). Every port
below has a label and repeatable comment in the Ghidra database
(`io:` address space).

Confidence legend:

* **CONFIRMED** — proven from code
* **LIKELY** — strong circumstantial evidence
* **SUSPECTED** — plausible, unproven

## Complete port list

| Port | Dir | Name | Function | Confidence |
|------|-----|------|----------|------------|
| 00h | R | io00_kbd_sense | Keyboard matrix sense (mask 3Fh); row selected via 02h. Reset checks sense==1Ch with drive 02h for the service key | CONFIRMED |
| 02h | W | io02_kbd_drive | Keyboard matrix drive / config latch (shadows F780, F782) | CONFIRMED |
| 03h | W | io03_lcd_data | LCD controller data byte | CONFIRMED |
| 04h | W | io04_out_latch | Output/power latch (shadow F784). FFh = idle/init; E0h/FDh select comms config modes | CONFIRMED (bits SUSPECTED) |
| 05h | R | io05_status_in | Status: bit0/bit1 sampled at reset (boot keys). Suspected battery/peripheral-present bits ("MAIN BATTERY LOW" strings) | bit0/1 usage CONFIRMED<br>meaning LIKELY |
| 07h | W | io07_port_07 | Control latch (shadow F786); bit1 toggled around comms activity | usage CONFIRMED<br>function SUSPECTED |
| 08h | W | RTC_ADDR | HD146818 register-address latch (data at 28h) | CONFIRMED |
| 23h | W | io23_lcd_clk | LCD strobe/select: 0Bh = command phase, 0Ch = data phase | CONFIRMED |
| 28h | R/W | RTC_DATA | HD146818 register data | CONFIRMED |
| 2Ah | W | io2a_ctl_latch | Peripheral control latch (shadow F78B). Init 20h; bit5 toggled in beep sequences; bit1/bit4 driven by the external-device bus arm/trigger path in ExtBusArm (1221)/Barcode_AttentionStrobe (14FF) for the 2A wire variant | usage CONFIRMED |
| 2Bh | W | io2b_sound | Sounder/beeper: 0 = off, 0Bh = beep pattern. **Also written 0 by the device front-end 35C9 to quiet before an external-bus timing window** | LIKELY |
| 2Ch | W | io2c_ctl_latch | Control latch (shadow F78D); **bit1/bit0 = attention strobe for the 2D external-device status bus** (toggled by ExtBusDisableFe 14DE / BeepAndLatch 14FF) | usage CONFIRMED |
| 2Dh | R | **EXTBUS_EDGE** | **Barcode-reader edge/level input** (read-only). Bit0 is sampled and timed by the capture front end; bit1 is a secondary/status input. The owner confirms the 5-pin side port was used with a barcode pen. (io:002d labelled `EXTBUS_EDGE`) | CONFIRMED code + owner hardware fact |
| 46h | W | io46_pwr_ctrl | Written from FC05 (70h at cold start) by WritePowerLatchPort46. Function unidentified - NOT confirmed as power latch | UNKNOWN |
| 47h | W | io47_bank_sel | Bank select, 32K window 0000-7FFF: values 0/1 = ROM images ROM00/ROM01, higher = 32K RAM pages. Shadow: f791 | CONFIRMED |
| 48h | W | io48_lcd_strobe | Control lines, bits 0-1: forced to 11 at cold init (FUN_0323), power-down (PowerDownSuspend) and toggled during link self-test. Paired sense port 49h. Bits look like control/power enables rather than per-link IR data | bits usage CONFIRMED, function SUSPECTED |
| 49h | R | io49_bootkeys | Bits 0-1 = boot-key status at reset; echoed to 48h by diagnostics. Suspected detector/status lines paired with 48h | bits used CONFIRMED, IR role SUSPECTED |
| 4Ah | W | io4a_ctrl | **External-link control latch** (shadow f794). Firmware mechanically drives bits 0, 4, 5 around transfers and toggles bit 1 via `LinkPortSelect` (3454) according to the active link id bit 5 (`AND 0x20` at ROM00:3277). Owner confirms link-id bit 5 selects one of two IR line states (V24 ADAPTOR top vs PLINTH back); which `LINK_CTRL` bit 1 value maps to which physical connector remains OPEN. No electrical names for control bits are proven. Drivers `LinkBlockTx` 3277-3377 / `LinkBlockRx` 3378-3453 | CONFIRMED mechanical |
| 4Bh | R | io4b_link_status | **Link status**: firmware polls bit 7 before each `OUTI` to 4Dh and bits 4/6 at handshake stages in `LinkBlockTx`, and bits 0-3 in `LinkBlockRx`. No electrical names (`TX-ready`, `RX-ready`, `ACK`, `peer-ready`/`type`, `frame phase`) are proven. MAME's "TX buffer empty"/"RX buffer full" comment is consistent with the bit 7 / bit 0 polls, but its driver does not implement the 4x ports. | CONFIRMED mechanical (firmware); electrical SUSPECTED |
| 4Ch | W | io4c_link_cmd | Mechanical: `0x81` written by `LinkPresent` (34EC) after `LINK_STATUS` bit 7 poll (`DE=0x02DA`) at TX open. Electrical label `command/ACK` remains SUSPECTED. | CONFIRMED mechanical |
| 4Dh | W | io4d_tx_data | **TX data byte**: `OUTI` (memory to port) per byte, gated by `LINK_STATUS` bit 7 polling (`DE=0x06F9` per-byte timeout in `LinkBlockTx`). | CONFIRMED mechanical |
| 4Eh | R | io4e_rx_data | **RX data byte**: `INI` (port to memory) per byte, gated/decoded via `LINK_STATUS` bits 0-3 in `LinkBlockRx`. | CONFIRMED mechanical |
| 4Fh | W | io4f_probe | Mechanical: `0x1F` written by `LinkProbe` (3489), then a `LINK_CTRL` latch sequence. Physical/reset meaning remains SUSPECTED. | CONFIRMED mechanical |

### Interface shape: byte-latch access — firmware behaviour CONFIRMED, electrical function OPEN

The firmware accesses the 4x block with **distinct latch addresses** and
status-gated byte pumps, which does not match a Z80 SCC/SIO/ADLC
register-select model. Distinguishing observations (mechanical, byte-verified):

* TX and RX use **distinct latch addresses** (4Dh write-only, 4Eh
  read-only) — an SCC has one bidirectional data port.
* Data moves via `OUTI` (mem→4Dh) gated by `LINK_STATUS` bit 7 and `INI`
  (4Eh→mem) gated by `LINK_STATUS` bit 0 (with bits 1-3 participating in the
  `LinkBlockRx` decode), not register-select + data sequences. No WR0/WR1-style
  command/register programming occurs.
* 4Ah is a control latch mechanically driven as bits 0/4/5 around transfers
  with bit 1 toggled per link-id bit 5 — electrical labels such as
  `idle/run`, `talk`/`RX-enable`, `clock`, or `online/enable` (bits 6/7) are
  **not proven**.
* 4Bh is a status port mechanically polled as bits 7, 4 and 6 in the TX
  handshake and bits 0-3 in the RX path — firmware polls are **CONFIRMED**;
  electrical labels such as `TX-ready` (bit 7), `RX-ready` (bit 0), `ACK`
  (bit 6), `peer-ready`/`type` (bit 4) or `frame phase` (bits 1/2) are
  **not proven**.
* 4Ch receives `0x81` after a `LINK_STATUS` bit 7 poll (`LinkPresent` →
  `LinkWaitReady`, `DE=0x02DA`); 4Fh receives `0x1F` during `LinkProbe`
  followed by a `LINK_CTRL` latch sequence — mechanical writes are **CONFIRMED**;
  labelling them `command/ACK` or `probe/reset` for the physical meaning
  remains **SUSPECTED**.
* The synchronous clock+data IR pairs (2 photodiodes + 2 LEDs per
  port, per US 4,423,319) are downstream of this byte interface —
  the M1000's Z80 mechanically pushes/pulls whole bytes while polling
  `LINK_STATUS`; electrical timing on the connector-facing side remains to be
  traced.

So the M1000 firmware sees six I/O addresses — `control (4A) + status (4B) +
tx-latch (4D) + rx-latch (4E) + 4C (0x81 write) + 4F (0x1F write)` — with the
mechanical drive/poll sequences listed under `LinkBlockTx` (3277-3377),
`LinkBlockRx` (3378-3453) and `LinkProbe` (3489). The physical serializing
to the IR clock/data lines lives off-pump and its semantics remain OPEN.

**No hardware address-filter or CRC register exists in this block** —
the only non-data write-outs are 4Ch=0x81 (present) and 4Fh=0x1F
(probe). Multidrop addressing is done in software: the frame's byte
at offset +4 is XOR-matched against the unit's link id `fdd4`
(`LinkValidateFrameHeader` ROM00:30DC). TX offset +4 constant `0x7F` (via `LinkFramePrefixWrite` 316B) is **SUSPECTED**; offset +5 is never read by ROM link code and may be writable by loaded code — link-path checksum **OPEN** (none verified). See [the Commstar protocol](../protocol/commstar.md).

## MAME driver (`micronic.cpp`) cross-check — what it confirms

The MAME driver (by Sandro Ronco) is a *model*, not gospel, and its
I/O map is **incomplete**. Verified against firmware code:

| Port | MAME claim | Matches firmware? |
|------|-----------|-------------------|
| 08/28 | RTC address/data (MC146818) | YES - also confirmed by RtcRegWrite/Read byte pattern |
| 4D/4E/4B | IR TX/RX/status (*comments only*) | comment is consistent with firmware polls, but MAME does NOT implement ports 04,07,2A,2D,33,4A-4F in `micronic_io` - so it is a suggestion |
| 05 | IRQ-flag byte (kbd/RTC/IR/batteries) | YES bit-cluster matches fd84 event masks |
| periodic IRQ | RTC-146818 periodic drives CPU INT | YES - matches ClockSelfTest 1024Hz tick + 16C9 HALT-wait loop |
| 03/23 | HD61830 LCD data/control | matches LcdRefreshScreen |
| 2B | beeper 16-tone | matches io2b_sounder |
| 00/02 | keyboard matrix (drive/sense) | matches matrix scan |
| 47 | bank select | confirmed |
| 46 | LCD contrast | plausible (firmware writes FC05->46h; MAME agrees) |
| 2C bit4 | LCD backlight | plausible (2C from p2c_shadow) |
| 33/2D/07/04/2A | unmapped/unused in MAME | firmware touches 07/04/2A/2C; MAME omits them |

Bottom line: MAME corroborates the RTC (08/28), the IRQ model,
port-05 irq bits, LCD, beep, keyboard, and banking. The IR serial
block (4A-4F) exists only as comments there and must stand on the
firmware analysis in this doc.

_Entries above marked "firmware"/"code-derived" are proved from the
ROM; MAME is used only as an independent hint where it agrees._

No serial EEPROM exists: the unit serial number is typed by the user
at the banner screen after battery removal and lives in battery RAM
(FEAB area).

## Bit-level functions known so far

### Port 04h — output/power latch
| Bit | Function | Evidence |
|-----|----------|----------|
| 0-2 | masked off on writes from shadow (AND E7h) — reserved/read-only? | ROM00:17EC |
| 1 | cleared (FDh) when loading comms config table into FD84 area; set (FFh) at power-down paths and idle init | FUN_22E9/2306, ShutdownSaveState |
| whole | E0h written before copying 19-byte comms config; FFh before shutdown/save | CONFIRMED sequence |

### Port 05h — status
| Bit | Function | Evidence |
|-----|----------|----------|
| 0 | boot key held at power-on (reset polls; clear ⇒ normal cold start) | ROM00:0168 |
| 1 | alternate-boot request (jump to 17A5 path) | ROM00:016E |
| others | unknown; suspected battery-low / peripheral-present flags | string evidence only |

### Port 07h — control latch
| Bit | Function | Evidence |
|-----|----------|----------|
| 1 | link/latch control: toggled around link activity (set OR 02h in link setup 24B0, cleared AND FDh by the RTC date-rollover detector 2468 side path) | CONFIRMED toggle pattern |
| 0 | written 1 during shutdown (ShutdownSaveState) alongside port 04h=FF | CONFIRMED sequence |

### Port 2Ah — peripheral control latch
| Bit | Function | Evidence |
|-----|----------|----------|
| 5 | toggled around beeps: cleared (AND DFh) then restored; also set (OR 20h) in warm-restart latch restore | CONFIRMED pattern |
| whole | initialised to 20h at reset (ROM00:0154) | CONFIRMED |

### Ports 48h/49h — drive/sense pair
| Line | Function | Evidence |
|------|----------|----------|
| 49h bit0/1 | read at reset as boot-key status; diagnostics IrSenseDiagEcho reads both and *echoes them to 48h*, latching result in FDAF | CONFIRMED behaviour |
| 48h bit0/1 | driven during LinkSelftestRun via f792 mask; also forced at power-down (PowerDownSuspend) and cold init (FUN_0323) | CONFIRMED behaviour |
| mapping | which bit = PLINTH vs V24 ADAPTOR is **not resolvable from this dump** — see architecture note below | OPEN |

**Architecture conclusion:** ports 48h/49h are touched by self-test,
boot-key sampling, and power-down rather than the link data path. The RTC
uses 08h/28h. The external link uses the 4Ah-4Fh latch block; active-link-id
bit 5 reaches LinkPortSelect, which changes the 4Ah/2Ch line state. Which
bit value names PLINTH or V24 remains open.

### Indexed peripheral 08h/28h — HD146818 RTC (address+data latch)

Access pattern: write register number to **port 08h**, then read/write
the register's data at **port 28h**. This is the classic 146818
(address-bus register select / 8-bit data) programming model.
CONFIRMED by decoding the register numbers against the HD146818 map
(see the register table below) — including the write-time sequence and
the periodic-interrupt enable handshake.

| Index | Function | Evidence |
|-------|----------|----------|
| 00h | **seconds** | written by RtcWriteTime (ROM00:22AB); read by RtcReadRegisterFile (20EF) |
| 01h | alarm seconds | written by RtcSetAlarm (ROM00:2158-62) |
| 02h | **minutes** | written by RtcWriteTime; read by RtcReadRegisterFile |
| 03h | alarm minutes | written by RtcSetAlarm |
| 04h | **hours** | written by RtcWriteTime; read by RtcReadRegisterFile |
| 05h | alarm hours | written by RtcSetAlarm |
| 06h | **day-of-week (weekday)** | written by RtcWriteTime (ROM00:22AB); read by RtcReadRegisterFile |
| 07h | **day-of-month** | written by RtcWriteTime; read by RtcReadRegisterFile |
| 08h | **month** | written by RtcWriteTime; read by RtcReadRegisterFile |
| 09h | **year** | written by RtcWriteTime; read by RtcReadRegisterFile |
| 0Ah | Register A (divider/rate) | `0x26` periodic rate, `0x2A`, `0x7A` during time-set; UIP bit7 polled |
| 0Bh | Register B (control) | `0x40`=PIE, `0x46`=PIE+24h+binary |
| 0Ch | Register C (IRQ flags, read-clears) | the "tick poke" (ClockSelftestTickWindow/288A) |
| 0Dh | Register D | (unused) |
| 0x46 | (via B=0x0B reg write of 0x46) | Actually this is **Reg B ← 0x46** |
| 00h-09h | time register file (10 bytes) | read by RtcReadRegisterFile (ROM00:20EF, ex-"CommsRxBurst16") into g_abRtcRegisterSnapshot (FD50) |

`RtcWriteTime` (ROM00:22AB) writes registers 09,08,07,04,02,00,06
(year/month/day-of-month/hours/minutes/seconds/day-of-week) from a
7-byte buffer. `RtcSetTimeFromBuffer` (ROM00:20AC) wraps it with the
standard SET-bit freeze → stop → write → restart → clear step.
`RtcInit` (ROM00:2084) writes Reg B ← 0x46 and loads a default time
block (source ROM00:20A7).

`RtcReadRegisterFile` (ROM00:20EF, ex-"CommsRxBurst16") = reading
registers 00h..09h (10 bytes, the time file) into
g_abRtcRegisterSnapshot (FD50) — a clock REGISTER READ, not a serial
Rx burst. The earlier "comms/modem peripheral" framing was based on UI
strings and function *names*; the register numbers are unambiguous.
The config-table "uploads" and the fd84 event table reflect the RTC
periodic interrupt + status bits, not a modem.
(see also [interrupts](interrupts.md) and [the RTC reference](rtc.md))

`RTC_AlarmDateMatches` (ROM00:223E, formerly `Link_StatusCompare_FD4B`)
compares `g_bRtcAlarmDayOfMonth`/`g_bRtcAlarmMonth` against the current
RTC date as the software gate for the FF alarm path (BDOS FFh bytes
+2/+3); see [the RTC reference](rtc.md#bdos-eight-byte-rtc-record).

## LCD channel (CONFIRMED)

`LcdRefreshScreen` (ROM00:1E27) sends the 160-byte framebuffer at FC06
byte-by-byte through `lcd_putc` (ROM00:1F79): port 23h ← 0Ch (data
phase strobe), port 03h ← char. Command phase uses 23h ← 0Bh.
`tty_out_char` (ROM00:1BEB) implements the console abstraction with a
control-character dispatch table (BEL/TAB/BS/CR/LF/FF/…).

## Ghidra I/O labels (created program-wide)

The `io:00xx` addresses are **labelled** with the peripheral names and
carry **repeatable comments** describing the port function, so the
Ghidra listing shows the label on every direct `IN n`/`OUT n` operand
and the repeatable comment near each access. For indirect accesses
(via register C, e.g. `OUT (C),B` in `lcd_bus_write`), the address is
only linked if a reference is added from the `LD C,<port>` instruction.

Use the datasheet register/bit name wherever one exists (e.g. RTC
Reg B `PIE`/`SET`/`24h`, Reg A `DV`/`RS`); for the proprietary IR
block the bit meanings below are descriptive assignments.

| Symbol | Port | Meaning |
|--------|------|---------|
| `KBD_SENSE` | 00h | keyboard matrix sense (read) |
| `KBD_DRIVE` | 02h | keyboard matrix drive/column (write) |
| `LCD_DATA` | 03h | LCD controller data byte |
| `OUT_LATCH` | 04h | output/power latch |
| `STATUS_IN` | 05h | status/boot-key byte |
| `CTRL_07` | 07h | control latch |
| `RTC_ADDR` | 08h | RTC address latch (HD146818) |
| `LCD_REG` | 23h | LCD register/command select |
| `RTC_DATA` | 28h | RTC data (HD146818) |
| `CTL_LATCH_2A` | 2Ah | peripheral control latch |
| `SOUND` | 2Bh | beeper/sounder |
| `CTL_LATCH_2C` | 2Ch | control latch |
| `EXTBUS_EDGE` | 2Dh | external-device bus level/edge input (bit0 data, bit1 status) |

\* The established label is `EXTBUS_EDGE`. The owner adjudicated the
port-2D capture subsystem as the barcode-reader front end; existing ExtBus*
function names are grandfathered. See
[the programmer-facing reader guide](../manual/barcode-reader.md).
| `LCD_CONTRAST` | 46h | LCD contrast DAC |
| `BANK_SEL` | 47h | 32K bank select |
| `LCD_STROBE` | 48h | LCD drive/sense strobe (with 49h) |
| `BOOTKEYS` | 49h | boot-key/probe sense (with 48h) |
| `LINK_CTRL` | 4Ah | external link control latch (firmware drives bits 0/4/5, toggles bit 1 per link-id bit 5; no electrical names such as idle/run, talk/RX-enable, clock, or port-select are proven — see mechanical sequences) |
| `LINK_STATUS` | 4Bh | link status (firmware polls bits 7/4/6 in TX handshake and bits 0-3 in RX decode; no electrical names such as TX-ready, RX-ready, ACK, peer-ready/type, or frame-phase are proven) |
| `LINK_CMD` | 4Ch | 4Ch latch (mechanical `0x81` write after `LINK_STATUS` bit 7 poll; electrical label `command/ACK` SUSPECTED) |
| `LINK_TXD` | 4Dh | link TX data byte (`OUTI` gated by `LINK_STATUS` bit 7) |
| `LINK_RXD` | 4Eh | link RX data byte (`INI` gated via `LINK_STATUS` bits 0-3) |
| `LINK_PROBE` | 4Fh | 4Fh latch (mechanical `0x1F` write then `LINK_CTRL` sequence; physical/reset meaning SUSPECTED) |
