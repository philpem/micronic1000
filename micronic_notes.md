# Micronic 1000 notes

## Specifications

CPU: Zilog Z80, 3.579545 MHz
RAM: 256k-byte static RAM
ROM: Two 27C256 EPROMs (64K-bytes)
I/O: Serial port, two infra-red ports
LCD: 20 character * 8-line LCD, backlit, Hitachi HD61830 LCD controller, Seiko Instruments C264001 (128 x 64 pixels)
RTC: Hitachi HD146818 real-time clock
K/B: Alphanumeric keyboard

## Z80 memory map

0000-7FFF   32 KB bank-switched window
8000-FFFF   32 KB fixed battery-backed RAM

Banks are selected via port 0x47.

Banks 0 and 1 map the two ROM images into the lower half; additional bank values select 32K pages of RAM. On reset ROM bank 0 is selected.

## Z80 I/O ports

TBD.

## Infrared ports

There are two infra-red ports. Each has two photodetectors and two emitters, which seem to implement a synchronous (clocked) protocol.

The ports are:

  * `PLINTH`: back of the unit
  * `V24_ADAPTOR`: top of the unit (where the strap attaches)

  (Corrected 2026-08-24 by the owner: top/back is the correct
  nomenclature; an earlier draft of these notes said bottom/front.)

Micronic held a US Patent for a similar infrared interface, US 4,423,319: https://patentimages.storage.googleapis.com/7c/9c/46/bb89fcac0aee3c/US4423319.pdf

## Keyboard (owner-supplied 2026-08-27)

32-key alphanumeric keypad. Physical key / shifted value:

    Shift(MODE)  Sun(2nd)
    A/(  B/)  C  D/Del  E  F
    G/+  H//  I/,  J/?  K/-  L/*  M/.
    N/Z  O/7  P/8  Q/9  DEPT
    R/4  S/5  T/6  END
    U/1  V/2  W/3  ENTER
    Backspace  Space/0  NO  YES

Matrix wiring (drive = port 02h, sense = port 00h; full diagram at
https://philpem.me.uk/elec/micronic). Modifier keys: Shift = MODE,
Sun = 2nd (Left Shift).

Firmware key codes (master table `tbl_kbd_map` at ROM00:1b58, three
36-entry pages; Kbd_ScanMain ROM00:18f0 indexes it as col*6+row):
letters are ASCII 0x41-0x57 ('A'..'W'), ENTER=0x0D, space=0x20,
backspace=0x7F. Function-key codes: 0x01/0x06/0x0b/0x0c/0x11/0x12/
0x14/0x1a/0xd0. Sun-shifted page: N->Z (0x5A), plus 0x58/0x59.

Owner UI navigation facts: YES/NO move between the form fields; N/Z
is said to cycle a choice field's value to the next predefined setting.

Emulator-confirmed key codes (2026-08-27): YES=0x06 (moves DOWN a
field), NO=0x01 (moves UP), ENTER=0x0D, space=0x20, backspace=0x7F.
N/Z = 0x4E/0x5A are plain letters: they TYPE into a text field. The
Load/Run "From" field is a free-text field (default "PLINTH") and
typing appends to it - no N/Z cycle observed in firmware (no CP
0x4E/0x5A in the field-edit path). OPEN: reconcile owner "N/Z cycles"
with firmware "N/Z types letters".

## Side port

There is a 5-pin port on the right side which seems like it could be some kind of serial port or barcode scanner input.

## Power supply

The main power source is four AA batteries. There is also a lithium coin cell which serves as a memory backup battery to retain the RAM contents while the
main batteries are chenged. It's reasonable to surmise that the unit can probably detect when the main or backup battery is running low by some means and
display this fact to the user.


## Websites

A few people tried to reverse-engineer the Micronic back in the day, notably Derek Kennedy and Lee Davison.

  * http://web.archive.org/web/20180104024745/http://www.philpem.me.uk/elec/micronic/
  * https://geocities.restorativland.org/SiliconValley/Port/8052/
  * https://6502.org/users/mycorner/z80/micronic/index.html

None of this work was completed 
