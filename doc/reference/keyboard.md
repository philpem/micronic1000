# Keyboard — layout, scan and special functions

This page documents the Micronic 1000 keyboard: the physical key
arrangement, the (different) electrical scan matrix, how the firmware
scans and decodes it, the three keycode pages, and the special functions
reachable with the red **Sun (☼ / "2nd")** modifier. Byte-level evidence
is in [RE notes: memory and I/O](../re-notes/memory-and-io-evidence.md).

## Physical layout

32 keys. Bold / red is the **Sun-held alternate function**; the `☼` key
is also red (owner-supplied, <https://philpem.me.uk/elec/micronic>).

| | | | | | |
|---|---|---|---|---|---|
| ⇕ | A **(STWDL)** | B **(LIGHT)** | ☼ | C **(CHNGE)** | D **(DEL)** |
| E **(F1)** | F **(F2)** | G + **(REFER)** | H / **(HELP)** | I , **(INSERT)** | J ? **Y** |
| K - **↑** | L * **↓** | M . | N Z | O 7 | P 8 |
| Q 9 | DEPT/POS | R 4 | S 5 | T 6 | END **(TOP)** |
| U 1 | V 2 | W 3 | ENTER **(BOT)** | ← (backspace) | Space 0 |
| NO | YES | | | | |

Alternate (Sun-held) meanings: A=STWDL, B=LIGHT, C=CHNGE, D=DEL, E=F1,
F=F2, G=REFER, H=HELP, I=INSERT, J=Y, K=↑, L=↓, END=TOP, ENTER=BOT.

## Electrical matrix and scan

The electrical matrix is **6 columns × 6 rows** — *not* the physical
4×8 arrangement (owner note). Confirmed from the firmware:

* `Kbd_ScanMain` (`ROM00:18F0`) drives **columns** on `KBD_DRIVE`
  (port `02h`), one at a time — masks `01h,02h,04h,08h,10h,20h`
  (`LD B,06h` / `SLA D`) — and senses **rows** on `KBD_SENSE`
  (port `00h`, low 6 bits, `AND 3Fh`). Key index = `col*6 + row`.
* `Kbd_SenseColumn` (`ROM00:1A44`): write A to `KBD_DRIVE`, read
  `KBD_SENSE & 3Fh`.
* `Kbd_SenseAllColumns` (`ROM00:1A42`): drive `3Fh` (all six columns at
  once) — the "any key?" prescan.

So the scan covers **36 electrical positions**, and `tbl_kbd_map` has
exactly 36 entries. The 32 physical keys occupy 32 of them; four
positions carry no key. *(Reconciling the exact physical↔electrical
position map is an open tidy-up.)*

## Keycode pages (`tbl_kbd_map`, ROM00:1B58)

Three 36-entry pages, indexed `col*6+row`:

| Page | Base | Selected by | Notes |
|---|---|---|---|
| 0 | `1B58` | default | unmodified keys |
| 1 | `1B7C` | **Shift** (MODE) | punctuation/digits; `N` = `DBh` |
| 2 | `1BA0` | **Sun** one-shot | sparse; `F/J/N` → `X/Y/Z` |

Common keycodes: letters `A`–`W` = ASCII `41h`–`57h`; `ENTER`=`0Dh`;
space=`20h`; backspace=`7Fh`; `NO`=`01h`; `YES`=`06h`; **Sun**=`D0h`.
Function-key codes in use: `01h/06h/0Bh/0Ch/11h/12h/14h/1Ah/D0h`.
Page 2 maps `F/J/N` → `X/Y/Z` (`58h/59h/5Ah`) and supplies `1Ah`,
`0Ch`, `12h`, `0Bh`, `11h`; every other page-2 position is `00`.

## Sun (☼) modifier — two mechanisms

The Sun key code is **`D0h`**. It works in two distinct ways:

**One-shot Sun** — tap Sun, release, then a key: `tbl_kbd_map` **page 2**
applies to that one key, which emits its page-2 code.

**Held Sun + key (direct chord)** — bypasses the keycode table. The
dispatch at `ROM00:19C0` matches the raw matrix pattern
(A = `KBD_DRIVE` byte, B = expected `KBD_SENSE` rows) against the
4-entry table at `ROM00:19E0` and tail-jumps to the handler:

| pattern (drive, sense) | handler | operation |
|---|---|---|
| `04h,01h` | `ROM00:1A0A` | **backlight toggle** (Sun+`LIGHT`/B) |
| `10h,08h` | `Lcd_ContrastUp` | **LCD contrast up** (Sun+END/TOP) |
| `08h,21h` | `Lcd_ContrastDown` | **LCD contrast down** (Sun+ENTER/BOT) |
| `01h,01h` | `ROM00:19FB` → `Power_DownSuspend` | **power-down** (Sun+MODE) |

## Backlight and contrast

* **Backlight:** `CTL_LATCH_2C` (port `2Ch`) **bit 4** is the **EL
  backlight** enable (CONFIRMED: Sun+`LIGHT`/B toggles it; the keyboard
  handler toggles `2Ch` bit 4 at `1A0A`-`1A25`).
* **Contrast:** `g_bLcdContrast` (`FC05`) is written to port **`46h`**
  (LCD contrast DAC) by `Lcd_ContrastWrite` (`1FD4`). `Lcd_ContrastUp`
  (`1D60`) / `Lcd_ContrastDown` (`1D4A`) step it by **±2** (ceiling
  `FFh` / floor `00h`). (Legacy `Power_Latch*` names were misnomers.)

## Wake from standby

After the display blanks into the deep standby (`Power_DownSuspend`),
**pressing any key wakes it**, but the keypress is *not decoded* in the
standby spin — it only drives the wake event (the spin keeps the
`KBD_DRIVE` bit-6 wake scan live). What, if anything, the waking key
then triggers is **OPEN**; the restart path restores the saved session
rather than acting on that key.

## Related

* [Memory and I/O map](memory-map.md) — port table and shadows
* [RE notes: memory and I/O](../re-notes/memory-and-io-evidence.md) — byte-level evidence
