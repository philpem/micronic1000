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

The keypad is alphanumeric. The second labels are produced by either the
**Shift** or **Sun** modifier, as shown below.

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

* **Shift (MODE)** selects page 1: punctuation, digits, red function labels,
  and `0xDB` at the N-key position. It is not the source of Z.
* **Sun (2nd)** is normally tapped and released, then page 2 applies to the
  next key. It supplies X/Y/Z at F/J/N and alternate navigation codes. Held
  Sun+X/Y/Z emits no key.
* **Held Sun** uses a separate direct-chord path: Sun+B toggles the backlight,
  Sun+END increases visible contrast, Sun+ENTER decreases it, and Sun+MODE
  enters power-down. These are not page-2 mappings.
* The field editor changes the cursor and keymap together. Text fields emit
  `ESC A`, selecting page 0 and the HD61830 cursor-blink mode (the observed
  underline). List fields emit `ESC B`, selecting page 1 and character blink
  (the observed block). The one-shot Sun page still overrides either page for
  one key.

The three firmware pages use the following physical layout. This follows the
owner's [keyboard table](https://philpem.me.uk/elec/micronic); a dash means
that the page supplies no key code for that position.

```text
Page 0: ordinary
             MODE    SUN
 A   B   C   D   E   F
 G   H   I   J   K   L   M
 N   O   P   Q   DEPT
 R   S   T   END
 U   V   W   ENTER
 BS  SPACE    NO  YES
```

```text
Page 1: Shift (MODE)
              MODE    SUN
 A=( B=) C=currency D=% E=# F=&
 G=+ H=/ I=,        J=? K=- L=* M=.
 N=0xDB O=7 P=8     Q=9 DEPT
 R=4 S=5 T=6        END
 U=1 V=2 W=3        ENTER
 BS  SPACE=0         NO  YES
```

```text
Page 2: tap/release Sun (2nd), then one key
             MODE  SUN
 A=- B=- C=- D=- E=- F=X
 G=- H=- I=- J=Y K=- L=- M=-
 N=Z O=- P=- Q=- DEPT=-
 R=- S=- T=- END=-
 U=- V=- W=- ENTER=last
 BS=cancel SPACE=- NO=previous YES=next
```

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
| YES | 0x06 | move to the next field; the last field gives an error beep |
| NO | 0x01 | move to the previous field |
| ENTER | 0x0d | accept/commit the current field, advance |
| Backspace | 0x7f | delete previous character |
| Space | 0x20 | space (and cursor advance in text fields) |
| A-W | 0x41-0x57 | type into a text field; field-specific handling may apply |

On the Load/Run `From` field, ordinary **N** (`0x4E`) is a printable
character: it appends `N` to the text. **Shift+N** produces `0xDB`, the
field's enumerate/change command; it advances the source selection, for
example `PLINTH` to `V24 ADAPTOR`. Sun+N produces `Z` (`0x5A`).

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
| 8010, 8012–8015 | Failed to connect |
| 8011, 8055, 8056, 8102, 8151, 8165, 8166 | Not available |
| 8016 | Modem fault |
| 8050, 8054, 8090, 8110, 8150, 8160, 8164 | Line failure |
| 8053, 8163 | Invalid reply |
| 8101 | Invalid data stream |

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

* The exact effect of the function labels (`CHNGE`, `REFER`, `HELP`,
  `INSRT`, `F1`/`F2`, `STWDL`, `LIGHT`, `TOP`, `BOT`, `/POS`).
* Whether menu items are selected by number (digits are shifted values) or
  by YES/NO + ENTER.
