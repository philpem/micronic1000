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
- **Template descriptor** (e.g. ROM01:758b): a header of stub-function
  pointers followed by per-field records; `fffe` separates records.

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
