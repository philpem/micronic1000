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
