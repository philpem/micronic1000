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

## The "Set Debug mode" menu option (partial)

ROM01 carries the strings **"Set Debug mode"** (`ROM01:7B52`) and
**"Set Debug Mode"** (`ROM01:7B61`), in the **config/setup menu** beside
`Serial No.`, `total RAM`, `RAMdisk size`, `Status`, `Device`,
`Log-on information`, `Mode`, `Linespeed`, `User id`, `Password`
(`ROM01:7B2E`-`7BAA`). The menu is driven by a **descriptor tree** in
the `ROM01:7700`-`7B00` region — entries at `7751`, `779D`, `77E8`,
`7853`, `7884`, … holding pointers to labels and RAM cells — rendered by
UI helpers such as `ROM01:6633` (entered from `ROM01:0718`).

**OPEN:** the descriptor field layout is not resolved, so the specific
handler for the debug item and the flag/cell it sets are not yet traced.
It is **not** `f81d` (that cell has only boot-time writers,
`0161`/`0195`). The clean way to settle it is to select the item in the
emulator and watch which RAM cell changes.

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
