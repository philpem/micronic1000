# User guide

How to operate the Micronic 1000: the keyboard, the menu tree, and the
meaning of the error screens. Firmware-derived; the internal mechanics are
in [forms and UI code](../internals/forms-ui.md).

## Power-on and boot

1. Power on. The unit runs its self test, then shows the banner
   (`PARCON 1000`, RAM size) and **`Press >> to continue`**.
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
 └─ banner + "Press >> to continue"
     └─ serial-number prompt
         └─ MAIN MENU
             ├─ 1  Load/Run Program
             │     └─ fields: Name (text), From (choice: PLINTH / V24 … )
             │        └─ From=PLINTH → Log-on information
             │             └─ Mode (LOCAL LINK) · Linespeed (9600)
             │                User id · Password · Group id · Telephone number
             ├─ 2  Set Clock
             │     └─ fields: Time, Date
             ├─ 3  Display Status
             │     └─ System Status · Version · Serial No.
             │        total RAM · RAMdisk size
             └─ 4  Diagnostics
                   └─ Set Debug mode · Status · Device
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

Session/commstar messages (ROM00:6d40-6e10):

| message | qualifier | meaning |
|---------|-----------|---------|
| Plinth not connected | 8000 / 8001 | IR link handshake failed (default / case-9 path) |
| Line failure | TBD | link dropped / line fault |
| Modem fault | TBD | modem-side fault |
| Failed to connect | TBD | connect handshake unsuccessful |
| Invalid reply | TBD | peer sent an unrecognised reply |
| Invalid command | TBD | peer sent an unrecognised command |
| Invalid data string | TBD | malformed received data |
| Not available | TBD | requested item unavailable |
| Program received | (status) | a program was received |
| Session complete | (status) | session finished cleanly |
| Logging on / Logged on / Logged off | (status) | session log-on progress |

Loader/application errors (ROM01):

| message | major | condition |
|---------|-------|-----------|
| No program in memory | TBD | Load from empty WORKSTATION MEMORY |
| Can't open or create file | TBD | file open/creat failed on the chosen device |
| System error · Consult dealer | — | unrecoverable system error |

The qualifiers marked TBD are ROM-derivable (each error site pushes its own
literal before `SessionShowMessage`); they are being traced and will be
filled in — they do **not** need the hardware.

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
* The Diagnostics sub-menu contents and self-test screens.
