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
| ⇕ MODE | A **(STWDL)** | B **(LIGHT)** | ☼ 2nd | C **(CHNGE)** | D **(DEL)** |
| E **(F1)** | F **(F2)** | G + **(REFER)** | H / **(HELP)** | I , **(INSERT)** | J ? **Y** |
| K - **↑** | L * **↓** | M . | N Z | O 7 | P 8 |
| Q 9 | DEPT/POS | R 4 | S 5 | T 6 | END **(TOP)** |
| U 1 | V 2 | W 3 | ENTER **(BOT)** | ← (backspace) | Space 0 |
| NO | YES | | | | |

The physical arrangement is **4 columns × 8 rows**; the electrical scan
(below) is a different geometry.

## Electrical matrix and scan

The electrical matrix is **6 sense rows × 6 drive columns** = 36
positions. Confirmed from the firmware:

* `Kbd_ScanMain` (`ROM00:18F0`) drives **columns** on `KBD_DRIVE`
  (port `02h`) one at a time — masks `01h,02h,04h,08h,10h,20h`
  (`LD B,06h` / `SLA D`) — and senses **rows** on `KBD_SENSE`
  (port `00h`, low 6 bits, `AND 3Fh`).
* Table index = **`sense*6 + drive`** (`ROM00:1933`, byte-verified; the
  older "col*6+row" wording used swapped axis names).
* `Kbd_SenseColumn` (`ROM00:1A44`): write A to `KBD_DRIVE`, read
  `KBD_SENSE & 3Fh`.
* `Kbd_SenseAllColumns` (`ROM00:1A42`): drive `3Fh` (all six columns) —
  the "any key?" prescan.

### Full matrix — keys and keycodes

Rows = sense line (0-5, `KBD_SENSE` bits), columns = drive bit (0-5,
`KBD_DRIVE` bits). Each cell is the key and its keycode on
**page 0 / page 1 (Shift) / page 2 (Sun)**. `--` = no keycode.

| sense\drive | 0 | 1 | 2 | 3 | 4 | 5 |
|---|---|---|---|---|---|---|
| **0** | ⇕ MODE `--` | A `41/28/--` | B `42/29/--` | ☼ 2nd `--` | U `55/31/--` | ⌫ `7F/7F/--` |
| **1** | C `43/ED/--` | D `44/25/1A` | E `45/23/--` | F `46/26/58 X` | V `56/32/--` | Space `20/30/--` |
| **2** | G `47/2B/--` | H `48/2F/--` | I `49/2C/--` | J `4A/3F/59 Y` | W `57/33/--` | NO `01/01/0C` |
| **3** | K `4B/2D/--` | L `4C/2A/--` | M `4D/2E/--` | N `4E/DB/5A Z` | ENTER `0D/0D/12` | YES `06/06/0B` |
| **4** | O `4F/37/--` | P `50/38/--` | Q `51/39/--` | DEPT `D0/D0/--` | — | — |
| **5** | R `52/34/--` | S `53/35/--` | T `54/36/--` | END `14/14/11` | — | — |

So the **modifier keys `⇕` (MODE/Shift) and `☼` (2nd/Sun) carry no
keycode** (`00`) — they select a map page instead. Note the older claim
"Sun = `D0h`" was wrong: `D0h` is **DEPT**; `14h` is **END**.

## Keycode pages (`tbl_kbd_map`, ROM00:1B58)

Three 36-entry pages, indexed `sense*6+drive`:

| Page | Base | Selected by | Notes |
|---|---|---|---|
| 0 | `1B58` | default | unmodified keys |
| 1 | `1B7C` | **Shift** (MODE) | punctuation/digits; `N` = `DBh` |
| 2 | `1BA0` | **Sun** one-shot | sparse (below) |

Keycodes: letters `A`–`W` = ASCII `41h`–`57h`; `ENTER`=`0Dh`;
space=`20h`; backspace=`7Fh`; `NO`=`01h`; `YES`=`06h`; `DEPT`=`D0h`;
`END`=`14h`. Page 2 maps **`F/J/N` → `X/Y/Z`** (`58h/59h/5Ah`) — which
independently pins the index formula — plus `1Ah`(⌫), `0Ch`(NO),
`12h`(ENTER), `0Bh`(YES), `11h`(END); all other page-2 positions are
`00`.

## Sun (☼) modifier — two mechanisms

**One-shot Sun** — tap Sun, release, then a key: page 2 applies to that
one key (e.g. F→`X`).

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
  backlight** enable (CONFIRMED: Sun+`LIGHT`/B toggles it; keyboard
  handler toggles `2Ch` bit 4 at `1A0A`-`1A25`).
* **Contrast:** `g_bLcdContrast` (`FC05`) → port **`46h`** (LCD contrast
  DAC) via `Lcd_ContrastWrite` (`1FD4`); `Lcd_ContrastUp` (`1D60`) /
  `Lcd_ContrastDown` (`1D4A`) step it by **±2**.

## Cross-check against MAME

MAME's `src/mame/skeleton/micronic.cpp` (Sandro Ronco, 2010) carries a
keypad matrix that matches `tbl_kbd_map` **for all letter/number keys**
(rows 0-3) and independently corroborates: `04h` = interrupt-enable mask
and `05h` = interrupt-flag byte with the same bit sources (kbd / RTC /
IR / main-battery / backup-battery); `48h`/`49h` as a write/read-back
pair; `2Ch` bit 4 = backlight. **One discrepancy:** MAME comments
`2Ch` bits 0-1 as "V24_ADAPTER IR clock/data", but the ROM puts them in
the barcode front end (`Barcode_AttentionStrobe`); MAME is a skeleton
with IR I/O marked TODO, so the ROM reading stands.

## Wake from standby

After the display blanks into the deep standby (`Power_DownSuspend`),
**pressing any key wakes it**, but the keypress is *not decoded* in the
standby spin — it only drives the wake event. What, if anything, the
waking key then triggers is **OPEN**; the restart path restores the
saved session rather than acting on that key.

## Related

* [Memory and I/O map](memory-map.md) — port table and shadows
* [RE notes: memory and I/O](../re-notes/memory-and-io-evidence.md) — byte-level evidence
