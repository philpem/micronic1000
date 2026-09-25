# Monitor / ICE hook and the debug facilities

The Micronic 1000 firmware contains a **complete monitor / ICE hook
topology but no monitor implementation in these ROMs**: every hook
converges on a two-byte stub. This is a **development/debug facility
whose hook targets are present in the production ROMs for a separate
monitor ROM or an ICE to occupy**. Byte-level evidence is in
[RE notes: memory and I/O](memory-and-io-evidence.md).

## The stub

`Debug_MonitorHookStub` (formerly
`Monitor_Enter`) at **`ROM00:3513`** is literally `AF C9` — **`XOR A;
RET`**. It returns immediately; no monitor, no handshake.

## Where the hook is reached from

`3513` is the target of a network of callers, all of which just fall
through when the stub returns:

| Caller | Site | Meaning |
|---|---|---|
| **`RST 30h`** (vector `0030h` → `JP F5F0`) and `ram:F5F0` `JP Debug_MonitorHookStub` (formerly `Monitor_Enter`) | — | the restart-vector **break/monitor hook**; RAM-redirectable, like the other resident-kernel stubs |
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

### `48h`/`49h` — boot-mode select, not a debug jumper

The self-test `Kernel_SenseDiagEcho` (`ROM00:24F2`) *drives* `48h` and
requires `49h` to read back the same value. If it had read back a
mismatch, that would reject the self-test — but it always passes with
the correct firmware drive. Either `49h` is the **readback of `48h`**
(one latch; MAME agrees), or `48h` drives the shared lines and
overrides any external state. The reset boot-mode value comes from the
**latch's power-on/retained state**, set by *writing `48h`*, not by a
physical jumper (stated as most likely in an earlier draft, not
confirmed).

## The "Set Debug mode" screen — CONFIRMED findings (2026-09-25)

`ROM01`'s **Diagnostics** screen (`ROM01:7860`) is a menu with a single
item — **"Set Debug mode"** (`7B52`, screen id `0x0003`) — which opens
the **"Set Debug Mode"** screen (title `7B61`). Per
[Forms and UI](forms-ui.md), that screen is a **form** (a template
descriptor built by `Form_Builder` into the form runtime) whose fields
are:

* **"Status"** (`7B70`) — an **ON/OFF** field (enable).
* **"Device"** (`7B77`) — a **choice** field starting at **PLINTH**.

### Backed by real RAM cells

**CONFIRMED:** The form's state is stored in two dedicated RAM cells:

| Cell | Role | Evidence |
|------|------|----------|
| `ram:ECC7` (`g_bDebugRunEnabled`) | Status enable byte (zero = off, nonzero = on) | Initialised to 0 at `ROM01:069A`. Sole consumer at `ROM01:038C` tests `A=(ECC7)`, jumps on zero. |
| `ram:ECC8` (`g_bDebugRunDeviceIndex`) | Device index (compared to 1) | Initialised to 0 at `ROM01:06A1`. Sole consumer at `ROM01:0393` loads it. |

These are **not** the `ram:EC6F`/`ram:EC6D` words used by the
Diagnostics menu selection (those are menu-retained choice values, not
debug status — CONFIRMED by the `EF4C`/`EF34` callback bodies at
`ROM01:0309`/`0319`).

The form descriptor pointer to `ECC7` (`g_bDebugRunEnabled`) is embedded at `ROM01:78C3-78C4`.
The form's callback-slot words at `ROM01:78CA`/`78CC` both point to
`ram:F168`. **State of `F168` is snapshot-dependent:** the current
Ghidra RAM image holds `21 01 00 C9` (`LD HL,1; RET`) — the pre-boot
placeholder — while the boot-installed emulator state recorded
`D7 01 68 67` (`RST 10h` banked call to `ROM01:6768`, a trivial success
callback). In either form this slot is a placeholder, **not** backing
storage for the debug-run feature.

### What it does — the activation chain

When `g_bDebugRunEnabled` (`ECC7`) is nonzero the form's status is ON. The activation path
proceeds as follows (CONFIRMED, byte-verified):

1. **Gate test:** `ROM01:038C` loads `(g_bDebugRunEnabled)`, `OR A`, jumps to skip on
   zero.
2. **Device selection:** `ROM01:0393` loads `(g_bDebugRunDeviceIndex)`, compares with 1
   via the `ram:E05A` equality helper. The result is saved on the stack.
3. **Value mapping:** `Debug_InvokeMonitorVector` (formerly
   `Session_StateWordPreparedCall`) at `ROM00:68E0` (via `ram:EF18`) reads the stack argument.
   If nonzero (ECC8==1) it stores `(g_wMonitorDeviceSelector)=4`; otherwise `(g_wMonitorDeviceSelector)=3`.
4. **Transient activation:** `ROM01:03A7` writes 1 to `ram:EB18` (`g_wDebugRunActive`).
5. **Program run:** `ROM01:03AE` calls `ROM01:106F` (`Program_RunByName`).
6. **Deactivation:** `ROM01:03B5` clears `ram:EB18` (`g_wDebugRunActive`) to 0.

While `g_wDebugRunActive` is nonzero, the generic handler phase at `ROM01:6286` reads
`(g_wDebugRunActive)`, tests nonzero, and calls `ram:EF24` → `Debug_InvokeMonitorVector`.

### Monitor/error-vector dispatch

The ROM-side setup and endpoint below were independently byte-reviewed.
The intervening RAM dispatcher and wrapper were traced by the investigator
but not fully re-verified by the reviewer; retain **LIKELY** for that
portion of the end-to-end chain pending a fresh RAM-image check.

`Debug_InvokeMonitorVector` (formerly `Session_StateWordPreparedCall`)
at `ROM00:68C7` (via `ram:EF24`) pushes `(g_wMonitorDeviceSelector)`, zero, and `13h`, then
calls `ram:DA27`. That dispatcher copies the stack words through
`ram:E0FE..E102`, indexes the three-byte page-zero vector table, places
the second argument in `BC`, third in `DE`, and jumps to the selected
vector.

Since `Debug_InvokeMonitorVector` executes in bank 0, vector `13h` is `ROM00:0139: JP
ram:F32F`; therefore `BC=0`, `DE=(g_wMonitorDeviceSelector)` = 3 or 4 at `ram:F32F`.

`ram:F32F` saves context, selects monitor target `Debug_MonitorHookStub`, and
enters the common monitor/error-hook wrapper. `Debug_MonitorHookStub` at
**`ROM00:3513`** is `AF C9` — **`XOR A; RET`**. It returns immediately;
no monitor, no handshake. The optional register display at
`ROM00:2D82/2DA5` is gated by `(FDBD) & 7`; system initialisation clears
`FDBD` at `ROM00:034E-0353`, and the debug form chain does not set it.

No IR transmit or debug-print operation was found in this traced path.
The stock monitor endpoint is a **CONFIRMED** returning stub. This does
not mean enabling debug has no effects: the selector and temporary gate
are written and the callback path is activated.

### Device selection: PLINTH and (LIKELY) V24 ADAPTOR

**CONFIRMED:** The form's Device field starts at PLINTH (UI observation).
The device index comparison (`ECC8` compared to 1) and the resulting
`DE=3` vs `DE=4` produce a two-value selector. The mapping of index 1
to V24 ADAPTOR is **LIKELY** by complementary field structure and the
paired PLINTH/V24 device-list pattern used elsewhere in the firmware
(e.g. the Load/Run `From` list). The bytes establish 3/4 as values
passed to the monitor hook, but do not by themselves prove physical
routing semantics.

### Prior claims corrected

- **Ephemeral-only / no-flag claims (2026-09-24):** The 500-line print
  cap was exhausted by boot zero-fill; the summary counted 6,767 writes,
  not 6,767 printed zero writes. `ECC7`/`ECC8` are inside the watched
  range. The capture therefore cannot exclude later nonzero writes.
  No successful OFF-to-ON edit was observed, and the ChoiceNext hit after
  ENTER returned to Diagnostics does not prove a debug-field edit or
  commit-on-exit. The cell pair is instead established by its descriptor,
  initialisers and behavioral consumers.
- **Debug mode sends diagnostics over IR:** No link call or link I/O
  exists in the complete static chain. The selected 3/4 value reaches
  `DE` at a monitor vector, and the stock monitor target is a no-op.
  An external monitor could assign those values to devices, but that is
  outside these ROMs.
- **Not `f81d`:** The cold-boot debug-gate flag (`f81d`) is a separate
  mechanism with boot-time-only writers. This is still correct.

## Installing a user-written hook from COM or DIP

**CONFIRMED, ROM-image and kernel-copy verified (2026-09-25):** an
executing program can redirect service/vector `13h` through writable
resident code. This is a **version-specific kernel patch**, not an
established supported monitor-installation API. Service `13h` here is
an entry in the firmware vector table, not CP/M BDOS function `13h`.

### Redirect point

The relevant stock instructions are:

```asm
; ROM00:0139
        JP   0F32Fh

; ram:F32F ... saves entry context, then:
; ram:F338
        LD   A,036h
; ram:F33A
        LD   HL,03513h       ; operand at ram:F33B-F33C
; ram:F33D
        JR   0F376h          ; common resident service wrapper
```

Change the **word at `ram:F33B`**, not the instruction opcode at
`ram:F33A`, to redirect the handler. Stock operand bytes are `13 35`.
The cold-start copy at `ROM00:02FE-0317` installs
`ROM00:369D..3BA9` into `ram:F180..F68C`; thus the instruction at
`ram:F33A` is sourced from `ROM00:3857` (`21 13 35`). Both the ROM
vector and the resident vector at `ram:F26E` reach `ram:F32F`.
Patching only the resident vector would miss the ROM-vector caller.

This patch affects **service/vector `13h` calls only**. Direct calls to
`ROM00:3513`, including the cold-boot and error-screen calls, and the
separate `RST 30h -> ram:F5F0 -> ROM00:3513` route bypass it.

### Placement and return contract

The wrapper selects **ROM bank 0** before invoking the handler. Place
the callback in application-reserved **fixed RAM**, rather than leaving
it at an address in the COM's banked window. For example, `ram:C000`
is a possible location only if the application reserves that region.

- **COM:** copy the callback and its private storage into reserved
  fixed RAM, then execute the installer.
- **DIP:** a type-0 block can load the fixed-RAM payload, followed by
  executable installer code. The ordinary DIP destination check uses
  the exclusive `D081h` ceiling (`ROM01:0E86-0EA4`); a data block
  directly targeting `ram:F33B` is not an installation method.

**CONFIRMED from the copied kernel image:** on the normal wrapper path
(`ram:FDBD & 07h = 0`), the callback returns using an ordinary `RET`
to **`ram:F3C4`**. The wrapper records returned `A` and restores the
caller's bank. Callback flags are not a preserved return contract.
The wrapper records internal service code `36h` at `ram:FEFC`.
The debug call's selected-device argument is intended to reach `DE`;
the stack-adapter portion of that argument transfer remains separately
qualified in the activation-chain discussion above.

The wrapper uses shared context cells including `ram:FEF6`,
`ram:FEFA`, and `ram:FEFE`. Calling BDOS or another wrapped service
inside the callback can overwrite this context. A reentrant interactive
monitor ABI has **not** been established: begin with a leaf callback
that records state and returns, without OS calls or bank changes.

### Minimal leaf-hook sketch

This is **proposed, untested application assembly**, not recovered
firmware or a tested monitor. All labels below must resolve into the
reserved fixed-RAM payload. The installer assumes normal application
execution with maskable interrupts enabled, and no concurrent owner or
invocation of this hook. It must first verify that `ram:F33A..F33C`
still contains the expected `21 13 35` instruction.

```asm
; After placing callback and storage in reserved fixed RAM:
        DI
        LD   HL,(0F33Bh)
        LD   (saved_target),HL
        LD   HL,monitor_callback
        LD   (0F33Bh),HL
        EI
        RET

; Leaf proof-of-entry callback, returning like the stock stub.
monitor_callback:
        LD   (observed_de),DE
        XOR  A
        RET

; Run only while this installation still owns the hook,
; before its payload/storage can be overwritten or released.
uninstall:
        DI
        LD   HL,(saved_target)
        LD   (0F33Bh),HL
        EI
        RET

saved_target: DW 0
observed_de:  DW 0
```

`DI` does not mask NMI; this sketch is not a concurrency-safe hook
manager. Do not replace another application's target or restore an old
target over a newer installation. A caller with interrupts already
disabled needs an installer that preserves that state rather than the
unconditional `EI` above.

### Lifetime

Cold initialization overwrites this operand when it recopies the
resident kernel. The examined warm branch (`ROM00:01A3 -> 024D`)
skips that copy, so the patch survives **that branch**. This is not a
guarantee of residency across arbitrary later loading: a subsequent
COM/DIP may overwrite the callback while leaving the kernel pointer
installed. Restore the old target before releasing its memory, or
establish an explicit ownership and placement scheme for resident use.
An installer run before the target program can intercept that later
run's debug hooks only if its callback survives the subsequent load.

## The monitor hook may host a separate artifact

These two ROM images contain **no monitor**. MAME defines BIOS 1
"**Micronic 1000 LCD monitor**" (`monitor2.bin`), and Lee Davison lists a
monitor ROM and disassembly — a separate artifact that could occupy the
`3513`/`F5F0` hook. An ICE could equally intercept the entry, use the
saved context, and return. However, neither `monitor2.bin`'s specific
shipping status nor its exact installation point is confirmed by ROM
evidence alone — the hook purpose is **SUSPECTED** as an alternate/patched
ROM monitor or ICE. The hook network is present; the monitor
implementation is not.

## Status

* **CONFIRMED:** `Debug_MonitorHookStub` (`3513`) = `XOR A; RET`; the caller network; the `49h` +
   H+L+P gate and `f81d` set/consume sites; the `48h`/`49h` readback.
* **CONFIRMED (2026-09-25):** `g_bDebugRunEnabled` (`ECC7`) enable byte, `g_bDebugRunDeviceIndex`
   (`ECC8`) device index, the `g_wDebugRunActive` (`EB18`) transient activation gate, the ROM-side
   `EF18`/`EF24` targets and vector `13h` setup, plus the returning `Debug_MonitorHookStub`.
   The intervening RAM dispatch/wrapper remains **LIKELY** pending
   independent RAM-byte verification.
* **LIKELY:** Form device index 1 = V24 ADAPTOR (by complementary field
   structure and the PLINTH/V24 pairing). `DE=3` (index 0) and `DE=4`
   (index 1) are the values passed to the monitor hook.
* **SUSPECTED:** The hook's purpose is an alternate/patched ROM monitor
   or an ICE. Neither is present in these dumps.
* **ACTUAL labels (installed in Ghidra 2026-09-25):**
  `g_bDebugRunEnabled` (`ECC7`), `g_bDebugRunDeviceIndex` (`ECC8`),
  `g_wDebugRunActive` (`EB18`). `g_wMonitorDeviceSelector` (`E2F8`)
  remains **PROPOSED** (not installed in Ghidra).
