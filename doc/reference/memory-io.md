# Memory and I/O map

This page states the **hardware and memory contract** visible to a
program. It lists the bank window, fixed RAM, and port assignments that
an application may rely on. The firmware evidence, bit-level polling,
and timing for each port are in
[RE notes: Commstar evidence](../re-notes/commstar-evidence.md#interface-shape)
and [RE notes: OS internals](../re-notes/os-diposb.md).

## Stability

| Area | Stability |
|---|---|
| Bank window `0000-7FFF`, `BANK_SEL` at `47h`; fixed RAM `8000-FFFF` | **Stable** |
| Port assignments below | **Stable** as addresses; bit-level electrical meanings are **Provisional** and live in RE notes |
| RTC at `08h/28h` (HD146818) | **Stable** address pair |
| 4-wire link at `4Ah-4Fh` (byte-latch transport) | **Stable** as a latch block; link framing is in [Protocol: Commstar](../protocol/commstar.md) |

## Memory organisation

| Region | Size | Role |
|---|---|---|
| `0000-7FFF` | 32K | Bank-switched window |
| `8000-FFFF` | 32K | Fixed, battery-backed static RAM (of 256K total) |

Banks of the lower window:

* Bank 0 — kernel ROM
* Bank 1 — UI/workstation ROM
* Banks 2+ — 32K pages of the 256K static RAM

Bank select is port `47h`; the shadow is maintained in RAM. The
replication of page-zero vectors into every bank is a system guarantee —
interrupts and `CALL 0005h` work regardless of selected bank.

Battery RAM retains program and filesystem state across power-off; the
exact retention and allocation policy of every banked configuration is
not a stable contract beyond the fixed `8000-FFFF` window.

## Vectors

| Address | Vector |
|---|---|
| `0000` | JP reset |
| `0005` | JP `F180` — BDOS/system-call gate |
| `0010` | `RST 10h` — banked-call dispatcher (`DB bank, DW target` after the `RST`) |
| `0020`, `0028`, `0030`, `0038` | `RST 20h/28h/30h/38h` — kernel entries; `0038` doubles as `IM 1` IRQ entry |
| `0066` | NMI |

All banks present the same page-zero gate.

## I/O ports

| Port | Name | Direction | Contract |
|---:|---|---|---|
| `00h` | `KBD_SENSE` | R | Keyboard matrix sense |
| `02h` | `KBD_DRIVE` | W | Keyboard matrix drive / config latch |
| `03h` | `LCD_DATA` | W | LCD controller data byte |
| `04h` | `OUT_LATCH` | W | Output/power latch |
| `05h` | `STATUS_IN` | R | Status / boot-key byte |
| `07h` | `CTRL_07` | W | Control latch |
| `08h` | `RTC_ADDR` | W | RTC register-address latch (HD146818) |
| `23h` | `LCD_REG` | W | LCD register/command select |
| `28h` | `RTC_DATA` | R/W | RTC data (paired with `08h`) |
| `2Ah` | `CTL_LATCH_2A` | W | Peripheral control latch |
| `2Bh` | `SOUND` | W | Beeper/sounder |
| `2Ch` | `CTL_LATCH_2C` | W | Control latch |
| `2Dh` | `EXTBUS_EDGE` | R | Barcode-reader edge/level input |
| `46h` | `LCD_CONTRAST` | W | LCD contrast DAC |
| `47h` | `BANK_SEL` | W | 32K bank select |
| `48h` | `LCD_STROBE` | W | Drive/sense strobe (paired with `49h`) |
| `49h` | `BOOTKEYS` | R | Boot-key/probe sense (paired with `48h`) |
| `4Ah` | `LINK_CTRL` | W | External-link control latch (shadowed). bit0 transfer active, bit1 port select, bit4 direction/enable, bit5 strobe |
| `4Bh` | `LINK_STATUS` | R | Link status. bit0 byte available, bit1 block finished, bit2 one more byte, bit3 failed, bit4 inbound pending, bit5 error latch, bit6 handshake busy, bit7 ready to send |
| `4Ch` | `LINK_CMD` | W | Link command latch (`0x81` during present/ready handshake) |
| `4Dh` | `LINK_TXD` | W | Link TX data latch |
| `4Eh` | `LINK_RXD` | R | Link RX data latch |
| `4Fh` | `LINK_PROBE` | W | Device probe/reset |

Detailed bit assignments, poll sequences, timeout values, and electrical
interpretations are **Provisional** and documented in the RE notes:

* Link bit-level evidence: [RE notes: Commstar evidence](../re-notes/commstar-evidence.md#interface-shape)
* RTC register map: [RE notes: RTC](../re-notes/rtc.md)
* Power-on/interrupt bank guarantees:
  [RE notes: Interrupts](../re-notes/interrupts.md) and
  [RE notes: OS internals](../re-notes/os-diposb.md)

For an emulator-facing model of the `4Ah-4Fh` handshake, see
[Protocol: Commstar](../protocol/commstar.md#controller-transaction).

## Related

* [BDOS calls](bdos.md) — `CALL 0005h` convention
* [Program file formats](program-formats.md) — resident module at `D081`
* [RE notes: OS internals](../re-notes/os-diposb.md) — battery-RAM layout
