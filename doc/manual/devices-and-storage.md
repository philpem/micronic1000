# Devices and storage

DIPOS-B routes console, reader, punch, list, and file-device operations
through configuration tables. A device selector is not a physical-port number.

## Two configuration tables

| RAM table | Shape | Role |
|---|---|---|
| FE83h | 16 one-byte entries | Console, reader, punch, and list device slots. |
| FE93h | 16 one-byte entries | Drive-letter/device mapping used by file operations. |

**CONFIRMED:** FE83 is not four four-byte records. Its cold-start contents are
80 AB 63 43 | 80 2B 63 43 | 80 67 63 43 | 80 67 63 43; consumers select
individual entries through different windows of the active-device field.
FE93 is separately letter-indexed.

BDOS F8h and FAh read/write FE83. BDOS FBh writes FE93. These calls can alter
the system-wide configuration, so applications should save and restore any
entries they modify.

## Active device selector

BDOS F6h reads and F7h writes fbc5, the packed active-device selector.
The documented consumers include:

| Consumer | Slot selection |
|---|---|
| Console (fn 01h/02h/06h) | low two bits select FE83 entries 1-4 |
| Reader (fn 03h) | next selector field selects FE83 entries 5-8 |
| Punch (fn 04h) | a wider field can select any FE83 entry |

The default ABh console value combines the local keyboard flag with the
barcode-reader route. A program that changes F7h should restore the prior
value before it exits.

## Drives

The firmware accepts drive selections 0-15 and treats an FCB drive byte of
zero as the current selection. WORKSTATION MEMORY, WORKSTATION RAMDISK,
PLINTH, V24 ADAPTOR, and EXT STORAGE ADAPTOR are user-interface/configuration
names, not a static, universal mapping from drive letters to hardware.

The owner confirms a backup cell retains RAM while main batteries are changed.
The retention and allocation policy of every banked-RAM configuration has not
been established, so applications must not assume that a named RAMDISK is
volatile or persistent without testing the configured machine.

For filesystem implementation details, see
[the CP/M comparison](../internals/cp-m-comparison.md) and
[the memory map](../internals/memory-map.md).
