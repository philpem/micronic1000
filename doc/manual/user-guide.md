# User guide

How to operate the Micronic 1000: the keyboard, the menu tree, and the
meaning of the error screens. Firmware-derived; the internal mechanics are
in [forms and UI code](../re-notes/forms-ui.md).

## Power-on and boot

1. Power on. The unit runs the self test (`TESTING...`), stepping through
   the screens **Clock test**, **Powerdown test**, **First Ram Bank**,
   **Full Ram**, **Contig Ram**, then shows the banner (`PARCON 1000`, RAM
   size) and **`Press >> to continue`**.
2. Press **ENTER** to continue.
3. At the serial-number prompt, key the 8-digit serial number and press
   **ENTER** (after a battery change the number defaults and is re-entered
   here).
4. The **Main Menu** appears.

## The keyboard

The keypad is an alphanumeric key. The layout below shows each key and its
shifted value (the second label is produced with the **Shift** or **Sun**
modifier held):

```
Shift(MODE)   Sun(2nd)
 A/(   B/)   C    D/Del   E     F
 G/+   H//   I/,  J/?     K/-   L/*   M/.
 N/Z   O/7   P/8  Q/9     DEPT
 R/4   S/5   T/6  END
 U/1   V/2   W/3  ENTER
 Backspace    Space/0      NO    YES
```

**Modifiers:**

* **Shift (MODE)** selects the shifted keymap — digits (U/1…Space/0), the
  punctuation shown above, and the function labels below.
* **Sun (2nd)** selects the Sun keymap — letters X/Y/Z and the shifted
  navigation keys (Sun+YES, Sun+NO, Sun+ENTER).

**Function labels** (their exact effect in each screen is still being
mapped):

| label | key | label | key | label | key |
|-------|-----|-------|-----|-------|-----|
| CHNGE | C | REFER | G | HELP | H |
| DEL | D | INSRT | I | F1 | E |
| F2 | F | STWDL | A | LIGHT | B |
| TOP | END | BOT | ENTER | /POS | DEPT |

**Navigation and editing keys:**

| key | code | action |
|-----|------|--------|
| YES | 0x06 | move to next field; in a choice field, step value forward |
| NO | 0x01 | move to previous field; in a choice field, step value back |
| ENTER | 0x0d | accept/commit the current field, advance |
| Backspace | 0x7f | delete previous character |
| Space | 0x20 | space (and cursor advance in text fields) |
| A–W | 0x41–0x57 | type into a text field; in a choice field, select the entry whose key matches |

Within a choice field (e.g. `From`), the value cycles through the device
list **PLINTH → V24 ADAPTOR → EXT STORAGE ADAPTER → WORKSTATION MEMORY →
WORKSTATION RAMDISK**. Sun+YES/NO duplicate YES/NO; Sun+ENTER jumps to the
last choice.

> **Note:** the ROM maps the cycle to **YES/NO**. The N/Z key labels type
> the letters N and Z. The operator-report that N/Z cycles the value is
> recorded as an open item to verify on hardware.

## Menu map

```
Cold boot
 └─ self test: Clock test · Powerdown test · First Ram Bank ·
    Full Ram · Contig Ram
     └─ banner + "Press >> to continue"
         └─ serial-number prompt
              └─ MAIN MENU
                  ├─ 1  Load/Run Program
                  │     └─ fields: Name (text), From (choice: PLINTH / V24 … )
                  │        └─ From=PLINTH → Log-on information
                  │             └─ Mode (LOCAL LINK) · Linespeed (9600)
                  │                User id · Password · Group id · Telephone number
                  ├─ 2  Set Clock
                  │     └─ fields: Time (00.00), Date (01/01/84)
                  ├─ 3  Display Status
                  │     └─ Version (Q229) · Serial No. · total RAM · RAMdisk size
                  └─ 4  Diagnostics
                        └─ Set Debug mode → "Set Debug Mode" screen
                              └─ Status (ON/OFF) · Device (PLINTH choice)
```

Menu items are selected by their number (type the digit — digits are the
shifted values of the letter keys).

## Error screens

Errors show a dedicated banner:

```
PARCON 1000

   *** ERROR ***
       <major>   ( <rcv1>/<rcv2> )
<message>
```

| part | meaning |
|------|---------|
| `<major>` | hard-coded error qualifier (e.g. 8000/8001); distinct per error site |
| `<rcv1>/<rcv2>` | two 3-digit session status values (RCV1/RCV2) |
| `<message>` | the error text |

Fatal errors instead show **`*** FATAL ERROR ***` … Consult Dealer**.

### Error list

The `<major>` field is a **per-site error code** (a source-line-style
identifier in the 8000-series; each error check has its own number, so the
same message text can appear at several codes). The `<message>` is the
error class.

Session/commstar errors (byte-verified error-code → message map):

| code | message |
|------|---------|
| 8000, 8001 | Plinth not connected |
| 8010, 8012–8015, 8020, 8022–8023, 8030, 8032–8034 | Failed to connect |
| 8011, 8021, 8031, 8041, 8055, 8056, 8091, 8102, 8111, 8121, 8131, 8141, 8151, 8165, 8166 | Not available |
| 8016, 8024, 8035, 8042 | Modem fault |
| 8040, 8050, 8054, 8090, 8100, 8110, 8120, 8130, 8140, 8150, 8160, 8164 | Line failure |
| 8053, 8163 | Invalid reply |
| 8101 | Invalid data stream |

The codes come in a **decade per session operation**: the failing `C-*` command
fixes the tens digit, and the result it returned fixes the units. So `8040` is
`C-DROP-LINE` — not a second connect attempt — reporting a result its own
switch does not recognise. The full operation → decade map, and how it was
byte-verified, is in
[Commstar evidence](../re-notes/commstar-evidence.md#session-operation-error-decades).
Codes above 8150 are in a region not yet swept.

The string "Invalid command" exists in ROM but is **unreferenced** (dead) — it
never appears on screen.

Status lines (not errors — no error-code prefix): "Program transmitted",
"Program received", "Session complete", "Logging on", "Logged on",
"Logged off".

Loader errors (ROM01, Load/Run Program — `ROM01:0A67-10CE` via `ram:D081→ram:D0F0`).
The error screen shows decimal IDs; hexadecimal IDs are included for RE use:

| error shown | condition |
|-------------|-----------------------|
| `0x2328` (9000), "No program in memory." | Load from empty WORKSTATION MEMORY |
| `0x2329` (9001), "Requested program not in memory." | named program absent |
| `0x232A` (9002), "DIP file too big." | `destination + payload` exceeds memory boundary |
| `0x2334` (9012), "DIP file has too many blocks." | block count `>5` and related bank-range bound |
| `0x2331` (9009), "Program not built for this system." | system ID at header `+2` is neither `0` (wildcard) nor `0x00E5` |
| `0x232B` (9003), "Bad DIP file." | truncated 8-byte block header or truncated payload read (NOT bad magic) |
| `0x232C` (9004), "COM file too big." | raw COM exceeds `0xCF81` bytes (53,121 bytes); COM occupies `0x0100-D080` because resident module B begins at `0xD081` |
| `0x2332` (9010), "Program corrupt." | post-load block checksum mismatch — `Program_VerifyBlockChecksums` (`09C2`) recompute vs `Program_GenerateBlockChecksums` (`0957`) value at descriptor `+8`; i.e. **loaded program memory changed / failed integrity**, not a file-header checksum |

COM vs DIP discrimination (stable): if the first input chunk is `<14`
bytes or its first word `!= 0xC8C9` (`C9 C8`), the loader treats it as raw
COM, loads at `0x0100`, run-bank `0`, entry `0x0100`. DIP magic `0xC8C9`
is at header `+0`. See [Program formats](../reference/program-formats.md) for the full
14-byte header and type 0/1 block grammar.

### Error recovery

* Transient errors (the commstar messages above) clear to the previous
  screen; retry the operation.
* **`Press >> to continue`** prompts wait for **ENTER**.
* **`*** FATAL ERROR ***` … Consult Dealer** is unrecoverable: power-cycle
  the unit.

## To confirm on hardware

These items cannot be settled from the ROM and are deferred until the unit
is available:

* Whether the value-cycle key is **N/Z** (operator report) or **YES/NO**
  (ROM maps next/prev to YES/NO; N/Z type letters).
* The exact effect of the function labels (`CHNGE`, `REFER`, `HELP`,
  `INSRT`, `F1`/`F2`, `STWDL`, `LIGHT`, `TOP`, `BOT`, `/POS`).
* Whether menu items are selected by number (digits are shifted values) or
  by YES/NO + ENTER.
