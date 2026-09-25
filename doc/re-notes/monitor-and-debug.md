# Monitor / ICE hook and the debug facilities

The Micronic 1000 firmware contains a **complete monitor / ICE hook
topology but no monitor implementation**: every hook converges on a
two-byte stub. This is a **vestigial development/debug facility** — the
production ROMs leave the hook for a separate monitor ROM or an ICE to
occupy. Byte-level evidence is in
[RE notes: memory and I/O](memory-and-io-evidence.md).

## The stub

`Monitor_Enter` at **`ROM00:3513`** is literally `AF C9` — **`XOR A;
RET`**. It returns immediately; no monitor, no handshake.

## Where the hook is reached from

`3513` is the target of a network of callers, all of which just fall
through when the stub returns:

| Caller | Site | Meaning |
|---|---|---|
| **`RST 30h`** (vector `0030h` → `JP F5F0`) and `ram:F5F0` `JP 3513` | — | the restart-vector **break/monitor hook**; RAM-redirectable, like the other resident-kernel stubs |
| cold-boot debug gate (`f81d`=FFh) | `ROM00:0296` | `CALL Z,3513` in `ColdStartSelfTestBanner` |
| `Diag_ErrorHandler` | `ROM00:2C4F` | saves context to `FEFA`/`FEF8`, then `CALL 3513` — a **break-on-error** hook |
| `Kbd_ReadChar` | `ROM00:18EB` | `JP Z,3513` |
| others | `ROM00:3857`, `ram:F33A`, `ROM00:3B0D` | additional hook sites |

## The hidden cold-boot debug gate

A two-factor gate can set the debug flag at power-up (see
[keyboard](../reference/keyboard.md) for the keys and the matrix):

1. **Port `49h` reads `bit0=1, bit1=0`** at reset (`ROM00:0168`/`016E`).
   `49h` is the read half of the `48h`/`49h` I/O port; a write to `48h`
   reads back at `49h`.
2. After `Lcd_Init`, the code (`ROM00:0175`) requires the keyboard
   pattern: drive `KBD_DRIVE`=`02h` and sense `KBD_SENSE`=`1Ch` =
   **H + L + P held** (mnemonic **"HELP"**).

On a match it sets `g_bBootmodeFlag` (`f81d`) = `FFh`, which
`ColdStartSelfTestBanner` (`0291`) tests and turns into `CALL 3513`
(the stub). So enabling the "monitor" needs **both** the `49h` state and
H+L+P held at power-on — and even then it only calls the empty stub.

### `48h`/`49h` — why the debug select is a latch, not a jumper

The self-test `Kernel_SenseDiagEcho` (`ROM00:24F2`) *drives* `48h` and
requires `49h` to read back the same value. That is only self-consistent
if `49h` is the **readback of `48h`** (one latch; MAME agrees), or `48h`
drives the shared lines. Either way, because the test drives `48h`, it
cannot detect a "stuck" external state — so the reset boot-mode value is
the **latch's retained state**, set by *writing `48h`*, not by a
physical jumper.

## The "Set Debug mode" screen

`ROM01`'s **Diagnostics** screen (`ROM01:7860`) is a menu with a single
item — **"Set Debug mode"** (`7B52`, screen id `0x0003`) — which opens
the **"Set Debug Mode"** screen (title `7B61`). Per
[Forms and UI](forms-ui.md), that screen is a **form** (a template
descriptor built by `Form_Builder` into the form runtime) whose fields
are:

* **"Status"** (`7B70`) — an **ON/OFF** field (enable).
* **"Device"** (`7B77`) — a **choice** field starting at **PLINTH**.

### Confirmed by emulator (2026-09-24, `analysis/boot_hw.py`)

The full path was driven end to end and is confirmed:

```
Main Menu: press '4'  (Diagnostics)
  -> Diagnostics screen, single item "~Set Debug mode"
  -> press ENTER      -> "Set Debug Mode" form
       window title "PARCON 1000"
       row: "Status  OFF"
       row: "Device  PLINTH_____"
```

So it is **specified in the forms/UI framework**: a menu item entry in
the Diagnostics menu table (`ROM01:7860`) whose `attr` is the screen id
`0x0003`, opening a form whose template (`ROM01:7898`) is built by the
generic `Form_Builder` into the form runtime (`Form_InitFromTemplates` /
`UI_PostDescriptor`). Toggling fields goes through `Ui_FieldEditPump`
(`ROM01:1FB5`) → `Kernel_TableDispatch` (`1F96`), whose table maps
`YES`/`NO` (`0x06`/`0x01`) to `Form_ChoiceNext`/`Prev` (stepping the
choice index `e739`/`e734`, boundary callback `*ec69`), and `ENTER`
returns.

### What it does

The pairing of an **ON/OFF enable** with an **IR-device choice** means
"debug mode" turns on diagnostic output routed to the selected device
(PLINTH, and by the same device-list style as the Load/Run *From* field,
V24 ADAPTOR).

**Emulator (2026-09-24):** the field-edit key routing was confirmed.
Watching the PC during `ENTER` + `YES` (`0x0D`+`0x06`) reached
`Form_ChoiceNext` (`ROM01:1E61`), proving `YES` does drive the choice
index (`e739`/`e734`, boundary callback `*ec69`). The screen then
returned to the Diagnostics menu (the edit values are committed on
return). Because the form re-renders the template on entry and the edit
commits on exit, screenshoting the "Status ON" state in a single driven
run was unreliable; the value/consumer is best read by watching the
field-state cell rather than the framebuffer.

**OPEN:** the exact backing cell and the consumer of the flag are not
yet pinned; the form runtime stores field values through shared UI cells
(`EC49`/`E739`/`E734`). It is **not** `f81d` (that cell has only
boot-time writers).

**Decisive next step:** watch the form-field state cell during the
`ENTER`+`YES` edit (bounded `--watch-mem` on the session-config region
`E700`-`ED1B`) to capture the actual flag cell and then follow any read
of it to the diagnostic-output path.

## The real monitor is a separate artifact

These two ROM images contain **no monitor**. MAME defines BIOS 1
"**Micronic 1000 LCD monitor**" (`monitor2.bin`), and Lee Davison lists a
monitor ROM and disassembly — i.e. Micronic shipped the monitor as a
**separate ROM** that occupies the `3513`/`F5F0` hook. An ICE could
equally intercept the entry, use the saved context, and return.

## Status

* **CONFIRMED:** `3513` = `XOR A; RET`; the caller network; the `49h` +
  H+L+P gate and `f81d` set/consume sites; the `48h`/`49h` readback.
* **SUSPECTED / historical:** the hook's purpose is an alternate/patched
  ROM monitor or an ICE. Neither is present in these dumps.
* **OPEN:** the handler/flag of the `Set Debug mode` menu option.
