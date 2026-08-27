# Forms and user-interface code

How the ROM01 application screens (menus, dialogs, forms) are built and
edited. This is the *internals* view; the operator-facing key/behaviour
summary is in the [user guide](../manual/user-guide.md).

## The form model

A screen is a **form**: an ordered list of fields, each of which is a
**choice** in an internal choice list. The form runtime keeps two cursors:

| cell | meaning |
|------|---------|
| `ec49` | pointer to the **field record** of the active list |
| `e739` | current choice/field **index** |
| `e734` | 5-byte-stride **entry cursor** into the choice table |
| `e736`/`e738` | walk cursor + index used by the letter-match handler |

A field record (`ec49`) is a small descriptor:

| offset | meaning |
|--------|---------|
| `+0` | type flag (must be 1 for an editable field) |
| `+6` | number of choices (choice count) |
| `+9` | pointer to the choice table (5-byte-stride entries) |

This one abstraction explains why YES/NO both *move between fields* (when
the active list is the form's field list) and *cycle a field's value*
(when the active list is a field's own choice list): the same
`Form_ChoiceNext`/`Form_ChoicePrev` code steps `e739`/`e734` through
whatever list `ec49` currently points at.

## Form initialisation

- **`Form_InitFromTemplates`** (ROM01:060b, was `Ui_CommSetupFormInit`)
  builds a form from three template descriptors (ROM01:758b, 75eb, 760d)
  via `TemplateBuilder`, into dest buffers `ec7e`/`ec97`/`ec98`, then
  zeroes the per-field state cells. It is generic, not comm-setup-specific.
- **`TemplateBuilder`** (ROM01:0271) walks a template descriptor: reads
  per-record data, and dispatches each record through a function pointer
  (`d828`). The template embeds at `+0x0c` a pointer to the field's choice
  table.
- **Template descriptor** (e.g. ROM01:758b): a `ScreenTemplateHeader`
  followed by per-field records; `fffe` separates records. The header
  (Ghidra struct `ScreenTemplateHeader`) is byte-verified across the three
  sibling templates 758b/75eb/760d:

  | offset | field | value (758b) | meaning |
  |--------|-------|--------------|---------|
  | +0 | buildStub | 0xefec | per-record builder fn (bank-called) |
  | +2 | stub2 | 0xf0f8 | stub fn |
  | +4 | stub3 | 0xef98 | stub fn |
  | +6 | stub4 | 0xefd8 | stub fn |
  | +8 | flags | 0x0801 | flags (LIKELY) |
  | +10 | count | 0x20 = 32 | element count (LIKELY) |
  | +12 | dataPtr | 0x757f | field's choice/string table |

  The three templates differ only in `count` (0x0120 vs 0x0020) and
  `dataPtr` (757f / 75e1 / 75ff).

## Menus

Menus are a separate structure, rendered by a menu handler (not
`TemplateBuilder`). The Main Menu table (`tbl_menu_main`, ROM01:772d) is a
title record `{label ptr, attr}` followed by 4 `MenuItem` records
`{key: u8, label: ptr, attr: u16}`:

| key | label | attr |
|-----|-------|------|
| '1' | Load/Run Program | 0x0104 |
| '2' | Set Clock | 0x0105 |
| '3' | Display Status | 0x0106 |
| '4' | Diagnostics | 0x0001 |

Selection is by **typing the digit**. The `attr` is the screen id; the
mapping is confirmed by driving the emulator (boot → Main Menu → digit):

| key | attr | screen opened |
|-----|------|---------------|
| '1' | 0x0104 | Load/Run Program |
| '2' | 0x0105 | Set Clock (Time/Date) |
| '3' | 0x0106 | Display Status (Version/Serial/RAM) |
| '4' | 0x0001 | Diagnostics |

The menu table header (7722) holds handler pointer **0x510d** (the menu item
label/index resolver: it reads a key + a table pointer, indexes
`table[key*2]` to fetch the item, then `strlen`/copies the label); the
window title "PARCON 1000" (0x7a82) precedes the menu title "Main Menu"
(0x7ac4). The Diagnostics screen (ROM01:7860) has one entry — "Set Debug
mode" (7b52, attr 0x0003) — which opens the **"Set Debug Mode"** screen
(title 7b61) whose *fields* are "Status" (7b70, ON/OFF) and "Device"
(7b77, PLINTH choice); "Status"/"Device" are field labels, not menu items.
(0x5114 is a mis-aligned pointer into the 0x510d function, not a separate
entry point.)

## Field validation

Typed input is validated per field type by four field-type validators
(ROM00:582a / 5834 / 583e / 5848) plus `Session_FieldParseValidate`
(ROM01:612a, numeric parse against the limit table `e34f` indexed by
`e88f`). Validators **return HL=0 on rejection** — they do not raise an
error banner themselves; the caller handles the display. "Invalid
reply"/"Invalid data stream" are session *protocol* errors, not field
validation messages, and "Invalid command" is an unreferenced (dead) string.
The protocol errors are dispatched by `Session_ProtocolErrorDispatch`
(ROM00:4f37): selectors 0x09→"Not available" (8102), 0x0A→"Invalid data
stream" (8101).

## The device list

`ROM01:757f` is a null-terminated pointer table of device names, used as the
choice list for the device-selector (the `From` field):

| addr | string |
|------|--------|
| 757f | WORKSTATION MEMORY |
| 7581 | WORKSTATION RAMDISK |
| 7583 | PLINTH |
| 7585 | V24 ADAPTOR |
| 7587 | EXT STORAGE ADAPTER |
| 7589 | (null terminator) |

## Field-edit key dispatch

The form's key input is read by `Ui_FieldEditPump` (ROM01:1fb5) and
dispatched through `InlineTableDispatch` at ROM01:1f96, whose inline table
(1f99) maps:

| case | key | handler |
|------|-----|---------|
| 0x06 | YES | `Form_ChoiceNext` (1e61) |
| 0x0b | Sun + YES | `Form_ChoiceNext` |
| 0x01 | NO | `Form_ChoicePrev` (1ea1) |
| 0x0c | Sun + NO | `Form_ChoicePrev` |
| 0x11 | (spare code) | `Form_ChoiceFirst` (1ece) |
| 0x12 | Sun + ENTER | `Form_ChoiceLast` (1eed) |
| default | any letter/char | `Form_ChoiceLetterMatch` (1f23) |

* `Form_ChoiceNext`/`Form_ChoicePrev` inc/dec `e739` and step `e734` by 5
  bytes; at the end of the list they invoke the boundary callback `*ec69`.
* `Form_ChoiceFirst`/`Form_ChoiceLast` jump the cursor to the first/last
  entry.
* `Form_ChoiceLetterMatch` walks the choice table comparing the typed key
  (after `Lib_CharTranslate`, ram:d8ce) against each entry key, returning
  the matched index — i.e. typing a letter selects a choice.

## Keyboard keymap

`tbl_kbd_map` (ROM00:1b58) is three 36-byte pages selected by the modifier
state (base in `fbda`; `Kbd_ScanMain` ROM00:18f0). Index = `col*6 + row`
(col = sense port 00h, row = drive port 02h).

| key | code | key | code |
|-----|------|-----|------|
| YES | 0x06 | NO | 0x01 |
| Sun+YES | 0x0b | Sun+NO | 0x0c |
| ENTER | 0x0d | Sun+ENTER | 0x12 |
| space | 0x20 | backspace | 0x7f |
| END | 0x14 | DEPT | 0xd0 |
| Sun+N (Z) | 0x5a | (spare) | 0x11 |

See the [user guide](../manual/user-guide.md) for the physical keypad and
the operator-level key meanings.

## Error screens

Errors are rendered by `SessionStateBuild` (ROM00:4351) through
`SessionMessageBox` (ROM00:4296). The on-screen format (major error
qualifier + `(RCV1/RCV2)` status pair + message) is documented in
[commstar — error/status screen format](../protocol/commstar.md) and
summarised for operators in the [user guide](../manual/user-guide.md).
The field names RCV1/RCV2/SEND/LOAD/PROG/TIME/ENDC come from the template
`tbl_sess_status_fmt` at ROM00:7310.
